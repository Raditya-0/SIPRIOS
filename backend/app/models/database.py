import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, SmallInteger, Boolean,
    Enum, TIMESTAMP, ForeignKey, DECIMAL, Text, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id          = Column(String(36), primary_key=True, default=new_uuid)
    nama        = Column(String(100), nullable=False)
    username    = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role        = Column(Enum("kepala_desa", "admin"), nullable=False)
    status      = Column(Enum("pending", "active"), default="pending", nullable=False)
    surat_url   = Column(String(500), nullable=True)
    created_at  = Column(TIMESTAMP, default=datetime.utcnow)

    warga_list  = relationship("Warga", back_populates="input_oleh_user")


class Warga(Base):
    __tablename__ = "warga"

    id                  = Column(String(36), primary_key=True, default=new_uuid)
    nomor_kk            = Column(String(16), nullable=False, index=True)
    nama                = Column(String(100), nullable=False)

    # ekonomi
    sewa_bulanan        = Column(Integer, default=0)
    punya_kulkas        = Column(Boolean, default=False)

    # komposisi keluarga
    total_anggota       = Column(SmallInteger, default=1)
    jumlah_dewasa       = Column(SmallInteger, default=1)
    jumlah_anak         = Column(SmallInteger, default=0)
    jumlah_lansia       = Column(SmallInteger, default=0)

    # hunian
    jumlah_ruangan      = Column(SmallInteger, default=1)
    kamar_tidur         = Column(SmallInteger, default=0)
    punya_kamar_mandi   = Column(Boolean, default=False)
    air_bersih          = Column(Boolean, default=False)
    ada_listrik         = Column(Boolean, default=False)
    punya_plafon        = Column(Boolean, default=False)
    punya_dapur         = Column(Boolean, default=False)
    status_toilet       = Column(Enum("Tidak Ada", "Tidak Layak", "Layak"), default="Tidak Ada")
    status_rumah        = Column(
        Enum("Milik Sendiri", "Sewa/Cicilan", "Tidak Layak", "Lainnya"),
        default="Lainnya"
    )

    # pendidikan
    rata_sekolah        = Column(DECIMAL(4, 1), default=0.0)
    ada_tidak_sekolah   = Column(Boolean, default=False)
    ada_pendidikan_tinggi = Column(Boolean, default=False)

    # foto
    foto_url            = Column(String(500), nullable=True)

    # hasil scoring (dihitung backend)
    score               = Column(SmallInteger, default=0)
    kategori_level      = Column(SmallInteger, default=4)
    kategori_label      = Column(String(30), default="Mandiri")

    # relasi
    input_oleh          = Column(String(36), ForeignKey("users.id"), nullable=False)
    input_oleh_user     = relationship("User", back_populates="warga_list")
    tanggal_input       = Column(TIMESTAMP, default=datetime.utcnow)
