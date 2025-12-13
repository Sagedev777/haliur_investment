from django.urls import path
from django.shortcuts import redirect
from django.contrib.auth.views import LogoutView
from . import views
app_name = 'core'

def root_redirect(request):
    return redirect('core:login')

def dashboard_redirect(request):
    if request.user.is_superuser:
        return redirect('core:admin_dashboard')
    elif request.user.is_staff:
        return redirect('core:staff_dashboard')
    return redirect('core:login')
urlpatterns = [path('', root_redirect), path('login/', views.custom_login, name='login'), path('logout/', LogoutView.as_view(next_page='core:login'), name='logout'), path('dashboard/', dashboard_redirect, name='dashboard_redirect'), path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'), path('dashboard/staff/', views.staff_dashboard, name='staff_dashboard'), path('switch/accounts/', views.switch_to_accounts, name='switch_to_accounts'), path('switch/loans/', views.switch_to_loans, name='switch_to_loans')]