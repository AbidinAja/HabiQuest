"""
views.py
========
Class-Based Views (CBVs) untuk antarmuka web Django aplikasi HabiQuest.

Sesuai rancangan pada Proposal Bab III & IV:
  - LoginView      : autentikasi & registrasi (polymorphic redirection)
  - DashboardView  : pencatatan aktivitas, progress XP, level, streak
  - HabitView      : CRUD kebiasaan belajar (3 jenis habit)
  - LencanaView    : koleksi achievement & grafik statistik 7 hari
  - AdminView      : kelola pengguna dan master lencana
"""
from datetime import date
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from database import DatabaseManager, ADMIN_EMAIL_DEFAULT
from models import (
    Admin,
    Mahasiswa,
    JENIS_HABIT,
    XP_PER_LEVEL,
)


def get_db():
    """Mengembalikan koneksi DatabaseManager ke basis data SQLite."""
    db_path = getattr(settings, 'HABIQUEST_DB_PATH', 'habiquest.db')
    return DatabaseManager(db_path)


def get_akun_login(request, db):
    """Mengambil objek Akun (Mahasiswa atau Admin) yang tersimpan di sesi."""
    akun_id = request.session.get('akun_id')
    if not akun_id:
        return None
    return db.ambil_akun(akun_id)


# =====================================================================
# REDIREKSI HALAMAN UTAMA
# =====================================================================
class HomeRedirectView(View):
    def get(self, request):
        db = get_db()
        akun = get_akun_login(request, db)
        if akun is None:
            return redirect('login')
        if isinstance(akun, Admin):
            return redirect('admin_panel')
        return redirect('dashboard')


