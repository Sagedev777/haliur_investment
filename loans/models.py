from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from client_accounts.models import ClientAccount
from decimal import Decimal, ROUND_HALF_UP
import datetime
from dateutil.relativedelta import relativedelta
import uuid

# -----------------------
# LOAN PRODUCTS (ENHANCED)
# -----------------------
class LoanProduct(models.Model):
    INTEREST_TYPES = [
        ('FLAT', 'Flat Rate (Simple Interest)'),
        ('REDUCING_MONTHLY', 'Reducing Balance (Monthly Rest)'),
        ('REDUCING_DAILY', 'Reducing Balance (Daily Rest)'),
    ]
    
    REPAYMENT_FREQUENCIES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('BIWEEKLY', 'Bi-weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)  # e.g., "PL-30D-15P"
    description = models.TextField(blank=True)
    
    # Interest Configuration
    interest_type = models.CharField(max_length=20, choices=INTEREST_TYPES, default='FLAT')
    annual_interest_rate = models.DecimalField(max_digits=6, decimal_places=2, help_text="Annual Percentage Rate (%)")
    interest_calculation_method = models.CharField(max_length=20, choices=[
        ('ACTUAL_365', 'Actual/365 Fixed'),
        ('ACTUAL_360', 'Actual/360'),
        ('30_360', '30/360'),
    ], default='ACTUAL_365')
    
    # Loan Amount Range
    min_loan_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('1000.00'))
    max_loan_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('1000000.00'))
    
    # Term Configuration
    min_term_days = models.IntegerField(default=7)
    max_term_days = models.IntegerField(default=365)
    
    # Fees
    processing_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    late_payment_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    early_repayment_penalty_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('2.00'))
    
    # Eligibility Criteria
    min_client_age_days = models.IntegerField(default=90, help_text="Minimum days as client")
    min_savings_balance_percent = models.DecimalField(
        max_digits=5, decimal_places=2, 
        default=Decimal('20.00'),
        help_text="Minimum savings balance as % of loan"
    )
    
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"{self.code} - {self.name} ({self.annual_interest_rate}% p.a.)"
    
    def clean(self):
        if self.min_loan_amount > self.max_loan_amount:
            raise ValidationError("Minimum loan amount cannot exceed maximum loan amount")
        if self.min_term_days > self.max_term_days:
            raise ValidationError("Minimum term cannot exceed maximum term")

