from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from decimal import Decimal

# Import your models
from client_accounts.models import ClientAccount, SavingsTransaction, ClientEditRequest, UserProfile
from loans.models import LoanApplication, Loan

# =========================
# Custom Login View
# =========================
def custom_login(request):
    # Redirect already logged-in users
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.role == UserProfile.ROLE_ADMIN or request.user.is_superuser:
                return redirect('accounts:dashboard')
            elif profile.role in [UserProfile.ROLE_STAFF, UserProfile.ROLE_LOAN_OFFICER, UserProfile.ROLE_ACCOUNTANT, UserProfile.ROLE_MANAGER]:
                return redirect('accounts:dashboard')
            else:
                messages.error(request, "You do not have access.")
                return redirect('core:login')
        except UserProfile.DoesNotExist:
            # If user doesn't have profile, redirect to appropriate dashboard
            if request.user.is_superuser:
                return redirect('accounts:dashboard')
            elif request.user.is_staff:
                return redirect('accounts:dashboard')
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
            try:
                profile = user.profile
                if profile.role == UserProfile.ROLE_ADMIN or user.is_superuser:
                    return redirect(next_url or 'accounts:dashboard')
                elif profile.role in [UserProfile.ROLE_STAFF, UserProfile.ROLE_LOAN_OFFICER, UserProfile.ROLE_ACCOUNTANT, UserProfile.ROLE_MANAGER]:
                    return redirect(next_url or 'accounts:dashboard')
                else:
                    messages.error(request, "You do not have access.")
                    return redirect('core:login')
            except UserProfile.DoesNotExist:
                # If user doesn't have profile, check superuser/staff
                if user.is_superuser:
                    return redirect(next_url or 'accounts:dashboard')
                elif user.is_staff:
                    return redirect(next_url or 'accounts:dashboard')
                else:
                    messages.error(request, "You do not have access.")
                    return redirect('core:login')
        else:
            messages.error(request, "Invalid credentials.")

    return render(request, 'core/login.html', {'next': next_url})


# =========================
# Helper function to get user role
# =========================
def get_user_role(user):
    """Helper function to get user role from UserProfile"""
    if user.is_superuser:
        return UserProfile.ROLE_ADMIN
    try:
        return user.profile.role
    except UserProfile.DoesNotExist:
        if user.is_staff:
            return UserProfile.ROLE_STAFF
        return None


