-- Jalankan satu kali di db_pusat_sumut menggunakan role administrator/owner.
-- Ganti PASSWORD_DIISI_SENDIRI dengan password kuat tanpa tanda kutip tunggal.
-- Jangan commit password ini atau file yang berisi password ke GitHub.

CREATE ROLE web_reader LOGIN PASSWORD 'PASSWORD_DIISI_SENDIRI';
GRANT CONNECT ON DATABASE db_pusat_sumut TO web_reader;
GRANT USAGE ON SCHEMA mart TO web_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA mart TO web_reader;

-- Jalankan kembali GRANT SELECT ini jika kelak membuat view baru di schema mart.
