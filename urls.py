"""
urls.py - Rute URL aplikasi HabiQuest.
"""
from django.urls import path
from views import (
    LoginView,
    DashboardView,
    HabitView,
    LencanaView,
    AdminView,
)

urlpatterns = [
    path('', LoginView.as_view(), name='home'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LoginView.as_view(), {'keluar': True}, name='logout'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('habits/', HabitView.as_view(), name='habits'),
    path('lencana/', LencanaView.as_view(), name='lencana'),
    path('admin-panel/', AdminView.as_view(), name='admin_panel'),
]
