from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# ── Auth ──

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user: dict


class MeResponse(BaseModel):
    nama: str
    username: str
    role: str


# ── Kategori & Kondisi ──

class Kategori(BaseModel):
    level: int
    label: str
    key: str


class Kondisi(BaseModel):
    label: str
    cls: str   # ok | warn | bad


class Faktor(BaseModel):
    cat: str
    detail: str
    dir: str   # up | down | neutral


# ── Warga ──

class WargaInput(BaseModel):
    nomorKK: str = Field(..., min_length=16, max_length=16)
    nama: str = Field(..., min_length=2)
    sewaBulanan: int = Field(default=0, ge=0)
    punyaKulkas: str = Field(default="Tidak")
    totalAnggota: int = Field(default=1, ge=1)
    jumlahDewasa: int = Field(default=1, ge=1)
    jumlahAnak: int = Field(default=0, ge=0)
    jumlahLansia: int = Field(default=0, ge=0)
    jumlahRuangan: int = Field(default=1, ge=1)
    kamarTidur: int = Field(default=0, ge=0)
    punyaKamarMandi: str = Field(default="Tidak")
    airBersih: str = Field(default="Tidak")
    adaListrik: str = Field(default="Tidak")
    punyaPlafon: str = Field(default="Tidak")
    punyaDapur: str = Field(default="Tidak")
    statusToilet: str = Field(default="Tidak Ada")
    statusRumah: str = Field(default="Lainnya")
    rataSekolah: float = Field(default=0.0, ge=0, le=20)
    adaTidakSekolah: str = Field(default="Tidak")
    adaPendidikanTinggi: str = Field(default="Tidak")


class WargaListItem(BaseModel):
    id: str
    nomorKK: str
    nama: str
    score: int
    kategori: Kategori
    kondisi: Kondisi
    tanggal: datetime
    inputOleh: str    # username kepala desa

    class Config:
        from_attributes = True


class WargaDetail(BaseModel):
    id: str
    nomorKK: str
    nama: str
    sewaBulanan: int
    punyaKulkas: str
    totalAnggota: int
    jumlahDewasa: int
    jumlahAnak: int
    jumlahLansia: int
    jumlahRuangan: int
    kamarTidur: int
    punyaKamarMandi: str
    airBersih: str
    adaListrik: str
    punyaPlafon: str
    punyaDapur: str
    statusToilet: str
    statusRumah: str
    rataSekolah: float
    adaTidakSekolah: str
    adaPendidikanTinggi: str
    fotoUrl: Optional[str]
    score: int
    kategori: Kategori
    kondisi: Kondisi
    faktor: list[Faktor]
    rekomendasi: str
    tanggal: datetime
    inputOleh: str


class WargaCreateResponse(BaseModel):
    id: str
    score: int
    kategori: Kategori
    kondisi: Kondisi
    faktor: list[Faktor]
    tanggal: datetime


# ── Akun Pending ──

class AkunPending(BaseModel):
    nama: str
    username: str
    suratUrl: Optional[str]
    tanggal: datetime
