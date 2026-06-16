from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db, User
from app.core.security import require_admin

router = APIRouter(prefix="/api/akun", tags=["Akun"])


@router.get("/pending")
async def list_pending(
    payload: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).filter(
        User.role == "kepala_desa",
        User.status == "pending"
    ).order_by(User.created_at.asc()).all()

    return [
        {
            "nama": u.nama,
            "username": u.username,
            "suratUrl": u.surat_url,
            "tanggal": u.created_at,
        }
        for u in users
    ]


@router.post("/{username}/approve")
async def approve_akun(
    username: str,
    payload: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan.")
    if user.status == "active":
        raise HTTPException(status_code=400, detail="Akun sudah aktif.")

    user.status = "active"
    db.commit()
    return {"message": "Akun disetujui. Kepala Desa dapat login."}


@router.delete("/{username}")
async def reject_akun(
    username: str,
    payload: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan.")

    db.delete(user)
    db.commit()
    return {"message": "Permohonan ditolak dan dihapus."}
