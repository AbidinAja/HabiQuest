"""
tests.py - Pengujian unit logika PBO, basis data, dan Class-Based Views Django.
Jalankan:  python tests.py
atau:      python manage.py test
"""
import os
import unittest
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
import django
django.setup()

from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware

from django.views import View

from models import (
    Akun, Mahasiswa, Admin, ProfilGamifikasi, Habit, LogAktivitas,
    HabitBelajar, HabitHarian, HabitTargetJumlah, buat_habit,
    Badge, BadgeStreak, BadgeXP, buat_badge,
)
from database import (
    DatabaseManager, ADMIN_EMAIL_DEFAULT, ADMIN_PASSWORD_DEFAULT,
)
from views import (
    LoginView, DashboardView, HabitView, LencanaView, AdminView,
)


def daftar_mhs(db, nama, email, password):
    """Registrasi sesuai class diagram: Mahasiswa.daftar() membuat objek,
    DatabaseManager.tambah_akun() menyimpannya, lalu dimuat ulang."""
    akun_id = db.tambah_akun(Mahasiswa.daftar(nama, email, password))
    return db.ambil_akun(akun_id)


class TestEncapsulationDanAkun(unittest.TestCase):
    def test_hash_dan_login(self):
        h = Akun.buat_hash("rahasia123")
        m = Mahasiswa(1, "Rina", "rina@mail.com", h)
        self.assertTrue(m.login("rahasia123"))
        self.assertFalse(m.login("salah"))
        # kata sandi asli tidak tersimpan di objek, hanya hash-nya
        self.assertNotIn("rahasia123", [str(v) for v in vars(m).values()])

    def test_validasi_setter(self):
        h = Akun.buat_hash("rahasia123")
        with self.assertRaises(ValueError):
            Mahasiswa(1, "R", "rina@mail.com", h)
        with self.assertRaises(ValueError):
            Mahasiswa(1, "Rina", "bukan-email", h)

    def test_xp_tidak_bisa_diubah_langsung(self):
        p = ProfilGamifikasi()
        with self.assertRaises(AttributeError):
            p.xp = 999
        with self.assertRaises(ValueError):
            p.tambah_xp(-5)

    def test_abstract_tidak_bisa_diinstansiasi(self):
        with self.assertRaises(TypeError):
            Akun(1, "A", "a@b.c", "x")
        with self.assertRaises(TypeError):
            Habit(1, "Baca", 5)


class TestPolymorphism(unittest.TestCase):
    def test_hitung_xp_berbeda_tiap_jenis(self):
        daftar = [
            HabitBelajar(1, "Baca jurnal"),
            HabitHarian(2, "Review catatan"),
            HabitTargetJumlah(3, "Latihan soal"),
        ]
        self.assertEqual([h.hitung_xp(30) for h in daftar], [6, 10, 60])

    def test_get_peran(self):
        h = Akun.buat_hash("rahasia123")
        self.assertEqual(Mahasiswa(1, "Rina", "r@m.com", h).get_peran(), "Mahasiswa")
        self.assertEqual(Admin(2, "Adm", "a@m.com", h).get_peran(), "Admin")

    def test_cek_syarat_badge(self):
        p = ProfilGamifikasi(xp=120, streak=3)
        self.assertTrue(BadgeXP(1, "x", "", 100).cek_syarat(p))
        self.assertFalse(BadgeXP(2, "x", "", 500).cek_syarat(p))
        self.assertTrue(BadgeStreak(3, "x", "", 3).cek_syarat(p))
        self.assertFalse(BadgeStreak(4, "x", "", 7).cek_syarat(p))

    def test_validasi_nilai(self):
        with self.assertRaises(ValueError):
            HabitBelajar(1, "Baca").catat(3)       # < 5 menit
        with self.assertRaises(ValueError):
            HabitHarian(1, "Review").catat(2)      # harus 1
        with self.assertRaises(ValueError):
            buat_habit("tidak-ada", "Baca")


