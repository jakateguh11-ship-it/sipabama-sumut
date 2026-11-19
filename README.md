# SIPABAMA — Sistem Informasi Produksi Bawang Merah Sumatera Utara

Dashboard Streamlit untuk menampilkan data produksi bawang merah tingkat kecamatan dari data mart PostgreSQL Neon.

## File
- `app.py`: aplikasi dashboard Streamlit.
- `requirements.txt`: dependensi Python.
- `warehouse_setup.sql`: membangun RAW, STAGING, WAREHOUSE (star schema), dan DATA MART pada `db_pusat_sumut`.
- `role_web_reader.sql`: membuat role read-only bagi website. Ganti password placeholder secara lokal sebelum dijalankan; jangan commit password.
- `.gitignore`: mencegah file rahasia masuk repository.

## Konfigurasi Streamlit Secrets
Tambahkan rahasia berikut melalui Streamlit Community Cloud → App settings → Secrets:

```toml
DATABASE_URL = "postgresql://web_reader:PASSWORD@HOST/db_pusat_sumut?sslmode=require"
```

Ambil URI dari Neon Console → Connect, pilih database `db_pusat_sumut` dan role `web_reader`. Gunakan pooled connection string jika tersedia dan sesuai kebutuhan koneksi aplikasi.

## Menjalankan lokal

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment
Upload repository ke GitHub, lalu hubungkan repository, branch, dan `app.py` melalui https://share.streamlit.io.

**Catatan data:** rincian produksi tingkat kecamatan pada dataset praktikum merupakan simulasi, bukan statistik kecamatan resmi BPS.
