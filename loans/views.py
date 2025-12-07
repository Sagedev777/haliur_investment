# loans/views.py

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

from .models import (
    LoanProduct, LoanApplication, Loan, LoanTransaction, 
    LoanRepaymentSchedule, Guarantor, LoanPayment, LoanApplicationDocument
)
from client_accounts.models import ClientAccount
from .forms import (
    LoanProductForm, LoanApplicationForm, LoanApprovalForm, 
    LoanDisbursementForm, LoanPaymentForm, GuarantorForm,
    LoanCalculatorForm, LoanSearchForm, BulkPaymentForm
)
from .services import InterestCalculationService, CreditScoringService, PaymentProcessingService, AmortizationService

# ============================================================================
# MIXINS & DECORATORS
# ============================================================================
class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is staff"""
    def test_func(self):
        return self.request.user.is_staff
    
    def handle_no_permission(self):
        messages.error(self.request, "Access denied. Staff members only.")
        return redirect('admin:index')

class LoanOfficerRequiredMixin(UserPassesTestMixin):
    """Mixin for loan officers only"""
    def test_func(self):
        return (self.request.user.is_staff or 
                self.request.user.groups.filter(name='Loan Officers').exists())
    
    def handle_no_permission(self):
        messages.error(self.request, "Access denied. Loan officers only.")
        return redirect('admin:index')

def staff_required(view_func):
    """Decorator to ensure user is staff"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "Access denied. Staff members only.")
            return redirect('admin:index')
        return view_func(request, *args, **kwargs)
    return wrapper

def loan_officer_required(view_func):
    """Decorator for loan officers only"""
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_staff or 
                request.user.groups.filter(name='Loan Officers').exists()):
            messages.error(request, "Access denied. Loan officers only.")
            return redirect('admin:index')
        return view_func(request, *args, **kwargs)
    return wrapper

