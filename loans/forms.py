# loans/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal
import datetime
from django.forms.widgets import FileInput
from .models import (
    LoanProduct, 
    LoanApplication, 
    Guarantor, 
    Loan,  # Changed from LoanPayment
    LoanTransaction,  # New model
    LoanRepaymentSchedule  # New model
)
from client_accounts.models import ClientAccount
# -------------------------
# LOAN PRODUCT FORMS
# -------------------------
class LoanProductForm(forms.ModelForm):
    """Form for creating/editing loan products"""
    
    class Meta:
        model = LoanProduct
        fields = [
            'name', 'code', 'description',
            'interest_type', 'annual_interest_rate', 'interest_calculation_method',
            'min_loan_amount', 'max_loan_amount',
            'min_term_days', 'max_term_days',
            'processing_fee_percent', 'late_payment_fee_percent', 'early_repayment_penalty_percent',
            'min_client_age_days', 'min_savings_balance_percent',
            'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Personal Loan - 30 Days'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., PL-30D-15P'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Product description and features...'
            }),
            'annual_interest_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'min_loan_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1000'
            }),
            'max_loan_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1000'
            }),
            'min_term_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'max_term_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'processing_fee_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '10'
            }),
            'late_payment_fee_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '20'
            }),
            'early_repayment_penalty_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '5'
            }),
            'min_client_age_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'min_savings_balance_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        min_loan = cleaned_data.get('min_loan_amount')
        max_loan = cleaned_data.get('max_loan_amount')
        min_term = cleaned_data.get('min_term_days')
        max_term = cleaned_data.get('max_term_days')
        
        if min_loan and max_loan and min_loan > max_loan:
            self.add_error('min_loan_amount', 'Minimum amount cannot be greater than maximum amount')
            self.add_error('max_loan_amount', 'Maximum amount cannot be less than minimum amount')
        
        if min_term and max_term and min_term > max_term:
            self.add_error('min_term_days', 'Minimum term cannot be greater than maximum term')
            self.add_error('max_term_days', 'Maximum term cannot be less than minimum term')
        
        return cleaned_data
    
    def clean_annual_interest_rate(self):
        rate = self.cleaned_data.get('annual_interest_rate')
        if rate and (rate < Decimal('0') or rate > Decimal('100')):
            raise ValidationError('Interest rate must be between 0% and 100%')
        return rate

# -------------------------
# LOAN APPLICATION FORMS
# -------------------------
from decimal import Decimal
import datetime
from django import forms
from django.utils import timezone
from .models import LoanApplication, LoanProduct, ClientAccount, Guarantor, CollateralDocument