class TestGamifikasi(unittest.TestCase):
    def setUp(self):
        self.mhs = Mahasiswa(1, "Rina", "rina@mail.com", Akun.buat_hash("rahasia123"))
        self.habit = HabitTargetJumlah(1, "Latihan soal")
        self.mhs.tambah_habit(self.habit)

    def test_naik_level(self):
        hasil = self.mhs.catat_selesai(self.habit, 50, date(2026, 1, 1))  # 100 XP
        self.assertTrue(hasil.naik_level)
        self.assertEqual(self.mhs.profil.level, 2)

    def test_streak_dan_bonus(self):
        t = date(2026, 1, 1)
        r1 = self.mhs.catat_selesai(self.habit, 1, t)
        self.assertEqual(r1.bonus_streak, 0)
        self.assertEqual(self.mhs.profil.streak, 1)
        r2 = self.mhs.catat_selesai(self.habit, 1, t + timedelta(days=1))
        self.assertEqual(self.mhs.profil.streak, 2)
        self.assertEqual(r2.bonus_streak, 4)
        # aktivitas kedua di hari yang sama: tidak ada bonus lagi
        r3 = self.mhs.catat_selesai(self.habit, 1, t + timedelta(days=1))
        self.assertEqual(r3.bonus_streak, 0)
        # lompat 3 hari: streak mulai dari 1
        self.mhs.catat_selesai(self.habit, 1, t + timedelta(days=5))
        self.assertEqual(self.mhs.profil.streak, 1)

    def test_badge_diberikan_sekali(self):
        badge = BadgeXP(10, "Langkah Pertama", "10 XP", 10)
        r1 = self.mhs.catat_selesai(self.habit, 5, date(2026, 1, 1), [badge])
        self.assertEqual([b.id for b in r1.badge_baru], [10])
        r2 = self.mhs.catat_selesai(self.habit, 5, date(2026, 1, 1), [badge])
        self.assertEqual(r2.badge_baru, [])

    def test_streak_kadaluarsa(self):
        p = ProfilGamifikasi()
        p.perbarui_streak(date(2026, 1, 1))
        self.assertEqual(p.streak_saat_ini(date(2026, 1, 2)), 1)
        self.assertEqual(p.streak_saat_ini(date(2026, 1, 5)), 0)


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(":memory:")

    def tearDown(self):
        self.db.tutup()

    def test_seed_admin_dan_badge(self):
        admin = self.db.ambil_akun(email=ADMIN_EMAIL_DEFAULT)
        self.assertIsInstance(admin, Admin)
        self.assertTrue(admin.login(ADMIN_PASSWORD_DEFAULT))
        self.assertGreaterEqual(len(self.db.daftar_badge()), 6)

    def test_registrasi_dan_email_ganda(self):
        m = daftar_mhs(self.db, "Rina", "Rina@Mail.com", "rahasia123")
        self.assertIsInstance(m, Mahasiswa)
        self.assertEqual(m.email, "rina@mail.com")
        self.assertTrue(self.db.email_terdaftar("rina@mail.com"))
        with self.assertRaises(ValueError):
            daftar_mhs(self.db, "Rina 2", "rina@mail.com", "rahasia123")
        with self.assertRaises(ValueError):
            daftar_mhs(self.db, "Budi", "budi@mail.com", "123")

    def test_method_proposal_class_mahasiswa_dan_admin(self):
        # Mahasiswa.daftar (classmethod)
        m = Mahasiswa.daftar("Zaenal", "zaenal@mail.com", "zaenal123")
        self.assertIsInstance(m, Mahasiswa)
        self.assertIsNone(m.id)                       # belum tersimpan
        akun_id = self.db.tambah_akun(m)              # tambah_akun(akun) : int
        self.assertIsInstance(akun_id, int)
        m = self.db.ambil_akun(akun_id)
        h = self.db.tambah_habit(m, "belajar", "Baca Buku PBO", 5)
        # Mahasiswa.ubah_habit
        m.ubah_habit(h.id, "Baca Buku PBO Lanjutan", 6)
        self.assertEqual(h.nama, "Baca Buku PBO Lanjutan")
        self.assertEqual(h.target_mingguan, 6)

        # Admin.tambah_badge dan hapus_badge
        admin = self.db.ambil_akun(email=ADMIN_EMAIL_DEFAULT)
        admin.tambah_badge(self.db, BadgeStreak(None, "Super Disiplin", "Streak 14 hari", 14))
        badges = self.db.daftar_badge()
        super_badge = [b for b in badges if b.nama == "Super Disiplin"][0]
        self.assertIsNotNone(super_badge)
        admin.hapus_badge(self.db, super_badge.id)
        badges_after = self.db.daftar_badge()
        self.assertNotIn(super_badge.id, [b.id for b in badges_after])

    def test_alur_lengkap_persisten(self):
        m = daftar_mhs(self.db, "Rina", "rina@mail.com", "rahasia123")
        h = self.db.tambah_habit(m, "jumlah", "Latihan soal", 5)
        hasil = m.catat_selesai(h, 10, date.today(), self.db.daftar_badge())
        self.db.simpan_hasil_catat(m, hasil)

        m2 = self.db.ambil_akun(m.id)          # muat ulang dari database
        self.assertEqual(m2.profil.xp, 20)
        self.assertEqual(m2.profil.streak, 1)
        self.assertEqual(len(m2.habits), 1)
        self.assertIsInstance(m2.habits[0], HabitTargetJumlah)
        log = m2.habits[0].logs                 # composition Habit-LogAktivitas
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0].tanggal, date.today())
        self.assertEqual(log[0].nilai, 10)
        self.assertGreaterEqual(len(m2.id_badge), 1)   # "Langkah Pertama"
        grafik = self.db.xp_harian(m.id, 7)
        self.assertEqual(len(grafik), 7)
        self.assertEqual(grafik[-1][1], 20)
        self.assertEqual(log[0].to_dict()["xp_didapat"], 20)

    def test_hapus_habit_dan_admin(self):
        m = daftar_mhs(self.db, "Rina", "rina@mail.com", "rahasia123")
        h = self.db.tambah_habit(m, "harian", "Review catatan", 3)
        m.hapus_habit(h.id)
        self.db.hapus_habit(h.id)
        self.assertEqual(len(m.habits), 0)
        self.assertEqual(len(self.db.ambil_akun(m.id).habits), 0)

        admin = self.db.ambil_akun(email=ADMIN_EMAIL_DEFAULT)
        with self.assertRaises(ValueError):
            admin.hapus_akun(self.db, admin.id)     # admin tidak boleh dihapus
        admin.hapus_akun(self.db, m.id)
        self.assertIsNone(self.db.ambil_akun(m.id))


