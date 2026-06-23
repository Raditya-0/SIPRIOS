import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.models.database import get_db, User, Warga
from app.core.security import (
    get_current_user, require_auth, require_kepala_desa, require_admin, require_admin_or_kd
)
from app.core.config import settings
from app.services.scoring import WargaData, proses_warga, yn, predict_house_condition
from app.services.storage import save_file, validate_file, delete_file_by_url
from app.services.export import export_pdf, export_excel

router = APIRouter(prefix="/api/warga", tags=["Warga"])


def _warga_to_dict(w: Warga, username: str) -> dict:
    return {
        "id": w.id,
        "nomorKK": w.nomor_kk,
        "nama": w.nama,
        "score": w.score,
        "kategori": {
            "level": w.kategori_level,
            "label": w.kategori_label,
            "key": f"need{w.kategori_level}"
        },
        "kondisi": _kondisi_label(w),
        "tanggal": w.tanggal_input,
        "inputOleh": username,
    }


def _kondisi_label(w: Warga) -> dict:
    bad = sum([
        not w.punya_kamar_mandi,
        not w.air_bersih,
        not w.ada_listrik,
        not w.punya_plafon,
        w.status_toilet == "Tidak Ada",
        w.status_rumah == "Tidak Layak",
    ])
    if bad >= 4:
        return {"label": "Kondisi Membutuhkan Perbaikan", "cls": "bad"}
    elif bad >= 2:
        return {"label": "Kondisi Perlu Perhatian", "cls": "warn"}
    return {"label": "Kondisi Baik", "cls": "ok"}


def _build_warga_data(
    sewa_bulanan, punya_kulkas, total_anggota, jumlah_dewasa,
    jumlah_anak, jumlah_lansia, jumlah_ruangan, kamar_tidur,
    punya_kamar_mandi, air_bersih, ada_listrik, punya_plafon,
    punya_dapur, status_toilet, status_rumah, rata_sekolah,
    ada_tidak_sekolah, ada_pendidikan_tinggi
) -> WargaData:
    return WargaData(
        sewa_bulanan=int(sewa_bulanan or 0),
        punya_kulkas=yn(punya_kulkas),
        total_anggota=int(total_anggota or 1),
        jumlah_dewasa=int(jumlah_dewasa or 1),
        jumlah_anak=int(jumlah_anak or 0),
        jumlah_lansia=int(jumlah_lansia or 0),
        jumlah_ruangan=int(jumlah_ruangan or 1),
        kamar_tidur=int(kamar_tidur or 0),
        punya_kamar_mandi=yn(punya_kamar_mandi),
        air_bersih=yn(air_bersih),
        ada_listrik=yn(ada_listrik),
        punya_plafon=yn(punya_plafon),
        punya_dapur=yn(punya_dapur),
        status_toilet=status_toilet or "Tidak Ada",
        status_rumah=status_rumah or "Lainnya",
        rata_sekolah=float(rata_sekolah or 0),
        ada_tidak_sekolah=yn(ada_tidak_sekolah),
        ada_pendidikan_tinggi=yn(ada_pendidikan_tinggi),
    )


# ── GET /api/warga ──
@router.get("")
async def list_warga(
    q: Optional[str] = Query(None),
    level: Optional[int] = Query(None),
    sort: str = Query("score_desc"),
    db: Session = Depends(get_db),
    payload: Optional[dict] = Depends(get_current_user),
):
    query = db.query(Warga, User.username).join(User, Warga.input_oleh == User.id)

    if q:
        query = query.filter(
            (Warga.nama.ilike(f"%{q}%")) | (Warga.nomor_kk.ilike(f"%{q}%"))
        )
    if level:
        query = query.filter(Warga.kategori_level == level)

    if sort == "score_desc":
        query = query.order_by(Warga.score.desc())
    elif sort == "score_asc":
        query = query.order_by(Warga.score.asc())
    else:
        query = query.order_by(Warga.tanggal_input.desc())

    rows = query.all()
    return [_warga_to_dict(w, username) for w, username in rows]


