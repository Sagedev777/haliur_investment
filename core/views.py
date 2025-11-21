from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def custom_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if user.is_superuser:
                return redirect('core:admin_dashboard')
            elif user.is_staff:
                return redirect('core:staff_dashboard')
            else:
                messages.error(request, "You do not have access.")
                return redirect('core:login')
        else:
            messages.error(request, "Invalid credentials.")
    return render(request, 'core/login.html')

@login_required
def admin_dashboard(request):
    return render(request, 'core/admin_dashboard.html')

@login_required
def staff_dashboard(request):
    return render(request, 'core/staff_dashboard.html')
