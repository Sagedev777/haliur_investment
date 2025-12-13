from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum, Count, Avg, Max, Min, F, ExpressionWrapper, DecimalField
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
User = get_user_model()
import json
import csv
import xlwt
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from .models import LoanProduct, LoanApplication, Loan, LoanTransaction, LoanRepaymentSchedule, Guarantor, LoanPayment, LoanApplicationDocument
from client_accounts.models import ClientAccount
from .forms import LoanProductForm, LoanApplicationForm, LoanApprovalForm, LoanDisbursementForm, LoanPaymentForm, GuarantorForm, LoanCalculatorForm, LoanSearchForm, BulkPaymentForm
from .services import InterestCalculationService, CreditScoringService, PaymentProcessingService, AmortizationService
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import Loan
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta, datetime
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from client_accounts.models import UserProfile
from datetime import datetime, timedelta, date

# Copy the decorator functions
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
            messages.error(request, "You do not have permission to access this page.")
            return redirect('accounts:dashboard')
        return _wrapped_view
    return decorator

def get_user_role(request):
    if request.user.is_superuser:
        return 'ADMIN'
    try:
        return request.user.profile.role
    except UserProfile.DoesNotExist:
        return None

@login_required
@require_http_methods(["GET"])
def api_loan_details(request):
    """API endpoint for loan details"""
    loan_number = request.GET.get('loan_number')
    
    if not loan_number:
        return JsonResponse({'success': False, 'error': 'Loan number required'}, status=400)
    
    try:
        loan = Loan.objects.get(loan_number=loan_number)
        
        return JsonResponse({
            'success': True,
            'client_name': loan.client.name,
            'principal_amount': float(loan.amount),
            'remaining_balance': float(loan.remaining_balance),
            'status': loan.status,
            'next_payment_date': loan.next_payment_date.strftime('%Y-%m-%d') if loan.next_payment_date else None,
        })
    except Loan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Loan not found'}, status=404)

@login_required
@require_http_methods(["GET"])
def api_loan_search(request):
    """API endpoint for searching loans"""
    query = request.GET.get('q', '')
    
    loans = Loan.objects.filter(
        client__name__icontains=query
    ).select_related('client')[:10]
    
    results = [
        {
            'id': loan.id,
            'loan_number': loan.loan_number,
            'client_name': loan.client.name,
            'amount': float(loan.amount),
            'status': loan.status,
        }
        for loan in loans
    ]
    
    return JsonResponse({
        'success': True,
        'results': results
    })
    

class StaffRequiredMixin(UserPassesTestMixin):

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        messages.error(self.request, 'Access denied. Staff members only.')
        return redirect('admin:index')

class LoanOfficerRequiredMixin(UserPassesTestMixin):

    def test_func(self):
        return self.request.user.is_staff or self.request.user.groups.filter(name='Loan Officers').exists()

    def handle_no_permission(self):
        messages.error(self.request, 'Access denied. Loan officers only.')
        return redirect('admin:index')

def staff_required(view_func):

    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, 'Access denied. Staff members only.')
            return redirect('admin:index')
        return view_func(request, *args, **kwargs)
    return wrapper

def loan_officer_required(view_func):

    def wrapper(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.groups.filter(name='Loan Officers').exists()):
            messages.error(request, 'Access denied. Loan officers only.')
            return redirect('admin:index')
        return view_func(request, *args, **kwargs)
    return wrapper

