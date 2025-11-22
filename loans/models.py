from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from client_accounts.models import ClientAccount
from decimal import Decimal
import datetime

# -----------------------
# Loan Products
# -----------------------
class LoanProduct(models.Model):
    INTEREST_METHODS = [('FLAT', 'Flat Rate'), ('REDUCING', 'Reducing Balance')]
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    interest_method = models.CharField(max_length=20, choices=INTEREST_METHODS)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    min_amount = models.DecimalField(max_digits=12, decimal_places=2)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2)
    loan_period = models.IntegerField(help_text="Loan duration in days")
    number_of_installments = models.IntegerField(editable=False, default=0)
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    
    def get_payment_mode(self):
        if self.loan_period <= 7:
            return 'WEEKLY'
        elif self.loan_period <= 14:
            return 'BI_WEEKLY'
        elif self.loan_period <= 30:
            return 'MONTHLY'
        else:
            return 'CUSTOM'

    def save(self, *args, **kwargs):
        # Auto calculate number of installments based on loan period
        # Example: 1 installment per week
        if self.loan_period <= 7:
            self.number_of_installments = 1
        elif self.loan_period <= 14:
            self.number_of_installments = 2
        elif self.loan_period <= 30:
            self.number_of_installments = 4
        else:
            self.number_of_installments = max(1, self.loan_period // 7)  # 1 installment per week for long loans
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} - {self.interest_rate}%"


# -----------------------
# Guarantors
# -----------------------
class Guarantor(models.Model):
    GUARANTOR_TYPES = [('INTERNAL', 'Internal'), ('EXTERNAL', 'External')]
    
    guarantor_type = models.CharField(max_length=20, choices=GUARANTOR_TYPES)
    internal_customer = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, null=True, blank=True)
    external_name = models.CharField(max_length=100, blank=True)
    external_contact = models.CharField(max_length=20, blank=True)
    external_nin = models.CharField(max_length=20, blank=True)
    external_address = models.TextField(blank=True)
    
    def clean(self):
        if self.guarantor_type == 'INTERNAL' and not self.internal_customer:
            raise ValidationError('Internal guarantor must be selected from existing customers.')
        elif self.guarantor_type == 'EXTERNAL':
            if not all([self.external_name, self.external_contact, self.external_nin, self.external_address]):
                raise ValidationError('All external guarantor details are required.')
    
    def __str__(self):
        return f"{'Internal: ' + self.internal_customer.full_account_name if self.guarantor_type == 'INTERNAL' else 'External: ' + self.external_name}"