# =====================================================================
# LOGIN & REGISTRASI (Polymorphic Redirect)
# =====================================================================
class LoginView(View):
    template_name = 'login.html'

    def get(self, request):
        db = get_db()
        akun = get_akun_login(request, db)
        if akun is not None:
            # Polymorphism: arahkan ke dashboard Admin atau Mahasiswa
            if isinstance(akun, Admin):
                return redirect('admin_panel')
            return redirect('dashboard')

        tab = request.GET.get('tab', 'masuk')
        return render(request, self.template_name, {
            'tab_aktif': tab,
            'admin_email': ADMIN_EMAIL_DEFAULT,
        })

    def post(self, request):
        action = request.POST.get('action', 'login')
        db = get_db()

        if action == 'login':
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')

            akun = db.ambil_akun_by_email(email)
            if akun is None or not akun.login(password):
                messages.error(request, 'Email atau kata sandi salah.')
                return render(request, self.template_name, {
                    'tab_aktif': 'masuk',
                    'email_masuk': email,
                    'admin_email': ADMIN_EMAIL_DEFAULT,
                })

            # Simpan ID akun ke sesi Django
            request.session['akun_id'] = akun.id

            # Polymorphism: LoginView mengarahkan rute sesuai jenis objek akun
            if isinstance(akun, Admin):
                return redirect('admin_panel')
            return redirect('dashboard')

        elif action == 'register':
            nama = request.POST.get('nama', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')

            try:
                # Memanfaatkan classmethod Mahasiswa.daftar
                mhs = Mahasiswa.daftar(db, nama, email, password)
                request.session['akun_id'] = mhs.id
                messages.success(request, f'Selamat datang, {mhs.nama}! Akun Anda berhasil dibuat.')
                return redirect('dashboard')
            except ValueError as e:
                messages.error(request, str(e))
                return render(request, self.template_name, {
                    'tab_aktif': 'daftar',
                    'nama_daftar': nama,
                    'email_daftar': email,
                    'admin_email': ADMIN_EMAIL_DEFAULT,
                })

        return redirect('login')


# =====================================================================
# LOGOUT
# =====================================================================
class LogoutView(View):
    def get(self, request):
        request.session.flush()
        return redirect('login')

    def post(self, request):
        request.session.flush()
        return redirect('login')


# =====================================================================
# DASHBOARD MAHASISWA
# =====================================================================
class DashboardView(View):
    template_name = 'dashboard.html'

    def get(self, request):
        db = get_db()
        akun = get_akun_login(request, db)
        if akun is None:
            return redirect('login')
        if isinstance(akun, Admin):
            return redirect('admin_panel')

        hari_ini = date.today()
        habits_tampilan = []
        for h in akun.habits:
            sudah = db.sudah_dicatat(h.id, hari_ini)
            total_hari = db.total_nilai_hari(h.id, hari_ini)
            hari_aktif = db.hari_aktif_7_hari(h.id, hari_ini)

            if h.JENIS == 'belajar':
                status_hari_ini = f'{total_hari} menit' if sudah else 'Belum'
            elif h.JENIS == 'harian':
                status_hari_ini = 'Selesai' if sudah else 'Belum'
            elif h.JENIS == 'jumlah':
                status_hari_ini = f'{total_hari} unit' if sudah else 'Belum'
            else:
                status_hari_ini = 'Selesai' if sudah else 'Belum'

            habits_tampilan.append({
                'obj': h,
                'id': h.id,
                'nama': h.nama,
                'jenis': h.NAMA_JENIS,
                'jenis_kode': h.JENIS,
                'satuan': h.SATUAN,
                'sudah_hari_ini': sudah,
                'status_hari_ini': status_hari_ini,
                'progres_7_hari': f'{hari_aktif}/{h.target_mingguan} hari',
                'aturan_xp': h.aturan_xp(),
                'label_input': h.label_input(),
            })

        profil = akun.profil
        xp_total = profil.xp
        level = profil.level
        xp_dalam_level = profil.xp_dalam_level
        persen_level = int((xp_dalam_level / XP_PER_LEVEL) * 100)
        streak_aktif = profil.streak_saat_ini(hari_ini)

        return render(request, self.template_name, {
            'akun': akun,
            'profil': profil,
            'xp_total': xp_total,
            'level': level,
            'level_selanjutnya': level + 1,
            'xp_dalam_level': xp_dalam_level,
            'persen_level': persen_level,
            'streak': streak_aktif,
            'habits': habits_tampilan,
        })

    def post(self, request):
        db = get_db()
        akun = get_akun_login(request, db)
        if akun is None or isinstance(akun, Admin):
            return redirect('login')

        action = request.POST.get('action')
        if action == 'catat':
            try:
                habit_id = int(request.POST.get('habit_id', 0))
            except (ValueError, TypeError):
                messages.error(request, 'Kebiasaan tidak valid.')
                return redirect('dashboard')

            habit = akun.cari_habit(habit_id)
            if not habit:
                messages.error(request, 'Kebiasaan tidak ditemukan.')
                return redirect('dashboard')

            hari_ini = date.today()
            if habit.SEKALI_PER_HARI and db.sudah_dicatat(habit.id, hari_ini):
                messages.warning(
                    request,
                    f"Kebiasaan '{habit.nama}' sudah dicatat selesai hari ini."
                )
                return redirect('dashboard')

            if habit.SEKALI_PER_HARI:
                nilai = 1
            else:
                raw_nilai = request.POST.get('nilai', '').strip()
                try:
                    nilai = int(raw_nilai)
                except (ValueError, TypeError):
                    messages.error(request, 'Nilai harus bilangan bulat positif.')
                    return redirect('dashboard')

            try:
                master_badges = db.daftar_badge()
                hasil = akun.catat_selesai(habit, nilai, hari_ini, master_badges)
                db.simpan_hasil_catat(akun, hasil)

                pesan = f"Pencatatan berhasil! +{hasil.xp_dasar} XP dasar"
                if hasil.bonus_streak > 0:
                    pesan += f" dan +{hasil.bonus_streak} bonus streak!"
                else:
                    pesan += "!"

                if hasil.naik_level:
                    pesan += f" 🎉 Hebat! Kamu naik ke Level {hasil.level_baru}!"

                if hasil.badge_baru:
                    nama_badge = ", ".join(b.nama for b in hasil.badge_baru)
                    pesan += f" 🏆 Lencana baru terbuka: {nama_badge}!"

                messages.success(request, pesan)
            except ValueError as e:
                messages.error(request, str(e))

        return redirect('dashboard')


# =====================================================================
# KELOLA KEBIASAAN (CRUD)
# =====================================================================
class HabitView(View):
    template_name = 'habits.html'

    def get(self, request):
        db = get_db()
        akun = get_akun_login(request, db)
        if akun is None:
            return redirect('login')
        if isinstance(akun, Admin):
            return redirect('admin_panel')

        daftar_jenis = [
            {'kode': 'belajar', 'nama': 'Belajar (durasi)', 'aturan': '1 XP setiap 5 menit'},
            {'kode': 'harian', 'nama': 'Harian (checklist)', 'aturan': '10 XP per hari'},
            {'kode': 'jumlah', 'nama': 'Target jumlah', 'aturan': '2 XP per unit'},
        ]

        return render(request, self.template_name, {
            'akun': akun,
            'habits': akun.habits,
            'daftar_jenis': daftar_jenis,
        })

    def post(self, request):
        db = get_db()
        akun = get_akun_login(request, db)
        if akun is None or isinstance(akun, Admin):
            return redirect('login')

        action = request.POST.get('action')

        if action == 'tambah':
            nama = request.POST.get('nama', '').strip()
            jenis = request.POST.get('jenis', '').strip()
            try:
                target = int(request.POST.get('target_mingguan', 5))
            except (ValueError, TypeError):
                target = 5

            try:
                db.tambah_habit(akun, jenis, nama, target)
                messages.success(request, f"Kebiasaan '{nama}' berhasil ditambahkan.")
            except ValueError as e:
                messages.error(request, str(e))

        elif action == 'ubah':
            try:
                habit_id = int(request.POST.get('habit_id', 0))
                target = int(request.POST.get('target_mingguan', 5))
            except (ValueError, TypeError):
                messages.error(request, 'Input tidak valid.')
                return redirect('habits')

            nama = request.POST.get('nama', '').strip()

            try:
                h = akun.ubah_habit(habit_id, nama, target)
                if h is not None:
                    db.ubah_habit(h)
                    messages.success(request, f"Kebiasaan '{nama}' berhasil diperbarui.")
                else:
                    messages.error(request, 'Kebiasaan tidak ditemukan.')
            except ValueError as e:
                messages.error(request, str(e))

        elif action == 'hapus':
            try:
                habit_id = int(request.POST.get('habit_id', 0))
                db.hapus_habit(akun, habit_id)
                messages.success(request, 'Kebiasaan berhasil dihapus.')
            except (ValueError, TypeError) as e:
                messages.error(request, f'Gagal menghapus kebiasaan: {e}')

        return redirect('habits')


# =====================================================================
# LENCANA & STATISTIK
# =====================================================================
class LencanaView(View):
    template_name = 'lencana.html'

    def get(self, request):
        db = get_db()
        akun = get_akun_login(request, db)
        if akun is None:
            return redirect('login')
        if isinstance(akun, Admin):
            return redirect('admin_panel')

        master_badges = db.daftar_badge()
        milik_dict = db.tanggal_badge_milik(akun.id)

        badges_tampilan = []
        for b in master_badges:
            terbuka = b.id in milik_dict
            tgl_didapat = milik_dict.get(b.id)
            if b.TIPE == 'streak':
                syarat_teks = f'Streak {b.ambang} hari'
            elif b.TIPE == 'xp':
                syarat_teks = f'Kumpulkan {b.ambang} XP'
            else:
                syarat_teks = f'Ambang {b.ambang}'

            badges_tampilan.append({
                'id': b.id,
                'nama': b.nama,
                'deskripsi': b.deskripsi,
                'syarat': syarat_teks,
                'tipe': b.TIPE,
                'terbuka': terbuka,
                'status': f'Terbuka ({tgl_didapat})' if terbuka else 'Terkunci',
            })

        # Grafik XP 7 hari terakhir
        hari_ini = date.today()
        raw_xp_harian = db.xp_harian(akun.id, 7, hari_ini)
        nilai_xp_list = [xp for _, xp in raw_xp_harian]
        maks_xp = max(nilai_xp_list) if nilai_xp_list else 0
        skala_maks = max(maks_xp, 50)

        grafik_7_hari = []
        daftar_hari_indonesia = {
            'Mon': 'Sen', 'Tue': 'Sel', 'Wed': 'Rab',
            'Thu': 'Kam', 'Fri': 'Jum', 'Sat': 'Sab', 'Sun': 'Min'
        }
        for tgl, xp in raw_xp_harian:
            nama_hari = daftar_hari_indonesia.get(tgl.strftime('%a'), tgl.strftime('%a'))
            persen = int((xp / skala_maks) * 100) if skala_maks > 0 else 0
            grafik_7_hari.append({
                'tanggal_str': tgl.strftime('%d/%m'),
                'hari_str': nama_hari,
                'xp': xp,
                'persen': max(persen, 4 if xp > 0 else 0),
                'is_hari_ini': tgl == hari_ini,
            })

        # Riwayat terbaru
        riwayat = db.riwayat(akun.id, batas=15)

        return render(request, self.template_name, {
            'akun': akun,
            'badges': badges_tampilan,
            'grafik_xp': grafik_7_hari,
            'riwayat': riwayat,
        })


# =====================================================================
# PANEL ADMIN (Pengguna & Master Lencana)
# =====================================================================
class AdminView(View):
    template_name = 'admin.html'

    def get(self, request):
        db = get_db()
        akun = get_akun_login(request, db)
        if akun is None:
            return redirect('login')
        if not isinstance(akun, Admin):
            return redirect('dashboard')

        tab = request.GET.get('tab', 'pengguna')
        pengguna_list = db.ringkasan_pengguna()
        badge_list = db.daftar_badge()

        return render(request, self.template_name, {
            'admin': akun,
            'tab_aktif': tab,
            'pengguna_list': pengguna_list,
            'badge_list': badge_list,
        })

    def post(self, request):
        db = get_db()
        akun = get_akun_login(request, db)
        if akun is None or not isinstance(akun, Admin):
            return redirect('login')

        action = request.POST.get('action')

        if action == 'hapus_akun':
            try:
                akun_id = int(request.POST.get('akun_id', 0))
                akun.hapus_akun(db, akun_id)
                messages.success(request, f'Akun ID #{akun_id} berhasil dihapus.')
            except ValueError as e:
                messages.error(request, str(e))
            return redirect('/admin-panel/?tab=pengguna')

        elif action == 'tambah_badge':
            tipe = request.POST.get('tipe', '').strip()
            nama = request.POST.get('nama', '').strip()
            deskripsi = request.POST.get('deskripsi', '').strip()
            try:
                ambang = int(request.POST.get('ambang', 0))
                akun.tambah_badge(db, tipe, nama, deskripsi, ambang)
                messages.success(request, f"Master lencana '{nama}' berhasil ditambahkan.")
            except ValueError as e:
                messages.error(request, str(e))
            return redirect('/admin-panel/?tab=badge')

        elif action == 'hapus_badge':
            try:
                badge_id = int(request.POST.get('badge_id', 0))
                akun.hapus_badge(db, badge_id)
                messages.success(request, f'Lencana ID #{badge_id} berhasil dihapus.')
            except ValueError as e:
                messages.error(request, str(e))
            return redirect('/admin-panel/?tab=badge')

        return redirect('admin_panel')
