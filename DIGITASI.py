import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # peta resolusi tinggi melebihi batas default Pillow

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# --- Database (SQLite) ---
conn = sqlite3.connect("foto.db", check_same_thread=False)
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


# --- Tampilan ---
st.title("Cek Foto Peta")
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

# --- Daftar foto yang sudah diambil ---
st.subheader("Foto yang sudah diambil")
df = pd.read_sql_query(
    "SELECT nama_file AS 'Nama File', pengunggah AS 'Pengunggah', waktu AS 'Waktu' "
    "FROM foto ORDER BY id DESC",
    conn,
)
if df.empty:
    st.info("Belum ada foto.")
else:
    st.dataframe(df, use_container_width=True, hide_index=True)