# -----------------------
# Loan Applications
# -----------------------
class LoanApplication(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('DISBURSED', 'Disbursed - Active'),
        ('COMPLETED', 'Completed'),
        ('DEFAULTED', 'Defaulted'),
    ]
    
    application_number = models.CharField(max_length=20, unique=True, blank=True)
    client_account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE)
    loan_product = models.ForeignKey(LoanProduct, on_delete=models.CASCADE)
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)  # entered by applicant
    
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    payment_mode = models.CharField(max_length=20, default='', editable=False)
    
    collateral_description = models.TextField()
    collateral_value = models.DecimalField(max_digits=12, decimal_places=2)
    collateral_images = models.ImageField(upload_to='collateral_images/', blank=True, null=True)
    
    guarantor = models.ForeignKey(Guarantor, on_delete=models.CASCADE)
    
    application_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    disbursement_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    loan_officer = models.ForeignKey(User, on_delete=models.CASCADE, editable=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_loans')
    disbursed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='disbursed_loans')
    rejection_reason = models.TextField(blank=True)
    
    disbursed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    transaction_reference = models.CharField(max_length=100, blank=True)
    disbursement_notes = models.TextField(blank=True)
    
    # -----------------------
    # Utility Methods
    # -----------------------
    def generate_application_number(self):
        year = datetime.datetime.now().year
        last_app = LoanApplication.objects.order_by('-id').first()
        next_num = (last_app.id + 1) if last_app else 1
        return f"HIL-L-{year}-{next_num:06d}"
    
    def calculate_interest(self):
        loan_period = Decimal(str(self.loan_product.loan_period))
        interest_rate = self.loan_product.interest_rate
        loan_amount = self.loan_amount
        
        if self.loan_product.interest_method == 'FLAT':
            daily_rate = interest_rate / Decimal('100') / Decimal('365')
            interest = loan_amount * daily_rate * loan_period
        else:
            daily_rate = interest_rate / Decimal('100') / Decimal('365')
            interest = loan_amount * daily_rate * loan_period * Decimal('0.8')
        
        return interest.quantize(Decimal('0.01'))
    
    def calculate_due_date(self):
        if not self.disbursement_date:
            return None
        return self.disbursement_date + datetime.timedelta(days=self.loan_product.loan_period)
    
    def get_days_remaining(self):
        if not self.due_date or self.status in ['COMPLETED', 'DEFAULTED', 'REJECTED']:
            return 0
        today = datetime.datetime.now().date()
        due = self.due_date.date()
        return max((due - today).days, 0)
    
    def get_total_paid(self):
        return self.loanpayment_set.aggregate(total=models.Sum('payment_amount'))['total'] or Decimal('0')
    
    def get_balance_remaining(self):
        return self.total_amount - self.get_total_paid()
    
    def get_payment_progress(self):
        if self.total_amount == 0:
            return 0
        return (self.get_total_paid() / self.total_amount * 100).quantize(Decimal('0.1'))
    
    def is_overdue(self):
        return self.status == 'DISBURSED' and self.due_date and datetime.datetime.now().date() > self.due_date.date()
    
    def clean(self):
        if not self.client_account.is_approved:
            raise ValidationError('Client account must be approved before applying for loan.')
        max_loan = self.client_account.get_max_loan_amount()
        if self.loan_amount > max_loan:
            raise ValidationError(f'Loan exceeds maximum allowed ({max_loan})')
        if self.loan_amount < self.loan_product.min_amount or self.loan_amount > self.loan_product.max_amount:
            raise ValidationError('Loan amount out of allowed product range.')
        if self.collateral_value < self.loan_amount * Decimal('1.2'):
            raise ValidationError('Collateral must be at least 120% of loan amount.')
    
    def save(self, *args, **kwargs):
        if not self.application_number:
            self.application_number = self.generate_application_number()
    
        # AUTO CALCULATE INTEREST
        self.interest_amount = self.calculate_interest()
        self.total_amount = self.loan_amount + self.interest_amount
    
        # AUTO SET PAYMENT MODE
        self.payment_mode = self.loan_product.get_payment_mode()
    
        # SET DUE DATE if disbursed
        if self.status == 'DISBURSED' and self.disbursement_date and not self.due_date:
            self.due_date = self.calculate_due_date()
        if self.status == 'DISBURSED' and not self.disbursed_amount:
            self.disbursed_amount = self.loan_amount
    
        # AUTO UPDATE STATUS BASED ON PAYMENTS
        total_paid = self.get_total_paid()
        if total_paid >= self.total_amount and self.status == 'DISBURSED':
            self.status = 'COMPLETED'
        elif self.is_overdue():
            self.status = 'DEFAULTED'
    
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.application_number} - {self.client_account.full_account_name}"


# -----------------------
# Loan Payments
# -----------------------
class LoanPayment(models.Model):
    PAYMENT_METHODS = [('CASH', 'Cash'), ('BANK_TRANSFER', 'Bank Transfer'), ('MOBILE_MONEY', 'Mobile Money'), ('CHEQUE', 'Cheque')]
    
    loan_application = models.ForeignKey(LoanApplication, on_delete=models.CASCADE)
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='CASH')
    received_by = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    def clean(self):
        if self.payment_amount <= 0:
            raise ValidationError('Payment amount must be greater than zero.')
        if self.payment_amount > self.loan_application.get_balance_remaining():
            raise ValidationError('Payment exceeds remaining balance.')
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Update loan status automatically
        loan = self.loan_application
        if loan.get_total_paid() >= loan.total_amount:
            loan.status = 'COMPLETED'
            loan.save()
        elif loan.is_overdue():
            loan.status = 'DEFAULTED'
            loan.save()
    
    def __str__(self):
        return f"Payment {self.payment_amount} for {self.loan_application.application_number}"
