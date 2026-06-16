import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.security import hash_password
from app.models.database import Base, engine, SessionLocal, User
from app.routers import auth, warga, akun

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_admin():
    """Buat akun admin default jika belum ada."""
    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        if not exists:
            admin = User(
                nama=settings.ADMIN_NAMA,
                username=settings.ADMIN_USERNAME,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
                status="active",
            )
            db.add(admin)
            db.commit()
            logger.info(f"Admin seed: '{settings.ADMIN_USERNAME}' dibuat.")
        else:
            logger.info("Admin sudah ada, skip seed.")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Membuat tabel database...")
    Base.metadata.create_all(bind=engine)

    logger.info("Seed admin...")
    seed_admin()

    from app.services.scoring import load_models
    load_models()

    Path("static/uploads/foto").mkdir(parents=True, exist_ok=True)
    Path("static/uploads/surat").mkdir(parents=True, exist_ok=True)

    logger.info("SIPRIOS Backend siap.")
    yield
    logger.info("Shutdown.")


app = FastAPI(
    title="SIPRIOS API",
    description="Backend API untuk Sistem Prioritas Sosial — Bantuan Sosial Skala RT",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# static files (foto & surat)
app.mount("/static", StaticFiles(directory="static"), name="static")

# routers
app.include_router(auth.router)
app.include_router(warga.router)
app.include_router(akun.router)


@app.get("/")
async def root():
    return {"app": "SIPRIOS API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health():
    from app.services.scoring import _rf_model, _cv_session
    return {
        "status": "ok",
        "version": "1.0.0",
        "ml_tabular": _rf_model is not None,
        "ml_cv": _cv_session is not None,
    }