class LoanDashboardView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    template_name = 'loans/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_loans'] = Loan.objects.count()
        context['active_loans'] = Loan.objects.filter(status='ACTIVE').count()
        context['overdue_loans'] = Loan.objects.filter(status='OVERDUE').count()
        context['pending_applications'] = LoanApplication.objects.filter(status__in=['SUBMITTED', 'UNDER_REVIEW']).count()
        context['total_portfolio'] = Loan.objects.filter(status__in=['ACTIVE', 'OVERDUE']).aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0')
        context['total_disbursed'] = Loan.objects.aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')
        context['total_interest_earned'] = LoanTransaction.objects.filter(transaction_type='INTEREST_PAYMENT').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        context['total_collections_today'] = LoanTransaction.objects.filter(transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT'], value_date=timezone.now().date()).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        context['recent_applications'] = LoanApplication.objects.filter(status__in=['SUBMITTED', 'UNDER_REVIEW']).select_related('client', 'loan_product', 'loan_officer').order_by('-application_date')[:10]
        context['upcoming_payments'] = LoanRepaymentSchedule.objects.filter(status__in=['PENDING', 'DUE'], due_date__lte=timezone.now().date() + timedelta(days=7), due_date__gte=timezone.now().date()).select_related('loan', 'loan__client').order_by('due_date')[:10]
        context['overdue_list'] = Loan.objects.filter(status='OVERDUE').select_related('client', 'loan_product').order_by('-days_overdue')[:10]
        if self.request.user.is_superuser:
            context['officer_performance'] = User.objects.filter(groups__name='Loan Officers').annotate(total_loans=Count('assigned_applications'), total_disbursed=Sum('assigned_applications__loan__principal_amount')).order_by('-total_disbursed')[:5]
        today = timezone.now().date()
        context['applications_today'] = LoanApplication.objects.filter(application_date__date=today).count()
        context['disbursements_today'] = Loan.objects.filter(disbursement_date=today).aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')
        context['payments_today'] = LoanTransaction.objects.filter(value_date=today, transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT']).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return context

@login_required
@staff_required
def dashboard_summary_api(request):
    today = timezone.now().date()
    data = {'total_portfolio': float(Loan.objects.filter(status__in=['ACTIVE', 'OVERDUE']).aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0')), 'overdue_amount': float(Loan.objects.filter(status='OVERDUE').aggregate(total=Sum('overdue_amount'))['total'] or Decimal('0')), 'today_collections': float(LoanTransaction.objects.filter(transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT'], value_date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0')), 'pending_applications': LoanApplication.objects.filter(status__in=['SUBMITTED', 'UNDER_REVIEW']).count(), 'active_loans': Loan.objects.filter(status='ACTIVE').count(), 'overdue_loans': Loan.objects.filter(status='OVERDUE').count(), 'timestamp': timezone.now().isoformat()}
    return JsonResponse(data)

class LoanProductListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    model = LoanProduct
    template_name = 'loans/loanproduct_list.html'
    context_object_name = 'products'
    paginate_by = 20

    def get_queryset(self):
        queryset = LoanProduct.objects.all().order_by('-created_date')
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=is_active == 'true')
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(description__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_count'] = LoanProduct.objects.filter(is_active=True).count()
        context['inactive_count'] = LoanProduct.objects.filter(is_active=False).count()
        context['total_products'] = LoanProduct.objects.count()
        return context

class LoanProductCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    model = LoanProduct
    form_class = LoanProductForm
    template_name = 'loans/loanproduct_form.html'
    success_url = reverse_lazy('loans:loan_product_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f"Loan product '{form.instance.name}' created successfully!")
        return super().form_valid(form)

class LoanProductUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    model = LoanProduct
    form_class = LoanProductForm
    template_name = 'loans/loanproduct_form.html'
    success_url = reverse_lazy('loans:loan_product_list')

    def form_valid(self, form):
        messages.success(self.request, f"Loan product '{form.instance.name}' updated successfully!")
        return super().form_valid(form)

class LoanProductDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    model = LoanProduct
    template_name = 'loans/loanproduct_confirm_delete.html'
    success_url = reverse_lazy('loans:loan_product_list')

    def delete(self, request, *args, **kwargs):
        product = self.get_object()
        messages.success(request, f"Loan product '{product.name}' deleted successfully!")
        return super().delete(request, *args, **kwargs)

@login_required
@staff_required
def loan_product_toggle_status(request, pk):
    product = get_object_or_404(LoanProduct, pk=pk)
    product.is_active = not product.is_active
    product.save()
    status = 'activated' if product.is_active else 'deactivated'
    messages.success(request, f"Loan product '{product.name}' {status} successfully!")
    return redirect('loans:loan_product_list')

class LoanApplicationListView(LoginRequiredMixin, LoanOfficerRequiredMixin, ListView):
    model = LoanApplication
    template_name = 'loans/loanapplication_list.html'
    context_object_name = 'applications'
    paginate_by = 20

    def get_queryset(self):
        queryset = LoanApplication.objects.select_related('client', 'loan_product', 'loan_officer').prefetch_related('guarantors').order_by('-application_date')
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        if not self.request.user.is_superuser:
            queryset = queryset.filter(loan_officer=self.request.user)
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from and date_to:
            queryset = queryset.filter(application_date__date__range=[date_from, date_to])
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(Q(application_number__icontains=search) | Q(client__full_account_name__icontains=search) | Q(client__account_number__icontains=search) | Q(purpose__icontains=search))
        min_amount = self.request.GET.get('min_amount')
        max_amount = self.request.GET.get('max_amount')
        if min_amount:
            queryset = queryset.filter(requested_amount__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(requested_amount__lte=max_amount)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status_counts = {}
        for status_choice in LoanApplication.APPLICATION_STATUS:
            status_counts[status_choice[0]] = LoanApplication.objects.filter(status=status_choice[0]).count()
        context['status_counts'] = status_counts
        context['total_applications'] = LoanApplication.objects.count()
        context['search_form'] = LoanSearchForm(self.request.GET or None)
        return context

class LoanApplicationCreateView(LoginRequiredMixin, LoanOfficerRequiredMixin, CreateView):
    model = LoanApplication
    form_class = LoanApplicationForm
    template_name = 'loans/loanapplication_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clients'] = ClientAccount.objects.all().order_by('person1_first_name')
        context['products'] = LoanProduct.objects.all()
        context['guarantors'] = Guarantor.objects.filter(is_active=True, verified=True)
        return context

    def form_valid(self, form):
        with transaction.atomic():
            application = form.save(commit=False)
            application.loan_officer = self.request.user
            application.created_by = self.request.user
            application.status = 'SUBMITTED'
            application.submitted_date = timezone.now()
            if hasattr(application, 'calculate_credit_score'):
                application.credit_score = application.calculate_credit_score()
                if application.credit_score >= 80:
                    application.risk_rating = 'A'
                elif application.credit_score >= 60:
                    application.risk_rating = 'B'
                elif application.credit_score >= 40:
                    application.risk_rating = 'C'
                else:
                    application.risk_rating = 'D'
            application.save()
            form.save_m2m()
            if 'collateral_documents' in form.cleaned_data:
                collateral_docs = form.cleaned_data.get('collateral_documents')
                if collateral_docs:
                    application.collateral_documents.set(collateral_docs)
            documents = self.request.FILES.getlist('documents')
            for document in documents:
                LoanApplicationDocument.objects.create(loan_application=application, document=document)
            messages.success(self.request, f'Loan application {application.application_number} submitted successfully!')
        return redirect('loans:loan_application_detail', pk=application.pk)

class LoanApplicationDetailView(LoginRequiredMixin, LoanOfficerRequiredMixin, DetailView):
    model = LoanApplication
    template_name = 'loans/loanapplication_detail.html'
    context_object_name = 'application'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.get_object()
        if hasattr(application.client, 'monthly_income') and application.client.monthly_income:
            context['debt_to_income_ratio'] = (application.requested_amount + sum((loan.remaining_balance for loan in application.client.loans.filter(status__in=['ACTIVE', 'OVERDUE'])))) / application.client.monthly_income
        context['similar_applications'] = LoanApplication.objects.filter(loan_product=application.loan_product, status='APPROVED', client__monthly_income__range=[application.client.monthly_income * Decimal('0.8') if application.client.monthly_income else Decimal('0'), application.client.monthly_income * Decimal('1.2') if application.client.monthly_income else Decimal('1000000')]).exclude(pk=application.pk)[:5]
        if application.client.current_balance:
            recommended_amount = min(application.requested_amount, application.client.current_balance * Decimal('3'), application.client.monthly_income * Decimal('6') if application.client.monthly_income else Decimal('1000000'))
            context['recommended_amount'] = recommended_amount.quantize(Decimal('1000'), rounding=ROUND_HALF_UP)
        return context

class LoanApplicationUpdateView(LoginRequiredMixin, LoanOfficerRequiredMixin, UpdateView):
    model = LoanApplication
    form_class = LoanApplicationForm
    template_name = 'loans/loanapplication_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            application = form.save(commit=False)
            if 'requested_amount' in form.changed_data:
                application.credit_score = application.calculate_credit_score()
                if application.credit_score >= 80:
                    application.risk_rating = 'A'
                elif application.credit_score >= 60:
                    application.risk_rating = 'B'
                elif application.credit_score >= 40:
                    application.risk_rating = 'C'
                else:
                    application.risk_rating = 'D'
            application.save()
            form.save_m2m()
            messages.success(self.request, f'Loan application {application.application_number} updated successfully!')
        return redirect('loans:loan_application_detail', pk=application.pk)

@login_required
@staff_required
def loan_application_review(request, pk):
    application = get_object_or_404(LoanApplication, pk=pk)
    if request.method == 'POST':
        form = LoanApprovalForm(request.POST, instance=application)
        if form.is_valid():
            with transaction.atomic():
                updated_application = form.save(commit=False)
                updated_application.reviewed_by = request.user
                updated_application.review_date = timezone.now()
                if updated_application.status == 'APPROVED':
                    product = updated_application.loan_product
                    processing_fee = updated_application.approved_amount * product.processing_fee_percent / Decimal('100')
                    updated_application.processing_fee_amount = processing_fee
                    updated_application.net_disbursement_amount = updated_application.approved_amount - processing_fee
                    interest_service = InterestCalculationService()
                    total_interest = interest_service.calculate_interest(updated_application.approved_amount, updated_application.approved_interest_rate, updated_application.approved_term_days, method=product.interest_calculation_method, interest_type=product.interest_type)
                    updated_application.total_interest_amount = total_interest
                    updated_application.total_repayment_amount = updated_application.approved_amount + total_interest
                    updated_application.approval_date = timezone.now()
                    updated_application.approved_by = request.user
                updated_application.save()
                if updated_application.status == 'APPROVED':
                    messages.success(request, f'Application {application.application_number} approved! You can now disburse the loan.')
                    return redirect('loans:loan_disbursement_create', application_id=application.pk)
                else:
                    messages.success(request, f'Application {application.application_number} updated successfully!')
                    return redirect('loans:loan_application_detail', pk=application.pk)
    else:
        form = LoanApprovalForm(instance=application)
    existing_loans = Loan.objects.filter(client=application.client, status__in=['ACTIVE', 'OVERDUE']).select_related('loan_product')
    total_existing_debt = sum((loan.remaining_balance for loan in existing_loans))
    max_loan_by_savings = application.client.current_balance * Decimal('3')
    max_loan_by_income = Decimal('0')
    if hasattr(application.client, 'monthly_income') and application.client.monthly_income:
        max_loan_by_income = application.client.monthly_income * Decimal('6')
    context = {'application': application, 'form': form, 'existing_loans': existing_loans, 'total_existing_debt': total_existing_debt, 'max_loan_by_savings': max_loan_by_savings, 'max_loan_by_income': max_loan_by_income, 'recommended_amount': min(application.requested_amount, max_loan_by_savings, max_loan_by_income)}
    return render(request, 'loans/loanapplication_review.html', context)

@login_required
@staff_required
def loan_application_documents(request, pk):
    application = get_object_or_404(LoanApplication, pk=pk)
    if request.method == 'POST' and request.FILES.getlist('documents'):
        documents = request.FILES.getlist('documents')
        for document in documents:
            LoanApplicationDocument.objects.create(loan_application=application, document=document)
        messages.success(request, f'{len(documents)} document(s) uploaded successfully!')
        return redirect('loans:loan_application_documents', pk=application.pk)
    documents = application.documents.all()
    return render(request, 'loans/loanapplication_documents.html', {'application': application, 'documents': documents})

@login_required
@staff_required
def loan_disbursement_create(request, application_id):
    application = get_object_or_404(LoanApplication, pk=application_id, status='APPROVED')
    if request.method == 'POST':
        form = LoanDisbursementForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    loan = Loan.objects.create(application=application, client=application.client, loan_product=application.loan_product, principal_amount=application.approved_amount, interest_rate=application.approved_interest_rate, term_days=application.approved_term_days, disbursement_date=form.cleaned_data['disbursement_date'], disbursed_by=request.user, loan_officer=application.loan_officer, status='PENDING_DISBURSEMENT', remaining_balance=application.total_repayment_amount, total_interest_amount=application.total_interest_amount, total_repayment_amount=application.total_repayment_amount, processing_fee_amount=application.processing_fee_amount)
                    amortization_service = AmortizationService()
                    schedule_data = amortization_service.generate_amortization_schedule(loan)
                    for installment_data in schedule_data:
                        LoanRepaymentSchedule.objects.create(loan=loan, installment_number=installment_data['installment_number'], due_date=installment_data['due_date'], principal_amount=installment_data['principal_amount'], interest_amount=installment_data['interest_amount'], total_amount=installment_data['total_amount'], status='PENDING')
                    first_installment = loan.repayment_schedule.order_by('due_date').first()
                    if first_installment:
                        loan.first_payment_date = first_installment.due_date
                        loan.next_payment_date = first_installment.due_date
                    loan.status = 'ACTIVE'
                    loan.save()
                    LoanTransaction.objects.create(loan=loan, transaction_type='DISBURSEMENT', payment_method=form.cleaned_data['payment_method'], amount=application.net_disbursement_amount, principal_amount=application.approved_amount, fee_amount=application.processing_fee_amount, notes=f'Loan disbursement for {application.application_number}', recorded_by=request.user, reference_number=form.cleaned_data.get('transaction_reference', ''))
                    application.status = 'DISBURSED'
                    application.save()
                    messages.success(request, f'Loan {loan.loan_number} created and disbursed successfully!')
                    return redirect('loans:loan_detail', pk=loan.pk)
            except Exception as e:
                messages.error(request, f'Error creating loan: {str(e)}')
    else:
        initial_data = {'disbursement_date': timezone.now().date(), 'payment_method': 'BANK_TRANSFER'}
        form = LoanDisbursementForm(initial=initial_data)
    context = {'application': application, 'form': form, 'title': f'Disburse Loan for {application.application_number}'}
    return render(request, 'loans/loan_disbursement_create.html', context)

@login_required
@staff_required
def bulk_loan_disbursement(request):
    if request.method == 'POST':
        loan_ids = request.POST.getlist('loan_ids')
        payment_method = request.POST.get('payment_method', 'BANK_TRANSFER')
        disbursement_date = request.POST.get('disbursement_date', timezone.now().date())
        reference_prefix = request.POST.get('reference_prefix', '')
        loans = Loan.objects.filter(pk__in=loan_ids, status='PENDING_DISBURSEMENT').select_related('application', 'client', 'loan_product')
        disbursed_count = 0
        errors = []
        for loan in loans:
            try:
                with transaction.atomic():
                    loan.disbursement_date = disbursement_date
                    loan.status = 'ACTIVE'
                    if disbursement_date and loan.term_days:
                        loan.maturity_date = disbursement_date + timedelta(days=loan.term_days)
                    if not loan.repayment_schedule.exists():
                        amortization_service = AmortizationService()
                        schedule_data = amortization_service.generate_amortization_schedule(loan)
                        for installment_data in schedule_data:
                            LoanRepaymentSchedule.objects.create(loan=loan, installment_number=installment_data['installment_number'], due_date=installment_data['due_date'], principal_amount=installment_data['principal_amount'], interest_amount=installment_data['interest_amount'], total_amount=installment_data['total_amount'], status='PENDING')
                    first_installment = loan.repayment_schedule.order_by('due_date').first()
                    if first_installment:
                        loan.first_payment_date = first_installment.due_date
                        loan.next_payment_date = first_installment.due_date
                    loan.save()
                    LoanTransaction.objects.create(loan=loan, transaction_type='DISBURSEMENT', payment_method=payment_method, amount=loan.application.net_disbursement_amount, principal_amount=loan.principal_amount, fee_amount=loan.processing_fee_amount, notes=f'Bulk loan disbursement', recorded_by=request.user, reference_number=f'{reference_prefix}-{loan.loan_number}' if reference_prefix else loan.loan_number)
                    if loan.application:
                        loan.application.status = 'DISBURSED'
                        loan.application.save()
                    disbursed_count += 1
            except Exception as e:
                errors.append(f'Loan {loan.loan_number}: {str(e)}')
        if disbursed_count > 0:
            messages.success(request, f'{disbursed_count} loans disbursed successfully!')
        if errors:
            messages.error(request, f"Errors: {', '.join(errors[:5])}" + ('...' if len(errors) > 5 else ''))
        return redirect('loans:loan_list')
    pending_loans = Loan.objects.filter(status='PENDING_DISBURSEMENT').select_related('client', 'loan_product').order_by('created_at')
    return render(request, 'loans/bulk_disbursement.html', {'pending_loans': pending_loans})

class LoanListView(LoginRequiredMixin, LoanOfficerRequiredMixin, ListView):
    model = Loan
    template_name = 'loans/loan_list.html'
    context_object_name = 'loans'
    paginate_by = 20

    def get_queryset(self):
        queryset = Loan.objects.select_related('client', 'loan_product', 'loan_officer', 'application').order_by('-disbursement_date')
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if not self.request.user.is_superuser:
            queryset = queryset.filter(loan_officer=self.request.user)
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(Q(loan_number__icontains=search_query) | Q(client__full_account_name__icontains=search_query) | Q(client__account_number__icontains=search_query) | Q(client__phone_number__icontains=search_query))
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from and date_to:
            queryset = queryset.filter(disbursement_date__range=[date_from, date_to])
        min_amount = self.request.GET.get('min_amount')
        max_amount = self.request.GET.get('max_amount')
        if min_amount:
            queryset = queryset.filter(principal_amount__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(principal_amount__lte=max_amount)
        product_id = self.request.GET.get('product')
        if product_id:
            queryset = queryset.filter(loan_product_id=product_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_loans'] = Loan.objects.count()
        context['total_portfolio'] = Loan.objects.filter(status__in=['ACTIVE', 'OVERDUE']).aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0')
        context['overdue_amount'] = Loan.objects.filter(status='OVERDUE').aggregate(total=Sum('overdue_amount'))['total'] or Decimal('0')
        status_counts = {}
        for status_choice in Loan.LOAN_STATUS:
            status_counts[status_choice[0]] = Loan.objects.filter(status=status_choice[0]).count()
        context['status_counts'] = status_counts
        context['search_form'] = LoanSearchForm(self.request.GET or None)
        context['products'] = LoanProduct.objects.filter(is_active=True)
        return context

class LoanDetailView(LoginRequiredMixin, LoanOfficerRequiredMixin, DetailView):
    model = Loan
    template_name = 'loans/loan_detail.html'
    context_object_name = 'loan'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan = self.get_object()
        repayment_schedule = loan.repayment_schedule.all().order_by('installment_number')
        context['repayment_schedule'] = repayment_schedule
        transactions = loan.transactions.all().order_by('-transaction_date')
        context['transactions'] = transactions
        payments = loan.payments.all().order_by('-payment_date')
        context['payments'] = payments
        total_paid = loan.transactions.filter(transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT']).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        context['total_paid'] = total_paid
        context['remaining_percent'] = loan.remaining_balance / loan.total_repayment_amount * 100 if loan.total_repayment_amount > 0 else 0
        next_installment = repayment_schedule.filter(status__in=['PENDING', 'DUE']).order_by('due_date').first()
        context['next_installment'] = next_installment
        context['days_until_next'] = (next_installment.due_date - timezone.now().date()).days if next_installment else None
        context['overdue_installments'] = repayment_schedule.filter(status__in=['DUE', 'OVERDUE'], due_date__lt=timezone.now().date()).order_by('due_date')
        context['payment_summary'] = {'principal_paid': loan.transactions.filter(transaction_type='PRINCIPAL_PAYMENT').aggregate(total=Sum('amount'))['total'] or Decimal('0'), 'interest_paid': loan.transactions.filter(transaction_type='INTEREST_PAYMENT').aggregate(total=Sum('amount'))['total'] or Decimal('0'), 'late_fees_paid': loan.transactions.filter(transaction_type='LATE_FEE_PAYMENT').aggregate(total=Sum('amount'))['total'] or Decimal('0')}
        return context

@login_required
@loan_officer_required
def loan_statement(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    transactions = loan.transactions.all().order_by('transaction_date')
    running_balance = loan.total_repayment_amount
    statement_lines = []
    for transaction in transactions:
        if transaction.transaction_type == 'DISBURSEMENT':
            running_balance -= transaction.amount
        elif transaction.transaction_type in ['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT']:
            running_balance += transaction.amount
        statement_lines.append({'date': transaction.value_date, 'description': transaction.get_transaction_type_display(), 'reference': transaction.reference_number or transaction.transaction_id, 'debit': transaction.amount if transaction.transaction_type == 'DISBURSEMENT' else Decimal('0'), 'credit': transaction.amount if transaction.transaction_type != 'DISBURSEMENT' else Decimal('0'), 'balance': running_balance})
    context = {'loan': loan, 'statement_lines': statement_lines, 'generated_date': timezone.now(), 'opening_balance': loan.total_repayment_amount, 'closing_balance': running_balance}
    if request.GET.get('format') == 'pdf':
        return render(request, 'loans/loan_statement_pdf.html', context)
    return render(request, 'loans/loan_statement.html', context)

@login_required
@staff_required
def loan_reschedule(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    if request.method == 'POST':
        new_term_days = int(request.POST.get('new_term_days'))
        new_interest_rate = Decimal(request.POST.get('new_interest_rate', loan.interest_rate))
        reason = request.POST.get('reason', '')
        try:
            amortization_service = AmortizationService()
            result = amortization_service.reschedule_loan(loan=loan, new_term_days=new_term_days, new_interest_rate=new_interest_rate, reschedule_date=timezone.now().date())
            LoanTransaction.objects.create(loan=loan, transaction_type='ADJUSTMENT', payment_method='SYSTEM', amount=Decimal('0'), notes=f'Loan rescheduled: {reason}', recorded_by=request.user)
            messages.success(request, f'Loan {loan.loan_number} rescheduled successfully!')
            return redirect('loans:loan_detail', pk=loan.pk)
        except Exception as e:
            messages.error(request, f'Error rescheduling loan: {str(e)}')
    context = {'loan': loan, 'current_term_days': loan.term_days, 'current_interest_rate': loan.interest_rate}
    return render(request, 'loans/loan_reschedule.html', context)

@login_required
@loan_officer_required
def process_payment(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    if request.method == 'POST':
        form = LoanPaymentForm(request.POST, loan=loan)
        if form.is_valid():
            try:
                with transaction.atomic():
                    payment_service = PaymentProcessingService()
                    allocation = payment_service.process_payment(loan=loan, amount=form.cleaned_data['amount'], payment_date=form.cleaned_data['payment_date'], payment_method=form.cleaned_data['payment_method'], received_by=request.user, notes=form.cleaned_data['notes'], allocation_strategy=form.cleaned_data['allocate_to'])
                    LoanPayment.objects.create(loan=loan, amount=form.cleaned_data['amount'], principal_amount=allocation['principal'], interest_amount=allocation['interest'], late_fee_amount=allocation['late_fees'], status='PAID')
                    messages.success(request, f"Payment of {form.cleaned_data['amount']} processed successfully!\nAllocated: Principal: {allocation['principal']}, Interest: {allocation['interest']}, Late Fees: {allocation['late_fees']}")
                    return redirect('loans:loan_detail', pk=loan.pk)
            except Exception as e:
                messages.error(request, f'Error processing payment: {str(e)}')
    else:
        form = LoanPaymentForm(loan=loan)
    context = {'loan': loan, 'form': form, 'outstanding_balance': loan.remaining_balance, 'overdue_amount': loan.overdue_amount, 'next_payment_date': loan.next_payment_date, 'overdue_installments': loan.repayment_schedule.filter(status__in=['DUE', 'OVERDUE'], due_date__lt=timezone.now().date())}
    return render(request, 'loans/process_payment.html', context)

@login_required
@staff_required
def bulk_payment_processing(request):
    if request.method == 'POST':
        form = BulkPaymentForm(request.POST)
        if form.is_valid():
            loan_ids = form.cleaned_data['loan_ids'].split(',')
            amount = form.cleaned_data['amount']
            payment_method = form.cleaned_data['payment_method']
            payment_date = form.cleaned_data['payment_date']
            reference_prefix = form.cleaned_data.get('reference_prefix', '')
            notes = form.cleaned_data.get('notes', '')
            loans = Loan.objects.filter(pk__in=loan_ids, status__in=['ACTIVE', 'OVERDUE']).select_related('client')
            processed_count = 0
            errors = []
            for loan in loans:
                try:
                    with transaction.atomic():
                        payment_service = PaymentProcessingService()
                        allocation = payment_service.process_payment(loan=loan, amount=amount, payment_date=payment_date, payment_method=payment_method, received_by=request.user, notes=f'{notes} (Bulk payment)', allocation_strategy='AUTO')
                        LoanPayment.objects.create(loan=loan, amount=amount, principal_amount=allocation['principal'], interest_amount=allocation['interest'], late_fee_amount=allocation['late_fees'], status='PAID')
                        processed_count += 1
                except Exception as e:
                    errors.append(f'Loan {loan.loan_number}: {str(e)}')
            if processed_count > 0:
                messages.success(request, f'{processed_count} payments processed successfully!')
            if errors:
                messages.warning(request, f"Errors: {', '.join(errors[:3])}" + ('...' if len(errors) > 3 else ''))
            return redirect('loans:loan_list')
    else:
        form = BulkPaymentForm()
    return render(request, 'loans/bulk_payment.html', {'form': form})

@login_required
@loan_officer_required
def payment_receipt(request, transaction_id):
    transaction = get_object_or_404(LoanTransaction, transaction_id=transaction_id)
    context = {'transaction': transaction, 'loan': transaction.loan, 'generated_date': timezone.now()}
    if request.GET.get('format') == 'pdf':
        return render(request, 'loans/payment_receipt_pdf.html', context)
    return render(request, 'loans/payment_receipt.html', context)

class GuarantorListView(LoginRequiredMixin, LoanOfficerRequiredMixin, ListView):
    model = Guarantor
    template_name = 'loans/guarantor_list.html'
    context_object_name = 'guarantors'
    paginate_by = 20

    def get_queryset(self):
        queryset = Guarantor.objects.select_related('individual').order_by('-created_at')
        guarantor_type = self.request.GET.get('type')
        if guarantor_type:
            queryset = queryset.filter(guarantor_type=guarantor_type)
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=is_active == 'true')
        verified = self.request.GET.get('verified')
        if verified in ['true', 'false']:
            queryset = queryset.filter(verified=verified == 'true')
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(Q(guarantor_id__icontains=search) | Q(individual__full_account_name__icontains=search) | Q(company_name__icontains=search) | Q(contact_person__icontains=search) | Q(phone_number__icontains=search) | Q(nin__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_guarantors'] = Guarantor.objects.count()
        context['active_guarantors'] = Guarantor.objects.filter(is_active=True).count()
        context['verified_guarantors'] = Guarantor.objects.filter(verified=True).count()
        return context

class GuarantorCreateView(LoginRequiredMixin, LoanOfficerRequiredMixin, CreateView):
    model = Guarantor
    form_class = GuarantorForm
    template_name = 'loans/guarantor_form.html'
    success_url = reverse_lazy('loans:guarantor_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Guarantor created successfully!')
        return super().form_valid(form)

class GuarantorDetailView(LoginRequiredMixin, LoanOfficerRequiredMixin, DetailView):
    model = Guarantor
    template_name = 'loans/guarantor_detail.html'
    context_object_name = 'guarantor'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guarantor = self.get_object()
        context['guaranteed_loans'] = LoanApplication.objects.filter(guarantors=guarantor).select_related('client', 'loan_product').order_by('-application_date')
        return context

class GuarantorUpdateView(LoginRequiredMixin, LoanOfficerRequiredMixin, UpdateView):
    model = Guarantor
    form_class = GuarantorForm
    template_name = 'loans/guarantor_form.html'

    def get_success_url(self):
        return reverse('loans:guarantor_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, f'Guarantor updated successfully!')
        return super().form_valid(form)

@login_required
@staff_required
def guarantor_verify(request, pk):
    guarantor = get_object_or_404(Guarantor, pk=pk)
    if request.method == 'POST':
        guarantor.verified = True
        guarantor.verified_by = request.user
        guarantor.verification_date = timezone.now().date()
        guarantor.save()
        messages.success(request, f'Guarantor {guarantor.guarantor_id} verified successfully!')
        return redirect('loans:guarantor_detail', pk=guarantor.pk)
    return render(request, 'loans/guarantor_verify.html', {'guarantor': guarantor})

@login_required
@loan_officer_required
def loan_calculator(request):
    if request.method == 'POST':
        form = LoanCalculatorForm(request.POST)
        if form.is_valid():
            principal = form.cleaned_data['loan_amount']
            annual_rate = form.cleaned_data['interest_rate']
            term_days = form.cleaned_data['term_days']
            interest_type = form.cleaned_data['interest_type']
            calculation_method = form.cleaned_data['calculation_method']
            interest_service = InterestCalculationService()
            total_interest = interest_service.calculate_interest(principal, annual_rate, term_days, method=calculation_method, interest_type=interest_type)
            total_repayment = principal + total_interest
            if term_days <= 30:
                installments = 4
                installment_days = 7
            elif term_days <= 90:
                installments = 12
                installment_days = term_days // 12
            else:
                installments = term_days // 30
                installment_days = 30
            installment_amount = total_repayment / installments
            schedule = []
            current_date = timezone.now().date()
            for i in range(1, installments + 1):
                due_date = current_date + timedelta(days=installment_days)
                schedule.append({'installment': i, 'due_date': due_date, 'amount': installment_amount})
                current_date = due_date
            context = {'form': form, 'calculation': {'principal': principal, 'annual_rate': annual_rate, 'term_days': term_days, 'total_interest': total_interest, 'total_repayment': total_repayment, 'installments': installments, 'installment_amount': installment_amount, 'schedule': schedule}}
            return render(request, 'loans/loan_calculator.html', context)
    else:
        form = LoanCalculatorForm()
    return render(request, 'loans/loan_calculator.html', {'form': form})

@login_required
@loan_officer_required
def client_eligibility_check(request, client_id):
    client = get_object_or_404(ClientAccount, pk=client_id)
    existing_loans = Loan.objects.filter(client=client, status__in=['ACTIVE', 'OVERDUE'])
    total_existing_debt = sum((loan.remaining_balance for loan in existing_loans))
    max_loan_by_savings = client.current_balance * Decimal('3')
    max_loan_by_income = Decimal('0')
    if hasattr(client, 'monthly_income') and client.monthly_income:
        max_loan_by_income = client.monthly_income * Decimal('6')
    eligible_amount = min(max_loan_by_savings, max_loan_by_income)
    available_amount = max(Decimal('0'), eligible_amount - total_existing_debt)
    recommended_products = LoanProduct.objects.filter(is_active=True, min_loan_amount__lte=available_amount, max_loan_amount__gte=available_amount).order_by('annual_interest_rate')
    context = {'client': client, 'existing_loans': existing_loans, 'total_existing_debt': total_existing_debt, 'max_loan_by_savings': max_loan_by_savings, 'max_loan_by_income': max_loan_by_income, 'eligible_amount': eligible_amount, 'available_amount': available_amount, 'recommended_products': recommended_products}
    return render(request, 'loans/client_eligibility.html', context)

@login_required
@require_http_methods(['GET'])
def api_calculate_repayment(request):
    try:
        principal = Decimal(request.GET.get('principal', '0'))
        annual_rate = Decimal(request.GET.get('annual_rate', '0'))
        term_days = int(request.GET.get('term_days', '0'))
        interest_type = request.GET.get('interest_type', 'FLAT')
        calculation_method = request.GET.get('calculation_method', 'ACTUAL_365')
        interest_service = InterestCalculationService()
        total_interest = interest_service.calculate_interest(principal, annual_rate, term_days, method=calculation_method, interest_type=interest_type)
        total_repayment = principal + total_interest
        if term_days <= 30:
            installments = 4
        elif term_days <= 90:
            installments = 12
        else:
            installments = term_days // 30
        installment_amount = total_repayment / installments
        return JsonResponse({'success': True, 'principal': float(principal), 'total_interest': float(total_interest), 'total_repayment': float(total_repayment), 'installments': installments, 'installment_amount': float(installment_amount), 'daily_interest': float(total_interest / term_days if term_days > 0 else 0)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(['GET'])
def api_client_eligibility(request, client_id):
    try:
        client = get_object_or_404(ClientAccount, pk=client_id)
        existing_loans = Loan.objects.filter(client=client, status__in=['ACTIVE', 'OVERDUE'])
        total_existing_debt = sum((loan.remaining_balance for loan in existing_loans))
        max_loan_by_savings = client.current_balance * Decimal('3')
        max_loan_by_income = Decimal('0')
        if hasattr(client, 'monthly_income') and client.monthly_income:
            max_loan_by_income = client.monthly_income * Decimal('6')
        eligible_amount = min(max_loan_by_savings, max_loan_by_income)
        available_amount = max(Decimal('0'), eligible_amount - total_existing_debt)
        return JsonResponse({'client_id': client_id, 'client_name': client.full_account_name, 'current_savings': float(client.current_balance), 'monthly_income': float(client.monthly_income) if client.monthly_income else 0, 'existing_debt': float(total_existing_debt), 'max_loan_by_savings': float(max_loan_by_savings), 'max_loan_by_income': float(max_loan_by_income), 'eligible_amount': float(eligible_amount), 'available_amount': float(available_amount), 'debt_to_income_ratio': float(total_existing_debt / client.monthly_income if client.monthly_income else 0)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(['POST'])
def api_webhook_payment(request):
    try:
        data = json.loads(request.body)
        loan_number = data.get('loan_number')
        amount = Decimal(data.get('amount', '0'))
        reference = data.get('reference')
        payment_method = data.get('payment_method', 'MOBILE_MONEY')
        loan = get_object_or_404(Loan, loan_number=loan_number)
        with transaction.atomic():
            payment_service = PaymentProcessingService()
            allocation = payment_service.process_payment(loan=loan, amount=amount, payment_date=timezone.now().date(), payment_method=payment_method, received_by=None, notes=f'Auto payment via webhook: {reference}', allocation_strategy='AUTO')
            LoanTransaction.objects.create(loan=loan, transaction_type='PRINCIPAL_PAYMENT' if allocation['principal'] > 0 else 'INTEREST_PAYMENT', payment_method=payment_method, amount=amount, principal_amount=allocation['principal'], interest_amount=allocation['interest'], fee_amount=allocation['late_fees'], notes=f'Auto payment: {reference}', recorded_by=None, reference_number=reference)
        return JsonResponse({'success': True, 'message': 'Payment processed'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@staff_required
def loan_portfolio_report(request):
    loans = Loan.objects.select_related('client', 'loan_product').all()
    status_filter = request.GET.get('status')
    if status_filter:
        loans = loans.filter(status=status_filter)
    product_filter = request.GET.get('product')
    if product_filter:
        loans = loans.filter(loan_product_id=product_filter)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from and date_to:
        loans = loans.filter(disbursement_date__range=[date_from, date_to])
    export_format = request.GET.get('export')
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="loan_portfolio.csv"'
        writer = csv.writer(response)
        writer.writerow(['Loan Number', 'Client', 'Product', 'Disbursement Date', 'Principal', 'Interest Rate', 'Status', 'Remaining Balance', 'Next Payment Date', 'Days Overdue'])
        for loan in loans:
            writer.writerow([loan.loan_number, loan.client.full_account_name, loan.loan_product.name, loan.disbursement_date, loan.principal_amount, loan.interest_rate, loan.status, loan.remaining_balance, loan.next_payment_date, loan.days_overdue])
        return response
    elif export_format == 'excel':
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="loan_portfolio.xls"'
        wb = xlwt.Workbook(encoding='utf-8')
        ws = wb.add_sheet('Loan Portfolio')
        headers = ['Loan Number', 'Client', 'Product', 'Disbursement Date', 'Principal', 'Interest Rate', 'Status', 'Remaining Balance', 'Next Payment Date', 'Days Overdue']
        for col, header in enumerate(headers):
            ws.write(0, col, header)
        for row, loan in enumerate(loans, 1):
            ws.write(row, 0, str(loan.loan_number))
            ws.write(row, 1, str(loan.client.full_account_name))
            ws.write(row, 2, str(loan.loan_product.name))
            ws.write(row, 3, loan.disbursement_date.strftime('%Y-%m-%d') if loan.disbursement_date else '')
            ws.write(row, 4, float(loan.principal_amount))
            ws.write(row, 5, float(loan.interest_rate))
            ws.write(row, 6, str(loan.status))
            ws.write(row, 7, float(loan.remaining_balance))
            ws.write(row, 8, loan.next_payment_date.strftime('%Y-%m-%d') if loan.next_payment_date else '')
            ws.write(row, 9, loan.days_overdue)
        wb.save(response)
        return response
    context = {'loans': loans, 'products': LoanProduct.objects.filter(is_active=True), 'total_count': loans.count(), 'total_principal': loans.aggregate(total=Sum('principal_amount'))['total'] or Decimal('0'), 'total_remaining': loans.aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0')}
    return render(request, 'loans/portfolio_report.html', context)

@login_required
@staff_required
def overdue_loans_report(request):
    overdue_loans = Loan.objects.filter(status='OVERDUE').select_related('client', 'loan_product').order_by('-days_overdue')
    aging = {'1_30_days': Decimal('0'), '31_60_days': Decimal('0'), '61_90_days': Decimal('0'), 'over_90_days': Decimal('0')}
    for loan in overdue_loans:
        days = loan.days_overdue
        amount = loan.overdue_amount
        if days <= 30:
            aging['1_30_days'] += amount
        elif days <= 60:
            aging['31_60_days'] += amount
        elif days <= 90:
            aging['61_90_days'] += amount
        else:
            aging['over_90_days'] += amount
    export_format = request.GET.get('export')
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="overdue_loans.csv"'
        writer = csv.writer(response)
        writer.writerow(['Loan Number', 'Client', 'Phone', 'Disbursement Date', 'Principal', 'Overdue Amount', 'Days Overdue', 'Last Payment Date', 'Loan Officer'])
        for loan in overdue_loans:
            last_payment = loan.transactions.filter(transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT']).order_by('-transaction_date').first()
            writer.writerow([loan.loan_number, loan.client.full_account_name, loan.client.phone_number, loan.disbursement_date, loan.principal_amount, loan.overdue_amount, loan.days_overdue, last_payment.transaction_date if last_payment else '', f'{loan.loan_officer.first_name} {loan.loan_officer.last_name}'])
        return response
    context = {'overdue_loans': overdue_loans, 'total_overdue': overdue_loans.count(), 'total_overdue_amount': sum((loan.overdue_amount for loan in overdue_loans)), 'aging_analysis': aging}
    return render(request, 'loans/overdue_report.html', context)

@login_required
@loan_officer_required
def quick_payment(request):
    if request.method == 'POST':
        loan_number = request.POST.get('loan_number')
        amount = Decimal(request.POST.get('amount', '0'))
        payment_method = request.POST.get('payment_method', 'CASH')
        try:
            loan = Loan.objects.get(loan_number=loan_number)
            with transaction.atomic():
                payment_service = PaymentProcessingService()
                allocation = payment_service.process_payment(loan=loan, amount=amount, payment_date=timezone.now().date(), payment_method=payment_method, received_by=request.user, notes='Quick payment', allocation_strategy='AUTO')
                messages.success(request, f'Payment of {amount} for loan {loan_number} processed successfully!')
                return redirect('loans:payment_receipt', transaction_id=allocation['transactions'][0].transaction_id)
        except Loan.DoesNotExist:
            messages.error(request, f'Loan {loan_number} not found!')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    return render(request, 'loans/quick_payment.html')

@login_required
@staff_required
def bulk_status_update(request):
    if request.method == 'POST':
        loan_ids = request.POST.getlist('loan_ids')
        new_status = request.POST.get('new_status')
        reason = request.POST.get('reason', '')
        effective_date = request.POST.get('effective_date', timezone.now().date())
        loans = Loan.objects.filter(pk__in=loan_ids)
        updated_count = 0
        for loan in loans:
            loan.status = new_status
            if new_status == 'CLOSED':
                loan.closed_at = timezone.now()
            loan.save()
            LoanTransaction.objects.create(loan=loan, transaction_type='ADJUSTMENT', payment_method='SYSTEM', amount=Decimal('0'), notes=f'Status changed to {new_status}: {reason}', recorded_by=request.user, value_date=effective_date)
            updated_count += 1
        messages.success(request, f'{updated_count} loans updated to {new_status} status!')
        return redirect('loans:loan_list')
    return render(request, 'loans/bulk_status_update.html')

def generate_loan_schedule_pdf(loan):
    return None

def send_payment_reminder(loan):
    print(f'Payment reminder sent for loan {loan.loan_number}')

def calculate_early_repayment_savings(loan, repayment_amount):
    interest_service = InterestCalculationService()
    remaining_schedule = loan.repayment_schedule.filter(status__in=['PENDING', 'DUE']).order_by('due_date')
    if not remaining_schedule.exists():
        return {'savings': Decimal('0'), 'new_schedule': []}
    total_interest_without_early = sum((installment.interest_amount for installment in remaining_schedule))
    new_principal = loan.remaining_balance - repayment_amount
    if new_principal <= 0:
        savings = total_interest_without_early
        new_schedule = []
    else:
        remaining_months = remaining_schedule.count()
        monthly_rate = loan.interest_rate / Decimal('100') / Decimal('12')
        if monthly_rate == Decimal('0'):
            new_payment = new_principal / remaining_months
        else:
            factor = (Decimal('1') + monthly_rate) ** remaining_months
            new_payment = new_principal * monthly_rate * factor / (factor - Decimal('1'))
        new_schedule = []
        remaining_balance = new_principal
        for i, installment in enumerate(remaining_schedule, 1):
            interest = remaining_balance * monthly_rate
            principal = new_payment - interest
            remaining_balance -= principal
            new_schedule.append({'period': i, 'due_date': installment.due_date, 'payment': new_payment.quantize(Decimal('0.01')), 'principal': principal.quantize(Decimal('0.01')), 'interest': interest.quantize(Decimal('0.01')), 'remaining_balance': max(remaining_balance, Decimal('0')).quantize(Decimal('0.01'))})
        total_interest_with_early = sum((item['interest'] for item in new_schedule))
        savings = total_interest_without_early - total_interest_with_early
    penalty = Decimal('0')
    if loan.loan_product.early_repayment_penalty_percent > 0:
        penalty = repayment_amount * loan.loan_product.early_repayment_penalty_percent / Decimal('100')
    net_savings = savings - penalty
    return {'savings': savings.quantize(Decimal('0.01')), 'penalty': penalty.quantize(Decimal('0.01')), 'net_savings': net_savings.quantize(Decimal('0.01')), 'new_schedule': new_schedule}

def handler404(request, exception):
    return render(request, 'loans/404.html', status=404)

def handler500(request):
    return render(request, 'loans/500.html', status=500)

def handler403(request, exception):
    return render(request, 'loans/403.html', status=403)

def handler400(request, exception):
    return render(request, 'loans/400.html', status=400)

@login_required
@require_http_methods(["POST"])
def guarantor_delete(request, pk):
    """Delete a guarantor"""
    guarantor = get_object_or_404(Guarantor, pk=pk)
    
    # Check if user has permission (superuser or admin)
    if not (request.user.is_superuser or hasattr(request.user, 'profile') and request.user.profile.role == 'ADMIN'):
        messages.error(request, 'You do not have permission to delete guarantors.')
        return redirect('loans:guarantor_list')
    
    guarantor_name = guarantor.name
    guarantor.delete()
    
    messages.success(request, f'Guarantor "{guarantor_name}" has been deleted successfully.')
    return redirect('loans:guarantor_list')

@login_required
@role_required(['ADMIN', 'MANAGER', 'LOAN_OFFICER'])
def portfolio_report(request):
    """Generate comprehensive loan portfolio report"""
    
    # Get filters from request
    start_date = request.GET.get('start_date', (timezone.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', timezone.now().strftime('%Y-%m-%d'))
    loan_officer_id = request.GET.get('loan_officer')
    loan_type = request.GET.get('loan_type')
    
    # Convert dates
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        start_date = (timezone.now() - timedelta(days=365)).date()
        end_date = timezone.now().date()
    
    # Base queryset
    loans = LoanApplication.objects.filter(
        application_date__range=[start_date, end_date]
    ).select_related('client_account', 'loan_officer')
    
    # Apply filters
    if loan_officer_id:
        loans = loans.filter(loan_officer_id=loan_officer_id)
    
    if loan_type:
        loans = loans.filter(loan_type=loan_type)
    
    # Calculate summary statistics
    total_loans = loans.count()
    active_loans = loans.filter(status__in=['ACTIVE', 'APPROVED', 'DISBURSED']).count()
    total_portfolio = loans.aggregate(total=Sum('loan_amount'))['total'] or Decimal('0.00')
    total_outstanding = loans.aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0.00')
    
    # Calculate NPL ratio (Non-Performing Loans > 90 days)
    npl_amount = loans.filter(
        status='ACTIVE',
        days_overdue__gt=90
    ).aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0.00')
    
    npl_ratio = (npl_amount / total_outstanding * 100) if total_outstanding > 0 else Decimal('0.00')
    
    # Calculate collection rate
    total_repayments = LoanRepayment.objects.filter(
        loan__in=loans,
        payment_date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    total_due = loans.filter(status='ACTIVE').aggregate(
        total=Sum('remaining_balance') + Sum('total_interest')
    )['total'] or Decimal('0.00')
    
    collection_rate = (total_repayments / total_due * 100) if total_due > 0 else Decimal('0.00')
    
    # Status distribution
    status_distribution = []
    for status_code, status_name in LoanApplication.STATUS_CHOICES:
        status_loans = loans.filter(status=status_code)
        count = status_loans.count()
        total_amount = status_loans.aggregate(total=Sum('loan_amount'))['total'] or Decimal('0.00')
        
        if count > 0:
            percentage = (total_amount / total_portfolio * 100) if total_portfolio > 0 else Decimal('0.00')
            avg_size = total_amount / count
            
            status_distribution.append({
                'status': status_code,
                'status_display': status_name,
                'count': count,
                'total_amount': total_amount,
                'percentage': percentage,
                'avg_size': avg_size,
                'badge_color': {
                    'PENDING': 'secondary',
                    'APPROVED': 'info',
                    'DISBURSED': 'primary',
                    'ACTIVE': 'success',
                    'COMPLETED': 'success',
                    'DEFAULTED': 'danger',
                    'WRITTEN_OFF': 'dark',
                }.get(status_code, 'secondary')
            })
    
    # Performance metrics
    par_30 = loans.filter(
        status='ACTIVE',
        days_overdue__gt=30,
        days_overdue__lte=60
    ).aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0.00')
    
    par_60 = loans.filter(
        status='ACTIVE',
        days_overdue__gt=60
    ).aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0.00')
    
    write_offs = loans.filter(
        status='WRITTEN_OFF',
        application_date__range=[start_date, end_date]
    ).aggregate(total=Sum('loan_amount'))['total'] or Decimal('0.00')
    
    # Prepare chart data
    status_labels = [s['status_display'] for s in status_distribution]
    status_data = [float(s['total_amount']) for s in status_distribution]
    status_colors = [f'#{hash(s["status_display"]) % 0xFFFFFF:06x}' for s in status_distribution]
    
    # Disbursement trend (last 12 months)
    disbursement_months = []
    disbursement_amounts = []
    for i in range(11, -1, -1):
        month_date = (timezone.now() - timedelta(days=30*i)).replace(day=1)
        month_start = month_date.replace(day=1)
        month_end = (month_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_amount = loans.filter(
            disbursement_date__range=[month_start, month_end]
        ).aggregate(total=Sum('loan_amount'))['total'] or Decimal('0.00')
        
        disbursement_months.append(month_date.strftime('%b %Y'))
        disbursement_amounts.append(float(month_amount))
    
    # Loan type distribution
    loan_types_data = loans.values('loan_type').annotate(
        count=Count('id'),
        total=Sum('loan_amount')
    ).order_by('-total')
    
    loan_type_labels = [dict(LoanApplication.LOAN_TYPE_CHOICES).get(item['loan_type'], item['loan_type']) 
                        for item in loan_types_data]
    loan_type_data = [float(item['total']) for item in loan_types_data]
    
    # Risk ratings (if available)
    risk_ratings = []
    # Add your risk rating logic here
    
    # Officer performance
    officer_performance = []
    officers = User.objects.filter(loan_applications__in=loans).distinct()
    for officer in officers:
        officer_loans = loans.filter(loan_officer=officer)
        officer_portfolio = officer_loans.aggregate(total=Sum('loan_amount'))['total'] or Decimal('0.00')
        officer_npl = officer_loans.filter(status='ACTIVE', days_overdue__gt=90).aggregate(
            total=Sum('remaining_balance'))['total'] or Decimal('0.00')
        officer_npl_ratio = (officer_npl / officer_portfolio * 100) if officer_portfolio > 0 else Decimal('0.00')
        
        officer_performance.append({
            'name': officer.get_full_name() or officer.username,
            'loan_count': officer_loans.count(),
            'portfolio': officer_portfolio,
            'npl_ratio': officer_npl_ratio,
            'collection_rate': Decimal('95.5')  # Replace with actual calculation
        })
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'selected_officer': int(loan_officer_id) if loan_officer_id else None,
        'selected_type': loan_type,
        'loan_officers': User.objects.filter(groups__name='Loan Officer').distinct(),
        'loan_types': LoanApplication.LOAN_TYPE_CHOICES,
        
        'summary': {
            'total_loans': total_loans,
            'active_loans': active_loans,
            'total_portfolio': total_portfolio,
            'total_outstanding': total_outstanding,
            'npl_ratio': npl_ratio,
            'collection_rate': collection_rate,
            'avg_loan_size': total_portfolio / total_loans if total_loans > 0 else Decimal('0.00'),
        },
        
        'status_distribution': status_distribution,
        'performance': {
            'par_30': par_30,
            'par_30_percentage': (par_30 / total_outstanding * 100) if total_outstanding > 0 else Decimal('0.00'),
            'par_60': par_60,
            'par_60_percentage': (par_60 / total_outstanding * 100) if total_outstanding > 0 else Decimal('0.00'),
            'write_offs': write_offs,
            'write_offs_percentage': (write_offs / total_portfolio * 100) if total_portfolio > 0 else Decimal('0.00'),
        },
        
        'status_labels': status_labels,
        'status_data': status_data,
        'status_colors': status_colors,
        'disbursement_months': disbursement_months,
        'disbursement_amounts': disbursement_amounts,
        'loan_type_labels': loan_type_labels,
        'loan_type_data': loan_type_data,
        
        'risk_ratings': risk_ratings,
        'officer_performance': officer_performance,
        
        'loans': loans[:100],  # Limit to 100 for performance
        'generated_at': timezone.now(),
    }
    
    # Handle exports
    if request.GET.get('export') == 'csv':
        return export_portfolio_csv(loans, context)
    elif request.GET.get('export') == 'pdf':
        return export_portfolio_pdf(context)
    
    return render(request, 'loans/portfolio_report.html', context)


def export_portfolio_csv(queryset, context):
    """Export portfolio report to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="portfolio_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    
    # Write summary section
    writer.writerow(['LOAN PORTFOLIO REPORT'])
    writer.writerow([f'Period: {context["start_date"]} to {context["end_date"]}'])
    writer.writerow([f'Generated: {context["generated_at"].strftime("%Y-%m-%d %H:%M:%S")}'])
    writer.writerow([])
    
    writer.writerow(['SUMMARY STATISTICS'])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Total Loans', context['summary']['total_loans']])
    writer.writerow(['Active Loans', context['summary']['active_loans']])
    writer.writerow(['Total Portfolio', f"${context['summary']['total_portfolio']:.2f}"])
    writer.writerow(['Total Outstanding', f"${context['summary']['total_outstanding']:.2f}"])
    writer.writerow(['NPL Ratio', f"{context['summary']['npl_ratio']:.2f}%"])
    writer.writerow(['Collection Rate', f"{context['summary']['collection_rate']:.2f}%"])
    writer.writerow([])
    
    # Write status distribution
    writer.writerow(['STATUS DISTRIBUTION'])
    writer.writerow(['Status', 'Count', 'Amount', '% of Portfolio', 'Avg Size'])
    for status in context['status_distribution']:
        writer.writerow([
            status['status_display'],
            status['count'],
            f"${status['total_amount']:.2f}",
            f"{status['percentage']:.2f}%",
            f"${status['avg_size']:.2f}"
        ])
    writer.writerow([])
    
    # Write loan details
    writer.writerow(['LOAN DETAILS'])
    writer.writerow([
        'Loan ID', 'Client', 'Loan Officer', 'Type', 'Disbursed',
        'Principal', 'Outstanding', 'Status', 'Days Overdue'
    ])
    
    for loan in queryset:
        writer.writerow([
            loan.id,
            loan.client_account.full_account_name,
            loan.loan_officer.get_full_name() or loan.loan_officer.username,
            loan.get_loan_type_display(),
            loan.disbursement_date.strftime('%Y-%m-%d') if loan.disbursement_date else '',
            f"${loan.loan_amount:.2f}",
            f"${loan.remaining_balance:.2f}",
            loan.get_status_display(),
            loan.days_overdue or 0
        ])
    
    return response

@login_required
@role_required([UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER, UserProfile.ROLE_LOAN_OFFICER, UserProfile.ROLE_ACCOUNTANT])
def overdue_report(request):
    """Generate overdue loans report"""
    
    # Get filters from request
    days_filter = request.GET.get('days_overdue', '')
    loan_officer_id = request.GET.get('loan_officer')
    risk_filter = request.GET.get('risk_rating')
    amount_filter = request.GET.get('amount_range')
    
    # Base queryset - get active loans with overdue payments
    loans = LoanApplication.objects.filter(
        status='ACTIVE',
        remaining_balance__gt=0
    ).select_related('client_account', 'loan_officer')
    
    # Calculate days overdue for each loan (you need to implement this logic)
    # This is a simplified version - adjust based on your model structure
    for loan in loans:
        # Calculate days overdue based on your payment schedule
        # This is placeholder logic
        loan.days_overdue = getattr(loan, 'days_overdue', 0) or 0
    
    # Apply filters
    if days_filter:
        if days_filter == '1-30':
            loans = [l for l in loans if 1 <= l.days_overdue <= 30]
        elif days_filter == '31-60':
            loans = [l for l in loans if 31 <= l.days_overdue <= 60]
        elif days_filter == '61-90':
            loans = [l for l in loans if 61 <= l.days_overdue <= 90]
        elif days_filter == '90+':
            loans = [l for l in loans if l.days_overdue >= 90]
    
    if loan_officer_id:
        loans = [l for l in loans if l.loan_officer_id == int(loan_officer_id)]
    
    if risk_filter:
        loans = [l for l in loans if l.risk_rating == risk_filter]
    
    # Apply amount filter (simplified)
    if amount_filter:
        if amount_filter == '0-1000':
            loans = [l for l in loans if l.remaining_balance <= 1000]
        elif amount_filter == '1001-5000':
            loans = [l for l in loans if 1001 <= l.remaining_balance <= 5000]
        elif amount_filter == '5001-10000':
            loans = [l for l in loans if 5001 <= l.remaining_balance <= 10000]
        elif amount_filter == '10000+':
            loans = [l for l in loans if l.remaining_balance >= 10000]
    
    # Convert back to queryset for pagination
    loan_ids = [loan.id for loan in loans]
    overdue_loans = LoanApplication.objects.filter(id__in=loan_ids).order_by('-days_overdue')
    
    # Calculate summary statistics
    total_overdue = len(loans)
    total_amount = sum(loan.remaining_balance for loan in loans)
    avg_days_overdue = sum(loan.days_overdue for loan in loans) / total_overdue if total_overdue > 0 else 0
    
    # Calculate PAR (Portfolio at Risk) by days
    par_30 = len([l for l in loans if l.days_overdue > 30])
    par_60 = len([l for l in loans if l.days_overdue > 60])
    npl_count = len([l for l in loans if l.days_overdue > 90])
    
    # Distribution data for chart
    distribution_data = [
        len([l for l in loans if 1 <= l.days_overdue <= 30]),
        len([l for l in loans if 31 <= l.days_overdue <= 60]),
        len([l for l in loans if 61 <= l.days_overdue <= 90]),
        len([l for l in loans if l.days_overdue > 90])
    ]
    
    # Officer analysis
    officer_analysis = []
    officers = User.objects.filter(loan_applications__in=overdue_loans).distinct()
    for officer in officers:
        officer_loans = [l for l in loans if l.loan_officer_id == officer.id]
        if officer_loans:
            officer_analysis.append({
                'name': officer.get_full_name() or officer.username,
                'count': len(officer_loans),
                'amount': sum(l.remaining_balance for l in officer_loans),
                'avg_days': sum(l.days_overdue for l in officer_loans) / len(officer_loans),
                'risk_score': min(100, sum(l.days_overdue for l in officer_loans) / len(officer_loans) * 10)
            })
    
    # Recovery stats
    recovery_stats = {
        'immediate': len([l for l in loans if l.days_overdue >= 60]),
        'followup': len([l for l in loans if 30 <= l.days_overdue < 60]),
        'contact_attempts': 0  # You need to implement contact tracking
    }
    
    # Pagination
    paginator = Paginator(overdue_loans, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'overdue_loans': page_obj,
        'summary': {
            'total_overdue': total_overdue,
            'total_amount': total_amount,
            'avg_days_overdue': avg_days_overdue,
            'par_30': par_30,
            'par_60': par_60,
            'npl_count': npl_count,
            'recovery_rate': 0,  # Implement based on your recovery logic
        },
        'days_filter': days_filter,
        'selected_officer': int(loan_officer_id) if loan_officer_id else None,
        'risk_filter': risk_filter,
        'amount_filter': amount_filter,
        'loan_officers': User.objects.filter(groups__name='Loan Officer').distinct(),
        'collection_officers': User.objects.filter(groups__name='Collection Officer').distinct(),
        'distribution_data': distribution_data,
        'officer_analysis': officer_analysis,
        'recovery_stats': recovery_stats,
        'user_role': get_user_role(request),
        'generated_at': timezone.now(),
    }
    
    return render(request, 'loans/overdue_report.html', context)


@login_required
@staff_required
def collections_report(request):
    """View for collections/payments report"""
    
    # Get date range from request or use defaults
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    period = request.GET.get('period', '')
    
    today = timezone.now().date()
    
    # Set date range based on period or custom dates
    if period == 'today':
        start_date = today
        end_date = today
    elif period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == 'month':
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'quarter':
        quarter = (today.month - 1) // 3 + 1
        start_date = today.replace(month=3 * quarter - 2, day=1)
        end_date = today
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today
    else:
        # Use custom dates or defaults
        if not start_date:
            start_date = (today - timedelta(days=30)).isoformat()
        if not end_date:
            end_date = today.isoformat()
        
        # Convert to date objects
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get payments using LoanTransaction (your actual model)
    payments = LoanTransaction.objects.filter(
        transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT'],
        value_date__range=[start_date, end_date]
    ).select_related('loan', 'loan__client', 'recorded_by').order_by('-value_date')
    
    # Calculate statistics - using 'amount' field (correct field name)
    total_collections = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Today's collections
    today_collections = LoanTransaction.objects.filter(
        transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT'],
        value_date=today
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # This week collections
    week_start = today - timedelta(days=today.weekday())
    week_collections = LoanTransaction.objects.filter(
        transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT'],
        value_date__gte=week_start
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # This month collections
    month_collections = LoanTransaction.objects.filter(
        transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT'],
        value_date__month=today.month,
        value_date__year=today.year
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Payment method breakdown
    by_method = payments.values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Calculate percentages for payment methods
    for method in by_method:
        if total_collections > 0:
            method['percentage'] = (method['total'] / total_collections) * 100
        else:
            method['percentage'] = 0
    
    # By officer breakdown
    by_officer = payments.values('recorded_by__username').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Daily totals for chart
    daily_totals = {}
    current_date = start_date
    while current_date <= end_date:
        daily_total = payments.filter(value_date=current_date).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        daily_totals[current_date.isoformat()] = float(daily_total)
        current_date += timedelta(days=1)
    
    # Calculate average daily collection
    days_in_period = (end_date - start_date).days + 1
    average_daily = total_collections / days_in_period if days_in_period > 0 else Decimal('0')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(payments, 50)  # 50 items per page
    
    try:
        payments_page = paginator.page(page)
    except PageNotAnInteger:
        payments_page = paginator.page(1)
    except EmptyPage:
        payments_page = paginator.page(paginator.num_pages)
    
    # Recent payments for activity feed
    recent_payments = LoanTransaction.objects.filter(
        transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT']
    ).order_by('-value_date')[:10]
    
    # Handle CSV export
    export_format = request.GET.get('export')
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="collections_{start_date}_to_{end_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Date', 'Loan Number', 'Client', 'Payment Method', 'Amount', 'Type', 'Recorded By'])
        
        for payment in payments:
            writer.writerow([
                payment.value_date,
                payment.loan.loan_number,
                payment.loan.client.full_account_name,
                payment.payment_method,
                payment.amount,
                payment.transaction_type,
                payment.recorded_by.username if payment.recorded_by else 'N/A'
            ])
        
        return response
    
    # Prepare context
    context = {
        'payments': payments_page,
        'start_date': start_date.isoformat() if isinstance(start_date, date) else start_date,
        'end_date': end_date.isoformat() if isinstance(end_date, date) else end_date,
        'period': period,
        'total_collections': total_collections,
        'today_collections': today_collections,
        'week_collections': week_collections,
        'month_collections': month_collections,
        'payment_count': payments.count(),
        'today_count': LoanTransaction.objects.filter(
            transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT'],
            value_date=today
        ).count(),
        'week_count': LoanTransaction.objects.filter(
            transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT'],
            value_date__gte=week_start
        ).count(),
        'month_count': LoanTransaction.objects.filter(
            transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT'],
            value_date__month=today.month,
            value_date__year=today.year
        ).count(),
        'by_method': by_method,
        'method_breakdown': by_method,  # Alias for template compatibility
        'by_officer': by_officer,
        'daily_totals': daily_totals,
        'average_daily': average_daily,
        'recent_payments': recent_payments,
    }
    
    return render(request, 'loans/collections_report.html', context)

@login_required
def export_collections_csv(request):
    """Export collections report as CSV"""
    from django.http import HttpResponse
    import csv
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="collections_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Payment Date', 'Application Number', 'Client Name', 
        'Amount (UGX)', 'Payment Method', 'Received By', 
        'Transaction Reference', 'Notes'
    ])
    
    payments = LoanPayment.objects.all().order_by('-payment_date')
    
    for payment in payments:
        writer.writerow([
            payment.payment_date.strftime('%Y-%m-%d %H:%M'),
            payment.loan_application.application_number,
            payment.loan_application.client_account.full_account_name,
            payment.payment_amount,
            payment.get_payment_method_display(),
            payment.received_by.get_full_name() or payment.received_by.username,
            payment.transaction_reference,
            payment.notes[:100] if payment.notes else ''
        ])
    
    return response

@login_required
def bulk_payment(request):
    """View for bulk payment processing"""
    # Get active loans for dropdown
    active_loans = LoanApplication.objects.filter(
        status='DISBURSED'
    ).select_related('client_account')
    
    # Prepare loan data for JavaScript
    loans_data = []
    for loan in active_loans:
        loans_data.append({
            'id': loan.id,
            'number': loan.application_number,
            'client': loan.client_account.full_account_name,
            'balance': float(loan.get_balance_remaining()),
            'balance_formatted': f"{loan.get_balance_remaining():,.2f} UGX"
        })
    
    context = {
        'active_loans': active_loans,
        'active_loans_json': json.dumps(loans_data),
        'today': timezone.now().date(),
    }
    return render(request, 'loans/bulk_payment.html', context)

@login_required
@transaction.atomic
def process_bulk_payments(request):
    """Process uploaded CSV file for bulk payments"""
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        
        # Read CSV file
        try:
            # Try different encodings
            content = csv_file.read().decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = csv_file.read().decode('latin-1')
            except UnicodeDecodeError:
                content = csv_file.read().decode('cp1252')
        
        io_string = io.StringIO(content)
        
        # Parse CSV
        reader = csv.DictReader(io_string)
        required_columns = ['loan_application_number', 'payment_amount']
        
        # Validate columns
        if not all(col in reader.fieldnames for col in required_columns):
            messages.error(request, f'CSV must contain columns: {", ".join(required_columns)}')
            return redirect('bulk_payment')
        
        # Process rows
        success_count = 0
        error_rows = []
        
        for i, row in enumerate(reader, start=2):  # start=2 for Excel row numbers
            try:
                # Get loan application
                app_number = row['loan_application_number'].strip()
                loan_app = LoanApplication.objects.get(application_number=app_number)
                
                # Validate loan status
                if loan_app.status != 'DISBURSED':
                    error_rows.append(f"Row {i}: Loan {app_number} is not active")
                    continue
                
                # Get payment amount
                payment_amount = Decimal(row['payment_amount'].replace(',', ''))
                
                # Check if payment exceeds balance
                balance = loan_app.get_balance_remaining()
                if payment_amount > balance:
                    error_rows.append(f"Row {i}: Payment {payment_amount} exceeds balance {balance}")
                    continue
                
                # Get optional fields
                transaction_ref = row.get('transaction_reference', '').strip()
                notes = row.get('notes', '').strip()
                payment_method = request.POST.get('default_payment_method', 'CASH')
                payment_date_str = request.POST.get('payment_date')
                
                # Create payment
                payment = LoanPayment(
                    loan_application=loan_app,
                    payment_amount=payment_amount,
                    payment_method=payment_method,
                    received_by=request.user,
                    transaction_reference=transaction_ref,
                    notes=notes
                )
                
                # Set custom payment date if provided
                if payment_date_str:
                    payment_date = timezone.datetime.strptime(payment_date_str, '%Y-%m-%d').date()
                    payment.payment_date = timezone.make_aware(
                        timezone.datetime.combine(payment_date, timezone.datetime.min.time())
                    )
                
                # Save payment
                payment.full_clean()
                payment.save()
                success_count += 1
                
            except LoanApplication.DoesNotExist:
                error_rows.append(f"Row {i}: Loan application {row['loan_application_number']} not found")
            except ValidationError as e:
                error_rows.append(f"Row {i}: Validation error - {e}")
            except (ValueError, KeyError) as e:
                error_rows.append(f"Row {i}: Data error - {e}")
        
        # Show results
        if success_count > 0:
            messages.success(request, f'Successfully processed {success_count} payments')
        
        if error_rows:
            messages.warning(request, f'{len(error_rows)} rows had errors. See details below.')
            for error in error_rows[:10]:  # Show first 10 errors
                messages.info(request, error)
            if len(error_rows) > 10:
                messages.info(request, f'... and {len(error_rows) - 10} more errors')
        
        return redirect('payments_list')
    
    return redirect('bulk_payment')

@login_required
@transaction.atomic
def save_bulk_payments(request):
    """Save multiple payments from manual entry form"""
    if request.method == 'POST':
        payment_date_str = request.POST.get('payment_date')
        payment_method = request.POST.get('payment_method', 'CASH')
        
        success_count = 0
        errors = []
        
        # Find all payment entries
        i = 1
        while True:
            loan_key = f'loan_application_{i}'
            if loan_key not in request.POST:
                break
            
            loan_id = request.POST.get(loan_key)
            if not loan_id:
                i += 1
                continue
            
            try:
                loan_app = LoanApplication.objects.get(id=loan_id)
                
                # Get payment data
                amount_key = f'payment_amount_{i}'
                ref_key = f'transaction_ref_{i}'
                notes_key = f'notes_{i}'
                
                payment_amount = Decimal(request.POST.get(amount_key, 0))
                
                if payment_amount <= 0:
                    i += 1
                    continue
                
                # Create payment
                payment = LoanPayment(
                    loan_application=loan_app,
                    payment_amount=payment_amount,
                    payment_method=payment_method,
                    received_by=request.user,
                    transaction_reference=request.POST.get(ref_key, ''),
                    notes=request.POST.get(notes_key, '')
                )
                
                # Set custom payment date
                if payment_date_str:
                    payment_date = timezone.datetime.strptime(payment_date_str, '%Y-m-%d').date()
                    payment.payment_date = timezone.make_aware(
                        timezone.datetime.combine(payment_date, timezone.datetime.min.time())
                    )
                
                payment.full_clean()
                payment.save()
                success_count += 1
                
            except LoanApplication.DoesNotExist:
                errors.append(f"Entry {i}: Loan not found")
            except ValidationError as e:
                errors.append(f"Entry {i}: {e}")
            except (ValueError, KeyError) as e:
                errors.append(f"Entry {i}: Data error - {e}")
            
            i += 1
        
        # Show results
        if success_count > 0:
            messages.success(request, f'Successfully saved {success_count} payments')
        
        if errors:
            messages.warning(request, f'{len(errors)} entries had errors')
            for error in errors[:5]:
                messages.info(request, error)
        
        return redirect('payments_list')
    
    return redirect('bulk_payment')

@login_required
def download_bulk_template(request):
    """Download CSV template for bulk payments"""
    template_type = request.GET.get('type', 'simple')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="bulk_payment_template.csv"'
    
    writer = csv.writer(response)
    
    if template_type == 'simple':
        writer.writerow(['loan_application_number', 'payment_amount', 'transaction_reference'])
        writer.writerow(['AN1234', '150000', 'TRX001'])
        writer.writerow(['AN5678', '75000', 'TRX002'])
        writer.writerow(['AN9012', '200000', ''])
    
    elif template_type == 'detailed':
        writer.writerow([
            'loan_application_number',
            'payment_amount',
            'payment_method',
            'transaction_reference',
            'notes',
            'payment_date'
        ])
        writer.writerow([
            'AN1234',
            '150000',
            'CASH',
            'TRX001',
            'Monthly installment',
            '2024-01-15'
        ])
    
    elif template_type == 'sample':
        # Add sample data for existing loans
        writer.writerow(['loan_application_number', 'payment_amount', 'transaction_reference'])
        
        # Get some real loan numbers for sample
        loans = LoanApplication.objects.filter(status='DISBURSED')[:3]
        for loan in loans:
            writer.writerow([
                loan.application_number,
                '50000',
                f'SMP{loan.id}'
            ])
    
    return response


@login_required
@require_http_methods(["POST"])
def process_bulk_payments(request):
    """Process bulk payments from CSV file"""
    
    if 'csv_file' not in request.FILES:
        messages.error(request, 'Please upload a CSV file.')
        return redirect('loans:bulk_payment')
    
    csv_file = request.FILES['csv_file']
    
    # Check file extension
    if not csv_file.name.endswith('.csv'):
        messages.error(request, 'File must be in CSV format.')
        return redirect('loans:bulk_payment')
    
    try:
        # Read CSV file
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        success_count = 0
        error_count = 0
        errors = []
        
        # Process each row
        with transaction.atomic():
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
                try:
                    # Get loan by loan number
                    loan_number = row.get('loan_number', '').strip()
                    amount = row.get('amount', '').strip()
                    payment_method = row.get('payment_method', 'CASH').strip().upper()
                    payment_date = row.get('payment_date', '').strip()
                    
                    # Validate required fields
                    if not loan_number or not amount:
                        errors.append(f"Row {row_num}: Missing required fields")
                        error_count += 1
                        continue
                    
                    # Get loan
                    try:
                        loan = Loan.objects.get(loan_number=loan_number)
                    except Loan.DoesNotExist:
                        errors.append(f"Row {row_num}: Loan {loan_number} not found")
                        error_count += 1
                        continue
                    
                    # Convert amount
                    try:
                        payment_amount = Decimal(amount)
                    except:
                        errors.append(f"Row {row_num}: Invalid amount format")
                        error_count += 1
                        continue
                    
                    # Parse date
                    if payment_date:
                        try:
                            from datetime import datetime
                            payment_date_obj = datetime.strptime(payment_date, '%Y-%m-%d').date()
                        except:
                            payment_date_obj = timezone.now().date()
                    else:
                        payment_date_obj = timezone.now().date()
                    
                    # Create transaction
                    LoanTransaction.objects.create(
                        loan=loan,
                        transaction_type='PRINCIPAL_PAYMENT',
                        amount=payment_amount,
                        payment_method=payment_method,
                        value_date=payment_date_obj,
                        recorded_by=request.user,
                        description=f'Bulk payment import - Row {row_num}'
                    )
                    
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    error_count += 1
        
        # Show results
        if success_count > 0:
            messages.success(request, f'Successfully processed {success_count} payment(s).')
        
        if error_count > 0:
            error_message = f'{error_count} payment(s) failed:<br>'
            error_message += '<br>'.join(errors[:10])  # Show first 10 errors
            if len(errors) > 10:
                error_message += f'<br>...and {len(errors) - 10} more errors'
            messages.warning(request, error_message)
        
    except Exception as e:
        messages.error(request, f'Error processing file: {str(e)}')
    
    return redirect('loans:bulk_payment')




@login_required
def bulk_disbursement(request):
    """View for bulk loan disbursement"""
    # Get approved loans ready for disbursement
    approved_loans = LoanApplication.objects.filter(
        status='APPROVED'
    ).select_related('client_account', 'loan_product').order_by('application_date')
    
    # Get recent disbursements for reference
    recent_disbursements = LoanApplication.objects.filter(
        status='DISBURSED'
    ).select_related('client_account').order_by('-disbursement_date')[:10]
    
    # Prepare loan data for calculations
    loans_data = []
    for loan in approved_loans:
        loans_data.append({
            'id': loan.id,
            'number': loan.application_number,
            'client': loan.client_account.full_account_name,
            'amount': float(loan.loan_amount),
            'interest': float(loan.interest_amount),
            'total': float(loan.total_amount)
        })
    
    context = {
        'approved_loans': approved_loans,
        'recent_disbursements': recent_disbursements,
        'approved_loans_json': json.dumps(loans_data),
        'today': timezone.now().date(),
    }
    return render(request, 'loans/bulk_disbursement.html', context)

@login_required
@transaction.atomic
def process_bulk_disbursement(request):
    """Process multiple loan disbursements"""
    if request.method == 'POST':
        loan_ids = request.POST.getlist('loan_ids')
        disbursement_date_str = request.POST.get('disbursement_date')
        disbursement_method = request.POST.get('disbursement_method', 'CASH')
        transaction_prefix = request.POST.get('transaction_prefix', 'DISB-')
        disbursement_notes = request.POST.get('disbursement_notes', '')
        
        if not loan_ids:
            messages.error(request, 'Please select at least one loan to disburse.')
            return redirect('bulk_disbursement')
        
        success_count = 0
        errors = []
        
        # Parse disbursement date
        try:
            disbursement_date = datetime.strptime(disbursement_date_str, '%Y-%m-%d').date()
            disbursement_datetime = timezone.make_aware(
                datetime.combine(disbursement_date, datetime.min.time())
            )
        except (ValueError, TypeError):
            disbursement_datetime = timezone.now()
        
        for i, loan_id in enumerate(loan_ids):
            try:
                loan = LoanApplication.objects.get(id=loan_id)
                
                # Validate loan is approved
                if loan.status != 'APPROVED':
                    errors.append(f"Loan {loan.application_number} is not approved (status: {loan.status})")
                    continue
                
                # Check if already disbursed
                if loan.disbursement_date:
                    errors.append(f"Loan {loan.application_number} was already disbursed on {loan.disbursement_date.date()}")
                    continue
                
                # Generate transaction reference
                transaction_ref = f"{transaction_prefix}{loan.application_number}"
                
                # Update loan for disbursement
                loan.status = 'DISBURSED'
                loan.disbursement_date = disbursement_datetime
                loan.disbursed_by = request.user
                loan.disbursed_amount = loan.loan_amount
                loan.transaction_reference = transaction_ref
                loan.disbursement_notes = disbursement_notes
                
                # Set due date based on loan period
                loan.due_date = loan.calculate_due_date()
                
                # Save the loan
                loan.save()
                success_count += 1
                
                # Log the action
                messages.info(request, f"✓ Disbursed {loan.application_number}: {loan.loan_amount} UGX to {loan.client_account.full_account_name}")
                
            except LoanApplication.DoesNotExist:
                errors.append(f"Loan with ID {loan_id} not found")
            except ValidationError as e:
                errors.append(f"Loan {loan_id}: {e}")
            except Exception as e:
                errors.append(f"Error processing loan {loan_id}: {str(e)}")
        
        # Show results
        if success_count > 0:
            messages.success(request, f'Successfully disbursed {success_count} loans')
        
        if errors:
            messages.warning(request, f'{len(errors)} errors occurred')
            for error in errors[:5]:  # Show first 5 errors
                messages.error(request, error)
            if len(errors) > 5:
                messages.info(request, f'... and {len(errors) - 5} more errors')
        
        return redirect('loan_applications_list')
    
    return redirect('bulk_disbursement')

@login_required
@transaction.atomic
def upload_bulk_disbursement(request):
    """Process CSV upload for bulk disbursement"""
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        
        # Read CSV file
        try:
            content = csv_file.read().decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = csv_file.read().decode('latin-1')
            except UnicodeDecodeError:
                content = csv_file.read().decode('cp1252')
        
        io_string = io.StringIO(content)
        
        # Parse CSV
        reader = csv.DictReader(io_string)
        required_columns = ['loan_application_number']
        
        # Validate columns
        if not all(col in reader.fieldnames for col in required_columns):
            messages.error(request, f'CSV must contain column: {", ".join(required_columns)}')
            return redirect('bulk_disbursement')
        
        # Get form data
        disbursement_date_str = request.POST.get('disbursement_date')
        disbursement_method = request.POST.get('disbursement_method', 'CASH')
        transaction_prefix = request.POST.get('transaction_prefix', 'DISB-')
        validate_only = request.POST.get('validate_only') == 'on'
        
        # Parse disbursement date
        try:
            disbursement_date = datetime.strptime(disbursement_date_str, '%Y-%m-%d').date()
            disbursement_datetime = timezone.make_aware(
                datetime.combine(disbursement_date, datetime.min.time())
            )
        except (ValueError, TypeError):
            disbursement_datetime = timezone.now()
        
        # Process rows
        success_count = 0
        error_rows = []
        
        for i, row in enumerate(reader, start=2):  # start=2 for Excel row numbers
            try:
                # Get loan application
                app_number = row['loan_application_number'].strip()
                loan = LoanApplication.objects.get(application_number=app_number)
                
                # Validate loan
                if loan.status != 'APPROVED':
                    error_rows.append(f"Row {i}: Loan {app_number} is not approved (status: {loan.status})")
                    continue
                
                if loan.disbursement_date:
                    error_rows.append(f"Row {i}: Loan {app_number} already disbursed")
                    continue
                
                # Get transaction reference from CSV or generate
                transaction_ref = row.get('transaction_reference', '').strip()
                if not transaction_ref:
                    transaction_ref = f"{transaction_prefix}{app_number}"
                
                # Get specific notes for this loan
                specific_notes = row.get('disbursement_notes', '').strip()
                
                if not validate_only:
                    # Update loan for disbursement
                    loan.status = 'DISBURSED'
                    loan.disbursement_date = disbursement_datetime
                    loan.disbursed_by = request.user
                    loan.disbursed_amount = loan.loan_amount
                    loan.transaction_reference = transaction_ref
                    loan.disbursement_notes = specific_notes or request.POST.get('general_notes', '')
                    
                    # Set due date
                    loan.due_date = loan.calculate_due_date()
                    
                    # Save the loan
                    loan.save()
                
                success_count += 1
                
            except LoanApplication.DoesNotExist:
                error_rows.append(f"Row {i}: Loan application {app_number} not found")
            except ValidationError as e:
                error_rows.append(f"Row {i}: Validation error - {e}")
            except Exception as e:
                error_rows.append(f"Row {i}: Error - {str(e)}")
        
        # Show results
        if validate_only:
            if success_count > 0:
                messages.info(request, f'Validation passed for {success_count} loans')
            if error_rows:
                messages.warning(request, f'{len(error_rows)} validation errors found')
                for error in error_rows[:10]:
                    messages.info(request, error)
        else:
            if success_count > 0:
                messages.success(request, f'Successfully disbursed {success_count} loans')
            if error_rows:
                messages.warning(request, f'{len(error_rows)} errors occurred')
                for error in error_rows[:5]:
                    messages.error(request, error)
        
        return redirect('loan_applications_list')
    
    return redirect('bulk_disbursement')

@login_required
def download_disbursement_template(request):
    """Download CSV template for bulk disbursement"""
    template_type = request.GET.get('type', 'simple')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="bulk_disbursement_template.csv"'
    
    writer = csv.writer(response)
    
    if template_type == 'simple':
        writer.writerow(['loan_application_number'])
        # Get some approved loans for example
        approved_loans = LoanApplication.objects.filter(status='APPROVED')[:3]
        for loan in approved_loans:
            writer.writerow([loan.application_number])
    
    elif template_type == 'detailed':
        writer.writerow([
            'loan_application_number',
            'transaction_reference',
            'disbursement_notes'
        ])
        writer.writerow([
            'AN1234',
            'DISB-001',
            'First disbursement of the month'
        ])
    
    elif template_type == 'sample':
        writer.writerow(['loan_application_number', 'transaction_reference', 'disbursement_notes'])
        writer.writerow(['AN1234', 'DISB-2024-001', 'Emergency loan disbursement'])
        writer.writerow(['AN5678', 'DISB-2024-002', 'Business expansion loan'])
        writer.writerow(['AN9012', '', 'Agricultural loan - seasonal'])
    
    return response