# -----------------------
# LOAN (Created when application is APPROVED)
# -----------------------
class Loan(models.Model):
    LOAN_STATUS = [
        ('PENDING_DISBURSEMENT', 'Pending Disbursement'),
        ('ACTIVE', 'Active'),
        ('OVERDUE', 'Overdue'),
        ('DEFAULTED', 'Defaulted'),
        ('CLOSED', 'Closed'),
        ('WRITTEN_OFF', 'Written Off'),
    ]
    
    # Link to Application
    application = models.OneToOneField('LoanApplication', on_delete=models.PROTECT, related_name='loan')
    
    # Identification
    loan_number = models.CharField(max_length=50, unique=True)
    
    # Core Loan Details
    client = models.ForeignKey(ClientAccount, on_delete=models.PROTECT, related_name='loans')
    loan_product = models.ForeignKey(LoanProduct, on_delete=models.PROTECT)
    principal_amount = models.DecimalField(max_digits=15, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=6, decimal_places=2)
    term_days = models.IntegerField()
    
    # Dates
    disbursement_date = models.DateField(null=True, blank=True)
    maturity_date = models.DateField(null=True, blank=True)
    first_payment_date = models.DateField(null=True, blank=True)
    next_payment_date = models.DateField(null=True, blank=True)
    
    # Financials
    total_interest_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_repayment_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    processing_fee_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    late_fee_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Current State
    remaining_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    overdue_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    days_overdue = models.IntegerField(default=0)
    
    # Status
    status = models.CharField(max_length=25, choices=LOAN_STATUS, default='PENDING_DISBURSEMENT')
    
    # Staff
    disbursed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='disbursed_loans')
    loan_officer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='managed_loans')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-disbursement_date']
        indexes = [
            models.Index(fields=['status', 'next_payment_date']),
            models.Index(fields=['client', 'status']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.loan_number:
            # Generate loan number: LN-YYYYMM-XXXXX
            year_month = datetime.datetime.now().strftime('%Y%m')
            last_loan = Loan.objects.filter(
                loan_number__startswith=f'LN-{year_month}'
            ).count()
            self.loan_number = f'LN-{year_month}-{last_loan + 1:05d}'
        
        # Calculate maturity date
        if self.disbursement_date and not self.maturity_date:
            self.maturity_date = self.disbursement_date + datetime.timedelta(days=self.term_days)
        
        # Update status based on dates
        if self.status == 'ACTIVE' and self.next_payment_date:
            today = datetime.date.today()
            if today > self.next_payment_date:
                self.status = 'OVERDUE'
                self.days_overdue = (today - self.next_payment_date).days
        
        super().save(*args, **kwargs)

# -----------------------
# LOAN APPLICATION (FIXED)
# -----------------------
class LoanApplication(models.Model):
    APPLICATION_STATUS = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('CONDITIONALLY_APPROVED', 'Conditionally Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Identification
    application_id = models.CharField(max_length=20, unique=True, editable=False)
    application_number = models.CharField(max_length=50, unique=True)
    
    # Client & Product
    client = models.ForeignKey(ClientAccount, on_delete=models.PROTECT, related_name='loan_applications')
    loan_product = models.ForeignKey(LoanProduct, on_delete=models.PROTECT)
    
    # Loan Details
    requested_amount = models.DecimalField(max_digits=15, decimal_places=2)
    requested_term_days = models.IntegerField()
    purpose = models.TextField()
    
    # Financial Calculations (AUTO-CALCULATED)
    approved_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    approved_term_days = models.IntegerField(null=True, blank=True)
    approved_interest_rate = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    processing_fee_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_disbursement_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    total_interest_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_repayment_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Collateral
    collateral_description = models.TextField(blank=True)
    collateral_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    collateral_documents = models.FileField(upload_to='loan_docs/', blank=True, null=True)

    # Guarantors (Can have multiple)
    guarantors = models.ManyToManyField('Guarantor', blank=True)
    
    # Status & Tracking
    status = models.CharField(max_length=25, choices=APPLICATION_STATUS, default='DRAFT')
    application_date = models.DateTimeField(auto_now_add=True)
    submitted_date = models.DateTimeField(null=True, blank=True)
    review_date = models.DateTimeField(null=True, blank=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    
    # Personnel
    loan_officer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assigned_applications')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_applications')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_applications')
    
    # Decision Information
    rejection_reason = models.TextField(blank=True)
    approval_conditions = models.TextField(blank=True)
    credit_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    risk_rating = models.CharField(max_length=1, choices=[
        ('A', 'Low Risk'), ('B', 'Medium Risk'), ('C', 'High Risk'), ('D', 'Very High Risk')
    ], null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_applications')
    
    class Meta:
        ordering = ['-application_date']
        indexes = [
            models.Index(fields=['status', 'application_date']),
            models.Index(fields=['client', 'status']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.application_id:
            # Generate unique ID: HALQ-YYYYMM-XXXXX
            year_month = datetime.datetime.now().strftime('%Y%m')
            last_id = LoanApplication.objects.filter(
                application_id__startswith=f'HALQ-{year_month}'
            ).count()
            self.application_id = f'HALQ-{year_month}-{last_id + 1:05d}'
        
        if not self.application_number:
            self.application_number = f"LA{datetime.datetime.now().strftime('%y%m%d')}{uuid.uuid4().hex[:6].upper()}"
        
        super().save(*args, **kwargs)
    
    def calculate_credit_score(self):
        """Professional credit scoring algorithm"""
        score = 100  # Base score
        
        # 1. Account Age Factor (up to 20 points)
        account_age_days = (datetime.datetime.now().date() - self.client.created_at.date()).days
        if account_age_days > 365:
            score += 20
        elif account_age_days > 180:
            score += 15
        elif account_age_days > 90:
            score += 10
        elif account_age_days > 30:
            score += 5
        
        # 2. Savings Balance Factor (up to 30 points)
        savings_percent = (self.client.current_balance / self.requested_amount * 100) if self.requested_amount > 0 else 0
        if savings_percent >= 50:
            score += 30
        elif savings_percent >= 30:
            score += 20
        elif savings_percent >= 20:
            score += 10
        elif savings_percent >= 10:
            score += 5
        
        # 3. Transaction History (up to 25 points)
        # You'd need to query transaction history from client_accounts
        # For now, assume good history
        
        # 4. Existing Debt Factor (deduct up to 40 points)
        
        existing_loans = self.client.loans.filter(
            status__in=['ACTIVE', 'OVERDUE']
        )
        
        
        total_existing_debt = sum(loan.remaining_balance for loan in existing_loans)
        debt_to_income_ratio = (total_existing_debt + self.requested_amount) / self.client.monthly_income if self.client.monthly_income > 0 else 0
        
        if debt_to_income_ratio > 0.8:
            score -= 40
        elif debt_to_income_ratio > 0.6:
            score -= 25
        elif debt_to_income_ratio > 0.4:
            score -= 10
        
        # 5. Collateral Factor (up to 25 points)
        if self.collateral_value:
            collateral_ratio = (self.collateral_value / self.requested_amount) if self.requested_amount > 0 else 0
            if collateral_ratio >= 1.5:
                score += 25
            elif collateral_ratio >= 1.2:
                score += 15
            elif collateral_ratio >= 1.0:
                score += 5
        
        return max(0, min(100, score))


class CollateralDocument(models.Model):
    loan_application = models.ForeignKey(
        LoanApplication, 
        on_delete=models.CASCADE, 
        related_name='collateral_documents'
    )
    file = models.FileField(upload_to='collaterals/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
class CollateralDocument(models.Model):
    loan_application = models.ForeignKey(LoanApplication, on_delete=models.CASCADE, related_name='collateral_docs')
    file = models.FileField(upload_to='collaterals/')

    
# loans/models.py
class LoanApplicationDocument(models.Model):
    loan_application = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document = models.FileField(upload_to='loan_collateral/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.loan_application.application_number} - {self.document.name}"

class LoanPayment(models.Model):
    """
    Compatibility layer for old code that expects a LoanPayment model.
    It maps payments to installments and stores clean payment info
    without replacing the more advanced LoanTransaction model.
    """

    PAYMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Fully Paid'),
    ]

    loan = models.ForeignKey('Loan', on_delete=models.CASCADE, related_name='payments')
    installment = models.ForeignKey('LoanRepaymentSchedule', on_delete=models.SET_NULL, null=True, blank=True)
    transaction = models.ForeignKey('LoanTransaction', on_delete=models.SET_NULL, null=True, blank=True)

    amount = models.DecimalField(max_digits=15, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    interest_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    late_fee_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    payment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default='PENDING')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment {self.id} - Loan {self.loan.loan_number} - {self.amount}"


# -----------------------
# LOAN REPAYMENT SCHEDULE (Amortization Table)
# -----------------------
class LoanRepaymentSchedule(models.Model):
    INSTALLMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('DUE', 'Due'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
    ]
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayment_schedule')
    installment_number = models.IntegerField()
    due_date = models.DateField()
    
    # Calculated amounts
    principal_amount = models.DecimalField(max_digits=15, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=15, decimal_places=2)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Payment tracking
    paid_principal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    paid_interest = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    paid_late_fee = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=INSTALLMENT_STATUS, default='PENDING')
    payment_date = models.DateField(null=True, blank=True)
    
    # Late fees
    late_fee_applied = models.BooleanField(default=False)
    late_fee_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    grace_period_days = models.IntegerField(default=5)
    
    class Meta:
        ordering = ['installment_number']
        unique_together = ['loan', 'installment_number']
    
    @property
    def remaining_balance(self):
        return self.total_amount - self.total_paid
    
    @property
    def is_overdue(self):
        if self.status in ['PAID', 'PARTIALLY_PAID']:
            return False
        return datetime.date.today() > self.due_date + datetime.timedelta(days=self.grace_period_days)

# -----------------------
# LOAN TRANSACTION (Payments & Adjustments)
# -----------------------
class LoanTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('DISBURSEMENT', 'Loan Disbursement'),
        ('PRINCIPAL_PAYMENT', 'Principal Payment'),
        ('INTEREST_PAYMENT', 'Interest Payment'),
        ('LATE_FEE_PAYMENT', 'Late Fee Payment'),
        ('EARLY_REPAYMENT', 'Early Repayment'),
        ('PENALTY_CHARGE', 'Penalty Charge'),
        ('ADJUSTMENT', 'Adjustment'),
        ('WRITE_OFF', 'Write Off'),
    ]
    
    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('CHEQUE', 'Cheque'),
        ('AUTO_DEBIT', 'Auto Debit'),
        ('OFFSET', 'Savings Offset'),
    ]
    
    # Identification
    transaction_id = models.CharField(max_length=50, unique=True, editable=False)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Related Objects
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name='transactions')
    installment = models.ForeignKey(LoanRepaymentSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    
    # Transaction Details
    transaction_type = models.CharField(max_length=25, choices=TRANSACTION_TYPES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    
    # Amounts
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    interest_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fee_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Dates
    transaction_date = models.DateTimeField(default=datetime.datetime.now)
    value_date = models.DateField(default=datetime.date.today)
    
    # Staff
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_transactions')
    
    # Status
    is_reversed = models.BooleanField(default=False)
    reversal_reason = models.TextField(blank=True)
    reversal_date = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    attachment = models.FileField(upload_to='loan_transactions/', blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['loan', 'transaction_date']),
            models.Index(fields=['transaction_type', 'value_date']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            # Generate transaction ID: TXN-YYYYMMDD-XXXXX
            date_str = datetime.datetime.now().strftime('%Y%m%d')
            last_txn = LoanTransaction.objects.filter(
                transaction_id__startswith=f'TXN-{date_str}'
            ).count()
            self.transaction_id = f'TXN-{date_str}-{last_txn + 1:05d}'
        
        super().save(*args, **kwargs)

# -----------------------
# GUARANTOR (Enhanced)
# -----------------------
class Guarantor(models.Model):
    GUARANTOR_TYPES = [
        ('INDIVIDUAL', 'Individual'),
        ('COMPANY', 'Company'),
        ('GROUP', 'Group'),
    ]
    
    # Identification
    guarantor_id = models.CharField(max_length=50, unique=True, editable=False)
    
    # Type and Details
    guarantor_type = models.CharField(max_length=20, choices=GUARANTOR_TYPES)
    
    # Individual Guarantor Details
    individual = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, null=True, blank=True, related_name='guarantor_for')
    
    # Company/External Guarantor Details
    company_name = models.CharField(max_length=200, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    contact_person = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    nin = models.CharField(max_length=50, blank=True)
    
    # Guarantee Details
    guarantee_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    guarantee_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Documents
    id_document = models.FileField(upload_to='guarantor_ids/', blank=True, null=True)
    signed_agreement = models.FileField(upload_to='guarantor_agreements/', blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='guarantors_verified'  # ADDED THIS
    )
    verification_date = models.DateField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        related_name='guarantors_created'  # ADDED THIS
    )
    
    def save(self, *args, **kwargs):
        if not self.guarantor_id:
            # Generate guarantor ID: GTR-YYYY-XXXXX
            year = datetime.datetime.now().strftime('%Y')
            last_guarantor = Guarantor.objects.filter(
                guarantor_id__startswith=f'GTR-{year}'
            ).count()
            self.guarantor_id = f'GTR-{year}-{last_guarantor + 1:05d}'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.guarantor_type == 'INDIVIDUAL' and self.individual:
            return f"Individual: {self.individual.full_account_name}"
        elif self.company_name:
            return f"Company: {self.company_name}"
        return f"Guarantor {self.guarantor_id}"
# -----------------------
# INTEREST CALCULATION SERVICE
# -----------------------
class InterestCalculationService:
    """Professional interest calculation service"""
    
    @staticmethod
    def calculate_interest(principal, annual_rate, term_days, method='ACTUAL_365', interest_type='FLAT'):
        """
        Calculate interest using professional banking standards
        
        Methods:
        - ACTUAL_365: Actual days / 365
        - ACTUAL_360: Actual days / 360 (US Standard)
        - 30_360: 30 days/month, 360 days/year (European)
        """
        annual_rate_decimal = Decimal(str(annual_rate)) / Decimal('100')
        
        # Convert to daily rate based on method
        if method == 'ACTUAL_365':
            daily_rate = annual_rate_decimal / Decimal('365')
            interest_days = term_days
        elif method == 'ACTUAL_360':
            daily_rate = annual_rate_decimal / Decimal('360')
            interest_days = term_days
        elif method == '30_360':
            # Approximate months
            months = term_days / Decimal('30')
            daily_rate = annual_rate_decimal / Decimal('360')
            interest_days = months * Decimal('30')
        else:
            raise ValueError(f"Unknown interest calculation method: {method}")
        
        if interest_type == 'FLAT':
            interest = principal * daily_rate * Decimal(str(interest_days))
        else:
            # Reducing balance calculation
            interest = Decimal('0')
            remaining = principal
            daily_rate_decimal = daily_rate
            
            # For simplicity in example - real implementation would use amortization formula
            # This is a simplified daily reducing balance
            for day in range(term_days):
                daily_interest = remaining * daily_rate_decimal
                interest += daily_interest
                # Assume equal daily principal repayment
                remaining -= principal / Decimal(str(term_days))
        
        return interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# -----------------------
# AMORTIZATION SCHEDULE SERVICE
# -----------------------
class AmortizationService:
    """Generate professional amortization schedules"""
    
    @staticmethod
    def generate_amortization_schedule(loan):
        """
        Generate amortization schedule for a loan
        Returns list of dictionaries with installment details
        """
        schedule = []
        
        # For flat interest loans
        if loan.loan_product.interest_type == 'FLAT':
            total_interest = InterestCalculationService.calculate_interest(
                loan.principal_amount,
                loan.interest_rate,
                loan.term_days,
                method=loan.loan_product.interest_calculation_method,
                interest_type='FLAT'
            )
            
            total_repayment = loan.principal_amount + total_interest
            
            # Determine installment frequency
            if loan.term_days <= 30:
                installments = 4  # Weekly
                installment_days = 7
            elif loan.term_days <= 90:
                installments = 12  # Weekly for 3 months
                installment_days = loan.term_days // 12
            else:
                installments = loan.term_days // 30  # Monthly
                installment_days = 30
            
            # Equal installments
            installment_amount = total_repayment / Decimal(str(installments))
            installment_principal = loan.principal_amount / Decimal(str(installments))
            installment_interest = total_interest / Decimal(str(installments))
            
            current_date = loan.disbursement_date
            remaining_balance = total_repayment
            
            for i in range(1, installments + 1):
                due_date = current_date + datetime.timedelta(days=installment_days)
                
                schedule.append({
                    'installment_number': i,
                    'due_date': due_date,
                    'principal_amount': installment_principal.quantize(Decimal('0.01')),
                    'interest_amount': installment_interest.quantize(Decimal('0.01')),
                    'total_amount': installment_amount.quantize(Decimal('0.01')),
                    'remaining_balance': (remaining_balance - installment_amount).quantize(Decimal('0.01')),
                })
                
                current_date = due_date
                remaining_balance -= installment_amount
        
        # For reducing balance loans (more complex - requires proper formula)
        else:
            # Implementation of reducing balance amortization
            # This would use the standard amortization formula
            pass
        
        return schedule