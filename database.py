"""
database.py
===========
DatabaseManager: satu-satunya class yang berbicara langsung dengan SQLite.
Class lain tidak perlu tahu SQL (pemisahan tanggung jawab / separation of concerns).
"""
import sqlite3
from datetime import date, timedelta

from models import (
    Akun, Mahasiswa, Admin, ProfilGamifikasi, Badge, LogAktivitas,
    buat_habit, buat_badge,
)

ADMIN_EMAIL_DEFAULT = "admin@habiquest.local"
ADMIN_PASSWORD_DEFAULT = "admin123"


class DatabaseManager:
    def __init__(self, path="habiquest.db"):
        self.__koneksi = sqlite3.connect(path, check_same_thread=False)
        self.__koneksi.row_factory = sqlite3.Row
        self.__koneksi.execute("PRAGMA foreign_keys = ON")
        self.__tertutup = False
        self._buat_tabel()
        self._isi_data_awal()

    # ------------------------------------------------------------------
    # Context manager: `with DatabaseManager(path) as db:` menutup
    # koneksi secara otomatis setelah blok selesai.
    # ------------------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.tutup()
        return False

    def __del__(self):
        # Jaring pengaman: koneksi ikut ditutup saat objek dibuang
        # (mis. di akhir sebuah view) walau tutup() lupa dipanggil.
        try:
            self.tutup()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Persiapan database
    # ------------------------------------------------------------------
    def _buat_tabel(self):
        with self.__koneksi:
            self.__koneksi.executescript("""
            CREATE TABLE IF NOT EXISTS akun (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                peran TEXT NOT NULL CHECK (peran IN ('Mahasiswa', 'Admin'))
            );
            CREATE TABLE IF NOT EXISTS profil (
                akun_id INTEGER PRIMARY KEY
                    REFERENCES akun(id) ON DELETE CASCADE,
                xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                streak INTEGER NOT NULL DEFAULT 0,
                terakhir_aktif TEXT
            );
            CREATE TABLE IF NOT EXISTS habit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                akun_id INTEGER NOT NULL
                    REFERENCES akun(id) ON DELETE CASCADE,
                nama TEXT NOT NULL,
                jenis TEXT NOT NULL,
                target_mingguan INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS log_aktivitas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL
                    REFERENCES habit(id) ON DELETE CASCADE,
                tanggal TEXT NOT NULL,
                nilai INTEGER NOT NULL,
                xp_didapat INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS badge_master (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipe TEXT NOT NULL,
                nama TEXT NOT NULL,
                deskripsi TEXT NOT NULL,
                ambang INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS badge_akun (
                akun_id INTEGER NOT NULL
                    REFERENCES akun(id) ON DELETE CASCADE,
                badge_id INTEGER NOT NULL
                    REFERENCES badge_master(id) ON DELETE CASCADE,
                tanggal TEXT NOT NULL,
                PRIMARY KEY (akun_id, badge_id)
            );
            """)

    def _isi_data_awal(self):
        """Membuat akun admin dan lencana bawaan bila masih kosong."""
        db = self.__koneksi
        ada_admin = db.execute(
            "SELECT 1 FROM akun WHERE peran = 'Admin'").fetchone()
        if not ada_admin:
            with db:
                db.execute(
                    "INSERT INTO akun (nama, email, password_hash, peran) "
                    "VALUES (?, ?, ?, 'Admin')",
                    ("Administrator", ADMIN_EMAIL_DEFAULT,
                     Akun.buat_hash(ADMIN_PASSWORD_DEFAULT)))
        ada_badge = db.execute("SELECT 1 FROM badge_master").fetchone()
        if not ada_badge:
            bawaan = [
                ("xp", "Langkah Pertama", "Kumpulkan 10 XP", 10),
                ("streak", "Pemanasan", "Streak 3 hari beruntun", 3),
                ("xp", "Pemula Tangguh", "Kumpulkan 100 XP", 100),
                ("streak", "Konsisten 7 Hari", "Streak 7 hari beruntun", 7),
                ("xp", "Pejuang Ilmu", "Kumpulkan 500 XP", 500),
                ("streak", "Disiplin Sejati", "Streak 30 hari beruntun", 30),
            ]
            with db:
                db.executemany(
                    "INSERT INTO badge_master (tipe, nama, deskripsi, ambang) "
                    "VALUES (?, ?, ?, ?)", bawaan)

    def tutup(self):
        """Menutup koneksi; aman dipanggil lebih dari sekali."""
        if not self.__tertutup:
            self.__koneksi.close()
            self.__tertutup = True

    # ------------------------------------------------------------------
    # Akun
    # ------------------------------------------------------------------
    def email_terdaftar(self, email):
        """Mengecek apakah email sudah terdaftar."""
        row = self.__koneksi.execute(
            "SELECT 1 FROM akun WHERE email = ?",
            ((email or "").strip().lower(),)).fetchone()
        return row is not None

    def tambah_akun(self, akun):
        """
        Menyimpan objek akun baru (Mahasiswa atau Admin) dan mengembalikan
        id-nya. Peran diambil dari akun.get_peran() (polymorphism).
        Melempar ValueError bila email sudah terdaftar.
        """
        if not isinstance(akun, Akun):
            raise ValueError("Akun tidak valid.")
        if self.email_terdaftar(akun.email):
            raise ValueError("Email sudah terdaftar.")
        try:
            with self.__koneksi:
                cur = self.__koneksi.execute(
                    "INSERT INTO akun (nama, email, password_hash, peran) "
                    "VALUES (?, ?, ?, ?)",
                    (akun.nama.strip(), akun.email.strip().lower(),
                     akun._hash_untuk_disimpan(), akun.get_peran()))
                if isinstance(akun, Mahasiswa):
                    self.__koneksi.execute(
                        "INSERT INTO profil (akun_id) VALUES (?)", (cur.lastrowid,))
        except sqlite3.IntegrityError:
            raise ValueError("Email sudah terdaftar.")
        return cur.lastrowid

    def daftar_mahasiswa(self):
        """Daftar semua akun Mahasiswa sebagai objek Mahasiswa."""
        rows = self.__koneksi.execute(
            "SELECT * FROM akun WHERE peran = 'Mahasiswa' ORDER BY id").fetchall()
        return [self._bangun_akun(r) for r in rows]

    def ambil_akun(self, akun_id=None, email=None):
        """Mengambil satu akun berdasarkan id ATAU email (untuk login)."""
        if akun_id is not None:
            row = self.__koneksi.execute(
                "SELECT * FROM akun WHERE id = ?", (akun_id,)).fetchone()
        else:
            row = self.__koneksi.execute(
                "SELECT * FROM akun WHERE email = ?",
                ((email or "").strip().lower(),)).fetchone()
        return self._bangun_akun(row) if row else None

    def _bangun_akun(self, row):
        """Mengubah baris tabel menjadi objek Mahasiswa atau Admin."""
        if row["peran"] == "Admin":
            return Admin(row["id"], row["nama"], row["email"], row["password_hash"])
        p = self.__koneksi.execute(
            "SELECT * FROM profil WHERE akun_id = ?", (row["id"],)).fetchone()
        terakhir = (date.fromisoformat(p["terakhir_aktif"])
                    if p and p["terakhir_aktif"] else None)
        profil = ProfilGamifikasi(p["xp"], p["level"], p["streak"], terakhir) \
            if p else ProfilGamifikasi()
        habits = [
            buat_habit(h["jenis"], h["nama"], h["target_mingguan"], h["id"],
                       self._ambil_log(h["id"]))
            for h in self.__koneksi.execute(
                "SELECT * FROM habit WHERE akun_id = ? ORDER BY id", (row["id"],))
        ]
        id_badge = [
            b["badge_id"] for b in self.__koneksi.execute(
                "SELECT badge_id FROM badge_akun WHERE akun_id = ?", (row["id"],))
        ]
        return Mahasiswa(row["id"], row["nama"], row["email"],
                         row["password_hash"], profil, habits, id_badge)

    def _ambil_log(self, habit_id):
        """Memuat LogAktivitas milik satu habit (composition Habit-LogAktivitas)."""
        return [
            LogAktivitas(r["habit_id"], date.fromisoformat(r["tanggal"]),
                         r["nilai"], r["xp_didapat"])
            for r in self.__koneksi.execute(
                "SELECT * FROM log_aktivitas WHERE habit_id = ? ORDER BY id",
                (habit_id,))
        ]

    def hapus_akun(self, akun_id):
        with self.__koneksi:
            self.__koneksi.execute("DELETE FROM akun WHERE id = ?", (akun_id,))

    # ------------------------------------------------------------------
    # Habit
    # ------------------------------------------------------------------
    def tambah_habit(self, mhs, jenis, nama, target_mingguan):
        """Menyimpan habit baru dan memasukkannya ke objek mahasiswa."""
        buat_habit(jenis, nama, target_mingguan)   # validasi dulu
        with self.__koneksi:
            cur = self.__koneksi.execute(
                "INSERT INTO habit (akun_id, nama, jenis, target_mingguan) "
                "VALUES (?, ?, ?, ?)",
                (mhs.id, nama.strip(), jenis, target_mingguan))
        habit = buat_habit(jenis, nama, target_mingguan, cur.lastrowid)
        mhs.tambah_habit(habit)
        return habit

    def ubah_habit(self, habit):
        """
        Menyimpan perubahan nama/target habit.
        Kepemilikan dicek lebih dulu oleh Mahasiswa.ubah_habit().
        """
        with self.__koneksi:
            cur = self.__koneksi.execute(
                "UPDATE habit SET nama = ?, target_mingguan = ? WHERE id = ?",
                (habit.nama, habit.target_mingguan, habit.id))
        if cur.rowcount == 0:
            raise ValueError("Kebiasaan tidak ditemukan.")

    def hapus_habit(self, habit_id):
        """
        Menghapus habit beserta log-nya.
        Kepemilikan dicek lebih dulu oleh Mahasiswa.hapus_habit().
        """
        with self.__koneksi:
            cur = self.__koneksi.execute(
                "DELETE FROM habit WHERE id = ?", (habit_id,))
        if cur.rowcount == 0:
            raise ValueError("Kebiasaan tidak ditemukan.")

    # ------------------------------------------------------------------
    # Log aktivitas & statistik
    # ------------------------------------------------------------------
    def simpan_hasil_catat(self, mhs, hasil):
        """Menyimpan log, profil terbaru, dan lencana baru dalam satu transaksi."""
        profil = mhs.profil
        with self.__koneksi:
            self.__koneksi.execute(
                "INSERT INTO log_aktivitas (habit_id, tanggal, nilai, xp_didapat) "
                "VALUES (?, ?, ?, ?)",
                (hasil.log.habit_id, hasil.log.tanggal.isoformat(),
                 hasil.log.nilai, hasil.log.xp_didapat))
            self.__koneksi.execute(
                "UPDATE profil SET xp = ?, level = ?, streak = ?, "
                "terakhir_aktif = ? WHERE akun_id = ?",
                (profil.xp, profil.level, profil.streak,
                 profil.terakhir_aktif.isoformat() if profil.terakhir_aktif else None,
                 mhs.id))
            for badge in hasil.badge_baru:
                self.__koneksi.execute(
                    "INSERT OR IGNORE INTO badge_akun (akun_id, badge_id, tanggal) "
                    "VALUES (?, ?, ?)",
                    (mhs.id, badge.id, hasil.log.tanggal.isoformat()))

    def xp_harian(self, akun_id, hari=7, akhir=None):
        """Daftar (tanggal, xp) untuk 'hari' hari terakhir, hari kosong = 0."""
        akhir = akhir or date.today()
        awal = akhir - timedelta(days=hari - 1)
        rows = self.__koneksi.execute(
            "SELECT l.tanggal, SUM(l.xp_didapat) AS xp "
            "FROM log_aktivitas l JOIN habit h ON h.id = l.habit_id "
            "WHERE h.akun_id = ? AND l.tanggal BETWEEN ? AND ? "
            "GROUP BY l.tanggal",
            (akun_id, awal.isoformat(), akhir.isoformat())).fetchall()
        peta = {r["tanggal"]: r["xp"] for r in rows}
        hasil = []
        for i in range(hari):
            t = awal + timedelta(days=i)
            hasil.append((t, peta.get(t.isoformat(), 0)))
        return hasil

    # ------------------------------------------------------------------
    # Badge
    # ------------------------------------------------------------------
    def daftar_badge(self):
        rows = self.__koneksi.execute(
            "SELECT * FROM badge_master ORDER BY tipe, ambang").fetchall()
        return [buat_badge(r["tipe"], r["nama"], r["deskripsi"],
                           r["ambang"], r["id"]) for r in rows]

    def tambah_badge(self, badge):
        """Menyimpan objek lencana (BadgeStreak/BadgeXP); mengembalikan id-nya."""
        if not isinstance(badge, Badge):
            raise ValueError("Lencana tidak valid.")
        with self.__koneksi:
            cur = self.__koneksi.execute(
                "INSERT INTO badge_master (tipe, nama, deskripsi, ambang) "
                "VALUES (?, ?, ?, ?)",
                (badge.TIPE, badge.nama, badge.deskripsi, badge.ambang))
        return cur.lastrowid

    def hapus_badge(self, badge_id):
        with self.__koneksi:
            self.__koneksi.execute(
                "DELETE FROM badge_master WHERE id = ?", (badge_id,))

