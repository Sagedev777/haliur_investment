from django.contrib import admin
from django.contrib import messages
from django import forms
import datetime
from .models import LoanProduct, Guarantor, LoanApplication, LoanPayment

class LoanApplicationForm(forms.ModelForm):
    class Meta:
        model = LoanApplication
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ['loan_officer', 'approved_by', 'disbursed_by', 'approval_date', 'disbursement_date', 'due_date']:
            if field in self.fields:
                del self.fields[field]

class LoanPaymentForm(forms.ModelForm):
    class Meta:
        model = LoanPayment
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'received_by' in self.fields:
            del self.fields['received_by']

@admin.register(LoanProduct)
class LoanProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'interest_rate', 'interest_method', 'min_amount', 'max_amount', 'get_loan_period', 'get_number_of_installments', 'is_active']
    list_editable = ['interest_rate', 'min_amount', 'max_amount', 'is_active']
    list_filter = ['is_active', 'interest_method']
    search_fields = ['name']
    
    def get_loan_period(self, obj):
        return f"{obj.loan_period} days"
    get_loan_period.short_description = 'Loan Period'
    
    def get_number_of_installments(self, obj):
        return obj.number_of_installments
    get_number_of_installments.short_description = 'Installments'

@admin.register(Guarantor)
class GuarantorAdmin(admin.ModelAdmin):
    list_display = ['guarantor_type', 'get_name', 'get_contact', 'get_nin']
    list_filter = ['guarantor_type']
    search_fields = ['external_name', 'internal_customer__person1_first_name', 'internal_customer__person1_last_name']
    
    def get_name(self, obj):
        if obj.guarantor_type == 'INTERNAL':
            return obj.internal_customer.full_account_name
        return obj.external_name
    get_name.short_description = 'Name'
    
    def get_contact(self, obj):
        if obj.guarantor_type == 'INTERNAL':
            return obj.internal_customer.person1_contact
        return obj.external_contact
    get_contact.short_description = 'Contact'
    
    def get_nin(self, obj):
        if obj.guarantor_type == 'INTERNAL':
            return obj.internal_customer.person1_nin
        return obj.external_nin
    get_nin.short_description = 'NIN'

