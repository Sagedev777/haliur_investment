from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum

# Import your models
from client_accounts.models import ClientAccount
from loans.models import LoanApplication

# =========================
# Custom Login View
# =========================
def custom_login(request):
    # Redirect already logged-in users
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('core:admin_dashboard')
        elif request.user.is_staff:
            return redirect('core:staff_dashboard')
        else:
            messages.error(request, "You do not have access.")
            return redirect('core:login')

    # Get next parameter
    next_url = request.GET.get('next') or request.POST.get('next') or None
    if next_url == '':
        next_url = None

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if user.is_superuser:
                return redirect(next_url or 'core:admin_dashboard')
            elif user.is_staff:
                return redirect(next_url or 'core:staff_dashboard')
            else:
                messages.error(request, "You do not have access.")
                return redirect('core:login')
        else:
            messages.error(request, "Invalid credentials.")

    return render(request, 'core/login.html', {'next': next_url})

# =========================
# Admin Dashboard
# =========================
@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        messages.error(request, "Unauthorized access.")
        return redirect('core:login')

    total_clients = ClientAccount.objects.count()
    active_accounts = ClientAccount.objects.filter(is_active=True).count()
    total_savings = ClientAccount.objects.aggregate(total=Sum('savings_balance'))['total'] or 0

    pending_loans = LoanApplication.objects.filter(status='pending')
    disbursed_loans = LoanApplication.objects.filter(status='disbursed')
    rejected_loans = LoanApplication.objects.filter(status='rejected')

    context = {
        'total_clients': total_clients,
        'active_accounts': active_accounts,
        'total_savings': total_savings,
        'pending_loans': pending_loans,
        'disbursed_loans': disbursed_loans,
        'rejected_loans': rejected_loans,
    }

    return render(request, 'core/admin_dashboard.html', context)

# =========================
# Staff Dashboard
# =========================
@login_required
def staff_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, "Unauthorized access.")
        return redirect('core:login')

    # Staff limited view
    pending_loans = LoanApplication.objects.filter(status='pending')
    approved_accounts = ClientAccount.objects.filter(is_active=True)
    
    context = {
        'pending_loans': pending_loans,
        'accounts': approved_accounts,
    }

    return render(request, 'core/staff_dashboard.html', context)