# Field for multiple file uploads
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class LoanApplicationForm(forms.ModelForm):
    """Form for creating new loan applications with multiple collateral files"""
    
    
    # Optional client search field for UX
    client_search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search client by name or account number...',
            'hx-get': '/loans/api/search-clients/',
            'hx-trigger': 'keyup changed delay:500ms',
            'hx-target': '#client-results'
        })
    )

    loan_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '1000',
            'hx-get': '/loans/api/calculate-repayment/',
            'hx-trigger': 'change',
            'hx-target': '#calculation-results',
            'hx-include': '[name="loan_product"], [name="requested_term_days"]'
        })
    )

    requested_term_days = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '7',
            'max': '365',
            'hx-get': '/loans/api/calculate-repayment/',
            'hx-trigger': 'change',
            'hx-target': '#calculation-results',
            'hx-include': '[name="loan_product"], [name="loan_amount"]'
        })
    )

    guarantors = forms.ModelMultipleChoiceField(
        queryset=Guarantor.objects.filter(is_active=True, verified=True),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2-multiple',
            'data-placeholder': 'Select guarantors...'
        })
    )

    class Meta:
        model = LoanApplication
        fields = [
            'client', 'loan_product',
            'loan_amount', 'requested_term_days', 'purpose',
            'collateral_description', 'collateral_value',
            'collateral_documents',
            'guarantors'
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-control select2'}),
            'loan_product': forms.Select(attrs={
                'class': 'form-control select2',
                'hx-get': '/loans/api/product-details/',
                'hx-trigger': 'change',
                'hx-target': '#product-details'
            }),
            'purpose': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the purpose of this loan...'
            }),
            'collateral_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the collateral offered...'
            }),
            'collateral_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1000'
            }),
            'collateral_documents': MultipleFileInput(attrs={
                'class': 'form-control',
                'multiple': True
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filter active loan products
        self.fields['loan_product'].queryset = LoanProduct.objects.filter(is_active=True)

        # Filter active clients (at least 30 days old)
        if user and user.is_staff:
            thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
            self.fields['client'].queryset = ClientAccount.objects.filter(
                is_active=True,
                created_at__lte=thirty_days_ago
            ).order_by('full_account_name')
        else:
            self.fields['client'].queryset = ClientAccount.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        client = cleaned_data.get('client')
        loan_product = cleaned_data.get('loan_product')
        loan_amount = cleaned_data.get('loan_amount')
        requested_term = cleaned_data.get('requested_term_days')
        collateral_value = cleaned_data.get('collateral_value')

        if all([client, loan_product, loan_amount, requested_term]):
            # Check loan amount range
            if loan_amount < loan_product.min_loan_amount:
                self.add_error('loan_amount',
                    f'Minimum loan amount for {loan_product.name} is {loan_product.min_loan_amount}')
            if loan_amount > loan_product.max_loan_amount:
                self.add_error('loan_amount',
                    f'Maximum loan amount for {loan_product.name} is {loan_product.max_loan_amount}')

            # Check term range
            if requested_term < loan_product.min_term_days:
                self.add_error('requested_term_days',
                    f'Minimum term for {loan_product.name} is {loan_product.min_term_days} days')
            if requested_term > loan_product.max_term_days:
                self.add_error('requested_term_days',
                    f'Maximum term for {loan_product.name} is {loan_product.max_term_days} days')

            # Check collateral
            if collateral_value and collateral_value < loan_amount * Decimal('1.2'):
                self.add_error('collateral_value',
                    'Collateral value must be at least 120% of the loan amount')

            # Client eligibility
            client_age_days = (timezone.now().date() - client.created_at.date()).days
            if client_age_days < loan_product.min_client_age_days:
                self.add_error('client',
                    f'Client must have been active for at least {loan_product.min_client_age_days} days')

            required_savings = loan_amount * loan_product.min_savings_balance_percent / Decimal('100')
            if client.current_balance < required_savings:
                self.add_error('loan_amount',
                    f'Client needs at least {required_savings} in savings for this loan amount')

        return cleaned_data

# -------------------------
# LOAN APPROVAL FORM (Staff Only)
# -------------------------
class LoanApprovalForm(forms.ModelForm):
    """Form for reviewing and approving/rejecting loan applications"""
    
    class Meta:
        model = LoanApplication
        fields = [
            'status', 'approved_amount', 'approved_interest_rate', 
            'approved_term_days', 'rejection_reason', 'approval_conditions',
            'credit_score', 'risk_rating'
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'approved_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1000'
            }),
            'approved_interest_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'approved_term_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '7'
            }),
            'rejection_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Reason for rejection...'
            }),
            'approval_conditions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any special conditions for approval...'
            }),
            'credit_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'readonly': 'readonly'
            }),
            'risk_rating': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        
        if instance:
            # Set initial values for approval
            self.fields['approved_amount'].initial = instance.requested_amount
            self.fields['approved_interest_rate'].initial = instance.loan_product.annual_interest_rate
            self.fields['approved_term_days'].initial = instance.requested_term_days
            
            # Calculate credit score
            if not instance.credit_score:
                instance.credit_score = instance.calculate_credit_score()
                self.fields['credit_score'].initial = instance.credit_score
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        approved_amount = cleaned_data.get('approved_amount')
        approved_interest_rate = cleaned_data.get('approved_interest_rate')
        approved_term_days = cleaned_data.get('approved_term_days')
        
        if status == 'APPROVED':
            # Validation for approved loans
            if not approved_amount or approved_amount <= 0:
                self.add_error('approved_amount', 'Approved amount is required for approval')
            
            if not approved_interest_rate or approved_interest_rate <= 0:
                self.add_error('approved_interest_rate', 'Interest rate is required for approval')
            
            if not approved_term_days or approved_term_days <= 0:
                self.add_error('approved_term_days', 'Loan term is required for approval')
        
        elif status == 'REJECTED':
            # Validation for rejected loans
            rejection_reason = cleaned_data.get('rejection_reason')
            if not rejection_reason:
                self.add_error('rejection_reason', 'Reason for rejection is required')
        
        return cleaned_data

