from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum
from .models import ClientAccount, SavingsTransaction
from loans.models import LoanApplication  # Loan model must have status: PENDING, APPROVED, REJECTED, DISBURSED
from django.contrib.auth.models import User, Group
from decimal import Decimal
import csv
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from functools import wraps
from .models import ClientAccount
from django.utils import timezone
from .forms import ClientAccountForm
# -----------------------
# Role-based decorator
# -----------------------
def role_required(roles):
    """Restrict view access to certain user groups"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser or request.user.groups.filter(name__in=roles).exists():
                return view_func(request, *args, **kwargs)
            messages.error(request, "You do not have permission to access this page.")
            return redirect('accounts:dashboard')
        return _wrapped_view
    return decorator


# -----------------------
# Dashboard
# -----------------------
@login_required
def dashboard(request):
    total_accounts = ClientAccount.objects.count()
    active_accounts = ClientAccount.objects.filter(is_active=True).count()
    total_savings = ClientAccount.objects.aggregate(total=Sum('savings_balance'))['total'] or Decimal('0')

    recent_accounts = ClientAccount.objects.order_by('-registration_date')[:5]
    recent_savings = SavingsTransaction.objects.order_by('-transaction_date')[:5]
    recent_loans = LoanApplication.objects.order_by('-application_date')[:5]

    context = {
        'total_accounts': total_accounts,
        'active_accounts': active_accounts,
        'total_savings': total_savings,
        'recent_accounts': recent_accounts,
        'recent_savings': recent_savings,
        'recent_loans': recent_loans,
    }
    return render(request, 'client_accounts/dashboard.html', context)


# -----------------------
# Client Accounts
# -----------------------
@login_required
@role_required(['Admin', 'Staff', 'Manager'])
def account_list(request):
    accounts = ClientAccount.objects.all().order_by('-registration_date')
    return render(request, 'client_accounts/account_list.html', {'accounts': accounts})


@login_required
@role_required(['Admin', 'Staff'])
def account_create(request):
    if request.method == 'POST':
        # Validate required fields manually
        errors = {}
        required_fields = [
            'account_type', 'person1_first_name', 'person1_last_name', 
            'person1_contact', 'person1_nin', 'person1_gender',
            'business_location', 'business_sector'
        ]
        
        for field in required_fields:
            if not request.POST.get(field):
                errors[field] = 'This field is required.'
        
        # For joint accounts, validate person2 fields
        if request.POST.get('account_type') == 'JOINT':
            joint_required_fields = [
                'person2_first_name', 'person2_last_name', 'person2_contact',
                'person2_nin', 'person2_gender'
            ]
            for field in joint_required_fields:
                if not request.POST.get(field):
                    errors[field] = 'This field is required for joint accounts.'
        
        if errors:
            # There are errors, render form with errors and submitted data
            return render(request, 'client_accounts/account_form.html', {
                'errors': errors,
                'submitted_data': request.POST,
                'title': 'Create Client Account'
            })
        
        # No errors, create the account
        account = ClientAccount(
            account_type=request.POST.get('account_type'),
            person1_first_name=request.POST.get('person1_first_name'),
            person1_last_name=request.POST.get('person1_last_name'),
            person1_contact=request.POST.get('person1_contact'),
            person1_address=request.POST.get('person1_address'),
            person1_area_code=request.POST.get('person1_area_code'),
            person1_next_of_kin=request.POST.get('person1_next_of_kin'),
            person1_nin=request.POST.get('person1_nin'),
            person1_gender=request.POST.get('person1_gender'),
            business_location=request.POST.get('business_location'),
            business_sector=request.POST.get('business_sector'),
            person2_first_name=request.POST.get('person2_first_name'),
            person2_last_name=request.POST.get('person2_last_name'),
            person2_contact=request.POST.get('person2_contact'),
            person2_address=request.POST.get('person2_address'),
            person2_area_code=request.POST.get('person2_area_code'),
            person2_next_of_kin=request.POST.get('person2_next_of_kin'),
            person2_nin=request.POST.get('person2_nin'),
            person2_gender=request.POST.get('person2_gender'),
            loan_officer=request.user
        )

        # Staff edits require Admin approval
        if request.user.groups.filter(name='Staff').exists():
            account.is_approved = False
            account.edit_requested_by = request.user
        else:
            account.is_approved = True

        account.save()
        messages.success(request, f"Account {account.account_number} created successfully.")
        return redirect('accounts:account_list')
    
    # GET request - render empty form
    return render(request, 'client_accounts/account_form.html', {
        'title': 'Create Client Account'
    })

@login_required
@role_required(['Admin', 'Staff', 'Manager'])
def account_detail(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    savings_transactions = SavingsTransaction.objects.filter(client_account=account).order_by('-transaction_date')
    loans = LoanApplication.objects.filter(client_account=account).order_by('-application_date')
    context = {
        'account': account,
        'savings_transactions': savings_transactions,
        'loans': loans,
    }
    return render(request, 'client_accounts/account_detail.html', context)


@login_required
@role_required(['Admin', 'Staff'])
# views.py

def account_edit(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)

    if request.method == 'POST':
        form = ClientAccountForm(request.POST, instance=account)
        if form.is_valid():
            account = form.save(commit=False)
            
            # Staff edits require admin approval
            if request.user.groups.filter(name='Staff').exists():
                account.is_approved = False
                messages.info(request, "Your changes are submitted for Admin approval.")
            else:
                account.is_approved = True
                messages.success(request, "Account updated successfully.")
            
            account.save()
            return redirect('accounts:account_detail', pk=account.pk)
    else:
        form = ClientAccountForm(instance=account)

    return render(request, 'client_accounts/account_form.html', {'form': form, 'account': account})


@login_required
@role_required(['Admin'])
def account_delete(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    account.is_active = False
    account.save()
    messages.success(request, f"Account {account.account_number} deactivated.")
    return redirect('accounts:account_list')


# -----------------------
# Savings
# -----------------------
@login_required
@role_required(['Admin', 'Staff', 'Accountant', 'Loan Officer'])
def savings_list(request):
    transactions = SavingsTransaction.objects.all().order_by('-transaction_date')
    return render(request, 'client_accounts/savings_list.html', {'transactions': transactions})


@login_required
@role_required(['Admin', 'Staff'])
def savings_deposit(request):
    if request.method == 'POST':
        account_id = request.POST.get('account_id')
        amount = Decimal(request.POST.get('amount'))
        account = get_object_or_404(ClientAccount, pk=account_id)
        transaction = SavingsTransaction(
            client_account=account,
            transaction_type='DEPOSIT',
            amount=amount,
            processed_by=request.user
        )
        transaction.save()
        messages.success(request, f"Deposited {amount} to {account.account_number}.")
        return redirect('accounts:account_detail', pk=account_id)
    return render(request, 'client_accounts/savings_form.html', {'type': 'Deposit'})


@login_required
@role_required(['Admin', 'Staff'])
def savings_withdrawal(request):
    if request.method == 'POST':
        account_id = request.POST.get('account_id')
        amount = Decimal(request.POST.get('amount'))
        account = get_object_or_404(ClientAccount, pk=account_id)
        if amount > account.savings_balance:
            messages.error(request, "Insufficient balance.")
            return redirect('accounts:account_detail', pk=account_id)
        transaction = SavingsTransaction(
            client_account=account,
            transaction_type='WITHDRAWAL',
            amount=amount,
            processed_by=request.user
        )
        transaction.save()
        messages.success(request, f"Withdrew {amount} from {account.account_number}.")
        return redirect('accounts:account_detail', pk=account_id)
    return render(request, 'client_accounts/savings_form.html', {'type': 'Withdrawal'})


@login_required
@role_required(['Admin', 'Staff', 'Accountant', 'Loan Officer'])
def account_savings(request, account_id):
    account = get_object_or_404(ClientAccount, pk=account_id)
    transactions = SavingsTransaction.objects.filter(client_account=account).order_by('-transaction_date')
    return render(request, 'client_accounts/account_savings.html', {'account': account, 'transactions': transactions})


# -----------------------
# Loan Actions (Admin only)
# -----------------------
@login_required
@role_required(['Admin'])
def approve_loan(request, pk):
    loan = get_object_or_404(LoanApplication, pk=pk)
    loan.status = 'APPROVED'
    loan.approved_by = request.user
    loan.save()
    messages.success(request, f"Loan {loan.id} approved.")
    return redirect('loans:loan_list')


@login_required
@role_required(['Admin'])
def reject_loan(request, pk):
    loan = get_object_or_404(LoanApplication, pk=pk)
    loan.status = 'REJECTED'
    loan.approved_by = request.user
    loan.save()
    messages.success(request, f"Loan {loan.id} rejected.")
    return redirect('loans:loan_list')


@login_required
@role_required(['Admin'])
def disburse_loan(request, pk):
    loan = get_object_or_404(LoanApplication, pk=pk)
    if loan.status != 'APPROVED':
        messages.error(request, "Cannot disburse a loan that is not approved.")
        return redirect('loans:loan_list')
    loan.status = 'DISBURSED'
    loan.disbursed_by = request.user
    loan.save()
    messages.success(request, f"Loan {loan.id} disbursed successfully.")
    return redirect('loans:loan_list')


# -----------------------
# API & Reports (JSON, CSV, PDF)
# -----------------------
@login_required
@role_required(['Admin', 'Staff', 'Accountant', 'Loan Officer'])
def api_account_list(request):
    accounts = list(ClientAccount.objects.values('id', 'account_number', 'account_type', 'person1_first_name', 'person1_last_name', 'savings_balance'))
    return JsonResponse(accounts, safe=False)


@login_required
@role_required(['Admin', 'Staff', 'Accountant', 'Loan Officer'])
def api_account_detail(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    data = {
        'id': account.id,
        'account_number': account.account_number,
        'account_type': account.account_type,
        'person1_first_name': account.person1_first_name,
        'person1_last_name': account.person1_last_name,
        'savings_balance': str(account.savings_balance),
    }
    return JsonResponse(data)


@login_required
@role_required(['Admin', 'Staff', 'Accountant', 'Loan Officer'])
def api_savings_balance(request, account_id):
    account = get_object_or_404(ClientAccount, pk=account_id)
    return JsonResponse({'balance': str(account.savings_balance)})


@login_required
@role_required(['Admin'])
def export_accounts_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="accounts.csv"'
    writer = csv.writer(response)
    writer.writerow(['Account Number', 'Type', 'Person 1', 'Person 2', 'Balance'])
    for acc in ClientAccount.objects.all():
        writer.writerow([acc.account_number, acc.account_type, acc.full_account_name, '', acc.savings_balance])
    return response


@login_required
@role_required(['Admin'])
def export_transactions_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    writer = csv.writer(response)
    writer.writerow(['Account Number', 'Type', 'Amount', 'Date', 'Processed By'])
    for tx in SavingsTransaction.objects.all():
        writer.writerow([tx.client_account.account_number, tx.transaction_type, tx.amount, tx.transaction_date, tx.processed_by.username])
    return response


@login_required
@role_required(['Admin'])
def export_accounts_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="accounts.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 14)
    p.drawString(1 * inch, height - 1 * inch, "Client Accounts Report")
    p.setFont("Helvetica", 11)
    y = height - 1.5 * inch
    p.drawString(1 * inch, y, "Account Number     Account Type     Full Name     Balance")

    y -= 0.3 * inch
    for acc in ClientAccount.objects.all():
        line = f"{acc.account_number}     {acc.account_type}     {acc.full_account_name}     {acc.savings_balance}"
        p.drawString(1 * inch, y, line)
        y -= 0.25 * inch
        if y <= 1 * inch:
            p.showPage()
            p.setFont("Helvetica", 11)
            y = height - 1 * inch

    p.showPage()
    p.save()
    return response


@login_required
@role_required(['Admin'])
def export_transactions_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="transactions.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 14)
    p.drawString(1 * inch, height - 1 * inch, "Savings Transactions Report")
    p.setFont("Helvetica", 11)
    y = height - 1.5 * inch
    p.drawString(1 * inch, y, "Account Number     Type     Amount     Date     Processed By")

    y -= 0.3 * inch
    for tx in SavingsTransaction.objects.all():
        line = f"{tx.client_account.account_number}     {tx.transaction_type}     {tx.amount}     {tx.transaction_date.strftime('%Y-%m-%d')}     {tx.processed_by.username}"
        p.drawString(1 * inch, y, line)
        y -= 0.25 * inch
        if y <= 1 * inch:
            p.showPage()
            p.setFont("Helvetica", 11)
            y = height - 1 * inch

    p.showPage()
    p.save()
    return response


@login_required
def account_approve(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    account.is_approved = True
    account.approval_date = timezone.now()
    account.save()
    return redirect('accounts:accounts_list')  # or wherever you want to redirect

@login_required
def account_reject(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    account.is_approved = False  # or set a "rejected" field if you have one
    account.rejection_date = timezone.now()  # optional
    account.save()
    return redirect('accounts:accounts_list')  # adjust redirect as needed


@login_required
def savings_transactions(request):
    transactions = SavingsTransaction.objects.all()  # or filter by user
    return render(request, 'client_accounts/savings_transactions.html', {'transactions': transactions})
