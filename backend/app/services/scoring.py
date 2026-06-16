"""
Scoring engine SIPRIOS menggunakan model ML:
- Tabular: Random Forest + XGBoost ensemble
- CV: EfficientNet-B0 ONNX untuk penilaian foto rumah

Mapping field form SIPRIOS → field model Costa Rica dataset:
Form SIPRIOS          | Model field
---------------------|------------------
sewaBulanan          | v2a1
punyaKulkas          | refrig
totalAnggota         | hogar_total
jumlahDewasa         | hogar_adul
jumlahAnak           | hogar_nin
jumlahLansia         | hogar_mayor
jumlahRuangan        | rooms
kamarTidur           | bedrooms
punyaKamarMandi      | v14a
airBersih            | abastaguadentro
adaListrik           | noelec (dibalik: Ya=0, Tidak=1)
punyaPlafon          | cielorazo
punyaDapur           | energcocinar1 (dibalik: Ya=0, Tidak=1)
statusToilet         | sanitario1, sanitario2
statusRumah          | tipovivi1, tipovivi4
rataSekolah          | meaneduc
adaTidakSekolah      | instlevel1
adaPendidikanTinggi  | instlevel8
foto (CV model)      | house_condition_score
computed             | dependency, overcrowding, hacdor, epared1, etecho1, eviv1
"""

import io
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

ML_DIR = Path(__file__).resolve().parent.parent.parent / "ml_models"

_rf_model   = None
_xgb_model  = None
_cv_session = None
_best_w_rf  = 0.80
_best_w_xgb = 0.20

FINAL_FEATURES = [
    'v2a1', 'refrig', 'hogar_nin', 'hogar_mayor', 'hogar_total',
    'dependency', 'overcrowding', 'v14a', 'abastaguadentro', 'sanitario1',
    'noelec', 'cielorazo', 'meaneduc', 'hacdor', 'rooms', 'hogar_adul',
    'tipovivi1', 'tipovivi4', 'sanitario2', 'energcocinar1', 'elimbasu1',
    'epared1', 'etecho1', 'eviv1', 'instlevel1', 'instlevel8',
    'edjefa', 'bedrooms', 'house_condition_score'
]

SCORE_MAP = {0: 90, 1: 70, 2: 45, 3: 15}
LABEL_MAP = {0: 'Membutuhkan', 1: 'Rawan', 2: 'Cukup', 3: 'Mandiri'}
IMG_SIZE  = 224
IMG_MEAN  = np.array([0.485, 0.456, 0.406])
IMG_STD   = np.array([0.229, 0.224, 0.225])


def load_models():
    """Load semua model saat startup."""
    global _rf_model, _xgb_model, _cv_session, _best_w_rf, _best_w_xgb

    import json, joblib

    rf_path   = ML_DIR / "rf_bansos_model.pkl"
    xgb_path  = ML_DIR / "xgb_bansos_model.pkl"
    meta_path = ML_DIR / "model_metadata.json"

    if rf_path.exists() and xgb_path.exists():
        try:
            _rf_model  = joblib.load(rf_path)
            _xgb_model = joblib.load(xgb_path)
            logger.info("Tabular models loaded.")
        except Exception as e:
            logger.error(f"Gagal load tabular model: {e}")
    else:
        logger.warning("Model .pkl tidak ditemukan, pakai rule-based fallback.")

    if meta_path.exists():
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            _best_w_rf  = meta.get('ensemble_weights', {}).get('rf', 0.80)
            _best_w_xgb = meta.get('ensemble_weights', {}).get('xgb', 0.20)
        except Exception:
            pass

    onnx_path = ML_DIR / "house_classifier.onnx"
    if onnx_path.exists():
        try:
            import onnxruntime as ort
            _cv_session = ort.InferenceSession(str(onnx_path))
            logger.info("CV ONNX model loaded.")
        except Exception as e:
            logger.warning(f"CV model tidak di-load: {e}")
    else:
        logger.warning("house_classifier.onnx tidak ditemukan.")


