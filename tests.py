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

from models import (
    Akun, Mahasiswa, Admin, ProfilGamifikasi, Habit,
    HabitBelajar, HabitHarian, HabitTargetJumlah, buat_habit,
    BadgeStreak, BadgeXP, buat_badge,
)
from database import (
    DatabaseManager, ADMIN_EMAIL_DEFAULT, ADMIN_PASSWORD_DEFAULT,
)
from views import (
    LoginView, DashboardView, HabitView, LencanaView, AdminView,
)


class TestEncapsulationDanAkun(unittest.TestCase):
    def test_hash_dan_login(self):
        h = Akun.buat_hash("rahasia123")
        m = Mahasiswa(1, "Rina", "rina@mail.com", h)
        self.assertTrue(m.login("rahasia123"))
        self.assertFalse(m.login("salah"))
        self.assertNotIn("rahasia123", m.password_hash)

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
        admin = self.db.ambil_akun_by_email(ADMIN_EMAIL_DEFAULT)
        self.assertIsInstance(admin, Admin)
        self.assertTrue(admin.login(ADMIN_PASSWORD_DEFAULT))
        self.assertGreaterEqual(len(self.db.daftar_badge()), 6)

    def test_registrasi_dan_email_ganda(self):
        m = self.db.daftar_mahasiswa("Rina", "Rina@Mail.com", "rahasia123")
        self.assertIsInstance(m, Mahasiswa)
        self.assertEqual(m.email, "rina@mail.com")
        self.assertTrue(self.db.email_terdaftar("rina@mail.com"))
        with self.assertRaises(ValueError):
            self.db.daftar_mahasiswa("Rina 2", "rina@mail.com", "rahasia123")
        with self.assertRaises(ValueError):
            self.db.daftar_mahasiswa("Budi", "budi@mail.com", "123")

    def test_method_proposal_class_mahasiswa_dan_admin(self):
        # Mahasiswa.daftar (classmethod)
        m = Mahasiswa.daftar(self.db, "Zaenal", "zaenal@mail.com", "zaenal123")
        self.assertIsInstance(m, Mahasiswa)
        h = self.db.tambah_habit(m, "belajar", "Baca Buku PBO", 5)
        # Mahasiswa.ubah_habit
        m.ubah_habit(h.id, "Baca Buku PBO Lanjutan", 6)
        self.assertEqual(h.nama, "Baca Buku PBO Lanjutan")
        self.assertEqual(h.target_mingguan, 6)

        # Admin.tambah_badge dan hapus_badge
        admin = self.db.ambil_akun_by_email(ADMIN_EMAIL_DEFAULT)
        admin.tambah_badge(self.db, "streak", "Super Disiplin", "Streak 14 hari", 14)
        badges = self.db.daftar_badge()
        super_badge = [b for b in badges if b.nama == "Super Disiplin"][0]
        self.assertIsNotNone(super_badge)
        admin.hapus_badge(self.db, super_badge.id)
        badges_after = self.db.daftar_badge()
        self.assertNotIn(super_badge.id, [b.id for b in badges_after])

    def test_alur_lengkap_persisten(self):
        m = self.db.daftar_mahasiswa("Rina", "rina@mail.com", "rahasia123")
        h = self.db.tambah_habit(m, "jumlah", "Latihan soal", 5)
        hasil = m.catat_selesai(h, 10, date.today(), self.db.daftar_badge())
        self.db.simpan_hasil_catat(m, hasil)

        m2 = self.db.ambil_akun(m.id)          # muat ulang dari database
        self.assertEqual(m2.profil.xp, 20)
        self.assertEqual(m2.profil.streak, 1)
        self.assertEqual(len(m2.habits), 1)
        self.assertIsInstance(m2.habits[0], HabitTargetJumlah)
        self.assertTrue(self.db.sudah_dicatat(h.id, date.today()))
        self.assertEqual(self.db.total_nilai_hari(h.id, date.today()), 10)
        self.assertEqual(self.db.hari_aktif_7_hari(h.id), 1)
        self.assertGreaterEqual(len(m2.id_badge), 1)   # "Langkah Pertama"
        grafik = self.db.xp_harian(m.id, 7)
        self.assertEqual(len(grafik), 7)
        self.assertEqual(grafik[-1][1], 20)
        self.assertEqual(len(self.db.riwayat(m.id)), 1)

    def test_hapus_habit_dan_admin(self):
        m = self.db.daftar_mahasiswa("Rina", "rina@mail.com", "rahasia123")
        h = self.db.tambah_habit(m, "harian", "Review catatan", 3)
        self.db.hapus_habit(m, h.id)
        self.assertEqual(len(m.habits), 0)

        admin = self.db.ambil_akun_by_email(ADMIN_EMAIL_DEFAULT)
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
            self.db.daftar_mahasiswa("Test Mhs", test_email, "mhs12345")
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
        mhs = self.db.ambil_akun_by_email(test_email)
        if not mhs:
            mhs = self.db.daftar_mahasiswa("Dashboard Tester", test_email, "pass123")

        req = self.factory.get('/dashboard/')
        self._tambah_session_dan_messages(req)
        req.session['akun_id'] = mhs.id
        resp = DashboardView.as_view()(req)
        self.assertEqual(resp.status_code, 200)

    def test_habits_crud_view(self):
        test_email = "test_crud@habiquest.local"
        mhs = self.db.ambil_akun_by_email(test_email)
        if not mhs:
            mhs = self.db.daftar_mahasiswa("CRUD Tester", test_email, "pass123")

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
        mhs = self.db.ambil_akun_by_email(test_email)
        if not mhs:
            mhs = self.db.daftar_mahasiswa("Lencana Tester", test_email, "pass123")

        req = self.factory.get('/lencana/')
        self._tambah_session_dan_messages(req)
        req.session['akun_id'] = mhs.id
        resp = LencanaView.as_view()(req)
        self.assertEqual(resp.status_code, 200)

    def test_admin_view(self):
        admin = self.db.ambil_akun_by_email(ADMIN_EMAIL_DEFAULT)
        req = self.factory.get('/admin-panel/')
        self._tambah_session_dan_messages(req)
        req.session['akun_id'] = admin.id
        resp = AdminView.as_view()(req)
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
