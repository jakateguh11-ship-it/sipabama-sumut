import os
from io import StringIO

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st

st.set_page_config(
    page_title="SIPABAMA | Produksi Bawang Merah Sumatera Utara",
    page_icon="🧅",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.7rem; padding-bottom: 2.5rem;}
      div[data-testid="stMetric"] {background: #f5f8f3; padding: 14px; border-radius: 12px;}
      .small-muted {color: #64748b; font-size: 0.88rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🧅 SIPABAMA")
st.subheader("Sistem Informasi Produksi Bawang Merah Sumatera Utara")
st.caption("Dashboard integrasi data produksi tingkat kabupaten dan kecamatan")
st.warning(
    "Transparansi data: angka produksi tingkat kecamatan pada demonstrasi ini adalah "
    "DATA SIMULASI. Total kabupaten mengikuti dataset acuan yang digunakan dalam praktikum; "
    "jangan mengutip angka kecamatan sebagai statistik resmi BPS."
)

if "DATABASE_URL" not in st.secrets:
    st.error(
        "DATABASE_URL belum diatur. Tambahkan connection string database pusat "
        "pada App settings → Secrets di Streamlit Community Cloud."
    )
    st.stop()

DATABASE_URL = st.secrets["DATABASE_URL"]


@st.cache_data(ttl=300, show_spinner="Mengambil data dari data mart...")
def load_data():
    """Ambil data read-only dari data mart di Neon."""
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=15)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    kode_data,
                    kabupaten,
                    kecamatan,
                    tahun,
                    komoditas,
                    produksi_ton,
                    jenis_data,
                    wilayah_sumber
                FROM mart.vw_produksi_kecamatan
                ORDER BY kabupaten, kecamatan
                """
            )
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
        return pd.DataFrame(rows, columns=columns)
    finally:
        conn.close()


try:
    df = load_data()
except Exception as exc:
    st.error("Tidak dapat membaca data warehouse. Periksa koneksi dan hak akses database.")
    st.caption(f"Jenis kesalahan: {type(exc).__name__}. Periksa DATABASE_URL dan izin SELECT pada schema mart.")
    st.stop()

if df.empty:
    st.info("Belum ada data pada mart.vw_produksi_kecamatan. Jalankan proses ETL di Neon terlebih dahulu.")
    st.stop()

df["produksi_ton"] = pd.to_numeric(df["produksi_ton"], errors="coerce")
df["tahun"] = pd.to_numeric(df["tahun"], errors="coerce").astype("Int64")

with st.sidebar:
    st.header("Navigasi SIPABAMA")
    page = st.radio(
        "Pilih halaman",
        ["Dashboard", "Data Produksi", "Analisis Wilayah", "Data Warehouse & ETL", "Tentang Sistem"],
    )
    st.divider()
    st.subheader("Filter Data")
    years = sorted([int(x) for x in df["tahun"].dropna().unique().tolist()])
    chosen_year = st.selectbox("Tahun", years, index=len(years) - 1)
    kabupaten_options = sorted(df["kabupaten"].dropna().unique().tolist())
    chosen_kabupaten = st.multiselect(
        "Kabupaten",
        kabupaten_options,
        default=kabupaten_options,
    )
    st.caption("Data diperbarui setelah proses ETL dijalankan. Cache dashboard: 5 menit.")

filtered = df[(df["tahun"] == chosen_year) & (df["kabupaten"].isin(chosen_kabupaten))].copy()

if page == "Dashboard":
    st.header("Dashboard Produksi")
    total = float(filtered["produksi_ton"].sum())
    n_kab = filtered["kabupaten"].nunique()
    n_kec = filtered["kecamatan"].nunique()
    n_rows = len(filtered)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total produksi", f"{total:,.2f} ton")
    c2.metric("Kabupaten", f"{n_kab}")
    c3.metric("Kecamatan", f"{n_kec}")
    c4.metric("Jumlah catatan", f"{n_rows}")

    if filtered.empty:
        st.info("Tidak ada data untuk filter yang dipilih.")
    else:
        by_kab = (
            filtered.groupby("kabupaten", as_index=False)["produksi_ton"]
            .sum()
            .sort_values("produksi_ton", ascending=False)
        )
        by_kec = filtered.sort_values("produksi_ton", ascending=True)
        left, right = st.columns(2)
        with left:
            st.subheader("Produksi menurut kabupaten")
            fig = px.bar(
                by_kab,
                x="produksi_ton",
                y="kabupaten",
                orientation="h",
                labels={"produksi_ton": "Produksi (ton)", "kabupaten": "Kabupaten"},
                text_auto=".2f",
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=420)
            st.plotly_chart(fig, use_container_width=True)
        with right:
            st.subheader("Produksi menurut kecamatan")
            fig2 = px.bar(
                by_kec,
                x="produksi_ton",
                y="kecamatan",
                orientation="h",
                color="kabupaten",
                labels={"produksi_ton": "Produksi (ton)", "kecamatan": "Kecamatan"},
                hover_data=["kabupaten", "tahun", "jenis_data"],
            )
            fig2.update_layout(height=420, showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Ringkasan kabupaten")
        summary = (
            filtered.groupby("kabupaten", as_index=False)
            .agg(jumlah_kecamatan=("kecamatan", "nunique"), total_produksi_ton=("produksi_ton", "sum"))
            .sort_values("total_produksi_ton", ascending=False)
        )
        st.dataframe(summary, use_container_width=True, hide_index=True)

elif page == "Data Produksi":
    st.header("Data Produksi per Kecamatan")
    st.write("Gunakan filter pada sidebar untuk melihat data menurut tahun dan kabupaten.")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    csv_data = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Unduh data hasil filter (CSV)",
        data=csv_data,
        file_name=f"data_produksi_bawang_merah_{chosen_year}.csv",
        mime="text/csv",
    )

elif page == "Analisis Wilayah":
    st.header("Analisis Perbandingan Wilayah")
    if filtered.empty:
        st.info("Tidak ada data untuk filter yang dipilih.")
    else:
        summary = (
            filtered.groupby("kabupaten", as_index=False)
            .agg(total_produksi_ton=("produksi_ton", "sum"), jumlah_kecamatan=("kecamatan", "nunique"))
            .sort_values("total_produksi_ton", ascending=False)
        )
        summary["kontribusi_persen"] = summary["total_produksi_ton"] / summary["total_produksi_ton"].sum() * 100
        fig = px.pie(
            summary,
            names="kabupaten",
            values="total_produksi_ton",
            hole=0.45,
            title="Proporsi produksi simulasi menurut kabupaten",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.caption("Persentase merupakan komposisi dari dataset yang sedang difilter, bukan pangsa produksi resmi provinsi.")

elif page == "Data Warehouse & ETL":
    st.header("Data Warehouse dan Proses ETL")
    st.markdown("""
    **Alur data:** database wilayah → database pusat → RAW → STAGING → WAREHOUSE → DATA MART → dashboard.

    - **Extract:** mengambil data dari lima database wilayah menggunakan Google Colab.
    - **Transform:** memeriksa kelengkapan, tipe, identitas wilayah, tahun, dan nilai produksi.
    - **Load:** menyimpan data terintegrasi ke Neon, kemudian memuat tabel dimensi dan fakta.
    - **Data mart:** `mart.vw_produksi_kecamatan` menjadi sumber pembacaan dashboard.
    """)
    c1, c2, c3 = st.columns(3)
    c1.metric("Baris pada data mart", len(df))
    c2.metric("Kabupaten", df["kabupaten"].nunique())
    c3.metric("Kecamatan", df["kecamatan"].nunique())
    st.subheader("Status dan kualitas data")
    quality = pd.DataFrame(
        {
            "Pemeriksaan": ["ID kosong", "Kabupaten kosong", "Kecamatan kosong", "Produksi kosong", "Produksi negatif", "Duplikasi kode_data"],
            "Jumlah masalah": [
                int(df["kode_data"].isna().sum()),
                int(df["kabupaten"].isna().sum()),
                int(df["kecamatan"].isna().sum()),
                int(df["produksi_ton"].isna().sum()),
                int((df["produksi_ton"] < 0).sum()),
                int(df["kode_data"].duplicated().sum()),
            ],
        }
    )
    st.dataframe(quality, use_container_width=True, hide_index=True)
    st.subheader("Asal data")
    if "wilayah_sumber" in df.columns:
        st.dataframe(df.groupby("wilayah_sumber", as_index=False).size().rename(columns={"size": "jumlah_baris"}), use_container_width=True, hide_index=True)
    st.info("Dataset praktikum saat ini berisi 20 baris simulasi tingkat kecamatan. Ini mendemonstrasikan pipeline dan warehouse, tetapi belum merupakan pemrosesan Big Data berskala besar.")

else:
    st.header("Tentang SIPABAMA")
    st.markdown("""
    SIPABAMA merupakan prototipe sistem informasi untuk menampilkan data produksi bawang merah di lima kabupaten Sumatera Utara.

    **Wilayah cakupan:** Karo, Simalungun, Humbang Hasundutan, Samosir, dan Tapanuli Utara.

    **Tahun dataset:** 2025.

    **Sumber dan batasan:** total produksi kabupaten menggunakan dataset acuan yang disusun dalam praktikum. Rincian produksi per kecamatan merupakan simulasi alokasi dan tidak boleh dikutip sebagai angka resmi BPS kecamatan.

    **Teknologi:** GitHub, Streamlit, Neon PostgreSQL, Google Colab, dan Plotly.
    """)
    st.markdown("Untuk penggunaan akademik, sertakan keterangan simulasi pada tabel, grafik, dan laporan.")

st.divider()
st.caption("SIPABAMA • Prototipe pembelajaran integrasi database dan data warehouse • Sumatera Utara")