def yn(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ('ya', 'yes', 'true', '1')


@dataclass
class WargaData:
    sewa_bulanan: int
    punya_kulkas: bool
    total_anggota: int
    jumlah_dewasa: int
    jumlah_anak: int
    jumlah_lansia: int
    jumlah_ruangan: int
    kamar_tidur: int
    punya_kamar_mandi: bool
    air_bersih: bool
    ada_listrik: bool
    punya_plafon: bool
    punya_dapur: bool
    status_toilet: str
    status_rumah: str
    rata_sekolah: float
    ada_tidak_sekolah: bool
    ada_pendidikan_tinggi: bool


def _map_to_features(d: WargaData, house_condition_score: float = 0.5) -> dict:
    dependency   = (d.jumlah_anak + d.jumlah_lansia) / max(d.jumlah_dewasa, 1)
    overcrowding = d.total_anggota / max(d.jumlah_ruangan, 1)
    hacdor       = 1 if (d.total_anggota / max(d.kamar_tidur, 1)) > 3 else 0
    sanitario1   = 1 if d.status_toilet == "Tidak Ada" else 0
    sanitario2   = 1 if d.status_toilet == "Layak" else 0
    tipovivi1    = 1 if d.status_rumah == "Milik Sendiri" else 0
    tipovivi4    = 1 if d.status_rumah == "Tidak Layak" else 0
    epared1      = 1 if house_condition_score > 0.6 else 0
    etecho1      = 1 if house_condition_score > 0.6 else 0
    eviv1        = 1 if house_condition_score > 0.6 else 0

    return {
        'v2a1': float(d.sewa_bulanan),
        'refrig': 1 if d.punya_kulkas else 0,
        'hogar_nin': d.jumlah_anak,
        'hogar_mayor': d.jumlah_lansia,
        'hogar_total': d.total_anggota,
        'dependency': round(dependency, 3),
        'overcrowding': round(overcrowding, 3),
        'v14a': 1 if d.punya_kamar_mandi else 0,
        'abastaguadentro': 1 if d.air_bersih else 0,
        'sanitario1': sanitario1,
        'noelec': 0 if d.ada_listrik else 1,
        'cielorazo': 1 if d.punya_plafon else 0,
        'meaneduc': float(d.rata_sekolah),
        'hacdor': hacdor,
        'rooms': d.jumlah_ruangan,
        'hogar_adul': d.jumlah_dewasa,
        'tipovivi1': tipovivi1,
        'tipovivi4': tipovivi4,
        'sanitario2': sanitario2,
        'energcocinar1': 0 if d.punya_dapur else 1,
        'elimbasu1': 0,
        'epared1': epared1,
        'etecho1': etecho1,
        'eviv1': eviv1,
        'instlevel1': 1 if d.ada_tidak_sekolah else 0,
        'instlevel8': 1 if d.ada_pendidikan_tinggi else 0,
        'edjefa': 0,
        'bedrooms': d.kamar_tidur,
        'house_condition_score': house_condition_score,
    }


def predict_house_condition(image_bytes: io.BytesIO) -> float:
    """Inferensi CV model dari foto rumah. Return 0=bagus, 1=buruk."""
    if _cv_session is None:
        return 0.5
    try:
        from PIL import Image
        img = Image.open(image_bytes).convert('RGB')
        img = img.resize((IMG_SIZE, IMG_SIZE))
        arr = np.array(img, dtype=np.float32) / 255.0
        arr = (arr - IMG_MEAN) / IMG_STD
        arr = arr.transpose(2, 0, 1)[np.newaxis].astype(np.float32)
        logits = _cv_session.run(None, {'image': arr})[0]
        logits = logits - logits.max()
        probs  = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
        return round(float(probs[0][0]), 4)
    except Exception as e:
        logger.warning(f"CV model error: {e}, fallback 0.5")
        return 0.5


def _predict_ml(features: dict) -> dict:
    import pandas as pd
    input_df = pd.DataFrame([features])
    for col in FINAL_FEATURES:
        if col not in input_df.columns:
            input_df[col] = 0
    input_df = input_df[FINAL_FEATURES].fillna(0)
    rf_prob  = _rf_model.predict_proba(input_df)[0]
    xgb_prob = _xgb_model.predict_proba(input_df)[0]
    ens_prob = _best_w_rf * rf_prob + _best_w_xgb * xgb_prob
    pred_class = int(np.argmax(ens_prob))
    weighted_score = sum(ens_prob[i] * SCORE_MAP[i] for i in range(4))
    return {
        'score': int(round(weighted_score)),
        'kategori_level': pred_class + 1,
        'kategori_label': LABEL_MAP[pred_class],
    }


def _predict_rule_based(d: WargaData) -> dict:
    score = 0
    if d.sewa_bulanan == 0:           score += 10
    elif d.sewa_bulanan < 300000:     score += 8
    elif d.sewa_bulanan < 600000:     score += 5
    if not d.punya_kulkas:            score += 10
    if d.status_rumah == "Tidak Layak": score += 5
    ratio = (d.jumlah_anak + d.jumlah_lansia) / max(d.jumlah_dewasa, 1)
    if ratio >= 3:    score += 20
    elif ratio >= 2:  score += 15
    elif ratio >= 1:  score += 10
    elif ratio >= 0.5: score += 5
    ovc = d.total_anggota / max(d.jumlah_ruangan, 1)
    if ovc >= 4:   score += 10
    elif ovc >= 3: score += 7
    elif ovc >= 2: score += 4
    if not d.punya_kamar_mandi:            score += 5
    if not d.air_bersih:                   score += 5
    if not d.ada_listrik:                  score += 5
    if not d.punya_plafon:                 score += 3
    if not d.punya_dapur:                  score += 2
    if d.status_toilet == "Tidak Ada":     score += 5
    elif d.status_toilet == "Tidak Layak": score += 2
    if d.rata_sekolah < 6:    score += 15
    elif d.rata_sekolah < 9:  score += 10
    elif d.rata_sekolah < 12: score += 5
    if d.ada_tidak_sekolah:     score += 7
    if d.ada_pendidikan_tinggi: score -= 5
    score = max(0, min(100, score))
    if score >= 70:   level, label = 1, 'Membutuhkan'
    elif score >= 50: level, label = 2, 'Rawan'
    elif score >= 30: level, label = 3, 'Cukup'
    else:             level, label = 4, 'Mandiri'
    return {'score': score, 'kategori_level': level, 'kategori_label': label}


def kategori_dari(level: int) -> dict:
    label = LABEL_MAP.get(level - 1, 'Mandiri')
    return {'level': level, 'label': label, 'key': f'need{level}'}


def kondisi_hunian(d: WargaData) -> dict:
    buruk = sum([
        not d.punya_kamar_mandi, not d.air_bersih, not d.ada_listrik,
        not d.punya_plafon, d.status_toilet == "Tidak Ada",
        d.status_rumah == "Tidak Layak",
    ])
    if buruk >= 4:   return {"label": "Kondisi Membutuhkan Perbaikan", "cls": "bad"}
    elif buruk >= 2: return {"label": "Kondisi Perlu Perhatian",       "cls": "warn"}
    return                  {"label": "Kondisi Baik",                   "cls": "ok"}


def faktor_penentu(nama: str, d: WargaData, house_score: float = 0.5) -> list:
    faktor = []
    if d.sewa_bulanan > 0:
        faktor.append({"cat": "Ekonomi", "dir": "up",
            "detail": f"Menanggung sewa hunian Rp {d.sewa_bulanan:,}/bulan"})
    elif not d.punya_kulkas:
        faktor.append({"cat": "Ekonomi", "dir": "up",
            "detail": "Tidak memiliki aset dasar rumah tangga"})
    else:
        faktor.append({"cat": "Ekonomi", "dir": "down",
            "detail": "Kondisi ekonomi relatif stabil"})
    ratio = (d.jumlah_anak + d.jumlah_lansia) / max(d.jumlah_dewasa, 1)
    if ratio >= 2:
        faktor.append({"cat": "Tanggungan", "dir": "up",
            "detail": f"Menanggung {d.jumlah_anak} anak dan {d.jumlah_lansia} lansia"})
    elif d.jumlah_lansia > 0:
        faktor.append({"cat": "Tanggungan", "dir": "up",
            "detail": f"Terdapat {d.jumlah_lansia} anggota lanjut usia"})
    else:
        faktor.append({"cat": "Tanggungan", "dir": "neutral",
            "detail": "Komposisi keluarga relatif seimbang"})
    if house_score > 0.6:
        faktor.append({"cat": "Kondisi Hunian", "dir": "up",
            "detail": "Kondisi fisik bangunan rumah perlu perhatian"})
    elif not d.air_bersih or not d.ada_listrik or d.status_toilet == "Tidak Ada":
        kekurangan = []
        if not d.air_bersih:               kekurangan.append("air bersih")
        if not d.ada_listrik:              kekurangan.append("listrik")
        if d.status_toilet == "Tidak Ada": kekurangan.append("toilet")
        faktor.append({"cat": "Kondisi Hunian", "dir": "up",
            "detail": f"Tidak memiliki akses {', '.join(kekurangan[:2])}"})
    else:
        faktor.append({"cat": "Kondisi Hunian", "dir": "down",
            "detail": "Fasilitas dasar hunian tersedia memadai"})
    if d.rata_sekolah < 6:
        faktor.append({"cat": "Pendidikan", "dir": "up",
            "detail": f"Rata-rata pendidikan di bawah SD ({d.rata_sekolah:.1f} tahun)"})
    elif d.ada_tidak_sekolah:
        faktor.append({"cat": "Pendidikan", "dir": "up",
            "detail": "Ada anggota yang tidak pernah sekolah"})
    elif d.ada_pendidikan_tinggi:
        faktor.append({"cat": "Pendidikan", "dir": "down",
            "detail": "Ada anggota berpendidikan tinggi (S1+)"})
    else:
        faktor.append({"cat": "Pendidikan", "dir": "neutral",
            "detail": f"Rata-rata pendidikan {d.rata_sekolah:.1f} tahun"})
    return faktor


def rekomendasi_teks(nama: str, score: int) -> str:
    if score >= 70:
        return (f"{nama} sangat disarankan masuk daftar penerima bantuan. "
                f"Kondisi keluarga menunjukkan kebutuhan yang signifikan.")
    elif score >= 50:
        return (f"{nama} disarankan dipertimbangkan sebagai penerima bantuan. "
                f"Verifikasi lapangan dapat memperkuat keputusan.")
    return (f"Berdasarkan data yang diinput, {nama} belum termasuk "
            f"prioritas utama penerima bantuan saat ini.")


def proses_warga(data: WargaData, nama: str,
                 house_condition_score: float = 0.5) -> dict:
    if _rf_model is not None and _xgb_model is not None:
        features = _map_to_features(data, house_condition_score)
        hasil    = _predict_ml(features)
        logger.info(f"ML model. Skor: {hasil['score']}")
    else:
        hasil = _predict_rule_based(data)
        logger.info(f"Rule-based fallback. Skor: {hasil['score']}")
    return {
        'score'      : hasil['score'],
        'kategori'   : kategori_dari(hasil['kategori_level']),
        'kondisi'    : kondisi_hunian(data),
        'faktor'     : faktor_penentu(nama, data, house_condition_score),
        'rekomendasi': rekomendasi_teks(nama, hasil['score']),
    }
