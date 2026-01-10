from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Q, Count
from .models import ClientAccount, SavingsTransaction, UserProfile, ClientEditRequest, ClientAuditLog
from loans.models import LoanApplication
from django.contrib.auth.models import User
from decimal import Decimal
import csv
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from functools import wraps
from django.utils import timezone
from django.core.paginator import Paginator
import json
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError

def role_required(allowed_roles):

    def decorator(view_func):

        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            try:
                profile = request.user.profile
                if profile.role in allowed_roles:
                    return view_func(request, *args, **kwargs)
            except UserProfile.DoesNotExist:
                pass
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('accounts:dashboard')
        return _wrapped_view
    return decorator

def get_user_role(request):
    if request.user.is_superuser:
        return UserProfile.ROLE_ADMIN
    try:
        return request.user.profile.role
    except UserProfile.DoesNotExist:
        return None

@login_required
def dashboard(request):
    user_role = get_user_role(request)
    accounts_qs = ClientAccount.objects.all()
    transactions_qs = SavingsTransaction.objects.all()
    if user_role == UserProfile.ROLE_STAFF:
        accounts_qs = accounts_qs.filter(loan_officer=request.user)
        transactions_qs = transactions_qs.filter(processed_by=request.user)
    elif user_role == UserProfile.ROLE_LOAN_OFFICER:
        accounts_qs = accounts_qs.filter(loan_officer=request.user)
    total_accounts = accounts_qs.count()
    active_accounts = accounts_qs.filter(account_status=ClientAccount.STATUS_ACTIVE).count()
    pending_accounts = accounts_qs.filter(account_status=ClientAccount.STATUS_PENDING).count()
    total_savings = accounts_qs.aggregate(total=Sum('savings_balance'))['total'] or Decimal('0')
    recent_accounts = accounts_qs.order_by('-registration_date')[:5]
    recent_savings = transactions_qs.order_by('-transaction_date')[:5]
    recent_loans = []
    try:
        if user_role == UserProfile.ROLE_ADMIN or user_role == UserProfile.ROLE_LOAN_OFFICER:
            recent_loans = LoanApplication.objects.all().order_by('-application_date')[:5]
        elif user_role == UserProfile.ROLE_STAFF:
            recent_loans = LoanApplication.objects.filter(client_account__loan_officer=request.user).order_by('-application_date')[:5]
    except:
        recent_loans = []
    pending_edit_requests = []
    if user_role == UserProfile.ROLE_ADMIN:
        pending_edit_requests = ClientEditRequest.objects.filter(status=ClientEditRequest.STATUS_PENDING).order_by('-created_at')[:5]
    context = {'user_role': user_role, 'total_accounts': total_accounts, 'active_accounts': active_accounts, 'pending_accounts': pending_accounts, 'total_savings': total_savings, 'recent_accounts': recent_accounts, 'recent_savings': recent_savings, 'recent_loans': recent_loans, 'pending_edit_requests': pending_edit_requests}
    return render(request, 'client_accounts/dashboard.html', context)

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_STAFF, UserProfile.ROLE_MANAGER, UserProfile.ROLE_LOAN_OFFICER])
def account_list(request):
    user_role = get_user_role(request)
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    accounts = ClientAccount.objects.all()
    if user_role == UserProfile.ROLE_STAFF or user_role == UserProfile.ROLE_LOAN_OFFICER:
        accounts = accounts.filter(loan_officer=request.user)
    if status_filter:
        accounts = accounts.filter(account_status=status_filter)
    if search_query:
        accounts = accounts.filter(Q(account_number__icontains=search_query) | Q(person1_first_name__icontains=search_query) | Q(person1_last_name__icontains=search_query) | Q(person1_nin__icontains=search_query) | Q(person2_first_name__icontains=search_query) | Q(person2_last_name__icontains=search_query) | Q(person2_nin__icontains=search_query))
    accounts = accounts.order_by('-registration_date')
    paginator = Paginator(accounts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {'page_obj': page_obj, 'status_filter': status_filter, 'search_query': search_query, 'status_choices': ClientAccount.STATUS_CHOICES, 'user_role': user_role}
    return render(request, 'client_accounts/account_list.html', context)

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_STAFF, UserProfile.ROLE_LOAN_OFFICER])
def account_create(request):
    user_role = get_user_role(request)
    if request.method == 'POST':
        try:
            account = ClientAccount(account_type=request.POST.get('account_type'), person1_first_name=request.POST.get('person1_first_name'), person1_last_name=request.POST.get('person1_last_name'), person1_contact=request.POST.get('person1_contact'), person1_address=request.POST.get('person1_address'), person1_area_code=request.POST.get('person1_area_code'), person1_next_of_kin=request.POST.get('person1_next_of_kin'), person1_nin=request.POST.get('person1_nin'), person1_gender=request.POST.get('person1_gender'), business_location=request.POST.get('business_location'), business_sector=request.POST.get('business_sector'), loan_officer=request.user, created_by=request.user)
            if request.POST.get('account_type') == 'JOINT':
                person2_client_id = request.POST.get('person2_client')
                if person2_client_id:
                    account.person2_client_id = person2_client_id
                else:
                    account.person2_first_name = request.POST.get('person2_first_name')
                    account.person2_last_name = request.POST.get('person2_last_name')
                    account.person2_contact = request.POST.get('person2_contact')
                    account.person2_address = request.POST.get('person2_address')
                    account.person2_area_code = request.POST.get('person2_area_code')
                    account.person2_next_of_kin = request.POST.get('person2_next_of_kin')
                    account.person2_nin = request.POST.get('person2_nin')
                    account.person2_gender = request.POST.get('person2_gender')
            if user_role == UserProfile.ROLE_ADMIN:
                account.account_status = ClientAccount.STATUS_ACTIVE
                account.approved_by = request.user
                account.approval_date = timezone.now()
                messages.success(request, f'Account created successfully and activated.')
            else:
                account.account_status = ClientAccount.STATUS_PENDING
                messages.success(request, f'Account created successfully. Waiting for admin approval.')
            account.save()
            ClientAuditLog.objects.create(client=account, action=ClientAuditLog.ACTION_CREATE, performed_by=request.user, note=f'Account created by {request.user.username}')
            return redirect('accounts:account_detail', pk=account.pk)
        except ValidationError as e:
            messages.error(request, f'Validation error: {e}')
            return render(request, 'client_accounts/account_form.html', {'title': 'Create Client Account', 'error': str(e), 'submitted_data': request.POST, 'user_role': user_role, 'account': ClientAccount()})
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return render(request, 'client_accounts/account_form.html', {'title': 'Create Client Account', 'error': f'An unexpected error occurred: {str(e)}', 'submitted_data': request.POST, 'user_role': user_role, 'account': ClientAccount()})
    active_accounts = ClientAccount.objects.filter(account_status=ClientAccount.STATUS_ACTIVE)
    account = ClientAccount()
    return render(request, 'client_accounts/account_form.html', {'title': 'Create Client Account', 'active_accounts': active_accounts, 'user_role': user_role, 'account': account})

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_STAFF, UserProfile.ROLE_MANAGER, UserProfile.ROLE_LOAN_OFFICER])
def account_detail(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    user_role = get_user_role(request)
    if user_role in [UserProfile.ROLE_STAFF, UserProfile.ROLE_LOAN_OFFICER] and account.loan_officer != request.user:
        messages.error(request, 'You do not have permission to view this account.')
        return redirect('accounts:account_list')
    savings_transactions = SavingsTransaction.objects.filter(client_account=account).order_by('-transaction_date')[:10]
    loans = []
    active_loans_count = 0
    try:
        loans = LoanApplication.objects.filter(client=account).order_by('-application_date')[:10]
        active_loans_count = LoanApplication.objects.filter(client=account, status__in=['APPROVED', 'DISBURSED', 'ACTIVE']).count()
    except:
        pass
    audit_logs = ClientAuditLog.objects.filter(client=account).order_by('-timestamp')[:10]
    edit_requests = account.edit_requests.filter(status=ClientEditRequest.STATUS_PENDING)
    context = {'account': account, 'savings_transactions': savings_transactions, 'loans': loans, 'audit_logs': audit_logs, 'edit_requests': edit_requests, 'user_role': user_role, 'can_edit': user_role == UserProfile.ROLE_ADMIN or (user_role in [UserProfile.ROLE_STAFF, UserProfile.ROLE_LOAN_OFFICER] and account.loan_officer == request.user), 'active_loans_count': active_loans_count}
    return render(request, 'client_accounts/account_detail.html', context)

@login_required
def account_edit(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    user_role = get_user_role(request)
    if user_role not in [UserProfile.ROLE_ADMIN] and account.loan_officer != request.user:
        messages.error(request, 'You do not have permission to edit this account.')
        return redirect('accounts:account_detail', pk=account.pk)
    if request.method == 'POST':
        if user_role == UserProfile.ROLE_ADMIN:
            try:
                for field in ['person1_first_name', 'person1_last_name', 'person1_contact', 'person1_address', 'person1_area_code', 'person1_next_of_kin', 'business_location', 'business_sector']:
                    if field in request.POST:
                        setattr(account, field, request.POST.get(field))
                if account.account_type == 'JOINT':
                    person2_client_id = request.POST.get('person2_client')
                    if person2_client_id:
                        account.person2_client_id = person2_client_id
                    else:
                        for field in ['person2_first_name', 'person2_last_name', 'person2_contact', 'person2_address', 'person2_area_code', 'person2_next_of_kin', 'person2_nin', 'person2_gender']:
                            if field in request.POST:
                                setattr(account, field, request.POST.get(field))
                account.last_edited_by = request.user
                account.last_edited_date = timezone.now()
                account.save()
                messages.success(request, 'Account updated successfully.')
                return redirect('accounts:account_detail', pk=account.pk)
            except Exception as e:
                messages.error(request, f'Error updating account: {str(e)}')
        else:
            changes = {}
            for field in request.POST:
                if field not in ['csrfmiddlewaretoken'] and request.POST[field]:
                    current_value = getattr(account, field, None)
                    if current_value != request.POST[field]:
                        changes[field] = request.POST[field]
            if changes:
                try:
                    edit_request = account.submit_edit_request(request.user, changes)
                    messages.success(request, 'Edit request submitted for admin approval.')
                    return redirect('accounts:account_detail', pk=account.pk)
                except Exception as e:
                    messages.error(request, f'Error submitting edit request: {str(e)}')
            else:
                messages.warning(request, 'No changes detected.')
    active_accounts = ClientAccount.objects.filter(account_status=ClientAccount.STATUS_ACTIVE).exclude(pk=account.pk)
    return render(request, 'client_accounts/account_form.html', {'account': account, 'active_accounts': active_accounts, 'user_role': user_role})

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def account_approve(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    if account.account_status != ClientAccount.STATUS_PENDING:
        messages.error(request, 'Only pending accounts can be approved.')
        return redirect('accounts:account_detail', pk=account.pk)
    if account.approve_account(request.user):
        messages.success(request, f'Account {account.account_number} approved successfully.')
    else:
        messages.error(request, 'Failed to approve account.')
    return redirect('accounts:account_detail', pk=account.pk)

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def account_reject(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    if account.account_status != ClientAccount.STATUS_PENDING:
        messages.error(request, 'Only pending accounts can be rejected.')
        return redirect('accounts:account_detail', pk=account.pk)
    reason = request.POST.get('reason', '')
    if account.reject_account(request.user, reason):
        messages.success(request, f'Account {account.account_number} rejected.')
    else:
        messages.error(request, 'Failed to reject account.')
    return redirect('accounts:account_detail', pk=account.pk)

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def account_change_status(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('new_status')
        reason = request.POST.get('reason', '')
        if new_status not in dict(ClientAccount.STATUS_CHOICES).keys():
            messages.error(request, 'Invalid status.')
        else:
            account.change_status(new_status, request.user, reason)
            messages.success(request, f'Account status changed to {new_status}.')
    return redirect('accounts:account_detail', pk=account.pk)

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def edit_request_list(request):
    status_filter = request.GET.get('status', 'PENDING')
    edit_requests = ClientEditRequest.objects.all()
    if status_filter:
        edit_requests = edit_requests.filter(status=status_filter)
    edit_requests = edit_requests.order_by('-created_at')
    return render(request, 'client_accounts/edit_request_list.html', {'edit_requests': edit_requests, 'status_filter': status_filter})

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def edit_request_detail(request, pk):
    edit_request = get_object_or_404(ClientEditRequest, pk=pk)
    return render(request, 'client_accounts/edit_request_detail.html', {'edit_request': edit_request})

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def edit_request_approve(request, pk):
    edit_request = get_object_or_404(ClientEditRequest, pk=pk)
    if edit_request.status != ClientEditRequest.STATUS_PENDING:
        messages.error(request, 'Only pending edit requests can be approved.')
        return redirect('accounts:edit_request_detail', pk=pk)
    comment = request.POST.get('comment', '')
    if edit_request.approve(request.user, comment):
        messages.success(request, 'Edit request approved and changes applied.')
    else:
        messages.error(request, 'Failed to approve edit request.')
    return redirect('accounts:edit_request_detail', pk=pk)

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def edit_request_reject(request, pk):
    edit_request = get_object_or_404(ClientEditRequest, pk=pk)
    if edit_request.status != ClientEditRequest.STATUS_PENDING:
        messages.error(request, 'Only pending edit requests can be rejected.')
        return redirect('accounts:edit_request_detail', pk=pk)
    comment = request.POST.get('comment', '')
    if edit_request.reject(request.user, comment):
        messages.success(request, 'Edit request rejected.')
    else:
        messages.error(request, 'Failed to reject edit request.')
    return redirect('accounts:edit_request_detail', pk=pk)

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_STAFF, UserProfile.ROLE_ACCOUNTANT, UserProfile.ROLE_LOAN_OFFICER])
def savings_list(request):
    user_role = get_user_role(request)
    transactions = SavingsTransaction.objects.all().order_by('-transaction_date')
    if user_role == UserProfile.ROLE_STAFF:
        transactions = transactions.filter(processed_by=request.user)
    elif user_role == UserProfile.ROLE_LOAN_OFFICER:
        client_accounts = ClientAccount.objects.filter(loan_officer=request.user)
        transactions = transactions.filter(client_account__in=client_accounts)
    account_filter = request.GET.get('account', '')
    type_filter = request.GET.get('type', '')
    if account_filter:
        transactions = transactions.filter(client_account__account_number__icontains=account_filter)
    if type_filter:
        transactions = transactions.filter(transaction_type=type_filter)
    paginator = Paginator(transactions, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'client_accounts/savings_list.html', {'page_obj': page_obj, 'account_filter': account_filter, 'type_filter': type_filter, 'user_role': user_role})

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_STAFF, UserProfile.ROLE_ACCOUNTANT])
def savings_deposit(request, account_id=None):
    account = None
    if account_id:
        account = get_object_or_404(ClientAccount, pk=account_id)
        user_role = get_user_role(request)
        if user_role not in [UserProfile.ROLE_ADMIN] and account.loan_officer != request.user:
            messages.error(request, 'You do not have permission to deposit to this account.')
            return redirect('accounts:account_list')
    if request.method == 'POST':
        try:
            if not account:
                account_number = request.POST.get('account_number')
                account = get_object_or_404(ClientAccount, account_number=account_number)
            amount = Decimal(request.POST.get('amount'))
            notes = request.POST.get('notes', '')
            transaction = SavingsTransaction(client_account=account, transaction_type='DEPOSIT', amount=amount, processed_by=request.user, notes=notes)
            transaction.save()
            messages.success(request, f'Deposited {amount} to account {account.account_number}.')
            if account_id:
                return redirect('accounts:account_detail', pk=account_id)
            else:
                return redirect('accounts:savings_list')
        except ValidationError as e:
            messages.error(request, f'Validation error: {e}')
        except Exception as e:
            messages.error(request, f'Error processing deposit: {str(e)}')
    accounts = ClientAccount.objects.filter(account_status=ClientAccount.STATUS_ACTIVE)
    return render(request, 'client_accounts/savings_deposit.html', {'account': account, 'accounts': accounts, 'user_role': get_user_role(request)})

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_STAFF, UserProfile.ROLE_ACCOUNTANT])
def savings_withdrawal(request, account_id=None):
    account = None
    if account_id:
        account = get_object_or_404(ClientAccount, pk=account_id)
        user_role = get_user_role(request)
        if user_role not in [UserProfile.ROLE_ADMIN] and account.loan_officer != request.user:
            messages.error(request, 'You do not have permission to withdraw from this account.')
            return redirect('accounts:account_list')
    if request.method == 'POST':
        try:
            if not account:
                account_number = request.POST.get('account_number')
                account = get_object_or_404(ClientAccount, account_number=account_number)
            amount = Decimal(request.POST.get('amount'))
            notes = request.POST.get('notes', '')
            if amount > account.savings_balance:
                messages.error(request, 'Insufficient balance for withdrawal.')
                return render(request, 'client_accounts/savings_withdrawal.html', {'account': account, 'accounts': ClientAccount.objects.filter(account_status=ClientAccount.STATUS_ACTIVE), 'user_role': get_user_role(request)})
            transaction = SavingsTransaction(client_account=account, transaction_type='WITHDRAWAL', amount=amount, processed_by=request.user, notes=notes)
            transaction.save()
            messages.success(request, f'Withdrew {amount} from account {account.account_number}.')
            if account_id:
                return redirect('accounts:account_detail', pk=account_id)
            else:
                return redirect('accounts:savings_list')
        except ValidationError as e:
            messages.error(request, f'Validation error: {e}')
        except Exception as e:
            messages.error(request, f'Error processing withdrawal: {str(e)}')
    accounts = ClientAccount.objects.filter(account_status=ClientAccount.STATUS_ACTIVE)
    return render(request, 'client_accounts/savings_withdrawal.html', {'account': account, 'accounts': accounts, 'user_role': get_user_role(request)})

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_ACCOUNTANT])
def transaction_reverse(request, pk):
    transaction = get_object_or_404(SavingsTransaction, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        try:
            if transaction.reverse_transaction(request.user, reason):
                messages.success(request, f'Transaction {transaction.reference_number} reversed successfully.')
            else:
                messages.error(request, 'Failed to reverse transaction.')
        except ValidationError as e:
            messages.error(request, f'Cannot reverse transaction: {e}')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    return redirect('accounts:savings_list')

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_STAFF, UserProfile.ROLE_ACCOUNTANT, UserProfile.ROLE_LOAN_OFFICER])
def account_savings(request, account_id):
    account = get_object_or_404(ClientAccount, pk=account_id)
    user_role = get_user_role(request)
    if user_role not in [UserProfile.ROLE_ADMIN] and account.loan_officer != request.user:
        messages.error(request, "You do not have permission to view this account's savings.")
        return redirect('accounts:account_list')
    transactions = SavingsTransaction.objects.filter(client_account=account).order_by('-transaction_date')
    return render(request, 'client_accounts/account_savings.html', {'account': account, 'transactions': transactions, 'user_role': user_role})

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER, UserProfile.ROLE_ACCOUNTANT])
def reports_dashboard(request):
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    accounts = ClientAccount.objects.all()
    transactions = SavingsTransaction.objects.all()
    if start_date:
        accounts = accounts.filter(registration_date__gte=start_date)
        transactions = transactions.filter(transaction_date__gte=start_date)
    if end_date:
        accounts = accounts.filter(registration_date__lte=end_date)
        transactions = transactions.filter(transaction_date__lte=end_date)
    stats = {'total_accounts': accounts.count(), 'active_accounts': accounts.filter(account_status=ClientAccount.STATUS_ACTIVE).count(), 'pending_accounts': accounts.filter(account_status=ClientAccount.STATUS_PENDING).count(), 'total_savings': accounts.aggregate(total=Sum('savings_balance'))['total'] or Decimal('0'), 'total_deposits': transactions.filter(transaction_type='DEPOSIT').aggregate(total=Sum('amount'))['total'] or Decimal('0'), 'total_withdrawals': transactions.filter(transaction_type='WITHDRAWAL').aggregate(total=Sum('amount'))['total'] or Decimal('0')}
    account_types = accounts.values('account_type').annotate(count=Count('id'))
    top_savings = accounts.filter(account_status=ClientAccount.STATUS_ACTIVE).order_by('-savings_balance')[:10]
    recent_transactions = transactions.order_by('-transaction_date')[:10]
    context = {'stats': stats, 'account_types': account_types, 'top_savings': top_savings, 'recent_transactions': recent_transactions, 'start_date': start_date, 'end_date': end_date, 'user_role': get_user_role(request)}
    return render(request, 'client_accounts/reports_dashboard.html', context)

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_STAFF, UserProfile.ROLE_MANAGER, UserProfile.ROLE_ACCOUNTANT, UserProfile.ROLE_LOAN_OFFICER])
def api_account_list(request):
    user_role = get_user_role(request)
    accounts = ClientAccount.objects.all()
    if user_role == UserProfile.ROLE_STAFF:
        accounts = accounts.filter(loan_officer=request.user)
    elif user_role == UserProfile.ROLE_LOAN_OFFICER:
        accounts = accounts.filter(loan_officer=request.user)
    data = list(accounts.values('id', 'account_number', 'account_type', 'account_status', 'person1_first_name', 'person1_last_name', 'savings_balance'))
    return JsonResponse(data, safe=False)

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_STAFF, UserProfile.ROLE_MANAGER, UserProfile.ROLE_ACCOUNTANT, UserProfile.ROLE_LOAN_OFFICER])
def api_account_detail(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    user_role = get_user_role(request)
    if user_role not in [UserProfile.ROLE_ADMIN] and account.loan_officer != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    data = {'id': account.id, 'account_number': account.account_number, 'account_type': account.account_type, 'account_status': account.account_status, 'person1_first_name': account.person1_first_name, 'person1_last_name': account.person1_last_name, 'person1_contact': account.person1_contact, 'person1_nin': account.person1_nin, 'savings_balance': str(account.savings_balance), 'total_savings_deposited': str(account.total_savings_deposited), 'registration_date': account.registration_date.isoformat()}
    return JsonResponse(data)

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_STAFF, UserProfile.ROLE_MANAGER, UserProfile.ROLE_ACCOUNTANT, UserProfile.ROLE_LOAN_OFFICER])
def api_savings_balance(request, account_id):
    account = get_object_or_404(ClientAccount, pk=account_id)
    user_role = get_user_role(request)
    if user_role not in [UserProfile.ROLE_ADMIN] and account.loan_officer != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    return JsonResponse({'account_number': account.account_number, 'balance': str(account.savings_balance), 'last_update': account.last_savings_date.isoformat() if account.last_savings_date else None})

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER])
def export_accounts_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="accounts_%s.csv"' % timezone.now().strftime('%Y%m%d')
    writer = csv.writer(response)
    writer.writerow(['Account Number', 'Account Type', 'Status', 'Primary Holder', 'Primary NIN', 'Primary Contact', 'Secondary Holder', 'Secondary NIN', 'Secondary Contact', 'Business Location', 'Business Sector', 'Savings Balance', 'Total Deposited', 'Registration Date'])
    for acc in ClientAccount.objects.all().order_by('-registration_date'):
        primary_holder = f'{acc.person1_first_name} {acc.person1_last_name}'
        secondary_holder = f'{acc.person2_first_name} {acc.person2_last_name}' if acc.person2_first_name else ''
        writer.writerow([acc.account_number, acc.get_account_type_display(), acc.get_account_status_display(), primary_holder, acc.person1_nin, acc.person1_contact, secondary_holder, acc.person2_nin or '', acc.person2_contact or '', acc.business_location, acc.business_sector, acc.savings_balance, acc.total_savings_deposited, acc.registration_date.strftime('%Y-%m-%d %H:%M:%S')])
    return response

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER])
def export_transactions_csv(request, account_id=None):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions_%s.csv"' % timezone.now().strftime('%Y%m%d')
    if account_id:
        account = get_object_or_404(ClientAccount, pk=account_id)
        filename = f"transactions_{account.account_number}_{timezone.now().strftime('%Y%m%d')}.csv"
        transactions = SavingsTransaction.objects.filter(client_account=account)
    else:
        filename = f"transactions_all_{timezone.now().strftime('%Y%m%d')}.csv"
        transactions = SavingsTransaction.objects.all()
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(['Reference', 'Account Number', 'Transaction Type', 'Amount', 'Date', 'Processed By', 'Notes', 'Status'])
    for tx in SavingsTransaction.objects.all().order_by('-transaction_date'):
        writer.writerow([tx.reference_number, tx.client_account.account_number, tx.get_transaction_type_display(), tx.amount, tx.transaction_date.strftime('%Y-%m-%d %H:%M:%S'), tx.processed_by.username if tx.processed_by else '', tx.notes, tx.transaction_status])
    return response

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def audit_logs(request):
    logs = ClientAuditLog.objects.all().order_by('-timestamp')
    action_filter = request.GET.get('action', '')
    account_filter = request.GET.get('account', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    if action_filter:
        logs = logs.filter(action=action_filter)
    if account_filter:
        logs = logs.filter(client__account_number__icontains=account_filter)
    if start_date:
        logs = logs.filter(timestamp__gte=start_date)
    if end_date:
        logs = logs.filter(timestamp__lte=end_date)
    unique_users = logs.exclude(performed_by__isnull=True).values('performed_by').distinct().count()
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    if request.GET.get('export') == 'csv':
        return export_audit_logs_csv(logs)
    return render(request, 'client_accounts/audit_logs.html', {'page_obj': page_obj, 'action_filter': action_filter, 'account_filter': account_filter, 'start_date': start_date, 'end_date': end_date, 'unique_users': unique_users})

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_STAFF, UserProfile.ROLE_MANAGER, UserProfile.ROLE_ACCOUNTANT, UserProfile.ROLE_LOAN_OFFICER])
def search_accounts(request):
    query = request.GET.get('q', '')
    if not query or len(query) < 2:
        return JsonResponse([], safe=False)
    accounts = ClientAccount.objects.filter(Q(account_number__icontains=query) | Q(person1_first_name__icontains=query) | Q(person1_last_name__icontains=query) | Q(person1_nin__icontains=query) | Q(person2_first_name__icontains=query) | Q(person2_last_name__icontains=query) | Q(person2_nin__icontains=query)).filter(account_status=ClientAccount.STATUS_ACTIVE)[:10]
    results = []
    for acc in accounts:
        results.append({'id': acc.id, 'account_number': acc.account_number, 'name': acc.full_account_name, 'balance': str(acc.savings_balance)})
    return JsonResponse(results, safe=False)

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def approve_loan(request, pk):
    loan = get_object_or_404(LoanApplication, pk=pk)
    loan.status = 'APPROVED'
    loan.approved_by = request.user
    loan.save()
    messages.success(request, f'Loan {loan.id} approved.')
    return redirect('loans:loan_list')

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def reject_loan(request, pk):
    loan = get_object_or_404(LoanApplication, pk=pk)
    loan.status = 'REJECTED'
    loan.approved_by = request.user
    loan.save()
    messages.success(request, f'Loan {loan.id} rejected.')
    return redirect('loans:loan_list')

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def disburse_loan(request, pk):
    loan = get_object_or_404(LoanApplication, pk=pk)
    if loan.status != 'APPROVED':
        messages.error(request, 'Cannot disburse a loan that is not approved.')
        return redirect('loans:loan_list')
    loan.status = 'DISBURSED'
    loan.disbursed_by = request.user
    loan.save()
    messages.success(request, f'Loan {loan.id} disbursed successfully.')
    return redirect('loans:loan_list')

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def account_delete(request, pk):
    account = get_object_or_404(ClientAccount, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Account closed by admin')
        try:
            integrity_issues = []
            if not account.created_by:
                integrity_issues.append("Account missing 'created_by' field")
            if not account.loan_officer:
                integrity_issues.append("Account missing 'loan_officer' field")
            if integrity_issues:
                messages.error(request, f"Cannot close account due to data integrity issues: {', '.join(integrity_issues)}")
                return redirect('accounts:account_detail', pk=account.pk)
            account.change_status(ClientAccount.STATUS_CLOSED, request.user, reason)
            messages.success(request, f'Account {account.account_number} has been closed.')
            return redirect('accounts:account_list')
        except ValidationError as e:
            error_message = 'Validation error: '
            for field, errors in e.message_dict.items():
                error_message += f"{field}: {', '.join(errors)} "
            messages.error(request, error_message.strip())
            return render(request, 'client_accounts/account_confirm_delete.html', {'account': account, 'error': error_message})
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {str(e)}')
            return render(request, 'client_accounts/account_confirm_delete.html', {'account': account, 'error': str(e)})
    return render(request, 'client_accounts/account_confirm_delete.html', {'account': account})

@login_required
def savings_transactions(request):
    user_role = get_user_role(request)
    transactions = SavingsTransaction.objects.all().order_by('-transaction_date')
    if user_role == UserProfile.ROLE_STAFF:
        transactions = transactions.filter(processed_by=request.user)
    elif user_role == UserProfile.ROLE_LOAN_OFFICER:
        client_accounts = ClientAccount.objects.filter(loan_officer=request.user)
        transactions = transactions.filter(client_account__in=client_accounts)
    account_filter = request.GET.get('account', '')
    type_filter = request.GET.get('type', '')
    if account_filter:
        transactions = transactions.filter(client_account__account_number__icontains=account_filter)
    if type_filter:
        transactions = transactions.filter(transaction_type=type_filter)
    paginator = Paginator(transactions, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {'page_obj': page_obj, 'account_filter': account_filter, 'type_filter': type_filter, 'user_role': user_role}
    return render(request, 'client_accounts/savings_transactions.html', context)

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def export_accounts_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="accounts.pdf"'
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    p.setFont('Helvetica-Bold', 14)
    p.drawString(1 * inch, height - 1 * inch, 'Client Accounts Report')
    p.setFont('Helvetica', 11)
    y = height - 1.5 * inch
    p.drawString(1 * inch, y, 'Account Number     Account Type     Full Name     Balance')
    y -= 0.3 * inch
    for acc in ClientAccount.objects.all().order_by('-registration_date'):
        line = f'{acc.account_number}     {acc.account_type}     {acc.full_account_name}     {acc.savings_balance}'
        p.drawString(1 * inch, y, line)
        y -= 0.25 * inch
        if y <= 1 * inch:
            p.showPage()
            p.setFont('Helvetica', 11)
            y = height - 1 * inch
    p.showPage()
    p.save()
    return response

@login_required
@role_required([UserProfile.ROLE_ADMIN])
def export_transactions_pdf(request, account_id=None):
    response = HttpResponse(content_type='application/pdf')
    if account_id:
        account = get_object_or_404(ClientAccount, pk=account_id)
        filename = f'transactions_{account.account_number}.pdf'
        transactions = SavingsTransaction.objects.filter(client_account=account)
    else:
        filename = 'transactions_all.pdf'
        transactions = SavingsTransaction.objects.all()
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    p.setFont('Helvetica-Bold', 14)
    if account_id:
        p.drawString(1 * inch, height - 1 * inch, f'Savings Transactions Report - {account.account_number}')
    else:
        p.drawString(1 * inch, height - 1 * inch, 'Savings Transactions Report')
    p.setFont('Helvetica', 11)
    y = height - 1.5 * inch
    p.drawString(1 * inch, y, 'Account Number     Type     Amount     Date     Processed By')
    y -= 0.3 * inch
    for tx in transactions.order_by('-transaction_date'):
        line = f"{tx.client_account.account_number}     {tx.transaction_type}     {tx.amount}     {tx.transaction_date.strftime('%Y-%m-%d')}     {(tx.processed_by.username if tx.processed_by else 'System')}"
        p.drawString(1 * inch, y, line)
        y -= 0.25 * inch
        if y <= 1 * inch:
            p.showPage()
            p.setFont('Helvetica', 11)
            y = height - 1 * inch
    p.showPage()
    p.save()
    return response

def export_audit_logs_csv(queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_logs_%s.csv"' % timezone.now().strftime('%Y%m%d_%H%M%S')
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Account Number', 'Account Name', 'Action', 'Performed By', 'Performed By Email', 'Changed Fields', 'Notes'])
    for log in queryset:
        changed_fields = []
        if log.changed_data:
            changed_fields = list(log.changed_data.keys())
        writer.writerow([log.timestamp.strftime('%Y-%m-%d %H:%M:%S'), log.client.account_number if log.client else '', log.client.full_account_name if log.client else '', log.get_action_display(), log.performed_by.get_full_name() if log.performed_by else 'System', log.performed_by.email if log.performed_by else '', ', '.join(changed_fields), log.note or ''])
    return response