# ============================================================================
# DASHBOARD & HOME VIEWS
# ============================================================================
class LoanDashboardView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    """Main dashboard for loan management"""
    template_name = 'loans/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Key Metrics
        context['total_loans'] = Loan.objects.count()
        context['active_loans'] = Loan.objects.filter(status='ACTIVE').count()
        context['overdue_loans'] = Loan.objects.filter(status='OVERDUE').count()
        context['pending_applications'] = LoanApplication.objects.filter(
            status__in=['SUBMITTED', 'UNDER_REVIEW']
        ).count()
        
        # Portfolio Summary
        context['total_portfolio'] = Loan.objects.filter(
            status__in=['ACTIVE', 'OVERDUE']
        ).aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0')
        
        context['total_disbursed'] = Loan.objects.aggregate(
            total=Sum('principal_amount')
        )['total'] or Decimal('0')
        
        context['total_interest_earned'] = LoanTransaction.objects.filter(
            transaction_type='INTEREST_PAYMENT'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        context['total_collections_today'] = LoanTransaction.objects.filter(
            transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT'],
            value_date=timezone.now().date()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Recent Applications
        context['recent_applications'] = LoanApplication.objects.filter(
            status__in=['SUBMITTED', 'UNDER_REVIEW']
        ).select_related('client', 'loan_product', 'loan_officer').order_by('-application_date')[:10]
        
        # Upcoming Payments (next 7 days)
        context['upcoming_payments'] = LoanRepaymentSchedule.objects.filter(
            status__in=['PENDING', 'DUE'],
            due_date__lte=timezone.now().date() + timedelta(days=7),
            due_date__gte=timezone.now().date()
        ).select_related('loan', 'loan__client').order_by('due_date')[:10]
        
        # Overdue Loans
        context['overdue_list'] = Loan.objects.filter(
            status='OVERDUE'
        ).select_related('client', 'loan_product').order_by('-days_overdue')[:10]
        
        # Loan Officer Performance
        if self.request.user.is_superuser:
            # Make sure User is imported
            context['officer_performance'] = User.objects.filter(
                groups__name='Loan Officers'
            ).annotate(
                total_loans=Count('assigned_applications'),
                total_disbursed=Sum('assigned_applications__loan__principal_amount')
            ).order_by('-total_disbursed')[:5]
        
        # Today's Stats
        today = timezone.now().date()
        context['applications_today'] = LoanApplication.objects.filter(
            application_date__date=today
        ).count()
        
        context['disbursements_today'] = Loan.objects.filter(
            disbursement_date=today
        ).aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')
        
        context['payments_today'] = LoanTransaction.objects.filter(
            value_date=today,
            transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return context

@login_required
@staff_required
def dashboard_summary_api(request):
    """API endpoint for dashboard summary (for AJAX updates)"""
    today = timezone.now().date()
    
    data = {
        'total_portfolio': float(Loan.objects.filter(
            status__in=['ACTIVE', 'OVERDUE']
        ).aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0')),
        
        'overdue_amount': float(Loan.objects.filter(
            status='OVERDUE'
        ).aggregate(total=Sum('overdue_amount'))['total'] or Decimal('0')),
        
        'today_collections': float(LoanTransaction.objects.filter(
            transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT'],
            value_date=today
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')),
        
        'pending_applications': LoanApplication.objects.filter(
            status__in=['SUBMITTED', 'UNDER_REVIEW']
        ).count(),
        
        'active_loans': Loan.objects.filter(status='ACTIVE').count(),
        'overdue_loans': Loan.objects.filter(status='OVERDUE').count(),
        'timestamp': timezone.now().isoformat(),
    }
    
    return JsonResponse(data)

# ============================================================================
# LOAN PRODUCT VIEWS
# ============================================================================
class LoanProductListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    """List all loan products"""
    model = LoanProduct
    template_name = 'loans/loanproduct_list.html'
    context_object_name = 'products'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = LoanProduct.objects.all().order_by('-created_date')
        
        # Filter by active status
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_count'] = LoanProduct.objects.filter(is_active=True).count()
        context['inactive_count'] = LoanProduct.objects.filter(is_active=False).count()
        context['total_products'] = LoanProduct.objects.count()
        return context

class LoanProductCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    """Create new loan product"""
    model = LoanProduct
    form_class = LoanProductForm
    template_name = 'loans/loanproduct_form.html'
    success_url = reverse_lazy('loans:loan_product_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f"Loan product '{form.instance.name}' created successfully!")
        return super().form_valid(form)

class LoanProductUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """Update existing loan product"""
    model = LoanProduct
    form_class = LoanProductForm
    template_name = 'loans/loanproduct_form.html'
    success_url = reverse_lazy('loans:loan_product_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"Loan product '{form.instance.name}' updated successfully!")
        return super().form_valid(form)

class LoanProductDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    """Delete loan product"""
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
    """Toggle loan product active status"""
    product = get_object_or_404(LoanProduct, pk=pk)
    product.is_active = not product.is_active
    product.save()
    
    status = "activated" if product.is_active else "deactivated"
    messages.success(request, f"Loan product '{product.name}' {status} successfully!")
    
    return redirect('loans:loan_product_list')

# ============================================================================
# LOAN APPLICATION VIEWS
# ============================================================================
class LoanApplicationListView(LoginRequiredMixin, LoanOfficerRequiredMixin, ListView):
    """List loan applications with filtering"""
    model = LoanApplication
    template_name = 'loans/loanapplication_list.html'
    context_object_name = 'applications'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = LoanApplication.objects.select_related(
            'client', 'loan_product', 'loan_officer'
        ).prefetch_related('guarantors').order_by('-application_date')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by loan officer (if not admin)
        if not self.request.user.is_superuser:
            queryset = queryset.filter(loan_officer=self.request.user)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from and date_to:
            queryset = queryset.filter(application_date__date__range=[date_from, date_to])
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(application_number__icontains=search) |
                Q(client__full_account_name__icontains=search) |
                Q(client__account_number__icontains=search) |
                Q(purpose__icontains=search)
            )
        
        # Filter by amount range
        min_amount = self.request.GET.get('min_amount')
        max_amount = self.request.GET.get('max_amount')
        if min_amount:
            queryset = queryset.filter(requested_amount__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(requested_amount__lte=max_amount)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Count by status
        status_counts = {}
        for status_choice in LoanApplication.APPLICATION_STATUS:
            status_counts[status_choice[0]] = LoanApplication.objects.filter(
                status=status_choice[0]
            ).count()
        
        context['status_counts'] = status_counts
        context['total_applications'] = LoanApplication.objects.count()
        context['search_form'] = LoanSearchForm(self.request.GET or None)
        
        return context

class LoanApplicationCreateView(LoginRequiredMixin, LoanOfficerRequiredMixin, CreateView):
    """Create new loan application"""
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
            
            # Calculate credit score (if the method exists)
            if hasattr(application, 'calculate_credit_score'):
                application.credit_score = application.calculate_credit_score()
            
                # Set risk rating
                if application.credit_score >= 80:
                    application.risk_rating = 'A'
                elif application.credit_score >= 60:
                    application.risk_rating = 'B'
                elif application.credit_score >= 40:
                    application.risk_rating = 'C'
                else:
                    application.risk_rating = 'D'
            
            # SAVE FIRST before setting relationships
            application.save()
            
            # NOW you can set many-to-many relationships
            form.save_m2m()  # This saves guarantors from the form
            
            # Handle collateral documents if they exist in the form
            if 'collateral_documents' in form.cleaned_data:
                collateral_docs = form.cleaned_data.get('collateral_documents')
                if collateral_docs:
                    application.collateral_documents.set(collateral_docs)
            
            # Handle uploaded documents
            documents = self.request.FILES.getlist('documents')
            for document in documents:
                LoanApplicationDocument.objects.create(
                    loan_application=application,
                    document=document
                )
            
            messages.success(
                self.request, 
                f"Loan application {application.application_number} submitted successfully!"
            )
        
        return redirect('loans:loan_application_detail', pk=application.pk)
    
    
class LoanApplicationDetailView(LoginRequiredMixin, LoanOfficerRequiredMixin, DetailView):
    """View loan application details"""
    model = LoanApplication
    template_name = 'loans/loanapplication_detail.html'
    context_object_name = 'application'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.get_object()
        
        # Calculate eligibility
        if hasattr(application.client, 'monthly_income') and application.client.monthly_income:
            context['debt_to_income_ratio'] = (
                (application.requested_amount + sum(
                    loan.remaining_balance for loan in application.client.loans.filter(
                        status__in=['ACTIVE', 'OVERDUE']
                    )
                )) / application.client.monthly_income
            )
        
        # Get similar approved applications for comparison
        context['similar_applications'] = LoanApplication.objects.filter(
            loan_product=application.loan_product,
            status='APPROVED',
            client__monthly_income__range=[
                application.client.monthly_income * Decimal('0.8') if application.client.monthly_income else Decimal('0'),
                application.client.monthly_income * Decimal('1.2') if application.client.monthly_income else Decimal('1000000')
            ]
        ).exclude(pk=application.pk)[:5]
        
        # Calculate recommended approval amount
        if application.client.current_balance:
            recommended_amount = min(
                application.requested_amount,
                application.client.current_balance * Decimal('3'),  # 3x savings
                application.client.monthly_income * Decimal('6') if application.client.monthly_income else Decimal('1000000')  # 6x monthly income
            )
            context['recommended_amount'] = recommended_amount.quantize(Decimal('1000'), rounding=ROUND_HALF_UP)
        
        return context

class LoanApplicationUpdateView(LoginRequiredMixin, LoanOfficerRequiredMixin, UpdateView):
    """Update loan application"""
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
            
            # Update credit score if amount changed
            if 'requested_amount' in form.changed_data:
                application.credit_score = application.calculate_credit_score()
                
                # Update risk rating
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
            
            messages.success(
                self.request, 
                f"Loan application {application.application_number} updated successfully!"
            )
        
        return redirect('loans:loan_application_detail', pk=application.pk)

@login_required
@staff_required
def loan_application_review(request, pk):
    """Review and approve/reject loan application"""
    application = get_object_or_404(LoanApplication, pk=pk)
    
    if request.method == 'POST':
        form = LoanApprovalForm(request.POST, instance=application)
        
        if form.is_valid():
            with transaction.atomic():
                updated_application = form.save(commit=False)
                updated_application.reviewed_by = request.user
                updated_application.review_date = timezone.now()
                
                if updated_application.status == 'APPROVED':
                    # Calculate final amounts
                    product = updated_application.loan_product
                    
                    # Calculate processing fee
                    processing_fee = (
                        updated_application.approved_amount * 
                        product.processing_fee_percent / Decimal('100')
                    )
                    
                    updated_application.processing_fee_amount = processing_fee
                    updated_application.net_disbursement_amount = (
                        updated_application.approved_amount - processing_fee
                    )
                    
                    # Calculate interest
                    interest_service = InterestCalculationService()
                    total_interest = interest_service.calculate_interest(
                        updated_application.approved_amount,
                        updated_application.approved_interest_rate,
                        updated_application.approved_term_days,
                        method=product.interest_calculation_method,
                        interest_type=product.interest_type
                    )
                    
                    updated_application.total_interest_amount = total_interest
                    updated_application.total_repayment_amount = (
                        updated_application.approved_amount + total_interest
                    )
                    
                    updated_application.approval_date = timezone.now()
                    updated_application.approved_by = request.user
                
                updated_application.save()
                
                # Create loan if approved
                if updated_application.status == 'APPROVED':
                    messages.success(
                        request, 
                        f"Application {application.application_number} approved! You can now disburse the loan."
                    )
                    return redirect('loans:loan_disbursement_create', application_id=application.pk)
                else:
                    messages.success(
                        request, 
                        f"Application {application.application_number} updated successfully!"
                    )
                    return redirect('loans:loan_application_detail', pk=application.pk)
    else:
        form = LoanApprovalForm(instance=application)
    
    # Get client's existing loans
    existing_loans = Loan.objects.filter(
        client=application.client,
        status__in=['ACTIVE', 'OVERDUE']
    ).select_related('loan_product')
    
    # Calculate client's debt capacity
    total_existing_debt = sum(loan.remaining_balance for loan in existing_loans)
    
    # Calculate max loan based on savings
    max_loan_by_savings = application.client.current_balance * Decimal('3')
    
    # Calculate max loan based on income
    max_loan_by_income = Decimal('0')
    if hasattr(application.client, 'monthly_income') and application.client.monthly_income:
        max_loan_by_income = application.client.monthly_income * Decimal('6')
    
    context = {
        'application': application,
        'form': form,
        'existing_loans': existing_loans,
        'total_existing_debt': total_existing_debt,
        'max_loan_by_savings': max_loan_by_savings,
        'max_loan_by_income': max_loan_by_income,
        'recommended_amount': min(application.requested_amount, max_loan_by_savings, max_loan_by_income),
    }
    
    return render(request, 'loans/loanapplication_review.html', context)

@login_required
@staff_required
def loan_application_documents(request, pk):
    """View and manage application documents"""
    application = get_object_or_404(LoanApplication, pk=pk)
    
    if request.method == 'POST' and request.FILES.getlist('documents'):
        documents = request.FILES.getlist('documents')
        for document in documents:
            LoanApplicationDocument.objects.create(
                loan_application=application,
                document=document
            )
        messages.success(request, f"{len(documents)} document(s) uploaded successfully!")
        return redirect('loans:loan_application_documents', pk=application.pk)
    
    documents = application.documents.all()
    
    return render(request, 'loans/loanapplication_documents.html', {
        'application': application,
        'documents': documents,
    })

# ============================================================================
# LOAN DISBURSEMENT VIEWS
# ============================================================================
@login_required
@staff_required
def loan_disbursement_create(request, application_id):
    """Create loan from approved application"""
    application = get_object_or_404(LoanApplication, pk=application_id, status='APPROVED')
    
    if request.method == 'POST':
        form = LoanDisbursementForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create Loan object
                    loan = Loan.objects.create(
                        application=application,
                        client=application.client,
                        loan_product=application.loan_product,
                        principal_amount=application.approved_amount,
                        interest_rate=application.approved_interest_rate,
                        term_days=application.approved_term_days,
                        disbursement_date=form.cleaned_data['disbursement_date'],
                        disbursed_by=request.user,
                        loan_officer=application.loan_officer,
                        status='PENDING_DISBURSEMENT',
                        remaining_balance=application.total_repayment_amount,
                        total_interest_amount=application.total_interest_amount,
                        total_repayment_amount=application.total_repayment_amount,
                        processing_fee_amount=application.processing_fee_amount,
                    )
                    
                    # Generate amortization schedule
                    amortization_service = AmortizationService()
                    schedule_data = amortization_service.generate_amortization_schedule(loan)
                    
                    # Create repayment schedule entries
                    for installment_data in schedule_data:
                        LoanRepaymentSchedule.objects.create(
                            loan=loan,
                            installment_number=installment_data['installment_number'],
                            due_date=installment_data['due_date'],
                            principal_amount=installment_data['principal_amount'],
                            interest_amount=installment_data['interest_amount'],
                            total_amount=installment_data['total_amount'],
                            status='PENDING',
                        )
                    
                    # Update first payment date
                    first_installment = loan.repayment_schedule.order_by('due_date').first()
                    if first_installment:
                        loan.first_payment_date = first_installment.due_date
                        loan.next_payment_date = first_installment.due_date
                    
                    # Update loan status to ACTIVE
                    loan.status = 'ACTIVE'
                    loan.save()
                    
                    # Create disbursement transaction
                    LoanTransaction.objects.create(
                        loan=loan,
                        transaction_type='DISBURSEMENT',
                        payment_method=form.cleaned_data['payment_method'],
                        amount=application.net_disbursement_amount,
                        principal_amount=application.approved_amount,
                        fee_amount=application.processing_fee_amount,
                        notes=f"Loan disbursement for {application.application_number}",
                        recorded_by=request.user,
                        reference_number=form.cleaned_data.get('transaction_reference', ''),
                    )
                    
                    # Update application status
                    application.status = 'DISBURSED'
                    application.save()
                    
                    # Update client account balance (if integrated with client_accounts)
                    # This would depend on your client_accounts implementation
                    # client_account = application.client
                    # client_account.current_balance += application.net_disbursement_amount
                    # client_account.save()
                    
                    messages.success(request, f"Loan {loan.loan_number} created and disbursed successfully!")
                    return redirect('loans:loan_detail', pk=loan.pk)
                    
            except Exception as e:
                messages.error(request, f"Error creating loan: {str(e)}")
    
    else:
        initial_data = {
            'disbursement_date': timezone.now().date(),
            'payment_method': 'BANK_TRANSFER',
        }
        form = LoanDisbursementForm(initial=initial_data)
    
    context = {
        'application': application,
        'form': form,
        'title': f'Disburse Loan for {application.application_number}',
    }
    
    return render(request, 'loans/loan_disbursement_create.html', context)

@login_required
@staff_required
def bulk_loan_disbursement(request):
    """Bulk disbursement of approved loans"""
    if request.method == 'POST':
        loan_ids = request.POST.getlist('loan_ids')
        payment_method = request.POST.get('payment_method', 'BANK_TRANSFER')
        disbursement_date = request.POST.get('disbursement_date', timezone.now().date())
        reference_prefix = request.POST.get('reference_prefix', '')
        
        loans = Loan.objects.filter(
            pk__in=loan_ids,
            status='PENDING_DISBURSEMENT'
        ).select_related('application', 'client', 'loan_product')
        
        disbursed_count = 0
        errors = []
        
        for loan in loans:
            try:
                with transaction.atomic():
                    # Update loan
                    loan.disbursement_date = disbursement_date
                    loan.status = 'ACTIVE'
                    
                    # Calculate maturity date
                    if disbursement_date and loan.term_days:
                        loan.maturity_date = disbursement_date + timedelta(days=loan.term_days)
                    
                    # Generate repayment schedule if not exists
                    if not loan.repayment_schedule.exists():
                        amortization_service = AmortizationService()
                        schedule_data = amortization_service.generate_amortization_schedule(loan)
                        
                        for installment_data in schedule_data:
                            LoanRepaymentSchedule.objects.create(
                                loan=loan,
                                installment_number=installment_data['installment_number'],
                                due_date=installment_data['due_date'],
                                principal_amount=installment_data['principal_amount'],
                                interest_amount=installment_data['interest_amount'],
                                total_amount=installment_data['total_amount'],
                                status='PENDING',
                            )
                    
                    # Update first payment date
                    first_installment = loan.repayment_schedule.order_by('due_date').first()
                    if first_installment:
                        loan.first_payment_date = first_installment.due_date
                        loan.next_payment_date = first_installment.due_date
                    
                    loan.save()
                    
                    # Create disbursement transaction
                    LoanTransaction.objects.create(
                        loan=loan,
                        transaction_type='DISBURSEMENT',
                        payment_method=payment_method,
                        amount=loan.application.net_disbursement_amount,
                        principal_amount=loan.principal_amount,
                        fee_amount=loan.processing_fee_amount,
                        notes=f"Bulk loan disbursement",
                        recorded_by=request.user,
                        reference_number=f"{reference_prefix}-{loan.loan_number}" if reference_prefix else loan.loan_number,
                    )
                    
                    # Update application status
                    if loan.application:
                        loan.application.status = 'DISBURSED'
                        loan.application.save()
                    
                    disbursed_count += 1
                    
            except Exception as e:
                errors.append(f"Loan {loan.loan_number}: {str(e)}")
        
        if disbursed_count > 0:
            messages.success(request, f"{disbursed_count} loans disbursed successfully!")
        
        if errors:
            messages.error(request, f"Errors: {', '.join(errors[:5])}" + ("..." if len(errors) > 5 else ""))
        
        return redirect('loans:loan_list')
    
    # GET request - show pending disbursement loans
    pending_loans = Loan.objects.filter(
        status='PENDING_DISBURSEMENT'
    ).select_related('client', 'loan_product').order_by('created_at')
    
    return render(request, 'loans/bulk_disbursement.html', {
        'pending_loans': pending_loans,
    })

# ============================================================================
# LOAN MANAGEMENT VIEWS
# ============================================================================
class LoanListView(LoginRequiredMixin, LoanOfficerRequiredMixin, ListView):
    """List all loans with filtering"""
    model = Loan
    template_name = 'loans/loan_list.html'
    context_object_name = 'loans'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Loan.objects.select_related(
            'client', 'loan_product', 'loan_officer', 'application'
        ).order_by('-disbursement_date')
        
        # Filter by status
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by loan officer (if not admin)
        if not self.request.user.is_superuser:
            queryset = queryset.filter(loan_officer=self.request.user)
        
        # Search
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(loan_number__icontains=search_query) |
                Q(client__full_account_name__icontains=search_query) |
                Q(client__account_number__icontains=search_query) |
                Q(client__phone_number__icontains=search_query)
            )
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from and date_to:
            queryset = queryset.filter(disbursement_date__range=[date_from, date_to])
        
        # Filter by amount range
        min_amount = self.request.GET.get('min_amount')
        max_amount = self.request.GET.get('max_amount')
        if min_amount:
            queryset = queryset.filter(principal_amount__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(principal_amount__lte=max_amount)
        
        # Filter by product
        product_id = self.request.GET.get('product')
        if product_id:
            queryset = queryset.filter(loan_product_id=product_id)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        context['total_loans'] = Loan.objects.count()
        context['total_portfolio'] = Loan.objects.filter(
            status__in=['ACTIVE', 'OVERDUE']
        ).aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0')
        
        context['overdue_amount'] = Loan.objects.filter(
            status='OVERDUE'
        ).aggregate(total=Sum('overdue_amount'))['total'] or Decimal('0')
        
        # Status counts
        status_counts = {}
        for status_choice in Loan.LOAN_STATUS:
            status_counts[status_choice[0]] = Loan.objects.filter(
                status=status_choice[0]
            ).count()
        
        context['status_counts'] = status_counts
        context['search_form'] = LoanSearchForm(self.request.GET or None)
        context['products'] = LoanProduct.objects.filter(is_active=True)
        
        return context

class LoanDetailView(LoginRequiredMixin, LoanOfficerRequiredMixin, DetailView):
    """Detailed loan view with transactions and schedule"""
    model = Loan
    template_name = 'loans/loan_detail.html'
    context_object_name = 'loan'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan = self.get_object()
        
        # Get repayment schedule
        repayment_schedule = loan.repayment_schedule.all().order_by('installment_number')
        context['repayment_schedule'] = repayment_schedule
        
        # Get transactions
        transactions = loan.transactions.all().order_by('-transaction_date')
        context['transactions'] = transactions
        
        # Get payments (compatibility layer)
        payments = loan.payments.all().order_by('-payment_date')
        context['payments'] = payments
        
        # Calculate statistics
        total_paid = loan.transactions.filter(
            transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        context['total_paid'] = total_paid
        context['remaining_percent'] = (
            loan.remaining_balance / loan.total_repayment_amount * 100
        ) if loan.total_repayment_amount > 0 else 0
        
        # Next payment info
        next_installment = repayment_schedule.filter(
            status__in=['PENDING', 'DUE']
        ).order_by('due_date').first()
        
        context['next_installment'] = next_installment
        context['days_until_next'] = (
            (next_installment.due_date - timezone.now().date()).days 
            if next_installment else None
        )
        
        # Overdue installments
        context['overdue_installments'] = repayment_schedule.filter(
            status__in=['DUE', 'OVERDUE'],
            due_date__lt=timezone.now().date()
        ).order_by('due_date')
        
        # Payment summary
        context['payment_summary'] = {
            'principal_paid': loan.transactions.filter(
                transaction_type='PRINCIPAL_PAYMENT'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
            'interest_paid': loan.transactions.filter(
                transaction_type='INTEREST_PAYMENT'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
            'late_fees_paid': loan.transactions.filter(
                transaction_type='LATE_FEE_PAYMENT'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
        }
        
        return context

@login_required
@loan_officer_required
def loan_statement(request, pk):
    """Generate loan statement"""
    loan = get_object_or_404(Loan, pk=pk)
    
    # Get all transactions
    transactions = loan.transactions.all().order_by('transaction_date')
    
    # Calculate running balance
    running_balance = loan.total_repayment_amount
    statement_lines = []
    
    for transaction in transactions:
        if transaction.transaction_type == 'DISBURSEMENT':
            running_balance -= transaction.amount
        elif transaction.transaction_type in ['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT']:
            running_balance += transaction.amount
        
        statement_lines.append({
            'date': transaction.value_date,
            'description': transaction.get_transaction_type_display(),
            'reference': transaction.reference_number or transaction.transaction_id,
            'debit': transaction.amount if transaction.transaction_type == 'DISBURSEMENT' else Decimal('0'),
            'credit': transaction.amount if transaction.transaction_type != 'DISBURSEMENT' else Decimal('0'),
            'balance': running_balance,
        })
    
    context = {
        'loan': loan,
        'statement_lines': statement_lines,
        'generated_date': timezone.now(),
        'opening_balance': loan.total_repayment_amount,
        'closing_balance': running_balance,
    }
    
    # Return as PDF if requested
    if request.GET.get('format') == 'pdf':
        # You would implement PDF generation here
        # For now, return HTML
        return render(request, 'loans/loan_statement_pdf.html', context)
    
    return render(request, 'loans/loan_statement.html', context)

@login_required
@staff_required
def loan_reschedule(request, pk):
    """Reschedule a loan"""
    loan = get_object_or_404(Loan, pk=pk)
    
    if request.method == 'POST':
        new_term_days = int(request.POST.get('new_term_days'))
        new_interest_rate = Decimal(request.POST.get('new_interest_rate', loan.interest_rate))
        reason = request.POST.get('reason', '')
        
        try:
            # Reschedule the loan
            amortization_service = AmortizationService()
            result = amortization_service.reschedule_loan(
                loan=loan,
                new_term_days=new_term_days,
                new_interest_rate=new_interest_rate,
                reschedule_date=timezone.now().date()
            )
            
            # Create adjustment transaction
            LoanTransaction.objects.create(
                loan=loan,
                transaction_type='ADJUSTMENT',
                payment_method='SYSTEM',
                amount=Decimal('0'),
                notes=f"Loan rescheduled: {reason}",
                recorded_by=request.user,
            )
            
            messages.success(request, f"Loan {loan.loan_number} rescheduled successfully!")
            return redirect('loans:loan_detail', pk=loan.pk)
            
        except Exception as e:
            messages.error(request, f"Error rescheduling loan: {str(e)}")
    
    context = {
        'loan': loan,
        'current_term_days': loan.term_days,
        'current_interest_rate': loan.interest_rate,
    }
    
    return render(request, 'loans/loan_reschedule.html', context)

# ============================================================================
# PAYMENT PROCESSING VIEWS
# ============================================================================
@login_required
@loan_officer_required
def process_payment(request, pk):
    """Process loan payment with allocation logic"""
    loan = get_object_or_404(Loan, pk=pk)
    
    if request.method == 'POST':
        form = LoanPaymentForm(request.POST, loan=loan)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    payment_service = PaymentProcessingService()
                    
                    allocation = payment_service.process_payment(
                        loan=loan,
                        amount=form.cleaned_data['amount'],
                        payment_date=form.cleaned_data['payment_date'],
                        payment_method=form.cleaned_data['payment_method'],
                        received_by=request.user,
                        notes=form.cleaned_data['notes'],
                        allocation_strategy=form.cleaned_data['allocate_to']
                    )
                    
                    # Create LoanPayment record for compatibility
                    LoanPayment.objects.create(
                        loan=loan,
                        amount=form.cleaned_data['amount'],
                        principal_amount=allocation['principal'],
                        interest_amount=allocation['interest'],
                        late_fee_amount=allocation['late_fees'],
                        status='PAID',
                    )
                    
                    messages.success(
                        request, 
                        f"Payment of {form.cleaned_data['amount']} processed successfully!\n"
                        f"Allocated: Principal: {allocation['principal']}, "
                        f"Interest: {allocation['interest']}, "
                        f"Late Fees: {allocation['late_fees']}"
                    )
                    
                    return redirect('loans:loan_detail', pk=loan.pk)
                    
            except Exception as e:
                messages.error(request, f"Error processing payment: {str(e)}")
    else:
        form = LoanPaymentForm(loan=loan)
    
    context = {
        'loan': loan,
        'form': form,
        'outstanding_balance': loan.remaining_balance,
        'overdue_amount': loan.overdue_amount,
        'next_payment_date': loan.next_payment_date,
        'overdue_installments': loan.repayment_schedule.filter(
            status__in=['DUE', 'OVERDUE'],
            due_date__lt=timezone.now().date()
        ),
    }
    
    return render(request, 'loans/process_payment.html', context)

@login_required
@staff_required
def bulk_payment_processing(request):
    """Process bulk payments for multiple loans"""
    if request.method == 'POST':
        form = BulkPaymentForm(request.POST)
        
        if form.is_valid():
            loan_ids = form.cleaned_data['loan_ids'].split(',')
            amount = form.cleaned_data['amount']
            payment_method = form.cleaned_data['payment_method']
            payment_date = form.cleaned_data['payment_date']
            reference_prefix = form.cleaned_data.get('reference_prefix', '')
            notes = form.cleaned_data.get('notes', '')
            
            loans = Loan.objects.filter(
                pk__in=loan_ids,
                status__in=['ACTIVE', 'OVERDUE']
            ).select_related('client')
            
            processed_count = 0
            errors = []
            
            for loan in loans:
                try:
                    with transaction.atomic():
                        payment_service = PaymentProcessingService()
                        
                        allocation = payment_service.process_payment(
                            loan=loan,
                            amount=amount,
                            payment_date=payment_date,
                            payment_method=payment_method,
                            received_by=request.user,
                            notes=f"{notes} (Bulk payment)",
                            allocation_strategy='AUTO'
                        )
                        
                        # Create LoanPayment record
                        LoanPayment.objects.create(
                            loan=loan,
                            amount=amount,
                            principal_amount=allocation['principal'],
                            interest_amount=allocation['interest'],
                            late_fee_amount=allocation['late_fees'],
                            status='PAID',
                        )
                        
                        processed_count += 1
                        
                except Exception as e:
                    errors.append(f"Loan {loan.loan_number}: {str(e)}")
            
            if processed_count > 0:
                messages.success(request, f"{processed_count} payments processed successfully!")
            
            if errors:
                messages.warning(request, f"Errors: {', '.join(errors[:3])}" + ("..." if len(errors) > 3 else ""))
            
            return redirect('loans:loan_list')
    
    else:
        form = BulkPaymentForm()
    
    return render(request, 'loans/bulk_payment.html', {'form': form})

@login_required
@loan_officer_required
def payment_receipt(request, transaction_id):
    """Generate payment receipt"""
    transaction = get_object_or_404(LoanTransaction, transaction_id=transaction_id)
    
    context = {
        'transaction': transaction,
        'loan': transaction.loan,
        'generated_date': timezone.now(),
    }
    
    # Return as PDF if requested
    if request.GET.get('format') == 'pdf':
        return render(request, 'loans/payment_receipt_pdf.html', context)
    
    return render(request, 'loans/payment_receipt.html', context)

# ============================================================================
# GUARANTOR VIEWS
# ============================================================================
class GuarantorListView(LoginRequiredMixin, LoanOfficerRequiredMixin, ListView):
    """List all guarantors"""
    model = Guarantor
    template_name = 'loans/guarantor_list.html'
    context_object_name = 'guarantors'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Guarantor.objects.select_related('individual').order_by('-created_at')
        
        # Filter by type
        guarantor_type = self.request.GET.get('type')
        if guarantor_type:
            queryset = queryset.filter(guarantor_type=guarantor_type)
        
        # Filter by status
        is_active = self.request.GET.get('is_active')
        if is_active in ['true', 'false']:
            queryset = queryset.filter(is_active=(is_active == 'true'))
        
        # Filter by verification status
        verified = self.request.GET.get('verified')
        if verified in ['true', 'false']:
            queryset = queryset.filter(verified=(verified == 'true'))
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(guarantor_id__icontains=search) |
                Q(individual__full_account_name__icontains=search) |
                Q(company_name__icontains=search) |
                Q(contact_person__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(nin__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_guarantors'] = Guarantor.objects.count()
        context['active_guarantors'] = Guarantor.objects.filter(is_active=True).count()
        context['verified_guarantors'] = Guarantor.objects.filter(verified=True).count()
        return context

class GuarantorCreateView(LoginRequiredMixin, LoanOfficerRequiredMixin, CreateView):
    """Create new guarantor"""
    model = Guarantor
    form_class = GuarantorForm
    template_name = 'loans/guarantor_form.html'
    success_url = reverse_lazy('loans:guarantor_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f"Guarantor created successfully!")
        return super().form_valid(form)

class GuarantorDetailView(LoginRequiredMixin, LoanOfficerRequiredMixin, DetailView):
    """View guarantor details"""
    model = Guarantor
    template_name = 'loans/guarantor_detail.html'
    context_object_name = 'guarantor'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guarantor = self.get_object()
        
        # Get loans where this guarantor is involved
        context['guaranteed_loans'] = LoanApplication.objects.filter(
            guarantors=guarantor
        ).select_related('client', 'loan_product').order_by('-application_date')
        
        return context

class GuarantorUpdateView(LoginRequiredMixin, LoanOfficerRequiredMixin, UpdateView):
    """Update guarantor"""
    model = Guarantor
    form_class = GuarantorForm
    template_name = 'loans/guarantor_form.html'
    
    def get_success_url(self):
        return reverse('loans:guarantor_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f"Guarantor updated successfully!")
        return super().form_valid(form)

@login_required
@staff_required
def guarantor_verify(request, pk):
    """Verify a guarantor"""
    guarantor = get_object_or_404(Guarantor, pk=pk)
    
    if request.method == 'POST':
        guarantor.verified = True
        guarantor.verified_by = request.user
        guarantor.verification_date = timezone.now().date()
        guarantor.save()
        
        messages.success(request, f"Guarantor {guarantor.guarantor_id} verified successfully!")
        return redirect('loans:guarantor_detail', pk=guarantor.pk)
    
    return render(request, 'loans/guarantor_verify.html', {'guarantor': guarantor})

# ============================================================================
# CALCULATOR & TOOLS VIEWS
# ============================================================================
@login_required
@loan_officer_required
def loan_calculator(request):
    """Loan calculator tool"""
    if request.method == 'POST':
        form = LoanCalculatorForm(request.POST)
        
        if form.is_valid():
            principal = form.cleaned_data['loan_amount']
            annual_rate = form.cleaned_data['interest_rate']
            term_days = form.cleaned_data['term_days']
            interest_type = form.cleaned_data['interest_type']
            calculation_method = form.cleaned_data['calculation_method']
            
            interest_service = InterestCalculationService()
            
            # Calculate interest
            total_interest = interest_service.calculate_interest(
                principal, annual_rate, term_days,
                method=calculation_method, interest_type=interest_type
            )
            
            total_repayment = principal + total_interest
            
            # Calculate installments
            if term_days <= 30:
                installments = 4  # Weekly
                installment_days = 7
            elif term_days <= 90:
                installments = 12  # Weekly
                installment_days = term_days // 12
            else:
                installments = term_days // 30  # Monthly
                installment_days = 30
            
            installment_amount = total_repayment / installments
            
            # Generate sample schedule
            schedule = []
            current_date = timezone.now().date()
            
            for i in range(1, installments + 1):
                due_date = current_date + timedelta(days=installment_days)
                schedule.append({
                    'installment': i,
                    'due_date': due_date,
                    'amount': installment_amount,
                })
                current_date = due_date
            
            context = {
                'form': form,
                'calculation': {
                    'principal': principal,
                    'annual_rate': annual_rate,
                    'term_days': term_days,
                    'total_interest': total_interest,
                    'total_repayment': total_repayment,
                    'installments': installments,
                    'installment_amount': installment_amount,
                    'schedule': schedule,
                }
            }
            
            return render(request, 'loans/loan_calculator.html', context)
    
    else:
        form = LoanCalculatorForm()
    
    return render(request, 'loans/loan_calculator.html', {'form': form})

@login_required
@loan_officer_required
def client_eligibility_check(request, client_id):
    """Check client eligibility for loans"""
    client = get_object_or_404(ClientAccount, pk=client_id)
    
    # Get existing loans
    existing_loans = Loan.objects.filter(
        client=client,
        status__in=['ACTIVE', 'OVERDUE']
    )
    
    total_existing_debt = sum(loan.remaining_balance for loan in existing_loans)
    
    # Calculate eligibility
    max_loan_by_savings = client.current_balance * Decimal('3')
    
    max_loan_by_income = Decimal('0')
    if hasattr(client, 'monthly_income') and client.monthly_income:
        max_loan_by_income = client.monthly_income * Decimal('6')
    
    eligible_amount = min(max_loan_by_savings, max_loan_by_income)
    available_amount = max(Decimal('0'), eligible_amount - total_existing_debt)
    
    # Get recommended products
    recommended_products = LoanProduct.objects.filter(
        is_active=True,
        min_loan_amount__lte=available_amount,
        max_loan_amount__gte=available_amount
    ).order_by('annual_interest_rate')
    
    context = {
        'client': client,
        'existing_loans': existing_loans,
        'total_existing_debt': total_existing_debt,
        'max_loan_by_savings': max_loan_by_savings,
        'max_loan_by_income': max_loan_by_income,
        'eligible_amount': eligible_amount,
        'available_amount': available_amount,
        'recommended_products': recommended_products,
    }
    
    return render(request, 'loans/client_eligibility.html', context)

# ============================================================================
# API ENDPOINTS
# ============================================================================
@login_required
@require_http_methods(["GET"])
def api_calculate_repayment(request):
    """API endpoint for repayment calculation"""
    try:
        principal = Decimal(request.GET.get('principal', '0'))
        annual_rate = Decimal(request.GET.get('annual_rate', '0'))
        term_days = int(request.GET.get('term_days', '0'))
        interest_type = request.GET.get('interest_type', 'FLAT')
        calculation_method = request.GET.get('calculation_method', 'ACTUAL_365')
        
        interest_service = InterestCalculationService()
        
        total_interest = interest_service.calculate_interest(
            principal, annual_rate, term_days,
            method=calculation_method, interest_type=interest_type
        )
        
        total_repayment = principal + total_interest
        
        # Calculate installments
        if term_days <= 30:
            installments = 4
        elif term_days <= 90:
            installments = 12
        else:
            installments = term_days // 30
        
        installment_amount = total_repayment / installments
        
        return JsonResponse({
            'success': True,
            'principal': float(principal),
            'total_interest': float(total_interest),
            'total_repayment': float(total_repayment),
            'installments': installments,
            'installment_amount': float(installment_amount),
            'daily_interest': float(total_interest / term_days if term_days > 0 else 0),
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
@require_http_methods(["GET"])
def api_client_eligibility(request, client_id):
    """API endpoint for client eligibility check"""
    try:
        client = get_object_or_404(ClientAccount, pk=client_id)
        
        existing_loans = Loan.objects.filter(
            client=client,
            status__in=['ACTIVE', 'OVERDUE']
        )
        
        total_existing_debt = sum(loan.remaining_balance for loan in existing_loans)
        
        max_loan_by_savings = client.current_balance * Decimal('3')
        
        max_loan_by_income = Decimal('0')
        if hasattr(client, 'monthly_income') and client.monthly_income:
            max_loan_by_income = client.monthly_income * Decimal('6')
        
        eligible_amount = min(max_loan_by_savings, max_loan_by_income)
        available_amount = max(Decimal('0'), eligible_amount - total_existing_debt)
        
        return JsonResponse({
            'client_id': client_id,
            'client_name': client.full_account_name,
            'current_savings': float(client.current_balance),
            'monthly_income': float(client.monthly_income) if client.monthly_income else 0,
            'existing_debt': float(total_existing_debt),
            'max_loan_by_savings': float(max_loan_by_savings),
            'max_loan_by_income': float(max_loan_by_income),
            'eligible_amount': float(eligible_amount),
            'available_amount': float(available_amount),
            'debt_to_income_ratio': float(
                total_existing_debt / client.monthly_income if client.monthly_income else 0
            ),
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def api_webhook_payment(request):
    """Webhook for external payment notifications (e.g., mobile money, bank)"""
    try:
        data = json.loads(request.body)
        
        # Verify the webhook (implement your verification logic)
        # This is a simplified example
        
        loan_number = data.get('loan_number')
        amount = Decimal(data.get('amount', '0'))
        reference = data.get('reference')
        payment_method = data.get('payment_method', 'MOBILE_MONEY')
        
        loan = get_object_or_404(Loan, loan_number=loan_number)
        
        with transaction.atomic():
            payment_service = PaymentProcessingService()
            
            allocation = payment_service.process_payment(
                loan=loan,
                amount=amount,
                payment_date=timezone.now().date(),
                payment_method=payment_method,
                received_by=None,  # System recorded
                notes=f"Auto payment via webhook: {reference}",
                allocation_strategy='AUTO'
            )
            
            # Create transaction
            LoanTransaction.objects.create(
                loan=loan,
                transaction_type='PRINCIPAL_PAYMENT' if allocation['principal'] > 0 else 'INTEREST_PAYMENT',
                payment_method=payment_method,
                amount=amount,
                principal_amount=allocation['principal'],
                interest_amount=allocation['interest'],
                fee_amount=allocation['late_fees'],
                notes=f"Auto payment: {reference}",
                recorded_by=None,
                reference_number=reference,
            )
        
        return JsonResponse({'success': True, 'message': 'Payment processed'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

# ============================================================================
# REPORT & EXPORT VIEWS
# ============================================================================
@login_required
@staff_required
def loan_portfolio_report(request):
    """Generate loan portfolio report"""
    loans = Loan.objects.select_related('client', 'loan_product').all()
    
    # Filters
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
    
    # Export format
    export_format = request.GET.get('export')
    
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="loan_portfolio.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Loan Number', 'Client', 'Product', 'Disbursement Date',
            'Principal', 'Interest Rate', 'Status', 'Remaining Balance',
            'Next Payment Date', 'Days Overdue'
        ])
        
        for loan in loans:
            writer.writerow([
                loan.loan_number,
                loan.client.full_account_name,
                loan.loan_product.name,
                loan.disbursement_date,
                loan.principal_amount,
                loan.interest_rate,
                loan.status,
                loan.remaining_balance,
                loan.next_payment_date,
                loan.days_overdue,
            ])
        
        return response
    
    elif export_format == 'excel':
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="loan_portfolio.xls"'
        
        wb = xlwt.Workbook(encoding='utf-8')
        ws = wb.add_sheet('Loan Portfolio')
        
        # Header
        headers = [
            'Loan Number', 'Client', 'Product', 'Disbursement Date',
            'Principal', 'Interest Rate', 'Status', 'Remaining Balance',
            'Next Payment Date', 'Days Overdue'
        ]
        
        for col, header in enumerate(headers):
            ws.write(0, col, header)
        
        # Data
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
    
    # HTML view
    context = {
        'loans': loans,
        'products': LoanProduct.objects.filter(is_active=True),
        'total_count': loans.count(),
        'total_principal': loans.aggregate(total=Sum('principal_amount'))['total'] or Decimal('0'),
        'total_remaining': loans.aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0'),
    }
    
    return render(request, 'loans/portfolio_report.html', context)

@login_required
@staff_required
def overdue_loans_report(request):
    """Generate overdue loans report"""
    overdue_loans = Loan.objects.filter(
        status='OVERDUE'
    ).select_related('client', 'loan_product').order_by('-days_overdue')
    
    # Aging analysis
    aging = {
        '1_30_days': Decimal('0'),
        '31_60_days': Decimal('0'),
        '61_90_days': Decimal('0'),
        'over_90_days': Decimal('0'),
    }
    
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
        writer.writerow([
            'Loan Number', 'Client', 'Phone', 'Disbursement Date',
            'Principal', 'Overdue Amount', 'Days Overdue',
            'Last Payment Date', 'Loan Officer'
        ])
        
        for loan in overdue_loans:
            last_payment = loan.transactions.filter(
                transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT']
            ).order_by('-transaction_date').first()
            
            writer.writerow([
                loan.loan_number,
                loan.client.full_account_name,
                loan.client.phone_number,
                loan.disbursement_date,
                loan.principal_amount,
                loan.overdue_amount,
                loan.days_overdue,
                last_payment.transaction_date if last_payment else '',
                f"{loan.loan_officer.first_name} {loan.loan_officer.last_name}",
            ])
        
        return response
    
    context = {
        'overdue_loans': overdue_loans,
        'total_overdue': overdue_loans.count(),
        'total_overdue_amount': sum(loan.overdue_amount for loan in overdue_loans),
        'aging_analysis': aging,
    }
    
    return render(request, 'loans/overdue_report.html', context)

@login_required
@staff_required
def collections_report(request):
    """Generate collections report"""
    start_date = request.GET.get('start_date', (timezone.now() - timedelta(days=30)).date().isoformat())
    end_date = request.GET.get('end_date', timezone.now().date().isoformat())
    
    payments = LoanTransaction.objects.filter(
        transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT'],
        value_date__range=[start_date, end_date]
    ).select_related('loan', 'loan__client', 'recorded_by')
    
    # Calculate totals
    total_collected = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # By payment method
    by_method = payments.values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # By loan officer
    by_officer = payments.values('recorded_by__username').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Daily breakdown
    daily_totals = {}
    current_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    while current_date <= end_date_obj:
        daily_total = payments.filter(value_date=current_date).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        daily_totals[current_date.isoformat()] = float(daily_total)
        current_date += timedelta(days=1)
    
    export_format = request.GET.get('export')
    
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="collections_{start_date}_to_{end_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Loan Number', 'Client', 'Payment Method',
            'Amount', 'Type', 'Recorded By'
        ])
        
        for payment in payments:
            writer.writerow([
                payment.value_date,
                payment.loan.loan_number,
                payment.loan.client.full_account_name,
                payment.payment_method,
                payment.amount,
                payment.transaction_type,
                payment.recorded_by.username,
            ])
        
        return response
    
    context = {
        'payments': payments,
        'start_date': start_date,
        'end_date': end_date,
        'total_collected': total_collected,
        'by_method': by_method,
        'by_officer': by_officer,
        'daily_totals': daily_totals,
        'average_daily': total_collected / ((end_date_obj - datetime.strptime(start_date, '%Y-%m-%d').date()).days + 1),
    }
    
    return render(request, 'loans/collections_report.html', context)

# ============================================================================
# QUICK ACTIONS
# ============================================================================
@login_required
@loan_officer_required
def quick_payment(request):
    """Quick payment processing"""
    if request.method == 'POST':
        loan_number = request.POST.get('loan_number')
        amount = Decimal(request.POST.get('amount', '0'))
        payment_method = request.POST.get('payment_method', 'CASH')
        
        try:
            loan = Loan.objects.get(loan_number=loan_number)
            
            with transaction.atomic():
                payment_service = PaymentProcessingService()
                
                allocation = payment_service.process_payment(
                    loan=loan,
                    amount=amount,
                    payment_date=timezone.now().date(),
                    payment_method=payment_method,
                    received_by=request.user,
                    notes="Quick payment",
                    allocation_strategy='AUTO'
                )
                
                messages.success(
                    request,
                    f"Payment of {amount} for loan {loan_number} processed successfully!"
                )
                
                return redirect('loans:payment_receipt', transaction_id=allocation['transactions'][0].transaction_id)
                
        except Loan.DoesNotExist:
            messages.error(request, f"Loan {loan_number} not found!")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    return render(request, 'loans/quick_payment.html')

@login_required
@staff_required
def bulk_status_update(request):
    """Bulk update loan statuses"""
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
            
            # Create adjustment transaction
            LoanTransaction.objects.create(
                loan=loan,
                transaction_type='ADJUSTMENT',
                payment_method='SYSTEM',
                amount=Decimal('0'),
                notes=f"Status changed to {new_status}: {reason}",
                recorded_by=request.user,
                value_date=effective_date,
            )
            
            updated_count += 1
        
        messages.success(request, f"{updated_count} loans updated to {new_status} status!")
        return redirect('loans:loan_list')
    
    return render(request, 'loans/bulk_status_update.html')

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def generate_loan_schedule_pdf(loan):
    """Generate PDF of loan repayment schedule"""
    # This would be implemented with a PDF generation library like ReportLab
    # For now, return None - implement based on your PDF library choice
    return None

def send_payment_reminder(loan):
    """Send payment reminder for overdue loans"""
    # This would integrate with your SMS/email service
    # For now, just log it
    print(f"Payment reminder sent for loan {loan.loan_number}")
    
def calculate_early_repayment_savings(loan, repayment_amount):
    """Calculate savings from early repayment"""
    interest_service = InterestCalculationService()
    
    # Get remaining schedule
    remaining_schedule = loan.repayment_schedule.filter(
        status__in=['PENDING', 'DUE']
    ).order_by('due_date')
    
    if not remaining_schedule.exists():
        return {'savings': Decimal('0'), 'new_schedule': []}
    
    # Calculate interest that would have been paid
    total_interest_without_early = sum(
        installment.interest_amount 
        for installment in remaining_schedule
    )
    
    # Apply early repayment to principal
    new_principal = loan.remaining_balance - repayment_amount
    
    if new_principal <= 0:
        # Loan fully repaid
        savings = total_interest_without_early
        new_schedule = []
    else:
        # Recalculate schedule with new principal
        remaining_months = remaining_schedule.count()
        monthly_rate = (loan.interest_rate / Decimal('100')) / Decimal('12')
        
        # Calculate new payment
        if monthly_rate == Decimal('0'):
            new_payment = new_principal / remaining_months
        else:
            factor = (Decimal('1') + monthly_rate) ** remaining_months
            new_payment = new_principal * monthly_rate * factor / (factor - Decimal('1'))
        
        # Generate new schedule
        new_schedule = []
        remaining_balance = new_principal
        
        for i, installment in enumerate(remaining_schedule, 1):
            interest = remaining_balance * monthly_rate
            principal = new_payment - interest
            remaining_balance -= principal
            
            new_schedule.append({
                'period': i,
                'due_date': installment.due_date,
                'payment': new_payment.quantize(Decimal('0.01')),
                'principal': principal.quantize(Decimal('0.01')),
                'interest': interest.quantize(Decimal('0.01')),
                'remaining_balance': max(remaining_balance, Decimal('0')).quantize(Decimal('0.01')),
            })
        
        # Calculate interest with new schedule
        total_interest_with_early = sum(item['interest'] for item in new_schedule)
        savings = total_interest_without_early - total_interest_with_early
    
    # Apply early repayment penalty if applicable
    penalty = Decimal('0')
    if loan.loan_product.early_repayment_penalty_percent > 0:
        penalty = repayment_amount * loan.loan_product.early_repayment_penalty_percent / Decimal('100')
    
    net_savings = savings - penalty
    
    return {
        'savings': savings.quantize(Decimal('0.01')),
        'penalty': penalty.quantize(Decimal('0.01')),
        'net_savings': net_savings.quantize(Decimal('0.01')),
        'new_schedule': new_schedule,
    }

# ============================================================================
# ERROR HANDLERS
# ============================================================================
def handler404(request, exception):
    return render(request, 'loans/404.html', status=404)

def handler500(request):
    return render(request, 'loans/500.html', status=500)

def handler403(request, exception):
    return render(request, 'loans/403.html', status=403)

def handler400(request, exception):
    return render(request, 'loans/400.html', status=400)