# -------------------------
# LOAN DISBURSEMENT FORM
# -------------------------
class LoanDisbursementForm(forms.Form):
    """Form for disbursing approved loans"""
    
    disbursement_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'value': datetime.date.today().isoformat()
        })
    )
    
    payment_method = forms.ChoiceField(
        choices=LoanTransaction.PAYMENT_METHODS,
        initial='BANK_TRANSFER',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    transaction_reference = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Bank/Mobile Money reference number...'
        })
    )
    
    disbursement_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Additional notes about disbursement...'
        })
    )
    
    auto_create_repayment_schedule = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def clean_disbursement_date(self):
        disbursement_date = self.cleaned_data.get('disbursement_date')
        if disbursement_date > datetime.date.today():
            raise ValidationError('Disbursement date cannot be in the future')
        return disbursement_date

# -------------------------
# LOAN PAYMENT FORM
# -------------------------
class LoanPaymentForm(forms.ModelForm):
    """Form for processing loan payments"""
    
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'value': datetime.date.today().isoformat()
        })
    )
    
    allocate_to = forms.ChoiceField(
        choices=[
            ('AUTO', 'Automatic Allocation (Recommended)'),
            ('PRINCIPAL_FIRST', 'Principal First'),
            ('INTEREST_FIRST', 'Interest First'),
            ('LATE_FEES_FIRST', 'Late Fees First'),
        ],
        initial='AUTO',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = LoanTransaction
        fields = [
            'payment_method', 'amount', 'reference_number', 'notes'
        ]
        widgets = {
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '100',
                'min': '0'
            }),
            'reference_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Payment reference number...'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Payment notes...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.loan = kwargs.pop('loan', None)
        super().__init__(*args, **kwargs)
        
        if self.loan:
            # Set max amount to remaining balance
            self.fields['amount'].widget.attrs['max'] = float(self.loan.remaining_balance)
            self.fields['amount'].help_text = f'Maximum: {self.loan.remaining_balance}'
    
    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        payment_date = cleaned_data.get('payment_date')
        
        if self.loan and amount:
            if amount <= 0:
                self.add_error('amount', 'Payment amount must be greater than zero')
            
            if amount > self.loan.remaining_balance:
                self.add_error('amount', 
                    f'Payment cannot exceed remaining balance: {self.loan.remaining_balance}')
            
            if payment_date and payment_date > datetime.date.today():
                self.add_error('payment_date', 'Payment date cannot be in the future')
        
        return cleaned_data

