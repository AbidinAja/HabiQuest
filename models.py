"""
models.py
=========
Kelas-kelas domain aplikasi HabiQuest.

Konsep PBO yang diterapkan di file ini:
  * Abstraction   : Akun, Habit, Badge adalah abstract class (ABC)
  * Encapsulation : atribut privat (__nama) + property + validasi
  * Inheritance   : Mahasiswa/Admin <- Akun, HabitXxx <- Habit, BadgeXxx <- Badge
  * Polymorphism  : hitung_xp(), cek_syarat(), get_peran() di-override subclass
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, timedelta
import hashlib
import hmac
import os

XP_PER_LEVEL = 100          # setiap 100 XP naik 1 level
MAKS_HARI_BONUS_STREAK = 7  # bonus streak maksimal dihitung sampai hari ke-7


# =====================================================================
# AKUN  (Abstract class + Inheritance)
# =====================================================================
class Akun(ABC):
    """Kelas dasar untuk semua pengguna aplikasi."""

    def __init__(self, id, nama, email, password_hash):
        self.__id = id                         # privat, hanya-baca
        self.__password_hash = password_hash   # privat, tidak boleh diubah dari luar
        self.nama = nama                       # melewati setter (validasi)
        self.email = email                     # melewati setter (validasi)

    # ---- property (Encapsulation) ----
    @property
    def id(self):
        return self.__id

    @property
    def nama(self):
        return self.__nama

    @nama.setter
    def nama(self, nilai):
        nilai = (nilai or "").strip()
        if len(nilai) < 2:
            raise ValueError("Nama minimal 2 karakter.")
        self.__nama = nilai

    @property
    def email(self):
        return self.__email

    @email.setter
    def email(self, nilai):
        nilai = (nilai or "").strip().lower()
        bagian = nilai.split("@")
        if len(bagian) != 2 or not bagian[0] or "." not in bagian[1]:
            raise ValueError("Format email tidak valid.")
        self.__email = nilai

    # Catatan: sengaja TIDAK ada getter publik untuk __password_hash.
    # Hash kata sandi dipakai di dalam class (oleh login()) dan hanya
    # diserahkan ke DatabaseManager saat akun disimpan (Encapsulation).
    def _hash_untuk_disimpan(self):
        """Protected: hanya dipakai DatabaseManager.tambah_akun()."""
        return self.__password_hash

    # ---- keamanan kata sandi ----
    @staticmethod
    def buat_hash(password, salt=None):
        """Menghasilkan 'salt$hash' memakai PBKDF2-HMAC-SHA256."""
        if password is None or len(password) < 6:
            raise ValueError("Kata sandi minimal 6 karakter.")
        salt = salt or os.urandom(16).hex()
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), 100_000
        ).hex()
        return f"{salt}${digest}"

    def login(self, password):
        """True bila kata sandi cocok."""
        salt, _, digest = self.__password_hash.partition("$")
        if not salt or not digest:
            return False
        try:
            cek = Akun.buat_hash(password, salt).partition("$")[2]
        except ValueError:
            return False
        return hmac.compare_digest(cek, digest)

    @abstractmethod
    def get_peran(self):
        """Polymorphism: tiap subclass mengembalikan peran berbeda."""

    def __str__(self):
        return f"{self.nama} <{self.email}> [{self.get_peran()}]"


# =====================================================================
# PROFIL GAMIFIKASI  (Encapsulation)
# =====================================================================
class ProfilGamifikasi:
    """Menyimpan XP, level, dan streak milik seorang mahasiswa."""

    def __init__(self, xp=0, level=1, streak=0, terakhir_aktif=None):
        self.__xp = xp
        self.__level = level
        self.__streak = streak
        self.__terakhir_aktif = terakhir_aktif   # objek date atau None

    @property
    def xp(self):
        return self.__xp

    @property
    def level(self):
        return self.__level

    @property
    def streak(self):
        return self.__streak

    @property
    def terakhir_aktif(self):
        return self.__terakhir_aktif

    def tambah_xp(self, jumlah):
        """Menambah XP; mengembalikan True bila naik level."""
        if jumlah < 0:
            raise ValueError("XP tidak boleh negatif.")
        self.__xp += jumlah
        return self.naik_level()

    def naik_level(self):
        level_baru = 1 + self.__xp // XP_PER_LEVEL
        if level_baru > self.__level:
            self.__level = level_baru
            return True
        return False

    def reset_streak(self):
        self.__streak = 0

    def perbarui_streak(self, tanggal):
        """
        Dipanggil saat ada aktivitas pada 'tanggal'.
        Mengembalikan True bila ini aktivitas pertama pada hari tsb
        (streak bertambah atau dimulai ulang), False bila sudah dihitung.
        """
        if self.__terakhir_aktif == tanggal:
            return False
        if self.__terakhir_aktif == tanggal - timedelta(days=1):
            self.__streak += 1
        else:
            self.__streak = 1
        self.__terakhir_aktif = tanggal
        return True

    def streak_saat_ini(self, hari_ini=None):
        """Streak yang masih berlaku (0 bila kemarin pun tidak aktif)."""
        hari_ini = hari_ini or date.today()
        if self.__terakhir_aktif is None:
            return 0
        if self.__terakhir_aktif >= hari_ini - timedelta(days=1):
            return self.__streak
        return 0


# =====================================================================
# LOG AKTIVITAS
# =====================================================================
class LogAktivitas:
    """Catatan satu kali penyelesaian kebiasaan."""

    def __init__(self, habit_id, tanggal, nilai, xp_didapat):
        self.__habit_id = habit_id
        self.__tanggal = tanggal
        self.__nilai = nilai
        self.__xp_didapat = xp_didapat

    @property
    def habit_id(self):
        return self.__habit_id

    @property
    def tanggal(self):
        return self.__tanggal

    @property
    def nilai(self):
        return self.__nilai

    @property
    def xp_didapat(self):
        return self.__xp_didapat

    def tambah_bonus(self, bonus):
        if bonus < 0:
            raise ValueError("Bonus tidak boleh negatif.")
        self.__xp_didapat += bonus

    def to_dict(self):
        return {
            "habit_id": self.__habit_id,
            "tanggal": self.__tanggal.isoformat(),
            "nilai": self.__nilai,
            "xp_didapat": self.__xp_didapat,
        }


# =====================================================================
# HABIT  (Abstract class + Inheritance + Polymorphism)
# =====================================================================
class Habit(ABC):
    """Kelas dasar kebiasaan belajar."""

    JENIS = "umum"
    NAMA_JENIS = "Umum"
    SATUAN = ""
    SEKALI_PER_HARI = False

    def __init__(self, id, nama, target_mingguan=5, logs=None):
        self.__id = id
        self.nama = nama
        self.target_mingguan = target_mingguan
        self.__logs = list(logs or [])     # composition: Habit memiliki LogAktivitas

    @property
    def id(self):
        return self.__id

    @property
    def logs(self):
        """LogAktivitas milik habit ini (hanya-baca), sesuai relasi composition."""
        return tuple(self.__logs)

    @property
    def nama(self):
        return self.__nama

    @nama.setter
    def nama(self, nilai):
        nilai = (nilai or "").strip()
        if len(nilai) < 3:
            raise ValueError("Nama kebiasaan minimal 3 karakter.")
        self.__nama = nilai

    @property
    def target_mingguan(self):
        return self.__target_mingguan

    @target_mingguan.setter
    def target_mingguan(self, nilai):
        if not isinstance(nilai, int) or not 1 <= nilai <= 7:
            raise ValueError("Target mingguan harus bilangan 1 sampai 7.")
        self.__target_mingguan = nilai

    # ---- method abstrak: wajib di-override ----
    @abstractmethod
    def hitung_xp(self, nilai):
        """Menghitung XP dasar dari 'nilai' yang diinput."""

    @abstractmethod
    def label_input(self):
        """Teks petunjuk input untuk GUI."""

    @abstractmethod
    def aturan_xp(self):
        """Penjelasan singkat aturan perolehan XP."""

    # ---- method konkret ----
    def validasi_nilai(self, nilai):
        if not isinstance(nilai, int) or nilai <= 0:
            raise ValueError("Nilai harus bilangan bulat positif.")

    def catat(self, nilai, tanggal=None):
        """
        Membuat LogAktivitas dari penyelesaian kebiasaan ini dan menyimpannya
        di dalam habit (composition). Kebiasaan checklist hanya boleh
        dicatat sekali per hari.
        """
        tanggal = tanggal or date.today()
        self.validasi_nilai(nilai)
        if self.SEKALI_PER_HARI and any(l.tanggal == tanggal for l in self.__logs):
            raise ValueError(f"Kebiasaan '{self.nama}' sudah dicatat selesai hari ini.")
        log = LogAktivitas(self.id, tanggal, nilai, self.hitung_xp(nilai))
        self.__logs.append(log)
        return log

    def __str__(self):
        return f"[{self.NAMA_JENIS}] {self.nama} (target {self.target_mingguan}x/minggu)"


class HabitBelajar(Habit):
    """Kebiasaan berbasis durasi (menit). 1 XP per 5 menit."""
    JENIS = "belajar"
    NAMA_JENIS = "Belajar (durasi)"
    SATUAN = "menit"

    def hitung_xp(self, menit):
        return menit // 5

    def validasi_nilai(self, nilai):
        super().validasi_nilai(nilai)
        if not 5 <= nilai <= 720:
            raise ValueError("Durasi belajar harus 5 sampai 720 menit.")

    def label_input(self):
        return "Berapa menit kamu belajar? (5-720)"

    def aturan_xp(self):
        return "1 XP setiap 5 menit"


class HabitHarian(Habit):
    """Kebiasaan checklist, cukup dicentang sekali per hari. 10 XP."""
    JENIS = "harian"
    NAMA_JENIS = "Harian (checklist)"
    SATUAN = "kali"
    SEKALI_PER_HARI = True

    def hitung_xp(self, nilai):
        return 10

    def validasi_nilai(self, nilai):
        super().validasi_nilai(nilai)
        if nilai != 1:
            raise ValueError("Kebiasaan harian hanya bernilai 1 (selesai).")

    def label_input(self):
        return "Tandai selesai untuk hari ini"

    def aturan_xp(self):
        return "10 XP per hari (sekali sehari)"


class HabitTargetJumlah(Habit):
    """Kebiasaan berbasis jumlah (soal, halaman, dll). 2 XP per unit."""
    JENIS = "jumlah"
    NAMA_JENIS = "Target jumlah"
    SATUAN = "unit"

    def hitung_xp(self, jumlah):
        return jumlah * 2

    def validasi_nilai(self, nilai):
        super().validasi_nilai(nilai)
        if nilai > 500:
            raise ValueError("Jumlah maksimal 500 per pencatatan.")

    def label_input(self):
        return "Berapa unit (soal/halaman) yang kamu selesaikan?"

    def aturan_xp(self):
        return "2 XP per unit"


# Registry jenis habit -> class (dipakai pola Factory)
JENIS_HABIT = {
    kls.JENIS: kls for kls in (HabitBelajar, HabitHarian, HabitTargetJumlah)
}


def buat_habit(jenis, nama, target_mingguan=5, id=None, logs=None):
    """Factory: membuat objek Habit yang sesuai dengan 'jenis'."""
    if jenis not in JENIS_HABIT:
        raise ValueError(f"Jenis kebiasaan tidak dikenal: {jenis}")
    return JENIS_HABIT[jenis](id, nama, target_mingguan, logs)


# =====================================================================
# BADGE  (Abstract class + Inheritance + Polymorphism)
# =====================================================================
class Badge(ABC):
    """Kelas dasar lencana (achievement)."""
    TIPE = "umum"
    NAMA_TIPE = "Umum"

    def __init__(self, id, nama, deskripsi, ambang):
        self.__id = id
        self.__nama = nama
        self.__deskripsi = deskripsi
        self.__ambang = ambang

    @property
    def id(self):
        return self.__id

    @property
    def nama(self):
        return self.__nama

    @property
    def deskripsi(self):
        return self.__deskripsi

    @property
    def ambang(self):
        return self.__ambang

    @abstractmethod
    def cek_syarat(self, profil):
        """True bila profil memenuhi syarat memperoleh lencana ini."""

    def __str__(self):
        return f"{self.nama} - {self.deskripsi}"


class BadgeStreak(Badge):
    TIPE = "streak"
    NAMA_TIPE = "Streak (hari beruntun)"

    def cek_syarat(self, profil):
        return profil.streak >= self.ambang


class BadgeXP(Badge):
    TIPE = "xp"
    NAMA_TIPE = "Total XP"

    def cek_syarat(self, profil):
        return profil.xp >= self.ambang


JENIS_BADGE = {kls.TIPE: kls for kls in (BadgeStreak, BadgeXP)}


def buat_badge(tipe, nama, deskripsi, ambang, id=None):
    """Factory untuk objek Badge."""
    if tipe not in JENIS_BADGE:
        raise ValueError(f"Tipe lencana tidak dikenal: {tipe}")
    if not isinstance(ambang, int) or ambang <= 0:
        raise ValueError("Ambang harus bilangan bulat positif.")
    if len((nama or "").strip()) < 3:
        raise ValueError("Nama lencana minimal 3 karakter.")
    return JENIS_BADGE[tipe](id, nama.strip(), (deskripsi or "").strip(), ambang)


# =====================================================================
# HASIL PENCATATAN
# =====================================================================
@dataclass
class HasilCatat:
    log: LogAktivitas
    xp_dasar: int
    bonus_streak: int
    naik_level: bool
    level_baru: int
    badge_baru: list = field(default_factory=list)

    @property
    def total_xp(self):
        return self.xp_dasar + self.bonus_streak


# =====================================================================
# MAHASISWA & ADMIN  (Inheritance dari Akun)
# =====================================================================
class Mahasiswa(Akun):
    """Pengguna utama: memiliki kebiasaan, profil gamifikasi, dan lencana."""

    def __init__(self, id, nama, email, password_hash,
                 profil=None, habits=None, id_badge=None):
        super().__init__(id, nama, email, password_hash)
        self.__profil = profil or ProfilGamifikasi()    # composition
        self.__habits = list(habits or [])              # aggregation
        self.__id_badge = set(id_badge or [])

    def get_peran(self):
        return "Mahasiswa"

    @property
    def profil(self):
        return self.__profil

    @property
    def habits(self):
        return tuple(self.__habits)

    @property
    def id_badge(self):
        return frozenset(self.__id_badge)

    @classmethod
    def daftar(cls, nama, email, password):
        """
        Membuat objek Mahasiswa baru dengan kata sandi yang sudah di-hash.
        Objek ini belum tersimpan; simpan dengan DatabaseManager.tambah_akun().
        Melempar ValueError bila nama/email/kata sandi tidak valid.
        """
        return cls(None, nama, email, cls.buat_hash(password))

    def tambah_habit(self, habit):
        self.__habits.append(habit)

    def ubah_habit(self, habit_id, nama, target_mingguan):
        """Memperbarui nama dan target mingguan kebiasaan di memori."""
        h = self.cari_habit(habit_id)
        if h is not None:
            h.nama = nama
            h.target_mingguan = target_mingguan
            return h
        return None

    def hapus_habit(self, habit_id):
        """Melepas habit dari daftar milik mahasiswa ini.
        Melempar ValueError bila habit bukan miliknya."""
        if self.cari_habit(habit_id) is None:
            raise ValueError("Kebiasaan tidak ditemukan.")
        self.__habits = [h for h in self.__habits if h.id != habit_id]

    def cari_habit(self, habit_id):
        for h in self.__habits:
            if h.id == habit_id:
                return h
        return None

    def catat_selesai(self, habit, nilai, tanggal=None, daftar_badge=()):
        """
        Mencatat penyelesaian 'habit'. Alur:
        1. habit.catat()  -> validasi + hitung XP (polymorphism)
        2. perbarui streak + bonus streak
        3. tambah XP & cek naik level
        4. cek lencana baru (polymorphism lewat Badge.cek_syarat)
        """
        tanggal = tanggal or date.today()
        log = habit.catat(nilai, tanggal)          # bisa melempar ValueError
        xp_dasar = log.xp_didapat

        streak_baru = self.__profil.perbarui_streak(tanggal)
        bonus = 0
        if streak_baru and self.__profil.streak >= 2:
            bonus = 2 * min(self.__profil.streak, MAKS_HARI_BONUS_STREAK)
            log.tambah_bonus(bonus)

        naik = self.__profil.tambah_xp(xp_dasar + bonus)

        baru = []
        for badge in daftar_badge:
            if badge.id not in self.__id_badge and badge.cek_syarat(self.__profil):
                self.__id_badge.add(badge.id)
                baru.append(badge)

        return HasilCatat(log, xp_dasar, bonus, naik, self.__profil.level, baru)


class Admin(Akun):
    """Pengelola aplikasi: mengelola akun dan master lencana."""

    def get_peran(self):
        return "Admin"

    def hapus_akun(self, db, akun_id):
        """Menghapus akun mahasiswa melalui DatabaseManager."""
        target = db.ambil_akun(akun_id)
        if target is None:
            raise ValueError("Akun tidak ditemukan.")
        if isinstance(target, Admin):
            raise ValueError("Akun Admin tidak boleh dihapus.")
        db.hapus_akun(akun_id)

    def tambah_badge(self, db, badge):
        """Menambah master lencana (objek BadgeStreak/BadgeXP) melalui
        DatabaseManager; mengembalikan id lencana baru."""
        if not isinstance(badge, Badge):
            raise ValueError("Lencana tidak valid.")
        return db.tambah_badge(badge)

    def hapus_badge(self, db, badge_id):
        """Menghapus master lencana melalui DatabaseManager."""
        return db.hapus_badge(badge_id)
