from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from client_accounts.models import ClientAccount
from decimal import Decimal
import datetime

class LoanProduct(models.Model):
    INTEREST_METHODS = [
        ('FLAT', 'Flat Rate'),
        ('REDUCING', 'Reducing Balance'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    interest_method = models.CharField(max_length=20, choices=INTEREST_METHODS)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    min_amount = models.DecimalField(max_digits=12, decimal_places=2)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2)
    loan_period = models.IntegerField(help_text="Loan duration in days")
    number_of_installments = models.IntegerField()
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
    
    def __str__(self):
        return f"{self.name} - {self.interest_rate}%"

class Guarantor(models.Model):
    GUARANTOR_TYPES = [
        ('INTERNAL', 'Internal (Existing Customer)'),
        ('EXTERNAL', 'External'),
    ]
    
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
        if self.guarantor_type == 'INTERNAL':
            return f"Internal: {self.internal_customer.full_account_name}"
        else:
            return f"External: {self.external_name}"

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
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=20, default='')
    
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
        
        loan_period = self.loan_product.loan_period
        return self.disbursement_date + datetime.timedelta(days=loan_period)
    
    def get_days_remaining(self):
        if not self.due_date or self.status in ['COMPLETED', 'DEFAULTED', 'REJECTED']:
            return 0
        
        today = datetime.datetime.now().date()
        due = self.due_date.date()
        
        if today > due:
            return 0
        return (due - today).days
    
    def get_loan_status_info(self):
        if self.status == 'DISBURSED':
            days_remaining = self.get_days_remaining()
            if days_remaining == 0 and self.due_date:
                return "OVERDUE"
            elif days_remaining > 0:
                return f"ACTIVE - {days_remaining} days remaining"
        
        return self.status
    
    def get_total_paid(self):
        """Calculate total amount paid so far"""
        return self.loanpayment_set.aggregate(total=models.Sum('payment_amount'))['total'] or Decimal('0')
    
    def get_balance_remaining(self):
        """Calculate remaining balance"""
        return self.total_amount - self.get_total_paid()
    
    def get_payment_progress(self):
        """Calculate payment progress percentage"""
        if self.total_amount == 0:
            return 0
        return (self.get_total_paid() / self.total_amount * 100).quantize(Decimal('0.1'))
    
    def is_overdue(self):
        """Check if loan is overdue"""
        if not self.due_date or self.status in ['COMPLETED', 'DEFAULTED']:
            return False
        return datetime.datetime.now().date() > self.due_date.date()
    
    def clean(self):
        if not self.client_account.is_approved:
            raise ValidationError('Client account must be approved before applying for loan.')
        
        if not self.client_account.can_take_loan(self.loan_amount):
            required_savings = self.loan_amount * Decimal('0.2')
            raise ValidationError(
                f'Customer does not have enough savings. Required: {required_savings}, '
                f'Available: {self.client_account.savings_balance}'
            )
        
        max_loan = self.client_account.get_max_loan_amount()
        if self.loan_amount > max_loan:
            raise ValidationError(
                f'Loan amount exceeds maximum allowed based on savings. '
                f'Maximum: {max_loan}, Requested: {self.loan_amount}'
            )
        
        if self.loan_amount < self.loan_product.min_amount:
            raise ValidationError(f'Loan amount must be at least {self.loan_product.min_amount}')
        
        if self.loan_amount > self.loan_product.max_amount:
            raise ValidationError(f'Loan amount cannot exceed {self.loan_product.max_amount}')
        
        min_collateral = self.loan_amount * Decimal('1.2')
        if self.collateral_value < min_collateral:
            raise ValidationError(f'Collateral value must be at least 120% of loan amount ({min_collateral})')
    
    def save(self, *args, **kwargs):
        if not self.application_number:
            self.application_number = self.generate_application_number()
        
        self.interest_amount = self.calculate_interest()
        self.total_amount = self.loan_amount + self.interest_amount
        self.payment_mode = self.loan_product.get_payment_mode()
        
        if self.status == 'DISBURSED' and self.disbursement_date and not self.due_date:
            self.due_date = self.calculate_due_date()
        
        if self.status == 'DISBURSED' and not self.disbursed_amount:
            self.disbursed_amount = self.loan_amount
        
        # Auto-update status based on payments
        total_paid = self.get_total_paid()
        if total_paid >= self.total_amount and self.status == 'DISBURSED':
            self.status = 'COMPLETED'
        elif self.is_overdue() and self.status == 'DISBURSED':
            self.status = 'DEFAULTED'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.application_number} - {self.client_account.full_account_name}"

class LoanPayment(models.Model):
    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('CHEQUE', 'Cheque'),
    ]
    
    loan_application = models.ForeignKey(LoanApplication, on_delete=models.CASCADE)
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='CASH')
    received_by = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    def clean(self):
        """Validate payment"""
        if self.payment_amount <= 0:
            raise ValidationError('Payment amount must be greater than zero.')
        
        # Check if payment exceeds remaining balance
        remaining_balance = self.loan_application.get_balance_remaining()
        if self.payment_amount > remaining_balance:
            raise ValidationError(f'Payment amount ({self.payment_amount}) exceeds remaining balance ({remaining_balance})')
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Update loan status based on payments
        total_paid = self.loan_application.get_total_paid()
        if total_paid >= self.loan_application.total_amount:
            self.loan_application.status = 'COMPLETED'
            self.loan_application.save()
        elif self.loan_application.is_overdue() and self.loan_application.status == 'DISBURSED':
            self.loan_application.status = 'DEFAULTED'
            self.loan_application.save()
    
    def __str__(self):
        return f"Payment of {self.payment_amount} for {self.loan_application.application_number}"