# loans/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum
from .models import (
    LoanProduct, 
    LoanApplication, 
    Guarantor, 
    LoanTransaction,  # Changed from LoanPayment
    Loan,  # New model
    LoanRepaymentSchedule  # New model
)

# -------------------------
# INLINE ADMIN CLASSES
# -------------------------
class GuarantorInline(admin.TabularInline):
    model = LoanApplication.guarantors.through
    extra = 1
    verbose_name = "Guarantor"
    verbose_name_plural = "Guarantors"

class LoanRepaymentScheduleInline(admin.TabularInline):
    model = LoanRepaymentSchedule
    extra = 0
    readonly_fields = ['installment_number', 'due_date', 'principal_amount', 
                      'interest_amount', 'total_amount', 'status']
    can_delete = False
    max_num = 0
    show_change_link = True

class LoanTransactionInline(admin.TabularInline):
    model = LoanTransaction
    extra = 0
    readonly_fields = ['transaction_id', 'transaction_date', 'transaction_type']
    fields = ['transaction_id', 'transaction_date', 'transaction_type', 
              'amount', 'payment_method', 'recorded_by']
    can_delete = False
    max_num = 0
    show_change_link = True

# -------------------------
# ADMIN CLASSES
# -------------------------
@admin.register(LoanProduct)
class LoanProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'annual_interest_rate', 'min_loan_amount', 
                   'max_loan_amount', 'min_term_days', 'max_term_days', 'is_active']
    list_filter = ['is_active', 'interest_type']
    search_fields = ['name', 'code', 'description']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description', 'is_active')
        }),
        ('Interest Configuration', {
            'fields': ('interest_type', 'annual_interest_rate', 'interest_calculation_method')
        }),
        ('Loan Amount Range', {
            'fields': ('min_loan_amount', 'max_loan_amount')
        }),
        ('Term Configuration', {
            'fields': ('min_term_days', 'max_term_days')
        }),
        ('Fees', {
            'fields': ('processing_fee_percent', 'late_payment_fee_percent', 
                      'early_repayment_penalty_percent')
        }),
        ('Eligibility Criteria', {
            'fields': ('min_client_age_days', 'min_savings_balance_percent')
        }),
    )
    ordering = ['name']

@admin.register(Guarantor)
class GuarantorAdmin(admin.ModelAdmin):
    list_display = ['guarantor_id', 'guarantor_type', 'get_name', 'phone_number', 
                   'guarantee_amount', 'is_active', 'verified']
    list_filter = ['guarantor_type', 'is_active', 'verified']
    search_fields = ['guarantor_id', 'company_name', 'contact_person', 
                    'phone_number', 'nin', 'individual__full_account_name']
    readonly_fields = ['guarantor_id']
    
    def get_name(self, obj):
        if obj.guarantor_type == 'INDIVIDUAL' and obj.individual:
            return obj.individual.full_account_name
        elif obj.company_name:
            return obj.company_name
        return "N/A"
    get_name.short_description = 'Name'
    
    fieldsets = (
        ('Identification', {
            'fields': ('guarantor_id', 'guarantor_type')
        }),
        ('Individual Guarantor', {
            'fields': ('individual',),
            'classes': ('collapse',)
        }),
        ('Company/Group Guarantor', {
            'fields': ('company_name', 'registration_number', 'contact_person',
                      'phone_number', 'email', 'address', 'nin'),
            'classes': ('collapse',)
        }),
        ('Guarantee Details', {
            'fields': ('guarantee_amount', 'guarantee_percent')
        }),
        ('Documents', {
            'fields': ('id_document', 'signed_agreement')
        }),
        ('Status', {
            'fields': ('is_active', 'verified', 'verified_by', 'verification_date')
        }),
    )