# =========================
# Admin Dashboard - FIXED
# =========================
@login_required
def admin_dashboard(request):
    user_role = get_user_role(request.user)
    
    if not (request.user.is_superuser or user_role == UserProfile.ROLE_ADMIN):
        messages.error(request, "Unauthorized access.")
        return redirect('core:login')

    # Calculate statistics
    total_clients = ClientAccount.objects.count()
    active_accounts = ClientAccount.objects.filter(account_status=ClientAccount.STATUS_ACTIVE).count()
    pending_accounts = ClientAccount.objects.filter(account_status=ClientAccount.STATUS_PENDING).count()
    total_savings = ClientAccount.objects.aggregate(total=Sum('savings_balance'))['total'] or Decimal('0')

    # Loan statistics - FIXED: Changed 'loan_amount' to correct field names
    pending_loans = LoanApplication.objects.filter(status='SUBMITTED').count()  # Assuming 'SUBMITTED' is pending
    approved_loans = LoanApplication.objects.filter(status='APPROVED').count()
    disbursed_loans_count = LoanApplication.objects.filter(status='DISBURSED').count()
    rejected_loans = LoanApplication.objects.filter(status='REJECTED').count()
    
    # Total loan amounts - FIXED: Using correct field names
    total_approved_loans = LoanApplication.objects.filter(status='APPROVED').aggregate(
        total=Sum('approved_amount')
    )['total'] or Decimal('0')
    
    # For disbursed loans, we should use the Loan model for actual disbursed amounts
    total_disbursed_loans = Loan.objects.aggregate(
        total=Sum('principal_amount')
    )['total'] or Decimal('0')

    # Recent activity
    recent_accounts = ClientAccount.objects.order_by('-registration_date')[:5]
    recent_transactions = SavingsTransaction.objects.order_by('-transaction_date')[:5]
    pending_edit_requests = ClientEditRequest.objects.filter(status=ClientEditRequest.STATUS_PENDING).order_by('-created_at')[:5]
    recent_loans = LoanApplication.objects.order_by('-application_date')[:5]
    
    # Pending loans list for the table
    pending_loans_list = LoanApplication.objects.filter(status='SUBMITTED').order_by('-application_date')[:5]

    # Staff performance (if needed)
    staff_performance = []
    if request.user.is_superuser:
        # Get top performing loan officers by number of clients
        staff_performance = ClientAccount.objects.filter(
            account_status=ClientAccount.STATUS_ACTIVE
        ).values(
            'loan_officer__username'
        ).annotate(
            client_count=Count('id'),
            total_savings=Sum('savings_balance')
        ).order_by('-client_count')[:5]

    context = {
        'user_role': user_role,
        'total_clients': total_clients,
        'active_accounts': active_accounts,
        'pending_accounts': pending_accounts,
        'total_savings': total_savings,
        'pending_loans': pending_loans,
        'approved_loans': approved_loans,
        'disbursed_loans': disbursed_loans_count,  # Renamed to avoid conflict
        'rejected_loans': rejected_loans,
        'total_approved_loans': total_approved_loans,
        'total_disbursed_loans': total_disbursed_loans,
        'recent_accounts': recent_accounts,
        'recent_transactions': recent_transactions,
        'pending_edit_requests': pending_edit_requests,
        'recent_loans': recent_loans,
        'pending_loans_list': pending_loans_list,  # Added for the table
        'staff_performance': staff_performance,
    }

    return render(request, 'core/admin_dashboard.html', context)


@login_required
def switch_to_accounts(request):
    """Redirect to accounts dashboard"""
    return redirect('accounts:dashboard')

@login_required
def switch_to_loans(request):
    """Redirect to loans dashboard"""
    return redirect('loans:dashboard')

# =========================
# Staff Dashboard - FIXED
# =========================
@login_required
def staff_dashboard(request):
    user_role = get_user_role(request.user)
    
    # Check if user has staff role or is staff user
    if not (user_role in [UserProfile.ROLE_STAFF, UserProfile.ROLE_LOAN_OFFICER, UserProfile.ROLE_ACCOUNTANT] or request.user.is_staff):
        messages.error(request, "Unauthorized access.")
        return redirect('core:login')

    # Staff limited view - only show their own clients
    my_clients = ClientAccount.objects.filter(loan_officer=request.user)
    active_clients = my_clients.filter(account_status=ClientAccount.STATUS_ACTIVE)
    pending_clients = my_clients.filter(account_status=ClientAccount.STATUS_PENDING)
    
    # My client statistics
    total_clients = my_clients.count()
    active_clients_count = active_clients.count()
    total_savings = my_clients.aggregate(total=Sum('savings_balance'))['total'] or Decimal('0')
    
    # Loans for my clients - FIXED: Changed to correct field name
    my_clients_loans = LoanApplication.objects.filter(client__in=my_clients)  # Changed from client_account to client
    pending_loans = my_clients_loans.filter(status='SUBMITTED')[:10]
    
    # Recent transactions for my clients
    recent_transactions = SavingsTransaction.objects.filter(
        client_account__in=my_clients
    ).order_by('-transaction_date')[:10]
    
    # My pending edit requests
    my_edit_requests = ClientEditRequest.objects.filter(
        requested_by=request.user,
        status=ClientEditRequest.STATUS_PENDING
    ).order_by('-created_at')[:5]

    context = {
        'user_role': user_role,
        'total_clients': total_clients,
        'active_clients': active_clients_count,
        'pending_clients': pending_clients.count(),
        'total_savings': total_savings,
        'pending_loans': pending_loans,
        'recent_transactions': recent_transactions,
        'my_edit_requests': my_edit_requests,
        'active_clients_list': active_clients.order_by('-registration_date')[:5],
    }

    return render(request, 'core/staff_dashboard.html', context)


