from django.contrib import admin
from .models import LoanProduct, LoanApplication, Guarantor, LoanPayment

# -----------------------
# Loan Products
# -----------------------
@admin.register(LoanProduct)
class LoanProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'interest_method', 'interest_rate', 'min_amount', 'max_amount', 'loan_period', 'number_of_installments', 'is_active', 'created_date')
    list_filter = ('is_active', 'interest_method')
    search_fields = ('name', 'description')


# -----------------------
# Guarantors
# -----------------------
@admin.register(Guarantor)
class GuarantorAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'guarantor_type')
    list_filter = ('guarantor_type',)
    search_fields = ('external_name', 'internal_customer__full_account_name')


# -----------------------
# Loan Applications
# -----------------------
@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = ('application_number', 'client_account', 'loan_product', 'loan_amount', 'interest_amount', 'total_amount', 'status', 'loan_officer', 'approval_date', 'disbursement_date', 'due_date')
    list_filter = ('status', 'loan_product', 'loan_officer')
    search_fields = ('application_number', 'client_account__full_account_name', 'loan_product__name')
    readonly_fields = ('application_number', 'interest_amount', 'total_amount', 'payment_mode', 'disbursed_amount')


# -----------------------
# Loan Payments
# -----------------------
@admin.register(LoanPayment)
class LoanPaymentAdmin(admin.ModelAdmin):
    list_display = ('loan_application', 'payment_amount', 'payment_date', 'payment_method', 'received_by', 'transaction_reference')
    list_filter = ('payment_method', 'received_by')
    search_fields = ('loan_application__application_number', 'received_by__username', 'transaction_reference')