class TestDjangoViews(unittest.TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        # Pakai database in-memory atau file test
        from django.conf import settings
        self.db = DatabaseManager(settings.HABIQUEST_DB_PATH)

    def _tambah_session_dan_messages(self, req):
        """Helper untuk memasang session dan messages middleware pada request dummy."""
        middleware_session = SessionMiddleware(lambda r: None)
        middleware_session.process_request(req)
        req.session.save()
        middleware_msg = MessageMiddleware(lambda r: None)
        middleware_msg.process_request(req)

    def test_login_view_get(self):
        req = self.factory.get('/login/')
        self._tambah_session_dan_messages(req)
        view = LoginView.as_view()
        resp = view(req)
        self.assertEqual(resp.status_code, 200)

    def test_login_polymorphic_redirect(self):
        # 1. Admin login -> redirect ke admin-panel
        req = self.factory.post('/login/', {
            'action': 'login',
            'email': ADMIN_EMAIL_DEFAULT,
            'password': ADMIN_PASSWORD_DEFAULT,
        })
        self._tambah_session_dan_messages(req)
        resp = LoginView.as_view()(req)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/admin-panel/')

        # 2. Mahasiswa login -> redirect ke dashboard
        test_email = "test_view_mhs@habiquest.local"
        if not self.db.email_terdaftar(test_email):
            daftar_mhs(self.db, "Test Mhs", test_email, "mhs12345")
        req_mhs = self.factory.post('/login/', {
            'action': 'login',
            'email': test_email,
            'password': "mhs12345",
        })
        self._tambah_session_dan_messages(req_mhs)
        resp_mhs = LoginView.as_view()(req_mhs)
        self.assertEqual(resp_mhs.status_code, 302)
        self.assertEqual(resp_mhs.url, '/dashboard/')

    def test_dashboard_view_mahasiswa(self):
        test_email = "test_dash@habiquest.local"
        mhs = self.db.ambil_akun(email=test_email)
        if not mhs:
            mhs = daftar_mhs(self.db, "Dashboard Tester", test_email, "pass123")

        req = self.factory.get('/dashboard/')
        self._tambah_session_dan_messages(req)
        req.session['akun_id'] = mhs.id
        resp = DashboardView.as_view()(req)
        self.assertEqual(resp.status_code, 200)

    def test_habits_crud_view(self):
        test_email = "test_crud@habiquest.local"
        mhs = self.db.ambil_akun(email=test_email)
        if not mhs:
            mhs = daftar_mhs(self.db, "CRUD Tester", test_email, "pass123")

        # GET habits
        req = self.factory.get('/habits/')
        self._tambah_session_dan_messages(req)
        req.session['akun_id'] = mhs.id
        resp = HabitView.as_view()(req)
        self.assertEqual(resp.status_code, 200)

        # POST tambah habit
        req_add = self.factory.post('/habits/', {
            'action': 'tambah',
            'nama': 'Membaca Dokumentasi',
            'jenis': 'belajar',
            'target_mingguan': '4',
        })
        self._tambah_session_dan_messages(req_add)
        req_add.session['akun_id'] = mhs.id
        resp_add = HabitView.as_view()(req_add)
        self.assertEqual(resp_add.status_code, 302)

    def test_lencana_view(self):
        test_email = "test_lencana@habiquest.local"
        mhs = self.db.ambil_akun(email=test_email)
        if not mhs:
            mhs = daftar_mhs(self.db, "Lencana Tester", test_email, "pass123")

        req = self.factory.get('/lencana/')
        self._tambah_session_dan_messages(req)
        req.session['akun_id'] = mhs.id
        resp = LencanaView.as_view()(req)
        self.assertEqual(resp.status_code, 200)

    def test_admin_view(self):
        admin = self.db.ambil_akun(email=ADMIN_EMAIL_DEFAULT)
        req = self.factory.get('/admin-panel/')
        self._tambah_session_dan_messages(req)
        req.session['akun_id'] = admin.id
        resp = AdminView.as_view()(req)
        self.assertEqual(resp.status_code, 200)

    def test_admin_panel_punya_tombol_keluar(self):
        admin = self.db.ambil_akun(email=ADMIN_EMAIL_DEFAULT)
        req = self.factory.get('/admin-panel/')
        self._tambah_session_dan_messages(req)
        req.session['akun_id'] = admin.id
        html = AdminView.as_view()(req).content.decode()
        self.assertIn('href="/logout/"', html)       # tombol Keluar tampil
        self.assertIn('Master Lencana', html)        # menu tab admin tampil


class TestAkunDanDatabaseManager(unittest.TestCase):
    """Pengujian bagian Akun, autentikasi, dan DatabaseManager (Laila)."""

    def setUp(self):
        self.db = DatabaseManager(":memory:")
        self.rina = daftar_mhs(self.db, "Rina", "rina@mail.com", "rahasia123")
        self.budi = daftar_mhs(self.db, "Budi", "budi@mail.com", "rahasia123")

    def tearDown(self):
        self.db.tutup()

    def test_password_hash_tidak_bisa_dibaca_dari_luar(self):
        self.assertFalse(hasattr(self.rina, "password_hash"))
        with self.assertRaises(AttributeError):
            self.rina.__password_hash
        self.assertTrue(self.rina.login("rahasia123"))   # tetap bisa login

    def test_hapus_habit_milik_orang_lain_ditolak(self):
        h = self.db.tambah_habit(self.rina, "belajar", "Baca jurnal", 5)
        with self.assertRaises(ValueError):
            self.budi.hapus_habit(h.id)                   # bukan milik Budi
        self.rina.hapus_habit(h.id)                       # pemilik boleh
        self.db.hapus_habit(h.id)
        self.assertEqual(len(self.db.ambil_akun(self.rina.id).habits), 0)

    def test_ubah_habit_milik_orang_lain_ditolak(self):
        h = self.db.tambah_habit(self.rina, "jumlah", "Latihan soal", 5)
        self.assertIsNone(self.budi.ubah_habit(h.id, "Diubah Budi", 5))
        self.assertEqual(self.db.ambil_akun(self.rina.id).habits[0].nama, "Latihan soal")
        h2 = self.rina.ubah_habit(h.id, "Latihan soal lanjutan", 6)   # pemilik boleh
        self.db.ubah_habit(h2)                            # ubah_habit(habit)
        self.assertEqual(self.db.ambil_akun(self.rina.id).habits[0].nama, "Latihan soal lanjutan")

    def test_tambah_akun_menolak_email_ganda(self):
        with self.assertRaises(ValueError):
            self.db.tambah_akun(Mahasiswa.daftar("Rina Lain", "rina@mail.com", "rahasia123"))

    def test_daftar_mahasiswa_mengembalikan_semua_mahasiswa(self):
        daftar = self.db.daftar_mahasiswa()
        self.assertEqual([m.nama for m in daftar], ["Rina", "Budi"])   # admin tidak ikut
        self.assertTrue(all(isinstance(m, Mahasiswa) for m in daftar))

    def test_tambah_badge_mengembalikan_id(self):
        admin = self.db.ambil_akun(email=ADMIN_EMAIL_DEFAULT)
        badge_id = admin.tambah_badge(self.db, BadgeXP(None, "Seribu XP", "Kumpulkan 1000 XP", 1000))
        self.assertIsInstance(badge_id, int)
        self.assertIn(badge_id, [b.id for b in self.db.daftar_badge()])

    def test_context_manager_menutup_koneksi(self):
        import sqlite3
        with DatabaseManager(":memory:") as db:
            self.assertIsNotNone(db.ambil_akun(email=ADMIN_EMAIL_DEFAULT))
        with self.assertRaises(sqlite3.ProgrammingError):  # koneksi sudah ditutup
            db.daftar_badge()
        db.tutup()                                        # aman dipanggil dua kali


class TestSesuaiLaporan(unittest.TestCase):
    """Isi publik setiap class harus sama dengan tabel 3.2 & tabel 3.1 laporan."""

    LAPORAN = {
        Akun: "id nama email login buat_hash get_peran",
        Mahasiswa: "profil habits id_badge daftar tambah_habit ubah_habit hapus_habit "
                   "cari_habit catat_selesai get_peran",
        Admin: "hapus_akun tambah_badge hapus_badge get_peran",
        ProfilGamifikasi: "xp level streak terakhir_aktif tambah_xp naik_level "
                          "perbarui_streak reset_streak streak_saat_ini",
        Habit: "id nama target_mingguan logs hitung_xp label_input aturan_xp "
               "validasi_nilai catat",
        LogAktivitas: "habit_id tanggal nilai xp_didapat tambah_bonus to_dict",
        Badge: "id nama deskripsi ambang cek_syarat",
        DatabaseManager: "daftar_mahasiswa ambil_akun email_terdaftar tambah_akun "
                         "hapus_akun tambah_habit ubah_habit hapus_habit "
                         "simpan_hasil_catat xp_harian daftar_badge tambah_badge "
                         "hapus_badge tutup",
    }

    def test_member_publik_sama_dengan_laporan(self):
        for cls, isi in self.LAPORAN.items():
            publik = {n for n in vars(cls)            # member milik class itu sendiri
                      if not n.startswith("_") and not n.isupper()}   # KONSTANTA kelas dikecualikan
            with self.subTest(cls=cls.__name__):
                self.assertEqual(publik, set(isi.split()))

    def test_view_sesuai_tabel_3_1(self):
        import views
        nama_view = {n for n, o in vars(views).items()
                     if isinstance(o, type) and issubclass(o, View) and o is not View}
        self.assertEqual(nama_view, {"LoginView", "DashboardView", "HabitView",
                                     "LencanaView", "AdminView"})

    def test_kebiasaan_harian_hanya_sekali_sehari(self):
        h = HabitHarian(1, "Review catatan", 7)
        h.catat(1, date(2026, 11, 24))
        with self.assertRaises(ValueError):
            h.catat(1, date(2026, 11, 24))
        self.assertEqual(len(h.logs), 1)

    def test_logout_dan_halaman_utama_lewat_loginview(self):
        from django.test import Client
        c = Client()
        self.assertEqual(c.get("/").status_code, 200)            # belum login: halaman login
        r = c.get("/logout/")
        self.assertEqual((r.status_code, r["Location"]), (302, "/login/"))


class TestKeamananHabitView(unittest.TestCase):
    """Mahasiswa tidak boleh menghapus kebiasaan milik mahasiswa lain lewat web."""

    def setUp(self):
        import uuid
        from django.conf import settings
        self.factory = RequestFactory()
        self.db = DatabaseManager(settings.HABIQUEST_DB_PATH)
        kode = uuid.uuid4().hex[:8]
        self.pemilik = daftar_mhs(self.db, "Pemilik", f"pemilik_{kode}@habiquest.local", "pass123")
        self.penyusup = daftar_mhs(self.db, "Penyusup", f"penyusup_{kode}@habiquest.local", "pass123")
        self.habit = self.db.tambah_habit(self.pemilik, "harian", "Review catatan", 5)

    def tearDown(self):
        self.db.hapus_akun(self.pemilik.id)
        self.db.hapus_akun(self.penyusup.id)
        self.db.tutup()

    def test_hapus_habit_orang_lain_lewat_view(self):
        req = self.factory.post('/habits/', {'action': 'hapus', 'habit_id': self.habit.id})
        SessionMiddleware(lambda r: None).process_request(req)
        req.session.save()
        MessageMiddleware(lambda r: None).process_request(req)
        req.session['akun_id'] = self.penyusup.id
        HabitView.as_view()(req)
        pemilik = self.db.ambil_akun(self.pemilik.id)
        self.assertEqual([h.nama for h in pemilik.habits], ["Review catatan"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
