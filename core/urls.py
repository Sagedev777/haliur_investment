from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'core'

urlpatterns = [
    path('login/', views.custom_login, name='login'),
    path('logout/', LogoutView.as_view(next_page='core:login'), name='logout'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
]
