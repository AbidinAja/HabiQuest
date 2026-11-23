"""
main.py - Titik masuk aplikasi HabiQuest (Django Web).
Jalankan:  python main.py
atau:      python manage.py runserver
"""
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

    from database import DatabaseManager
    # Pastikan basis data lokal SQLite dan master data awal terinisialisasi
    db = DatabaseManager("habiquest.db")
    db.tutup()

    from django.core.management import execute_from_command_line

    print("=" * 60)
    print(" HabiQuest: Aplikasi Pelacak Kebiasaan Belajar (Gamifikasi) ")
    print(" Berbasis Python Django & Pemrograman Berorientasi Objek    ")
    print(" Server berjalan di: http://127.0.0.1:8000/                 ")
    print("=" * 60)

    args = sys.argv if len(sys.argv) > 1 else [sys.argv[0], "runserver", "127.0.0.1:8000"]
    execute_from_command_line(args)


if __name__ == "__main__":
    main()