@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    form = LoanApplicationForm
    list_display = ['application_number', 'client_account', 'loan_product', 'loan_amount', 'total_amount', 'get_total_paid', 'get_balance_remaining', 'status', 'get_loan_status_info', 'disbursement_date', 'due_date']
    list_filter = ['status', 'loan_product', 'application_date', 'disbursement_date']
    search_fields = ['application_number', 'client_account__person1_first_name', 'client_account__person1_last_name']
    readonly_fields = ['application_number', 'application_date', 'interest_amount', 'total_amount', 'payment_mode', 'display_loan_officer', 'disbursement_info', 'days_remaining_info', 'display_approved_by', 'display_disbursed_by', 'display_approval_date', 'display_disbursement_date', 'display_due_date', 'payment_progress_info', 'payment_history']
    actions = ['approve_applications', 'reject_applications', 'disburse_loans']
    
    fieldsets = (
        ('Application Details', {
            'fields': ('application_number', 'client_account', 'loan_product', 'loan_amount')
        }),
        ('Auto-Calculated Information', {
            'fields': ('interest_amount', 'total_amount', 'payment_mode', 'display_due_date', 'payment_progress_info'),
            'classes': ('collapse',)
        }),
        ('Security & Collateral', {
            'fields': ('collateral_description', 'collateral_value', 'collateral_images')
        }),
        ('Guarantor', {
            'fields': ('guarantor',)
        }),
        ('Payment Information', {
            'fields': ('payment_history',),
            'classes': ('collapse',)
        }),
        ('Approval Workflow', {
            'fields': ('status', 'rejection_reason', 'display_loan_officer', 'display_approved_by', 'display_approval_date', 'display_disbursed_by', 'display_disbursement_date', 'disbursement_info', 'days_remaining_info')
        }),
    )
    
    def display_loan_officer(self, obj):
        return f"{obj.loan_officer.get_full_name() or obj.loan_officer.username}"
    display_loan_officer.short_description = 'Loan Officer'
    
    def display_approved_by(self, obj):
        if obj.approved_by:
            return f"{obj.approved_by.get_full_name() or obj.approved_by.username}"
        return "Not approved yet"
    display_approved_by.short_description = 'Approved By'
    
    def display_disbursed_by(self, obj):
        if obj.disbursed_by:
            return f"{obj.disbursed_by.get_full_name() or obj.disbursed_by.username}"
        return "Not disbursed yet"
    display_disbursed_by.short_description = 'Disbursed By'
    
    def display_approval_date(self, obj):
        if obj.approval_date:
            return obj.approval_date.strftime('%Y-%m-%d %H:%M')
        return "Not approved yet"
    display_approval_date.short_description = 'Approval Date'
    
    def display_disbursement_date(self, obj):
        if obj.disbursement_date:
            return obj.disbursement_date.strftime('%Y-%m-%d %H:%M')
        return "Not disbursed yet"
    display_disbursement_date.short_description = 'Disbursement Date'
    
    def display_due_date(self, obj):
        if obj.due_date:
            return obj.due_date.strftime('%Y-%m-%d')
        return "Not set yet"
    display_due_date.short_description = 'Due Date'
    
    def get_loan_status_info(self, obj):
        return obj.get_loan_status_info()
    get_loan_status_info.short_description = 'Status Info'
    
    def get_total_paid(self, obj):
        return obj.get_total_paid()
    get_total_paid.short_description = 'Total Paid'
    
    def get_balance_remaining(self, obj):
        return obj.get_balance_remaining()
    get_balance_remaining.short_description = 'Balance Due'
    
    def disbursement_info(self, obj):
        if obj.status == 'DISBURSED' and obj.disbursement_date:
            info = [
                f"Money disbursed on: {obj.disbursement_date.strftime('%Y-%m-%d %H:%M')}",
                f"Amount given: {obj.disbursed_amount}",
                f"Transaction Ref: {obj.transaction_reference}",
                f"Due date: {obj.due_date.strftime('%Y-%m-%d') if obj.due_date else 'Not set'}",
            ]
            return "\n".join(info)
        return "Not yet disbursed"
    disbursement_info.short_description = 'Disbursement Information'
    
    def days_remaining_info(self, obj):
        if obj.status == 'DISBURSED' and obj.due_date:
            days_remaining = obj.get_days_remaining()
            if days_remaining == 0:
                return "⚠️ OVERDUE - Payment is due!"
            elif days_remaining > 0:
                return f"✅ {days_remaining} days remaining"
            else:
                return "❌ Loan term completed"
        return "-"
    days_remaining_info.short_description = 'Time Status'
    
    def payment_progress_info(self, obj):
        if obj.status in ['DISBURSED', 'COMPLETED']:
            progress = obj.get_payment_progress()
            total_paid = obj.get_total_paid()
            balance = obj.get_balance_remaining()
            
            info = [
                f"Progress: {progress}%",
                f"Total Paid: {total_paid}",
                f"Balance Due: {balance}",
                f"Total Amount: {obj.total_amount}",
            ]
            return "\n".join(info)
        return "No payments yet - loan not disbursed"
    payment_progress_info.short_description = 'Payment Progress'
    
    def payment_history(self, obj):
        payments = obj.loanpayment_set.all().order_by('-payment_date')
        if payments.exists():
            history = []
            for payment in payments:
                history.append(
                    f"{payment.payment_date.strftime('%Y-%m-%d')}: {payment.payment_amount} "
                    f"({payment.payment_method}) - {payment.received_by.username}"
                )
            return "\n".join(history)
        return "No payments recorded yet"
    payment_history.short_description = 'Payment History'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.loan_officer = request.user
        
        if obj.status == 'APPROVED' and not obj.approved_by:
            obj.approved_by = request.user
            obj.approval_date = datetime.datetime.now()
        
        if obj.status == 'DISBURSED' and not obj.disbursed_by:
            obj.disbursed_by = request.user
            obj.disbursement_date = datetime.datetime.now()
            obj.disbursed_amount = obj.loan_amount
        
        super().save_model(request, obj, form, change)
    
    def approve_applications(self, request, queryset):
        for application in queryset:
            application.status = 'APPROVED'
            application.approved_by = request.user
            application.approval_date = datetime.datetime.now()
            application.save()
        self.message_user(request, f'{queryset.count()} loan applications approved.')
    approve_applications.short_description = "Approve selected applications"
    
    def reject_applications(self, request, queryset):
        updated = queryset.update(status='REJECTED')
        self.message_user(request, f'{updated} loan applications rejected.')
    reject_applications.short_description = "Reject selected applications"
    
    def disburse_loans(self, request, queryset):
        for application in queryset.filter(status='APPROVED'):
            application.status = 'DISBURSED'
            application.disbursed_by = request.user
            application.disbursement_date = datetime.datetime.now()
            application.disbursed_amount = application.loan_amount
            application.save()
        self.message_user(request, f'{queryset.filter(status="APPROVED").count()} loans disbursed.')
    disburse_loans.short_description = "Disburse approved loans"

@admin.register(LoanPayment)
class LoanPaymentAdmin(admin.ModelAdmin):
    form = LoanPaymentForm
    list_display = ['loan_application', 'payment_amount', 'payment_method', 'payment_date', 'received_by', 'transaction_reference']
    list_filter = ['payment_date', 'received_by', 'payment_method']
    search_fields = ['loan_application__application_number', 'transaction_reference']
    readonly_fields = ['payment_date', 'display_received_by']
    
    def display_received_by(self, obj):
        return f"{obj.received_by.get_full_name() or obj.received_by.username}"
    display_received_by.short_description = 'Received By'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.received_by = request.user
        super().save_model(request, obj, form, change)