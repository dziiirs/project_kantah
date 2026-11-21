import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # peta resolusi tinggi melebihi batas default Pillow

DATA_DIR = Path(os.environ.get("DATA_DIR", "."))  # folder penyimpanan (disk permanen saat hosting)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- Database (SQLite) ---
conn = sqlite3.connect(DATA_DIR / "foto.db", check_same_thread=False)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS foto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_file TEXT UNIQUE,
        hash TEXT UNIQUE,
        pengunggah TEXT,
        waktu TEXT
    )
    """
)
conn.commit()


def hitung_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cek_foto(nama_file: str, hash_file: str):
    """Kembalikan (pengunggah, alasan) jika sudah ada, None jika belum."""
    row = conn.execute(
        "SELECT pengunggah FROM foto WHERE nama_file = ?", (nama_file,)
    ).fetchone()
    if row:
        return row[0], "nama file sama"
    row = conn.execute(
        "SELECT pengunggah FROM foto WHERE hash = ?", (hash_file,)
    ).fetchone()
    if row:
        return row[0], "isi foto sama (nama file berbeda)"
    return None


def simpan_foto(file, hash_file: str, pengunggah: str):
    (UPLOAD_DIR / file.name).write_bytes(file.getvalue())
    conn.execute(
        "INSERT INTO foto (nama_file, hash, pengunggah, waktu) VALUES (?, ?, ?, ?)",
        (file.name, hash_file, pengunggah, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()


def hapus_foto(nama_file: str):
    conn.execute("DELETE FROM foto WHERE nama_file = ?", (nama_file,))
    conn.commit()
    path = UPLOAD_DIR / nama_file
    if path.exists():
        path.unlink()


# --- Tampilan ---
st.title("Cek Foto Peta")

# Password opsional: aktif jika variabel lingkungan APP_PASSWORD diisi
PASSWORD = os.environ.get("APP_PASSWORD")
if PASSWORD and st.text_input("Password", type="password") != PASSWORD:
    st.stop()

st.caption("Unggah foto peta yang akan Anda kerjakan. Foto yang sudah diambil orang lain akan ditolak.")

pengunggah = st.text_input("Nama Anda")
files = st.file_uploader(
    "Pilih foto peta",
    type=["png", "jpg", "jpeg", "tif", "tiff"],
    accept_multiple_files=True,
)

if st.button("Unggah", type="primary"):
    if not pengunggah.strip():
        st.warning("Isi nama Anda dulu.")
    elif not files:
        st.warning("Pilih minimal satu foto.")
    else:
        for f in files:
            h = hitung_hash(f.getvalue())
            hasil = cek_foto(f.name, h)
            if hasil:
                st.error(f"❌ {f.name} ditolak: sudah diunggah oleh {hasil[0]} ({hasil[1]}).")
            else:
                simpan_foto(f, h, pengunggah.strip())
                st.success(f"✅ {f.name} berhasil diunggah.")
                img = Image.open(f)
                img.draft("RGB", (1600, 1600))  # percepat pembacaan JPEG besar
                img.thumbnail((1600, 1600))  # tampilkan versi kecil saja
                st.image(img, caption=f.name, use_container_width=True)

# --- Daftar foto yang sudah diambil (dengan tombol hapus) ---
PASSWORD_HAPUS = os.environ.get("PASSWORD_HAPUS") or PASSWORD


@st.dialog("Hapus foto")
def dialog_hapus(nama_file: str):
    st.write(f"Hapus **{nama_file}**?")
    pw = st.text_input("Masukkan password", type="password")
    if st.button("Hapus", type="primary"):
        if pw != PASSWORD_HAPUS:
            st.error("Password salah.")
        else:
            hapus_foto(nama_file)
            st.toast(f"{nama_file} dihapus.", icon="🗑️")
            st.rerun()


st.subheader("Foto yang sudah diambil")
rows = conn.execute(
    "SELECT nama_file, pengunggah, waktu FROM foto ORDER BY id DESC"
).fetchall()

if not rows:
    st.info("Belum ada foto.")
else:
    if not PASSWORD_HAPUS:
        st.caption("Tombol hapus nonaktif. Isi PASSWORD_HAPUS atau APP_PASSWORD untuk mengaktifkannya.")
    kolom = [4, 2, 2, 1]
    judul = st.columns(kolom)
    for c, t in zip(judul, ["Nama File", "Pengunggah", "Waktu", ""]):
        c.markdown(f"**{t}**")
    for nama, peng, waktu in rows:
        c1, c2, c3, c4 = st.columns(kolom)
        c1.write(nama)
        c2.write(peng)
        c3.write(waktu)
        if c4.button("🗑️", key=f"hapus_{nama}", disabled=not PASSWORD_HAPUS):
            dialog_hapus(nama)