# -------------------------
# GUARANTOR FORMS
# -------------------------
class GuarantorForm(forms.ModelForm):
    """Form for creating/editing guarantors"""
    
    class Meta:
        model = Guarantor
        fields = [
            'guarantor_type', 'individual', 'company_name',
            'registration_number', 'contact_person', 'phone_number',
            'email', 'address', 'nin',
            'guarantee_amount', 'guarantee_percent',
            'id_document', 'signed_agreement',
            'is_active', 'verified'
        ]
        widgets = {
            'guarantor_type': forms.Select(attrs={
                'class': 'form-control',
                'onchange': 'toggleGuarantorFields(this.value)'
            }),
            'individual': forms.Select(attrs={'class': 'form-control select2'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'nin': forms.TextInput(attrs={'class': 'form-control'}),
            'guarantee_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000'}),
            'guarantee_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'id_document': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'signed_agreement': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active clients in individual guarantor field
        self.fields['individual'].queryset = ClientAccount.objects.filter(
            is_active=True
        ).order_by('full_account_name')
    
    def clean(self):
        cleaned_data = super().clean()
        guarantor_type = cleaned_data.get('guarantor_type')
        individual = cleaned_data.get('individual')
        company_name = cleaned_data.get('company_name')
        phone_number = cleaned_data.get('phone_number')
        
        if guarantor_type == 'INDIVIDUAL':
            if not individual:
                self.add_error('individual', 'Please select a client for individual guarantor')
            # Clear company fields
            cleaned_data['company_name'] = ''
            cleaned_data['registration_number'] = ''
            cleaned_data['contact_person'] = ''
        
        elif guarantor_type in ['COMPANY', 'GROUP']:
            if not company_name:
                self.add_error('company_name', 'Company/Group name is required')
            if not phone_number:
                self.add_error('phone_number', 'Contact phone number is required')
            # Clear individual field
            cleaned_data['individual'] = None
        
        # Validate guarantee amount/percent
        guarantee_amount = cleaned_data.get('guarantee_amount')
        guarantee_percent = cleaned_data.get('guarantee_percent')
        
        if not guarantee_amount and not guarantee_percent:
            self.add_error('guarantee_amount', 'Either guarantee amount or percentage is required')
            self.add_error('guarantee_percent', 'Either guarantee amount or percentage is required')
        
        return cleaned_data

# -------------------------
# LOAN SEARCH & FILTER FORMS
# -------------------------
class LoanSearchForm(forms.Form):
    """Form for searching/filtering loans"""
    
    STATUS_CHOICES = [('', 'All Statuses')] + Loan.LOAN_STATUS
    PRODUCT_CHOICES = [('', 'All Products')] + [
        (p.id, p.name) for p in LoanProduct.objects.filter(is_active=True)
    ]
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by loan number, client name, or account number...'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    loan_product = forms.ChoiceField(
        choices=PRODUCT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'placeholder': 'From date...'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'placeholder': 'To date...'
        })
    )
    
    min_amount = forms.DecimalField(
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min amount...'
        })
    )
    
    max_amount = forms.DecimalField(
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max amount...'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        min_amount = cleaned_data.get('min_amount')
        max_amount = cleaned_data.get('max_amount')
        
        if date_from and date_to and date_from > date_to:
            self.add_error('date_from', 'From date cannot be after To date')
            self.add_error('date_to', 'To date cannot be before From date')
        
        if min_amount and max_amount and min_amount > max_amount:
            self.add_error('min_amount', 'Minimum amount cannot be greater than maximum amount')
            self.add_error('max_amount', 'Maximum amount cannot be less than minimum amount')
        
        return cleaned_data

# -------------------------
# BULK ACTION FORMS
# -------------------------
class BulkPaymentForm(forms.Form):
    """Form for processing bulk payments"""
    
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'value': datetime.date.today().isoformat()
        })
    )
    
    payment_method = forms.ChoiceField(
        choices=LoanTransaction.PAYMENT_METHODS,
        initial='CASH',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    reference_prefix = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'BULK-REF-'
        })
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Notes for all payments...'
        })
    )
    
    loan_ids = forms.CharField(
        widget=forms.HiddenInput()
    )

class BulkStatusUpdateForm(forms.Form):
    """Form for updating status of multiple loans"""
    
    new_status = forms.ChoiceField(
        choices=Loan.LOAN_STATUS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Reason for status change...'
        })
    )
    
    effective_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'value': datetime.date.today().isoformat()
        })
    )
    
    loan_ids = forms.CharField(
        widget=forms.HiddenInput()
    )

