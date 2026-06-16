from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.models.database import get_db, User
from app.models.schemas import LoginRequest, TokenResponse, MeResponse
from app.core.security import (
    hash_password, verify_password, create_token,
    require_auth, require_admin
)
from app.core.config import settings
from app.services.storage import save_file, validate_file

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Username atau kata sandi salah.")

    if user.status == "pending":
        raise HTTPException(status_code=403, detail="Akun Anda masih menunggu persetujuan admin.")

    token = create_token({"sub": user.id, "username": user.username, "role": user.role})
    return {
        "token": token,
        "user": {"nama": user.nama, "username": user.username, "role": user.role}
    }


@router.post("/register", status_code=201)
async def register(
    nama: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    surat: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # cek username duplikat
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username sudah dipakai.")

    # validasi & simpan surat
    await validate_file(surat, settings.allowed_doc_types_list, settings.MAX_FILE_SIZE_MB)
    surat_url = await save_file(surat, subfolder="surat")

    user = User(
        nama=nama,
        username=username,
        password_hash=hash_password(password),
        role="kepala_desa",
        status="pending",
        surat_url=surat_url,
    )
    db.add(user)
    db.commit()

    return {"message": "Pendaftaran berhasil. Menunggu persetujuan admin."}


@router.post("/logout")
async def logout(payload: dict = Depends(require_auth)):
    # JWT stateless — client hapus token di sessionStorage
    # di sini bisa blacklist token jika perlu
    return {"message": "Logout berhasil."}


@router.get("/me", response_model=MeResponse)
async def me(payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")
    return {"nama": user.nama, "username": user.username, "role": user.role}