# =========================
# Role-based Dashboard Redirector
# =========================
@login_required
def dashboard_redirect(request):
    """Redirect users to appropriate dashboard based on their role"""
    user_role = get_user_role(request.user)
    
    if request.user.is_superuser or user_role == UserProfile.ROLE_ADMIN:
        return redirect('core:admin_dashboard')
    elif user_role in [UserProfile.ROLE_STAFF, UserProfile.ROLE_LOAN_OFFICER, 
                       UserProfile.ROLE_ACCOUNTANT, UserProfile.ROLE_MANAGER]:
        return redirect('core:staff_dashboard')
    else:
        messages.error(request, "You do not have access to any dashboard.")
        return redirect('core:login')


# =========================
# Accountant Dashboard (Optional)
# =========================
@login_required
def accountant_dashboard(request):
    user_role = get_user_role(request.user)
    
    if not (user_role == UserProfile.ROLE_ACCOUNTANT or request.user.is_superuser):
        messages.error(request, "Unauthorized access.")
        return redirect('core:login')

    # Accountant specific statistics
    total_savings = ClientAccount.objects.aggregate(total=Sum('savings_balance'))['total'] or Decimal('0')
    total_deposits = SavingsTransaction.objects.filter(
        transaction_type='DEPOSIT'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    total_withdrawals = SavingsTransaction.objects.filter(
        transaction_type='WITHDRAWAL'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Today's transactions
    from django.utils import timezone
    today = timezone.now().date()
    today_transactions = SavingsTransaction.objects.filter(
        transaction_date__date=today
    ).order_by('-transaction_date')
    
    # Recent reversals
    recent_reversals = SavingsTransaction.objects.filter(
        is_reversed=True
    ).order_by('-reversal_date')[:5]

    context = {
        'user_role': user_role,
        'total_savings': total_savings,
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
        'today_transactions': today_transactions,
        'recent_reversals': recent_reversals,
    }

    return render(request, 'core/accountant_dashboard.html', context)


# =========================
# Loan Officer Dashboard (Optional)
# =========================
@login_required
def loan_officer_dashboard(request):
    user_role = get_user_role(request.user)
    
    if not (user_role == UserProfile.ROLE_LOAN_OFFICER or request.user.is_superuser):
        messages.error(request, "Unauthorized access.")
        return redirect('core:login')

    # Loan officer specific statistics
    my_clients = ClientAccount.objects.filter(loan_officer=request.user)
    active_clients = my_clients.filter(account_status=ClientAccount.STATUS_ACTIVE)
    
    # Client loan eligibility
    eligible_for_loan = []
    for client in active_clients:
        if client.has_minimum_savings():
            max_loan = client.get_max_loan_amount()
            eligible_for_loan.append({
                'client': client,
                'max_loan': max_loan,
                'current_loan_balance': client.total_loan_balance,
                'available_limit': client.available_loan_limit,
            })
    
    # My clients' loans
    my_clients_loans = LoanApplication.objects.filter(client__in=my_clients)  # Changed from client_account to client
    pending_loans = my_clients_loans.filter(status='SUBMITTED')
    active_loans = my_clients_loans.filter(status__in=['APPROVED', 'DISBURSED'])

    context = {
        'user_role': user_role,
        'total_clients': my_clients.count(),
        'active_clients': active_clients.count(),
        'eligible_for_loan': eligible_for_loan[:10],  # Top 10
        'pending_loans': pending_loans,
        'active_loans': active_loans,
    }

    return render(request, 'core/loan_officer_dashboard.html', context)


# =========================
# Home/Index Page
# =========================
def home(request):
    """Public home page"""
    if request.user.is_authenticated:
        return dashboard_redirect(request)
    return render(request, 'core/home.html')


# =========================
# Context Processor for current date/time
# =========================
def add_current_datetime(request):
    from django.utils import timezone
    return {
        'current_date': timezone.now().date(),
        'current_time': timezone.now().time(),
    }