# -------------------------
# CALCULATION FORMS
# -------------------------
class LoanCalculatorForm(forms.Form):
    """Form for loan calculations"""
    
    loan_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '1000',
            'placeholder': 'Loan amount...'
        })
    )
    
    interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Annual interest rate (%)...'
        })
    )
    
    term_days = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '7',
            'max': '365',
            'placeholder': 'Loan term in days...'
        })
    )
    
    interest_type = forms.ChoiceField(
        choices=LoanProduct.INTEREST_TYPES,
        initial='FLAT',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    calculation_method = forms.ChoiceField(
        choices=LoanProduct._meta.get_field('interest_calculation_method').choices,
        initial='ACTUAL_365',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        loan_amount = cleaned_data.get('loan_amount')
        interest_rate = cleaned_data.get('interest_rate')
        term_days = cleaned_data.get('term_days')
        
        if loan_amount and loan_amount <= 0:
            self.add_error('loan_amount', 'Loan amount must be greater than zero')
        
        if interest_rate and (interest_rate < 0 or interest_rate > 100):
            self.add_error('interest_rate', 'Interest rate must be between 0% and 100%')
        
        if term_days and term_days < 7:
            self.add_error('term_days', 'Minimum loan term is 7 days')
        
        return cleaned_data

# -------------------------
# REPORT GENERATION FORMS
# -------------------------
class LoanReportForm(forms.Form):
    """Form for generating loan reports"""
    
    REPORT_CHOICES = [
        ('portfolio', 'Loan Portfolio Report'),
        ('disbursements', 'Disbursement Report'),
        ('repayments', 'Repayment Collection Report'),
        ('overdue', 'Overdue Loans Report'),
        ('interest_income', 'Interest Income Report'),
        ('risk_analysis', 'Risk Analysis Report'),
        ('client_statement', 'Client Loan Statement'),
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'onchange': 'toggleReportFields(this.value)'
        })
    )
    
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'value': datetime.date.today().isoformat()
        })
    )
    
    format = forms.ChoiceField(
        choices=[('html', 'Web View'), ('pdf', 'PDF'), ('excel', 'Excel')],
        initial='html',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Client-specific fields (for client statement)
    client = forms.ModelChoiceField(
        queryset=ClientAccount.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control select2'})
    )
    
    # Product-specific fields
    loan_product = forms.ModelChoiceField(
        queryset=LoanProduct.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control select2'})
    )
    
    # Status filter
    status = forms.MultipleChoiceField(
        choices=Loan.LOAN_STATUS,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2-multiple'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        report_type = cleaned_data.get('report_type')
        
        if start_date and end_date and start_date > end_date:
            self.add_error('start_date', 'Start date cannot be after end date')
            self.add_error('end_date', 'End date cannot be before start date')
        
        if report_type == 'client_statement':
            client = cleaned_data.get('client')
            if not client:
                self.add_error('client', 'Client is required for client statement report')
        
        return cleaned_data

# -------------------------
# QUICK ACTION FORMS
# -------------------------
class QuickPaymentForm(forms.Form):
    """Form for quick payment processing"""
    
    loan_number = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter loan number...',
            'hx-get': '/loans/api/quick-loan-lookup/',
            'hx-trigger': 'keyup changed delay:500ms',
            'hx-target': '#loan-details'
        })
    )
    
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Amount...'
        })
    )
    
    payment_method = forms.ChoiceField(
        choices=LoanTransaction.PAYMENT_METHODS,
        initial='CASH',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class QuickApplicationForm(forms.Form):
    """Form for quick loan application (simplified)"""
    
    client_id = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Client ID or Phone...'
        })
    )
    
    product_id = forms.ChoiceField(
        choices=[('', 'Select Product')] + [
            (p.id, f"{p.name} ({p.annual_interest_rate}%)") 
            for p in LoanProduct.objects.filter(is_active=True)
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )