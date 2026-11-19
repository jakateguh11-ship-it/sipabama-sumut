-- Jalankan pada database db_pusat_sumut SETELAH public.produksi_bawang_merah_pusat berisi data.
-- SQL ini membuat lapisan RAW, STAGING, WAREHOUSE (star schema), dan DATA MART.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS mart;

-- 1. RAW: salinan tabel integrasi pusat.
CREATE TABLE IF NOT EXISTS raw.produksi_bawang_merah (
    kode_data VARCHAR(20) PRIMARY KEY,
    kabupaten VARCHAR(100),
    kecamatan VARCHAR(100),
    komoditas VARCHAR(50),
    tahun INTEGER,
    produksi_ton NUMERIC(12,2),
    wilayah_sumber VARCHAR(100),
    updated_at TIMESTAMPTZ
);

INSERT INTO raw.produksi_bawang_merah
(kode_data, kabupaten, kecamatan, komoditas, tahun, produksi_ton, wilayah_sumber, updated_at)
SELECT kode_data, kabupaten, kecamatan, komoditas, tahun, produksi_ton,
       wilayah_sumber, updated_at
FROM public.produksi_bawang_merah_pusat
ON CONFLICT (kode_data) DO UPDATE SET
    kabupaten = EXCLUDED.kabupaten,
    kecamatan = EXCLUDED.kecamatan,
    komoditas = EXCLUDED.komoditas,
    tahun = EXCLUDED.tahun,
    produksi_ton = EXCLUDED.produksi_ton,
    wilayah_sumber = EXCLUDED.wilayah_sumber,
    updated_at = EXCLUDED.updated_at;

-- 2. STAGING: pemeriksaan sederhana sebelum masuk warehouse.
CREATE TABLE IF NOT EXISTS staging.stg_produksi_bawang_merah (
    kode_data VARCHAR(20) PRIMARY KEY,
    kabupaten VARCHAR(100),
    kecamatan VARCHAR(100),
    komoditas VARCHAR(50),
    tahun INTEGER,
    produksi_ton NUMERIC(12,2),
    wilayah_sumber VARCHAR(100),
    status_validasi VARCHAR(30),
    updated_at TIMESTAMPTZ
);

INSERT INTO staging.stg_produksi_bawang_merah
(kode_data, kabupaten, kecamatan, komoditas, tahun, produksi_ton, wilayah_sumber, status_validasi, updated_at)
SELECT kode_data, kabupaten, kecamatan, komoditas, tahun, produksi_ton,
       wilayah_sumber,
       CASE WHEN kabupaten IS NULL OR kecamatan IS NULL OR tahun IS NULL
                  OR produksi_ton IS NULL OR produksi_ton < 0
            THEN 'TIDAK VALID' ELSE 'VALID' END,
       updated_at
FROM raw.produksi_bawang_merah
ON CONFLICT (kode_data) DO UPDATE SET
    kabupaten = EXCLUDED.kabupaten,
    kecamatan = EXCLUDED.kecamatan,
    komoditas = EXCLUDED.komoditas,
    tahun = EXCLUDED.tahun,
    produksi_ton = EXCLUDED.produksi_ton,
    wilayah_sumber = EXCLUDED.wilayah_sumber,
    status_validasi = EXCLUDED.status_validasi,
    updated_at = EXCLUDED.updated_at;

-- 3. WAREHOUSE: tabel dimensi.
CREATE TABLE IF NOT EXISTS warehouse.dim_wilayah (
    wilayah_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kabupaten VARCHAR(100) NOT NULL,
    kecamatan VARCHAR(100) NOT NULL,
    UNIQUE (kabupaten, kecamatan)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_tahun (
    tahun_key INTEGER PRIMARY KEY,
    keterangan VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_komoditas (
    komoditas_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nama_komoditas VARCHAR(100) UNIQUE NOT NULL
);

INSERT INTO warehouse.dim_wilayah (kabupaten, kecamatan)
SELECT DISTINCT kabupaten, kecamatan
FROM staging.stg_produksi_bawang_merah
WHERE status_validasi = 'VALID'
ON CONFLICT (kabupaten, kecamatan) DO NOTHING;

INSERT INTO warehouse.dim_tahun (tahun_key, keterangan)
SELECT DISTINCT tahun, 'Tahun ' || tahun
FROM staging.stg_produksi_bawang_merah
WHERE status_validasi = 'VALID'
ON CONFLICT (tahun_key) DO UPDATE SET keterangan = EXCLUDED.keterangan;

INSERT INTO warehouse.dim_komoditas (nama_komoditas)
SELECT DISTINCT komoditas
FROM staging.stg_produksi_bawang_merah
WHERE status_validasi = 'VALID'
ON CONFLICT (nama_komoditas) DO NOTHING;

-- 4. WAREHOUSE: tabel fakta.
CREATE TABLE IF NOT EXISTS warehouse.fact_produksi (
    fact_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kode_data VARCHAR(20) UNIQUE NOT NULL,
    wilayah_key BIGINT REFERENCES warehouse.dim_wilayah(wilayah_key),
    tahun_key INTEGER REFERENCES warehouse.dim_tahun(tahun_key),
    komoditas_key BIGINT REFERENCES warehouse.dim_komoditas(komoditas_key),
    produksi_ton NUMERIC(12,2) NOT NULL,
    jenis_data VARCHAR(30),
    wilayah_sumber VARCHAR(100),
    updated_at TIMESTAMPTZ,
    loaded_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO warehouse.fact_produksi
(kode_data, wilayah_key, tahun_key, komoditas_key, produksi_ton, jenis_data, wilayah_sumber, updated_at)
SELECT s.kode_data, w.wilayah_key, t.tahun_key, k.komoditas_key,
       s.produksi_ton, 'SIMULASI', s.wilayah_sumber, s.updated_at
FROM staging.stg_produksi_bawang_merah s
JOIN warehouse.dim_wilayah w
  ON s.kabupaten = w.kabupaten AND s.kecamatan = w.kecamatan
JOIN warehouse.dim_tahun t ON s.tahun = t.tahun_key
JOIN warehouse.dim_komoditas k ON s.komoditas = k.nama_komoditas
WHERE s.status_validasi = 'VALID'
ON CONFLICT (kode_data) DO UPDATE SET
    wilayah_key = EXCLUDED.wilayah_key,
    tahun_key = EXCLUDED.tahun_key,
    komoditas_key = EXCLUDED.komoditas_key,
    produksi_ton = EXCLUDED.produksi_ton,
    jenis_data = EXCLUDED.jenis_data,
    wilayah_sumber = EXCLUDED.wilayah_sumber,
    updated_at = EXCLUDED.updated_at,
    loaded_at = NOW();

-- 5. DATA MART: view yang dibaca website.
CREATE OR REPLACE VIEW mart.vw_produksi_kecamatan AS
SELECT f.kode_data, w.kabupaten, w.kecamatan,
       t.tahun_key AS tahun, k.nama_komoditas AS komoditas,
       f.produksi_ton, f.jenis_data, f.wilayah_sumber
FROM warehouse.fact_produksi f
JOIN warehouse.dim_wilayah w ON f.wilayah_key = w.wilayah_key
JOIN warehouse.dim_tahun t ON f.tahun_key = t.tahun_key
JOIN warehouse.dim_komoditas k ON f.komoditas_key = k.komoditas_key;

CREATE OR REPLACE VIEW mart.vw_ringkasan_kabupaten AS
SELECT kabupaten, tahun,
       SUM(produksi_ton) AS total_produksi_ton,
       COUNT(*) AS jumlah_kecamatan,
       ROUND(AVG(produksi_ton), 2) AS rata_rata_produksi
FROM mart.vw_produksi_kecamatan
GROUP BY kabupaten, tahun;

-- 6. Verifikasi warehouse dan data mart.
SELECT COUNT(*) AS jumlah_fakta FROM warehouse.fact_produksi;
SELECT * FROM mart.vw_produksi_kecamatan ORDER BY kabupaten, kecamatan;
SELECT * FROM mart.vw_ringkasan_kabupaten ORDER BY total_produksi_ton DESC;