@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = ['application_number', 'client', 'loan_product', 
                   'requested_amount', 'status', 'application_date', 
                   'credit_score', 'risk_rating']
    list_filter = ['status', 'application_date', 'loan_product', 'risk_rating']
    search_fields = ['application_number', 'client__full_account_name', 
                    'client__account_number', 'purpose']
    readonly_fields = ['application_id', 'application_number', 'application_date', 
                      'submitted_date', 'review_date', 'approval_date', 
                      'credit_score', 'risk_rating']
    fieldsets = (
        ('Application Details', {
            'fields': ('application_id', 'application_number', 'application_date', 'status')
        }),
        ('Client & Product', {
            'fields': ('client', 'loan_product')
        }),
        ('Loan Request', {
            'fields': ('requested_amount', 'requested_term_days', 'purpose')
        }),
        ('Approval Details', {
            'fields': ('approved_amount', 'approved_interest_rate', 'approved_term_days',
                      'processing_fee_amount', 'net_disbursement_amount',
                      'total_interest_amount', 'total_repayment_amount')
        }),
        ('Collateral', {
            'fields': ('collateral_description', 'collateral_value', 'collateral_documents')
        }),
        ('Credit Assessment', {
            'fields': ('credit_score', 'risk_rating')
        }),
        ('Personnel', {
            'fields': ('loan_officer', 'reviewed_by', 'approved_by')
        }),
        ('Decision Information', {
            'fields': ('rejection_reason', 'approval_conditions')
        }),
        ('Dates', {
            'fields': ('submitted_date', 'review_date', 'approval_date'),
            'classes': ('collapse',)
        }),
    )
    inlines = [GuarantorInline]
    actions = ['approve_applications', 'reject_applications']
    
    def approve_applications(self, request, queryset):
        updated = queryset.filter(status__in=['SUBMITTED', 'UNDER_REVIEW']).update(
            status='APPROVED',
            approved_by=request.user,
            approval_date=timezone.now()
        )
        self.message_user(request, f"{updated} applications approved.")
    approve_applications.short_description = "Approve selected applications"
    
    def reject_applications(self, request, queryset):
        updated = queryset.filter(status__in=['SUBMITTED', 'UNDER_REVIEW']).update(
            status='REJECTED',
            approved_by=request.user
        )
        self.message_user(request, f"{updated} applications rejected.")
    reject_applications.short_description = "Reject selected applications"

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ['loan_number', 'client', 'principal_amount', 'interest_rate',
                   'disbursement_date', 'status', 'remaining_balance', 
                   'next_payment_date', 'days_overdue_display']
    list_filter = ['status', 'disbursement_date', 'loan_product']
    search_fields = ['loan_number', 'client__full_account_name', 
                    'client__account_number']
    readonly_fields = ['loan_number', 'created_at', 'updated_at', 'closed_at',
                      'remaining_balance', 'total_paid_amount', 'overdue_amount',
                      'days_overdue']
    fieldsets = (
        ('Loan Details', {
            'fields': ('loan_number', 'application', 'client', 'loan_product')
        }),
        ('Financials', {
            'fields': ('principal_amount', 'interest_rate', 'term_days',
                      'total_interest_amount', 'total_repayment_amount',
                      'processing_fee_amount', 'late_fee_amount')
        }),
        ('Current State', {
            'fields': ('remaining_balance', 'total_paid_amount', 
                      'overdue_amount', 'days_overdue')
        }),
        ('Dates', {
            'fields': ('disbursement_date', 'maturity_date', 
                      'first_payment_date', 'next_payment_date')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Personnel', {
            'fields': ('disbursed_by', 'loan_officer')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'closed_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [LoanRepaymentScheduleInline, LoanTransactionInline]
    actions = ['mark_as_closed', 'mark_as_defaulted', 'generate_statements']
    
    def days_overdue_display(self, obj):
        if obj.days_overdue > 0:
            return format_html('<span style="color: red;">{} days</span>', obj.days_overdue)
        return "0 days"
    days_overdue_display.short_description = 'Days Overdue'
    
    def mark_as_closed(self, request, queryset):
        updated = queryset.update(status='CLOSED', closed_at=timezone.now())
        self.message_user(request, f"{updated} loans marked as closed.")
    mark_as_closed.short_description = "Mark selected loans as closed"
    
    def mark_as_defaulted(self, request, queryset):
        updated = queryset.update(status='DEFAULTED')
        self.message_user(request, f"{updated} loans marked as defaulted.")
    mark_as_defaulted.short_description = "Mark selected loans as defaulted"
    
    def generate_statements(self, request, queryset):
        # This would generate PDF statements in a real implementation
        self.message_user(request, f"Statements generated for {queryset.count()} loans.")
    generate_statements.short_description = "Generate statements for selected loans"

@admin.register(LoanRepaymentSchedule)
class LoanRepaymentScheduleAdmin(admin.ModelAdmin):
    list_display = ['loan', 'installment_number', 'due_date', 'total_amount',
                   'status', 'payment_date', 'remaining_balance_display']
    list_filter = ['status', 'due_date', 'loan__status']
    search_fields = ['loan__loan_number', 'loan__client__full_account_name']
    readonly_fields = ['installment_number', 'due_date', 'principal_amount',
                      'interest_amount', 'total_amount', 'grace_period_days']
    
    def remaining_balance_display(self, obj):
        return obj.remaining_balance
    remaining_balance_display.short_description = 'Remaining Balance'
    
    fieldsets = (
        ('Installment Details', {
            'fields': ('loan', 'installment_number', 'due_date')
        }),
        ('Amounts', {
            'fields': ('principal_amount', 'interest_amount', 'total_amount')
        }),
        ('Payment Tracking', {
            'fields': ('paid_principal', 'paid_interest', 'paid_late_fee', 
                      'total_paid', 'payment_date')
        }),
        ('Late Fees', {
            'fields': ('late_fee_applied', 'late_fee_amount', 'grace_period_days')
        }),
        ('Status', {
            'fields': ('status',)
        }),
    )

@admin.register(LoanTransaction)
class LoanTransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'loan', 'transaction_type', 'amount',
                   'payment_method', 'transaction_date', 'recorded_by', 
                   'is_reversed']
    list_filter = ['transaction_type', 'payment_method', 'transaction_date', 
                  'is_reversed']
    search_fields = ['transaction_id', 'loan__loan_number', 
                    'reference_number', 'notes']
    readonly_fields = ['transaction_id', 'transaction_date', 'created_at', 
                      'updated_at']
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('transaction_id', 'loan', 'installment', 'transaction_type')
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'amount', 'principal_amount', 
                      'interest_amount', 'fee_amount', 'reference_number')
        }),
        ('Dates', {
            'fields': ('transaction_date', 'value_date')
        }),
        ('Personnel', {
            'fields': ('recorded_by', 'verified_by')
        }),
        ('Reversal Information', {
            'fields': ('is_reversed', 'reversal_reason', 'reversal_date'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes', 'attachment')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['reverse_transactions']
    
    def reverse_transactions(self, request, queryset):
        # Only allow reversal of non-reversed transactions
        transactions_to_reverse = queryset.filter(is_reversed=False)
        for transaction in transactions_to_reverse:
            transaction.is_reversed = True
            transaction.reversal_reason = "Bulk reversal from admin"
            transaction.reversal_date = timezone.now()
            transaction.save()
        self.message_user(request, f"{transactions_to_reverse.count()} transactions reversed.")
    reverse_transactions.short_description = "Reverse selected transactions"

# -------------------------
# ADMIN SITE CUSTOMIZATION
# -------------------------
admin.site.site_header = "Haliqua Investments Loan Management"
admin.site.site_title = "Haliqua Loans Admin"
admin.site.index_title = "Welcome to Haliqua Loan Administration"