# ── POST /api/warga ──
@router.post("", status_code=201)
async def create_warga(
    nomorKK: str = Form(...),
    nama: str = Form(...),
    sewaBulanan: int = Form(default=0),
    punyaKulkas: str = Form(default="Tidak"),
    totalAnggota: int = Form(default=1),
    jumlahDewasa: int = Form(default=1),
    jumlahAnak: int = Form(default=0),
    jumlahLansia: int = Form(default=0),
    jumlahRuangan: int = Form(default=1),
    kamarTidur: int = Form(default=0),
    punyaKamarMandi: str = Form(default="Tidak"),
    airBersih: str = Form(default="Tidak"),
    adaListrik: str = Form(default="Tidak"),
    punyaPlafon: str = Form(default="Tidak"),
    punyaDapur: str = Form(default="Tidak"),
    statusToilet: str = Form(default="Tidak Ada"),
    statusRumah: str = Form(default="Lainnya"),
    rataSekolah: float = Form(default=0.0),
    adaTidakSekolah: str = Form(default="Tidak"),
    adaPendidikanTinggi: str = Form(default="Tidak"),
    foto: Optional[UploadFile] = File(default=None),
    payload: dict = Depends(require_kepala_desa),
    db: Session = Depends(get_db),
):
    # validasi nomor KK hanya angka
    if not nomorKK.isdigit():
        raise HTTPException(status_code=422, detail="Nomor KK hanya boleh mengandung angka.")

    # validasi nomor KK tepat 16 digit
    if len(nomorKK) != 16:
        raise HTTPException(status_code=422, detail="Nomor KK harus tepat 16 digit angka.")

    # validasi nama minimal 3 karakter
    if len(nama.strip()) < 3:
        raise HTTPException(status_code=422, detail="Nama minimal 3 karakter.")

    # cek duplikat
    existing = db.query(Warga).filter(Warga.nomor_kk == nomorKK).first()
    if existing:
        raise HTTPException(status_code=409, detail="Nomor KK sudah terdaftar. Gunakan fitur Edit untuk memperbarui data.")

    # upload foto + hitung kondisi rumah dari CV model
    foto_url    = None
    house_score = 0.5

    if foto and foto.filename:
        await validate_file(foto, settings.allowed_image_types_list, settings.MAX_FILE_SIZE_MB)
        foto_content = await foto.read()
        house_score = predict_house_condition(io.BytesIO(foto_content))
        await foto.seek(0)
        foto_url = await save_file(foto, subfolder="foto")

    # hitung skor dengan ML model
    data = _build_warga_data(
        sewaBulanan, punyaKulkas, totalAnggota, jumlahDewasa,
        jumlahAnak, jumlahLansia, jumlahRuangan, kamarTidur,
        punyaKamarMandi, airBersih, adaListrik, punyaPlafon,
        punyaDapur, statusToilet, statusRumah, rataSekolah,
        adaTidakSekolah, adaPendidikanTinggi,
    )
    hasil = proses_warga(data, nama, house_condition_score=house_score)

    warga = Warga(
        nomor_kk=nomorKK, nama=nama,
        sewa_bulanan=sewaBulanan, punya_kulkas=yn(punyaKulkas),
        total_anggota=totalAnggota, jumlah_dewasa=jumlahDewasa,
        jumlah_anak=jumlahAnak, jumlah_lansia=jumlahLansia,
        jumlah_ruangan=jumlahRuangan, kamar_tidur=kamarTidur,
        punya_kamar_mandi=yn(punyaKamarMandi), air_bersih=yn(airBersih),
        ada_listrik=yn(adaListrik), punya_plafon=yn(punyaPlafon),
        punya_dapur=yn(punyaDapur),
        status_toilet=statusToilet, status_rumah=statusRumah,
        rata_sekolah=rataSekolah,
        ada_tidak_sekolah=yn(adaTidakSekolah),
        ada_pendidikan_tinggi=yn(adaPendidikanTinggi),
        foto_url=foto_url,
        score=hasil["score"],
        kategori_level=hasil["kategori"]["level"],
        kategori_label=hasil["kategori"]["label"],
        input_oleh=payload["sub"],
    )
    db.add(warga)
    db.commit()
    db.refresh(warga)

    return {
        "id": warga.id,
        "score": warga.score,
        "kategori": hasil["kategori"],
        "kondisi": hasil["kondisi"],
        "faktor": hasil["faktor"],
        "tanggal": warga.tanggal_input,
    }


# ── GET /api/warga/export/pdf ──
@router.get("/export/pdf")
async def export_pdf_route(
    q: Optional[str] = Query(None),
    level: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    payload: dict = Depends(require_admin_or_kd),
):
    rows = db.query(Warga, User.username).join(User, Warga.input_oleh == User.id)
    if q:
        rows = rows.filter((Warga.nama.ilike(f"%{q}%")) | (Warga.nomor_kk.ilike(f"%{q}%")))
    if level:
        rows = rows.filter(Warga.kategori_level == level)
    rows = rows.order_by(Warga.score.desc()).all()

    data = []
    for w, username in rows:
        d = _warga_to_dict(w, username)
        d["totalAnggota"] = w.total_anggota
        d["airBersih"] = w.air_bersih
        d["adaListrik"] = w.ada_listrik
        d["statusToilet"] = w.status_toilet
        d["statusRumah"] = w.status_rumah
        d["rataSekolah"] = float(w.rata_sekolah)
        data.append(d)

    return export_pdf(data)


