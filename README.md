# SIPRIOS  (Sistem Prioritas Sosial)

> Sistem pendukung keputusan penyaluran bantuan sosial skala RT berbasis kecerdasan artifisial

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-yellow?logo=javascript)
![License](https://img.shields.io/badge/License-MIT-red)
![Status](https://img.shields.io/badge/Status-Live-brightgreen)

**Live:** [https://siprios.my.id](https://siprios.my.id)

---

## Tentang Proyek

SIPRIOS adalah aplikasi web yang membantu **Pengurus RT** menentukan prioritas penerima bantuan sosial secara **objektif, transparan, dan terukur** berdasarkan data kondisi rumah tangga warga.

Sistem menggunakan algoritma penilaian berbasis data untuk menghasilkan **skor kebutuhan (0–100)** per kepala keluarga, dilengkapi penjelasan faktor penentu yang mudah dipahami.

### Fitur Utama

- **Sistem Login 3 Role** —> Admin, Kepala Desa, Warga
- **Input Data Warga** —> 21 field kondisi rumah tangga + upload foto
- **Skor Prioritas Otomatis** —> dihitung backend, tidak bisa dimanipulasi
- **Penjelasan Keputusan** —> faktor penentu dalam bahasa manusiawi
- **Manajemen Akun** —> Admin approve/tolak pendaftaran Kepala Desa
- **Export Laporan** —> PDF dan Excel
- **Keamanan** —> JWT Authentication, bcrypt password hashing

---

## Arsitektur

```
User (Browser)
      ↓
https://siprios.my.id
      ↓
VPS Ubuntu 22.04 
├── Nginx (port 80/443 + SSL Let's Encrypt)
│   ├── /        → Frontend HTML/CSS/JS
│   ├── /api     → FastAPI Backend
│   └── /static  → File Upload (foto/surat)
└── FastAPI (port 8000, systemd service)
    ├── ML Model: Random Forest + XGBoost
    └── CV Model: EfficientNet-B0 ONNX
```

---

## Struktur Proyek

```
siprios/
├── frontend/                   # Antarmuka pengguna
│   ├── index.html              # Dashboard (root)
│   ├── pages/                  # Halaman lainnya
│   │   ├── input.html          # Form input data warga
│   │   ├── prioritas.html      # Daftar & ranking warga
│   │   ├── profil.html         # Profil kelayakan warga
│   │   ├── approval.html       # Persetujuan akun (admin)
│   │   ├── 403.html            # Akses ditolak
│   │   └── 404.html            # Halaman tidak ditemukan
│   ├── js/
│   │   ├── core.js             # Auth, API calls, komponen shared
│   │   └── input-page.js       # Logika form input
│   ├── css/
│   │   └── style.css           # Design system lengkap
│   └── assets/
│       ├── favicon.svg         # Logo bowl-food
│       └── fontawesome/        # Font Awesome 6 (lokal)
│
└── backend/                    # REST API
    ├── app/
    │   ├── main.py             # Entry point FastAPI
    │   ├── core/
    │   │   ├── config.py       # Konfigurasi dari .env
    │   │   └── security.py     # JWT + bcrypt
    │   ├── models/
    │   │   ├── database.py     # SQLAlchemy models
    │   │   └── schemas.py      # Pydantic schemas
    │   ├── routers/
    │   │   ├── auth.py         # /api/auth/*
    │   │   ├── warga.py        # /api/warga/*
    │   │   └── akun.py         # /api/akun/*
    │   └── services/
    │       ├── scoring.py      # Algoritma penilaian skor
    │       ├── storage.py      # Upload file
    │       └── export.py       # Generate PDF & Excel
    ├── requirements.txt
    ├── .env.example
    └── README.md
```

---

## Cara Menjalankan Lokal

### Prasyarat

- Python 3.11+
- Git

### 1. Clone Repository

```bash
git clone https://github.com/username/siprios.git
cd siprios
```

### 2. Setup Backend

```bash
cd backend
python -m venv venv

# Windows
source venv/Scripts/activate

# Mac/Linux
# source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Edit file `.env` sesuai kebutuhan, minimal:

```env
DATABASE_URL=sqlite:///./siprios.db
SECRET_KEY=ganti-dengan-random-string-panjang
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password_anda
```

Jalankan backend:

```bash
cd backend
uvicorn app.main:app --reload
```

Backend berjalan di: http://localhost:8000
Dokumentasi API: http://localhost:8000/docs

### 3. Setup Frontend

Buka terminal baru:

```bash
cd frontend
python -m http.server 3000
```

Buka browser: **http://localhost:3000**

### 4. Login Pertama

Akun admin dibuat otomatis saat backend pertama kali dijalankan, sesuai konfigurasi di `.env`:

- Username: sesuai `ADMIN_USERNAME`
- Password: sesuai `ADMIN_PASSWORD`

---

## API Endpoints

| Method | Endpoint                        | Role        | Keterangan            |
| ------ | ------------------------------- | ----------- | --------------------- |
| POST   | `/api/auth/login`             | Publik      | Login → JWT token    |
| POST   | `/api/auth/register`          | Publik      | Register Kepala Desa  |
| POST   | `/api/auth/logout`            | Login       | Logout                |
| GET    | `/api/auth/me`                | Login       | Profil user           |
| GET    | `/api/warga`                  | Publik      | Daftar warga          |
| POST   | `/api/warga`                  | Kepala Desa | Input data warga baru |
| GET    | `/api/warga/:id`              | Publik      | Detail satu warga     |
| PUT    | `/api/warga/:id`              | Kepala Desa | Update data warga     |
| DELETE | `/api/warga/:id`              | Admin       | Hapus data warga      |
| GET    | `/api/warga/export/pdf`       | Admin       | Export PDF            |
| GET    | `/api/warga/export/excel`     | Admin       | Export Excel          |
| GET    | `/api/akun/pending`           | Admin       | Daftar akun pending   |
| POST   | `/api/akun/:username/approve` | Admin       | Setujui akun          |
| DELETE | `/api/akun/:username`         | Admin       | Tolak akun            |
| GET    | `/health`                     | Publik      | Status server         |

---

## Role & Akses

| Halaman          | Warga      | Kepala Desa        | Admin      |
| ---------------- | ---------- | ------------------ | ---------- |
| Dashboard        | ✓         | ✓                 | ✓         |
| Daftar Prioritas | ✓ (lihat) | ✓ (lihat)         | ✓ + Hapus |
| Input Data Warga | X          | ✓                 | X          |
| Edit Data Warga  | X          | ✓ (milik sendiri) | X          |
| Profil Warga     | ✓         | ✓                 | ✓         |
| Persetujuan Akun | X          | X                  | ✓         |

---

## Tech Stack

**Frontend**

- HTML5, CSS3, Vanilla JavaScript (ES6+)
- Font Awesome 6 (lokal)
- Multi-page architecture

**Backend**

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy + Alembic
- JWT (python-jose) + bcrypt
- ReportLab (PDF) + OpenPyXL (Excel)

**Database**

- SQLite (development)
- PostgreSQL (production)

---

## Model AI

### Tabular Model — Skor Prioritas Warga
- **Algoritma:** Random Forest + XGBoost ensemble
  (weights: RF=0.8, XGB=0.2)
- **Training data:** Costa Rica Household Poverty dataset
- **Output:** skor 0–100 + kategori
  (Membutuhkan / Rawan / Cukup / Mandiri)
- **Notebook:** [tabular-bansos-model (Kaggle)](https://www.kaggle.com/code/raditya0/tabular-bansos-model)
- **Fallback:** rule-based algorithm jika model tidak tersedia

### CV Model — Kondisi Fisik Rumah
- **Algoritma:** EfficientNet-B0 (format ONNX)
- **Input:** foto kondisi rumah (JPG/PNG/WebP, maks 5MB)
- **Output:** house_condition_score (0=bagus, 1=buruk)
- **Notebook:** [house-image-classification (Kaggle)](https://www.kaggle.com/code/raditya0/house-image-classification)
- **Penggunaan:** digunakan sebagai salah satu fitur
  input ke tabular model

---

## Tim Pengembang

**KPPL RKA(N) Kelompok 4**
Rekayasa Kecerdasan Artifisial
Institut Teknologi Sepuluh Nopember Surabaya 2026

| Nama                 | NRP        |
| -------------------- | ---------- |
| Raditya Akmal        | 5054241027 |
| Izzah Naufalia Adila | 5054241021 |
| Muhammad Fathur Aziz | 5054241043 |

**Dosen Pengampu:**
Dr. Sarwosri, S.Kom., M.T. · Dr. Muhammad Alfian, M.Tr.Kom.

---

## Lisensi

MIT License bebas digunakan untuk keperluan akademik.
