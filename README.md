# HabiQuest: Aplikasi Pelacak Kebiasaan Belajar Berbasis Gamifikasi

Proyek Tugas Akhir Mata Kuliah **Pemrograman Berorientasi Obyek (IF 7D)**  
**Program Studi Teknik Informatika — Universitas Trunojoyo Madura (2026)**

---

## 👥 Tim Penyusun
- **Laila Maghfiroh** (240411100006) — Class Akun, Mahasiswa, Admin; Autentikasi; DatabaseManager (`models.py`, `database.py`)
- **Aisyah Salsabilah** (240411100029) — Class Habit dan turunannya, LogAktivitas, ProfilGamifikasi, Logika XP & Streak (`models.py`)
- **Mochammad Zaenal Abidin** (240411100131) — Class Badge, Antarmuka Web Django (CBVs, URLs, Templates HTML/CSS), Pengujian & Dokumentasi (`views.py`, `urls.py`, `templates/`, `tests.py`)

**Dosen Pengampu:** Ach. Khozaimi, S.Kom., M.Kom.

---

## 🚀 Fitur Utama Sesuai Proposal
1. **Autentikasi & Otorisasi Pengguna (KF-01):**
   - Registrasi dan login mahasiswa dengan kata sandi ber-hash PBKDF2-HMAC-SHA256 + salt acak.
   - Akun Admin bawaan untuk pengelolaan sistem.
   - *Polymorphic Redirection* pada `LoginView` (mengarahkan otomatis ke Dashboard Mahasiswa atau Panel Admin sesuai jenis class objek akun).

2. **Manajemen Kebiasaan Belajar (KF-02):**
   - 3 jenis kebiasaan belajar berbasis class inheritance:
     - **Belajar (durasi):** 1 XP setiap 5 menit (durasi 5 - 720 menit).
     - **Harian (checklist):** 10 XP per hari (dicatat sekali per hari).
     - **Target Jumlah:** 2 XP per unit (maksimal 500 unit per pencatatan).
   - CRUD kebiasaan: Tambah, Ubah nama & target mingguan (jenis bersifat immutable karena mencerminkan tipe class), dan Hapus.

3. **Gamifikasi & Pencatatan Progres (KF-03, KF-04, KF-05):**
   - Perhitungan XP dasar, kenaikan Level otomatis (setiap 100 XP), dan Streak hari beruntun.
   - Bonus Streak harian: `2 * min(streak, 7)` XP pada aktivitas pertama setiap hari mulai streak hari ke-2.
   - Pembagian Lencana (*achievement*) otomatis berdasarkan pencapaian Streak dan akumulasi Total XP.

4. **Visualisasi Statistik & Riwayat 7 Hari (KF-06):**
   - Grafik batang interaktif XP 7 hari terakhir (highlight hari ini).
   - Tabel riwayat aktivitas penyelesaian belajar lengkap dengan XP yang diperoleh.

5. **Panel Admin (KF-07):**
   - Manajemen akun pengguna: melihat daftar mahasiswa, level, total XP, dan opsi hapus akun.
   - Master lencana: menambah lencana baru (tipe streak / XP) dan menghapus lencana.

---

## 🏛️ Penerapan Konsep PBO

| Konsep PBO | Penerapan dalam Proyek |
|---|---|
| **Abstraction** | Class abstrak `Akun`, `Habit`, dan `Badge` menggunakan modul `abc` (`ABC`, `@abstractmethod`). |
| **Encapsulation** | Atribut sensitif dibuat privat (`__id`, `__xp`, `__password_hash`, dsb.) dan diakses melalui `@property` serta setter dengan validasi ketat. |
| **Inheritance** | `Mahasiswa` & `Admin` mewarisi `Akun`; `HabitBelajar`, `HabitHarian`, `HabitTargetJumlah` mewarisi `Habit`; `BadgeStreak`, `BadgeXP` mewarisi `Badge`. |
| **Polymorphism** | Method `hitung_xp()`, `cek_syarat()`, dan `get_peran()` di-override oleh masing-masing subclass. Pengalihan rute pada `LoginView` menyesuaikan tipe akun runtime. |
| **Separation of Concerns** | `DatabaseManager` menjadi satu-satunya class penghubung ke SQLite, menjaga domain logic tetap bersih dari sintaks SQL. |

---

## 🛠️ Kebutuhan Sistem & Teknologi
- **Bahasa Pemrograman:** Python 3.10+ (atau Python 3.13)
- **Web Framework:** Django 5.1+ (menggunakan arsitektur MVT & Class-Based Views)
- **Basis Data:** SQLite melalui modul standar `sqlite3`
- **Keamanan:** Modul `hashlib` & `hmac` (PBKDF2-HMAC-SHA256)
- **Pengujian:** Modul `unittest` bawaan Python & Django Test Client

---

## 💻 Cara Menjalankan Aplikasi

### 1. Instalasi Dependensi
Pastikan Python 3.10+ sudah terpasang, lalu pasang dependensi proyek:
```bash
pip install -r requirements.txt
```

### 2. Menjalankan Web Server Django
Jalankan perintah berikut pada terminal:
```bash
python main.py
```
atau menggunakan perintah standar Django:
```bash
python manage.py runserver
```
Buka browser dan akses: **`http://127.0.0.1:8000/`**

### 3. Akun Pengguna Bawaan
- **Admin:**
  - Email: `admin@habiquest.local`
  - Kata Sandi: `admin123`
- **Mahasiswa:**
  - Buat akun baru langsung melalui tab **Daftar** pada halaman Login.

### 4. Menjalankan Pengujian Unit (Unit Tests)
Jalankan seluruh pengujian (logika PBO, enkapsulasi, polimorfisme, gamifikasi, basis data, dan Django CBVs):
```bash
python tests.py
```
atau:
```bash
python manage.py test
```

---

## 📁 Struktur Direktori
```text
Tugas Akhir/
├── habiquest.db        # Basis data SQLite lokal
├── database.py         # DatabaseManager (koneksi & manipulasi SQLite)
├── models.py           # Class Domain PBO (Akun, Habit, Badge, Profil, Log)
├── views.py            # Class-Based Views Django (Login, Dashboard, Habit, Lencana, Admin)
├── urls.py             # Pemetaan rute URL aplikasi
├── settings.py         # Konfigurasi Django
├── manage.py           # Skrip utilitas CLI Django
├── main.py             # Titik masuk utama menjalankan web server
├── tests.py            # Pengujian unit komprehensif
├── requirements.txt    # Seluruh dependensi proyek (lengkap)
├── templates/          # Template antarmuka HTML responsif
│   ├── base.html       # Kerangka dasar (header, navbar, footer, flash message)
│   ├── login.html      # Halaman Masuk & Daftar (Sketsa 1)
│   ├── dashboard.html  # Dashboard utama mahasiswa & catat selesai (Sketsa 2)
│   ├── habits.html     # CRUD kebiasaan belajar (Sketsa 3)
│   ├── lencana.html    # Koleksi lencana & grafik 7 hari (Sketsa 4)
│   └── admin.html      # Panel kelola pengguna & master lencana
├── static/             # File statis
│   └── css/
│       └── style.css   # Stylesheet CSS kustom responsif
└── README.md           # Dokumentasi proyek
```