# ── GET /api/warga/export/excel ──
@router.get("/export/excel")
async def export_excel_route(
    q: Optional[str] = Query(None),
    level: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    payload: dict = Depends(require_admin_or_kd),
):
    rows = db.query(Warga, User.username).join(User, Warga.input_oleh == User.id)
    if q:
        rows = rows.filter((Warga.nama.ilike(f"%{q}%")) | (Warga.nomor_kk.ilike(f"%{q}%")))
    if level:
        rows = rows.filter(Warga.kategori_level == level)
    rows = rows.order_by(Warga.score.desc()).all()

    data = []
    for w, username in rows:
        d = _warga_to_dict(w, username)
        d["totalAnggota"] = w.total_anggota
        d["airBersih"] = w.air_bersih
        d["adaListrik"] = w.ada_listrik
        d["statusToilet"] = w.status_toilet
        d["statusRumah"] = w.status_rumah
        d["rataSekolah"] = float(w.rata_sekolah)
        data.append(d)

    return export_excel(data)


# ── GET /api/warga/:id ──
@router.get("/{warga_id}")
async def get_warga(
    warga_id: str,
    db: Session = Depends(get_db),
    payload: Optional[dict] = Depends(get_current_user),
):
    row = (
        db.query(Warga, User.username)
        .join(User, Warga.input_oleh == User.id)
        .filter(Warga.id == warga_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan.")

    w, username = row
    data = WargaData(
        sewa_bulanan=w.sewa_bulanan, punya_kulkas=w.punya_kulkas,
        total_anggota=w.total_anggota, jumlah_dewasa=w.jumlah_dewasa,
        jumlah_anak=w.jumlah_anak, jumlah_lansia=w.jumlah_lansia,
        jumlah_ruangan=w.jumlah_ruangan, kamar_tidur=w.kamar_tidur,
        punya_kamar_mandi=w.punya_kamar_mandi, air_bersih=w.air_bersih,
        ada_listrik=w.ada_listrik, punya_plafon=w.punya_plafon,
        punya_dapur=w.punya_dapur, status_toilet=w.status_toilet,
        status_rumah=w.status_rumah, rata_sekolah=float(w.rata_sekolah),
        ada_tidak_sekolah=w.ada_tidak_sekolah,
        ada_pendidikan_tinggi=w.ada_pendidikan_tinggi,
    )
    hasil = proses_warga(data, w.nama)

    return {
        "id": w.id,
        "nomorKK": w.nomor_kk,
        "nama": w.nama,
        "sewaBulanan": w.sewa_bulanan,
        "punyaKulkas": "Ya" if w.punya_kulkas else "Tidak",
        "totalAnggota": w.total_anggota,
        "jumlahDewasa": w.jumlah_dewasa,
        "jumlahAnak": w.jumlah_anak,
        "jumlahLansia": w.jumlah_lansia,
        "jumlahRuangan": w.jumlah_ruangan,
        "kamarTidur": w.kamar_tidur,
        "punyaKamarMandi": "Ya" if w.punya_kamar_mandi else "Tidak",
        "airBersih": "Ya" if w.air_bersih else "Tidak",
        "adaListrik": "Ya" if w.ada_listrik else "Tidak",
        "punyaPlafon": "Ya" if w.punya_plafon else "Tidak",
        "punyaDapur": "Ya" if w.punya_dapur else "Tidak",
        "statusToilet": w.status_toilet,
        "statusRumah": w.status_rumah,
        "rataSekolah": float(w.rata_sekolah),
        "adaTidakSekolah": "Ya" if w.ada_tidak_sekolah else "Tidak",
        "adaPendidikanTinggi": "Ya" if w.ada_pendidikan_tinggi else "Tidak",
        "fotoUrl": w.foto_url,
        "score": w.score,
        "kategori": hasil["kategori"],
        "kondisi": hasil["kondisi"],
        "faktor": hasil["faktor"],
        "rekomendasi": hasil["rekomendasi"],
        "tanggal": w.tanggal_input,
        "inputOleh": username,
    }


# ── PUT /api/warga/:id ──
@router.put("/{warga_id}")
async def update_warga(
    warga_id: str,
    nama: str = Form(...),
    sewaBulanan: int = Form(default=0),
    punyaKulkas: str = Form(default="Tidak"),
    totalAnggota: int = Form(default=1),
    jumlahDewasa: int = Form(default=1),
    jumlahAnak: int = Form(default=0),
    jumlahLansia: int = Form(default=0),
    jumlahRuangan: int = Form(default=1),
    kamarTidur: int = Form(default=0),
    punyaKamarMandi: str = Form(default="Tidak"),
    airBersih: str = Form(default="Tidak"),
    adaListrik: str = Form(default="Tidak"),
    punyaPlafon: str = Form(default="Tidak"),
    punyaDapur: str = Form(default="Tidak"),
    statusToilet: str = Form(default="Tidak Ada"),
    statusRumah: str = Form(default="Lainnya"),
    rataSekolah: float = Form(default=0.0),
    adaTidakSekolah: str = Form(default="Tidak"),
    adaPendidikanTinggi: str = Form(default="Tidak"),
    foto: Optional[UploadFile] = File(default=None),
    payload: dict = Depends(require_kepala_desa),
    db: Session = Depends(get_db),
):
    warga = db.query(Warga).filter(Warga.id == warga_id).first()
    if not warga:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan.")

    # cek kepemilikan — hanya bisa edit data sendiri
    if warga.input_oleh != payload["sub"]:
        raise HTTPException(status_code=403, detail="Anda tidak berhak mengubah data ini.")

    # validasi nama minimal 3 karakter
    if len(nama.strip()) < 3:
        raise HTTPException(status_code=422, detail="Nama minimal 3 karakter.")

    # upload foto baru jika ada + hitung kondisi rumah dari CV model
    house_score = 0.5
    if foto and foto.filename:
        await validate_file(foto, settings.allowed_image_types_list, settings.MAX_FILE_SIZE_MB)
        foto_content = await foto.read()
        house_score = predict_house_condition(io.BytesIO(foto_content))
        await foto.seek(0)
        delete_file_by_url(warga.foto_url)
        warga.foto_url = await save_file(foto, subfolder="foto")

    # update field
    warga.nama = nama
    warga.sewa_bulanan = sewaBulanan
    warga.punya_kulkas = yn(punyaKulkas)
    warga.total_anggota = totalAnggota
    warga.jumlah_dewasa = jumlahDewasa
    warga.jumlah_anak = jumlahAnak
    warga.jumlah_lansia = jumlahLansia
    warga.jumlah_ruangan = jumlahRuangan
    warga.kamar_tidur = kamarTidur
    warga.punya_kamar_mandi = yn(punyaKamarMandi)
    warga.air_bersih = yn(airBersih)
    warga.ada_listrik = yn(adaListrik)
    warga.punya_plafon = yn(punyaPlafon)
    warga.punya_dapur = yn(punyaDapur)
    warga.status_toilet = statusToilet
    warga.status_rumah = statusRumah
    warga.rata_sekolah = rataSekolah
    warga.ada_tidak_sekolah = yn(adaTidakSekolah)
    warga.ada_pendidikan_tinggi = yn(adaPendidikanTinggi)

    # hitung ulang skor dengan ML model
    data = _build_warga_data(
        sewaBulanan, punyaKulkas, totalAnggota, jumlahDewasa,
        jumlahAnak, jumlahLansia, jumlahRuangan, kamarTidur,
        punyaKamarMandi, airBersih, adaListrik, punyaPlafon,
        punyaDapur, statusToilet, statusRumah, rataSekolah,
        adaTidakSekolah, adaPendidikanTinggi,
    )
    hasil = proses_warga(data, nama, house_condition_score=house_score)
    warga.score = hasil["score"]
    warga.kategori_level = hasil["kategori"]["level"]
    warga.kategori_label = hasil["kategori"]["label"]

    db.commit()
    db.refresh(warga)

    return {
        "id": warga.id,
        "score": warga.score,
        "kategori": hasil["kategori"],
        "kondisi": hasil["kondisi"],
        "faktor": hasil["faktor"],
        "tanggal": warga.tanggal_input,
    }


# ── DELETE /api/warga/:id ──
@router.delete("/{warga_id}")
async def delete_warga(
    warga_id: str,
    payload: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    warga = db.query(Warga).filter(Warga.id == warga_id).first()
    if not warga:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan.")

    delete_file_by_url(warga.foto_url)
    db.delete(warga)
    db.commit()
    return {"message": "Data warga berhasil dihapus."}
