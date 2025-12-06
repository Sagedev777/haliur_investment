from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import random
import string

# Modern Django JSONField
JSONField = models.JSONField


# ------------------------
# Role / Profile model
# ------------------------
class UserProfile(models.Model):
    ROLE_ADMIN = 'ADMIN'
    ROLE_STAFF = 'STAFF'
    ROLE_MANAGER = 'MANAGER'
    ROLE_ACCOUNTANT = 'ACCOUNTANT'
    ROLE_LOAN_OFFICER = 'LOAN_OFFICER'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_STAFF, 'Staff'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_ACCOUNTANT, 'Accountant'),
        (ROLE_LOAN_OFFICER, 'Loan Officer'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STAFF)
    phone = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    # Convenience properties
    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN or self.user.is_superuser

    @property
    def is_staff_role(self):
        return self.role == self.ROLE_STAFF

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER

    @property
    def is_accountant(self):
        return self.role == self.ROLE_ACCOUNTANT

    @property
    def is_loan_officer(self):
        return self.role == self.ROLE_LOAN_OFFICER

    class Meta:
        ordering = ['user__username']


# ------------------------
# Audit log model
# ------------------------
class ClientAuditLog(models.Model):
    ACTION_CREATE = 'CREATE'
    ACTION_UPDATE = 'UPDATE'
    ACTION_EDIT_REQUEST = 'EDIT_REQUEST'
    ACTION_APPROVE_EDIT = 'APPROVE_EDIT'
    ACTION_REJECT_EDIT = 'REJECT_EDIT'
    ACTION_SAVINGS_TX = 'SAVINGS_TX'
    ACTION_ACCOUNT_APPROVE = 'ACCOUNT_APPROVE'
    ACTION_ACCOUNT_REJECT = 'ACCOUNT_REJECT'
    ACTION_STATUS_CHANGE = 'STATUS_CHANGE'

    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create Account'),
        (ACTION_UPDATE, 'Update Account'),
        (ACTION_EDIT_REQUEST, 'Edit Request Submitted'),
        (ACTION_APPROVE_EDIT, 'Edit Request Approved'),
        (ACTION_REJECT_EDIT, 'Edit Request Rejected'),
        (ACTION_SAVINGS_TX, 'Savings Transaction'),
        (ACTION_ACCOUNT_APPROVE, 'Account Approved'),
        (ACTION_ACCOUNT_REJECT, 'Account Rejected'),
        (ACTION_STATUS_CHANGE, 'Account Status Changed'),
    ]

    client = models.ForeignKey('ClientAccount', on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    changed_data = JSONField(blank=True, null=True)  # stores {field: {'old': x, 'new': y}, ...}
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Client Audit Log'
        verbose_name_plural = 'Client Audit Logs'

    def __str__(self):
        return f"Audit: {self.client.account_number} - {self.get_action_display()} @ {self.timestamp}"
    
    def get_action_badge_color(self):
        """Return Bootstrap badge color based on action type"""
        color_map = {
            'CREATE': 'success',
            'UPDATE': 'info',
            'EDIT_REQUEST': 'warning',
            'APPROVE_EDIT': 'success',
            'REJECT_EDIT': 'danger',
            'SAVINGS_TX': 'primary',
            'ACCOUNT_APPROVE': 'success',
            'ACCOUNT_REJECT': 'danger',
            'STATUS_CHANGE': 'secondary',
        }
        return color_map.get(self.action, 'secondary')

# ------------------------
# ClientAccount - UPDATED VERSION
# ------------------------
class ClientAccount(models.Model):
    # Account Status Choices
    STATUS_PENDING = 'PENDING'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'
    STATUS_SUSPENDED = 'SUSPENDED'
    STATUS_CLOSED = 'CLOSED'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_SUSPENDED, 'Suspended'),
        (STATUS_CLOSED, 'Closed'),
    ]

    # Account Type Choices
    ACCOUNT_TYPES = [
        ('SINGLE', 'Single Account'),
        ('JOINT', 'Joint Account'),
    ]

    # Gender Choices
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    # Account Identification - FIXED FORMAT: HIL-ACC-YYYY-XXXXX
    account_number = models.CharField(max_length=30, unique=True, blank=True, editable=False)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    account_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    
    # Person 1 Information (Primary Account Holder - Required)
    person1_first_name = models.CharField(max_length=100)
    person1_last_name = models.CharField(max_length=100)
    person1_contact = models.CharField(max_length=20)
    person1_address = models.TextField()
    person1_area_code = models.CharField(max_length=10)
    person1_next_of_kin = models.CharField(max_length=100)
    person1_photo = models.ImageField(upload_to='client_photos/', blank=True, null=True)
    person1_signature = models.ImageField(upload_to='client_signatures/', blank=True, null=True)
    person1_nin = models.CharField(max_length=20, unique=True)
    person1_gender = models.CharField(max_length=1, choices=GENDER_CHOICES)

    # Person 2 Information - FIXED: Option C Implementation
    # Can be linked to existing client OR manual entry
    person2_client = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='joint_accounts_as_person2',
        help_text="Link to existing client (if available)"
    )
    person2_first_name = models.CharField(max_length=100, blank=True, null=True)
    person2_last_name = models.CharField(max_length=100, blank=True, null=True)
    person2_contact = models.CharField(max_length=20, blank=True, null=True)
    person2_address = models.TextField(blank=True, null=True)
    person2_area_code = models.CharField(max_length=10, blank=True, null=True)
    person2_next_of_kin = models.CharField(max_length=100, blank=True, null=True)
    person2_photo = models.ImageField(upload_to='client_photos/', blank=True, null=True)
    person2_signature = models.ImageField(upload_to='client_signatures/', blank=True, null=True)
    person2_nin = models.CharField(max_length=20, blank=True, null=True)
    person2_gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)

    # Business Information
    business_location = models.CharField(max_length=100)
    business_sector = models.CharField(max_length=100)

    # Savings Information
    savings_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_savings_deposited = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    last_savings_date = models.DateTimeField(null=True, blank=True)

    # System Fields
    registration_date = models.DateTimeField(auto_now_add=True)
    loan_officer = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='client_accounts',
        help_text="Loan officer responsible for this client"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        null=False, 
        blank=False,
        related_name='created_accounts',
        help_text="User who created this account"
    )
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_accounts',
        help_text="User who approved this account"
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    
    # Edit workflow
    is_edit_pending = models.BooleanField(default=False)
    last_edited_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='edited_accounts'
    )
    last_edited_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-registration_date']
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['person1_nin']),
            models.Index(fields=['account_status']),
            models.Index(fields=['registration_date']),
        ]
        verbose_name = 'Client Account'
        verbose_name_plural = 'Client Accounts'

    def generate_account_number(self):
        """Generate HIL-ACC-YYYY-XXXXX format account number"""
        year = timezone.now().year
        random_digits = ''.join(random.choices(string.digits, k=5))
        account_num = f"HIL-ACC-{year}-{random_digits}"
        
        # Ensure uniqueness
        while ClientAccount.objects.filter(account_number=account_num).exists():
            random_digits = ''.join(random.choices(string.digits, k=5))
            account_num = f"HIL-ACC-{year}-{random_digits}"
        
        return account_num

    def save(self, *args, **kwargs):
        # Generate account number if not exists
        if not self.account_number:
            self.account_number = self.generate_account_number()

        # Auto-fill person2 details if linked to existing client
        if self.account_type == 'JOINT' and self.person2_client and not self.person2_nin:
            self.person2_first_name = self.person2_client.person1_first_name
            self.person2_last_name = self.person2_client.person1_last_name
            self.person2_contact = self.person2_client.person1_contact
            self.person2_address = self.person2_client.person1_address
            self.person2_area_code = self.person2_client.person1_area_code
            self.person2_nin = self.person2_client.person1_nin
            self.person2_gender = self.person2_client.person1_gender
            self.person2_next_of_kin = self.person2_client.person1_next_of_kin

        # VALIDATION: Ensure created_by is set for new records
        if not self.pk and not self.created_by:
            # For new records, created_by MUST be set
            # This should be set in the view, but as a fallback:
            if hasattr(self, 'loan_officer') and self.loan_officer:
                self.created_by = self.loan_officer
            else:
                # This will trigger validation error
                pass
            
        # For existing records missing created_by, try to infer it
        elif self.pk and not self.created_by:
            # Try to get from loan_officer
            if self.loan_officer:
                self.created_by = self.loan_officer

        try:
            self.full_clean()
        except ValidationError as e:
            # Log the validation error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Validation error saving ClientAccount {self.account_number}: {e}")
            raise e

        super().save(*args, **kwargs)
                                                                            
    def clean(self):
        """Business rule validation - FIXED"""
        super().clean()
        
        errors = {}
        
        # Check if this is a joint account
        if self.account_type == 'JOINT':
            # Option C: Either link to existing client OR provide details manually
            if not self.person2_client and not self.person2_nin:
                errors['person2_nin'] = ValidationError(
                    'For joint accounts, either link to an existing client or provide Person 2 details.'
                )
            
            # If linking to existing client, verify it's not the same as person1
            if self.person2_client and self.person2_client.pk == self.pk:
                errors['person2_client'] = ValidationError('Cannot link to same account.')
            
            # If providing manual details, ensure required fields are present
            if self.person2_nin and not self.person2_client:
                required_fields = ['person2_first_name', 'person2_last_name', 'person2_contact']
                for field in required_fields:
                    if not getattr(self, field):
                        errors[field] = ValidationError('This field is required for manual joint account entry.')
        
        # Check primary person NIN uniqueness for active accounts
        if self.person1_nin and self.account_status == self.STATUS_ACTIVE:
            existing = ClientAccount.objects.filter(
                models.Q(person1_nin=self.person1_nin) | models.Q(person2_nin=self.person1_nin),
                account_status=self.STATUS_ACTIVE
            ).exclude(pk=self.pk).exists()
            
            if existing:
                errors['person1_nin'] = ValidationError(
                    f'Person with NIN {self.person1_nin} already has an active account.'
                )
        
        # Check person2 NIN uniqueness if provided
        if self.person2_nin and self.account_status == self.STATUS_ACTIVE:
            existing = ClientAccount.objects.filter(
                models.Q(person1_nin=self.person2_nin) | models.Q(person2_nin=self.person2_nin),
                account_status=self.STATUS_ACTIVE
            ).exclude(pk=self.pk).exists()
            
            if existing and not self.person2_client:
                errors['person2_nin'] = ValidationError(
                    f'Person with NIN {self.person2_nin} already has an active account.'
                )
        
        if errors:
            raise ValidationError(errors)

    # FIXED Loan Eligibility Methods
    def can_take_loan(self, loan_amount):
        """Check if customer can take a loan based on savings (20% rule)"""
        try:
            loan_amount_decimal = Decimal(str(loan_amount))
            required_savings = loan_amount_decimal * Decimal('0.2')
            return self.savings_balance >= required_savings
        except (InvalidOperation, TypeError):
            return False

    def has_minimum_savings(self):
        """Check if client has minimum savings to qualify for loan - FIXED"""
        # Changed from total_savings to savings_balance
        return self.savings_balance >= Decimal('100000.00')  # 100,000 UGX minimum

    def get_max_loan_amount(self):
        """Calculate maximum loan amount based on savings (5x rule)"""
        if self.savings_balance <= 0:
            return Decimal('0.00')
        return self.savings_balance * Decimal('5')

    def approve_account(self, approved_by_user):
        """Approve a pending account"""
        if self.account_status == self.STATUS_PENDING:
            old_status = self.account_status
            self.account_status = self.STATUS_ACTIVE
            self.approved_by = approved_by_user
            self.approval_date = timezone.now()
            self.save()
            
            # Create audit log
            ClientAuditLog.objects.create(
                client=self,
                action=ClientAuditLog.ACTION_ACCOUNT_APPROVE,
                changed_data={
                    'status': {'old': old_status, 'new': self.STATUS_ACTIVE}
                },
                performed_by=approved_by_user,
                note=f"Account approved by {approved_by_user.username}"
            )
            return True
        return False

    def reject_account(self, rejected_by_user, reason=""):
        """Reject a pending account"""
        if self.account_status == self.STATUS_PENDING:
            old_status = self.account_status
            self.account_status = self.STATUS_INACTIVE
            self.save()
            
            # Create audit log
            ClientAuditLog.objects.create(
                client=self,
                action=ClientAuditLog.ACTION_ACCOUNT_REJECT,
                changed_data={
                    'status': {'old': old_status, 'new': self.STATUS_INACTIVE}
                },
                performed_by=rejected_by_user,
                note=f"Account rejected. Reason: {reason}"
            )
            return True
        return False

    def change_status(self, new_status, changed_by_user, reason=""):
        """Change account status with audit logging"""
        if new_status not in dict(self.STATUS_CHOICES).keys():
            raise ValueError(f"Invalid status: {new_status}")

        old_status = self.account_status

        # Ensure created_by is set before saving
        if not self.created_by:
            # Try to set created_by from loan_officer or current user
            if self.loan_officer:
                self.created_by = self.loan_officer
            elif changed_by_user:
                self.created_by = changed_by_user
            else:
                raise ValidationError({
                    'created_by': ['This field is required. Cannot determine who created this account.']
                })

        self.account_status = new_status
        self.last_edited_by = changed_by_user
        self.last_edited_date = timezone.now()

        try:
            self.save()
        except ValidationError as e:
            # Log detailed error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Validation error changing status for account {self.account_number}: {e}")

            # Re-raise with user-friendly message
            raise ValidationError({
                'created_by': ['Account cannot be saved. Please ensure all required fields are filled.']
            })

        # Create audit log
        ClientAuditLog.objects.create(
            client=self,
            action=ClientAuditLog.ACTION_STATUS_CHANGE,
            changed_data={
                'status': {'old': old_status, 'new': new_status}
            },
            performed_by=changed_by_user,
            note=f"Account status changed. Reason: {reason}"
        ) 
        

    def __str__(self):
        if self.account_type == 'SINGLE':
            return f"{self.account_number} - {self.person1_first_name} {self.person1_last_name}"
        else:
            person2_name = self.person2_client.full_account_name if self.person2_client else f"{self.person2_first_name or 'Joint Holder'}"
            return f"{self.account_number} - {self.person1_first_name} & {person2_name}"

    @property
    def full_account_name(self):
        if self.account_type == 'SINGLE':
            return f"{self.person1_first_name} {self.person1_last_name}"
        else:
            person2_name = f"{self.person2_first_name} {self.person2_last_name}" if self.person2_first_name else "Joint Holder"
            return f"{self.person1_first_name} {self.person1_last_name} & {person2_name}"

    @property
    def can_create_joint_account(self):
        return self.account_status == self.STATUS_ACTIVE

    def submit_edit_request(self, requested_by: User, changes: dict):
        """
        Create a ClientEditRequest for the supplied changes.
        - changes should be a dict of {field_name: new_value}
        - marks this client as having a pending edit
        """
        if not isinstance(changes, dict) or not changes:
            raise ValueError("`changes` must be a non-empty dict.")

        req = ClientEditRequest.objects.create(
            client=self,
            requested_by=requested_by,
            data=changes,
            status=ClientEditRequest.STATUS_PENDING
        )
        self.is_edit_pending = True
        self.save(update_fields=['is_edit_pending'])
        
        # Audit log
        ClientAuditLog.objects.create(
            client=self,
            action=ClientAuditLog.ACTION_EDIT_REQUEST,
            changed_data=changes,
            performed_by=requested_by,
            note="Edit request submitted"
        )
        return req

    @property
    def total_loan_balance(self):
        """Calculate total outstanding loan balance"""
        try:
            from loans.models import LoanApplication
            total = LoanApplication.objects.filter(
                client_account=self,
                status__in=['APPROVED', 'DISBURSED', 'ACTIVE']
            ).aggregate(total=models.Sum('remaining_balance'))['total']
            return total or Decimal('0.00')
        except ImportError:
            return Decimal('0.00')

    @property
    def total_loan_limit(self):
        """Calculate total loan limit based on savings"""
        return self.get_max_loan_amount()

    @property
    def available_loan_limit(self):
        """Calculate available loan limit"""
        return self.total_loan_limit - self.total_loan_balance


# ------------------------
# Client Edit Request (soft workflow) - UPDATED
# ------------------------
class ClientEditRequest(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    client = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name='edit_requests')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='client_edit_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    data = JSONField(
        help_text="JSON object of proposed changes, e.g. {'person1_contact': '2567...','business_sector':'Retail'}"
    )
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_edit_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Client Edit Request'
        verbose_name_plural = 'Client Edit Requests'

    def __str__(self):
        return f"EditRequest({self.client.account_number}) by {self.requested_by} [{self.status}]"

    def approve(self, reviewer: User, comment: str = ""):
        """Apply the changes to the client account, create audit log, and mark approved."""
        if self.status != self.STATUS_PENDING:
            raise ValueError("Only pending requests can be approved.")

        client = self.client
        changed = {}
        
        # Apply changes field-by-field
        for field, new_value in (self.data or {}).items():
            if hasattr(client, field):
                old_value = getattr(client, field, None)
                try:
                    # Handle different field types
                    field_obj = client._meta.get_field(field)
                    if isinstance(field_obj, models.DecimalField):
                        new_value = Decimal(str(new_value))
                    elif isinstance(field_obj, models.ForeignKey):
                        # Handle foreign key updates
                        if new_value:
                            new_value = field_obj.related_model.objects.get(pk=new_value)
                        else:
                            new_value = None
                except (ValueError, InvalidOperation, field_obj.related_model.DoesNotExist):
                    # If conversion fails, keep as-is (will be validated in client.save())
                    pass
                
                setattr(client, field, new_value)
                changed[field] = {'old': str(old_value) if old_value else None, 'new': str(new_value) if new_value else None}

        # Save client (validation will run)
        client.is_edit_pending = False
        client.last_edited_by = reviewer
        client.last_edited_date = timezone.now()
        client.save()

        # Mark request approved
        self.status = self.STATUS_APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_comment = comment or ""
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_comment'])

        # Audit log
        ClientAuditLog.objects.create(
            client=client,
            action=ClientAuditLog.ACTION_APPROVE_EDIT,
            changed_data=changed,
            performed_by=reviewer,
            note=f"EditRequest approved. {comment or ''}"
        )
        
        return True

    def reject(self, reviewer: User, comment: str = ""):
        """Reject the request and keep client unchanged."""
        if self.status != self.STATUS_PENDING:
            raise ValueError("Only pending requests can be rejected.")
        
        self.status = self.STATUS_REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_comment = comment or ""
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_comment'])

        # Update client's edit pending status
        self.client.is_edit_pending = False
        self.client.save(update_fields=['is_edit_pending'])

        # Audit log
        ClientAuditLog.objects.create(
            client=self.client,
            action=ClientAuditLog.ACTION_REJECT_EDIT,
            changed_data=self.data,
            performed_by=reviewer,
            note=f"EditRequest rejected. {comment or ''}"
        )
        
        return True

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING

    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED

    @property
    def is_rejected(self):
        return self.status == self.STATUS_REJECTED


# ------------------------
# SavingsTransaction - UPDATED
# ------------------------
class SavingsTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
    ]

    client_account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE, related_name='savings_transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    transaction_date = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_savings')
    notes = models.TextField(blank=True)
    reference_number = models.CharField(max_length=50, blank=True, unique=True)
    is_reversed = models.BooleanField(default=False)
    reversed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reversed_transactions')
    reversal_date = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-transaction_date']
        verbose_name = 'Savings Transaction'
        verbose_name_plural = 'Savings Transactions'

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.client_account.account_number}"

    def generate_reference(self):
        """Generate unique reference number"""
        date_str = timezone.now().strftime("%Y%m%d")
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"SAV-{date_str}-{random_str}"

    def save(self, *args, **kwargs):
        # Generate reference number if not exists
        if not self.reference_number and not self.is_reversed:
            self.reference_number = self.generate_reference()
        
        # Validate amount
        try:
            amount = Decimal(str(self.amount))
        except (InvalidOperation, TypeError):
            raise ValidationError("Invalid amount for SavingsTransaction.")

        if amount <= 0:
            raise ValidationError("Transaction amount must be greater than zero.")

        # For new transactions (not reversals)
        if not self.pk and not self.is_reversed:
            # Enforce withdrawal limit and update balance atomically
            with transaction.atomic():
                # Lock the row to prevent concurrent updates
                client = ClientAccount.objects.select_for_update().get(pk=self.client_account.pk)

                if self.transaction_type == 'WITHDRAWAL' and amount > client.savings_balance:
                    raise ValidationError("Insufficient balance for withdrawal.")

                # Save transaction first
                super().save(*args, **kwargs)

                # Apply balance change
                if self.transaction_type == 'DEPOSIT':
                    client.savings_balance = (client.savings_balance or Decimal('0.00')) + amount
                    client.total_savings_deposited = (client.total_savings_deposited or Decimal('0.00')) + amount
                else:  # WITHDRAWAL
                    client.savings_balance = client.savings_balance - amount

                client.last_savings_date = timezone.now()
                client.save(update_fields=['savings_balance', 'total_savings_deposited', 'last_savings_date'])

                # Audit log for savings operation
                ClientAuditLog.objects.create(
                    client=client,
                    action=ClientAuditLog.ACTION_SAVINGS_TX,
                    changed_data={
                        'transaction_type': self.transaction_type,
                        'amount': str(amount),
                        'balance_after': str(client.savings_balance),
                        'reference': self.reference_number
                    },
                    performed_by=self.processed_by,
                    note=f"Savings {self.transaction_type} of {amount}. Notes: {self.notes}"
                )
        else:
            # For existing transactions (like reversals)
            super().save(*args, **kwargs)

    def reverse_transaction(self, reversed_by_user, reason=""):
        """Reverse this transaction"""
        if self.is_reversed:
            raise ValidationError("Transaction already reversed.")
        
        with transaction.atomic():
            # Lock client
            client = ClientAccount.objects.select_for_update().get(pk=self.client_account.pk)
            
            # Reverse the balance change
            if self.transaction_type == 'DEPOSIT':
                if self.amount > client.savings_balance:
                    raise ValidationError("Cannot reverse deposit: insufficient balance.")
                client.savings_balance -= self.amount
            else:  # WITHDRAWAL
                client.savings_balance += self.amount
            
            client.save(update_fields=['savings_balance'])
            
            # Mark transaction as reversed
            self.is_reversed = True
            self.reversed_by = reversed_by_user
            self.reversal_date = timezone.now()
            self.reversal_reason = reason
            self.save(update_fields=['is_reversed', 'reversed_by', 'reversal_date', 'reversal_reason'])
            
            # Create reversal audit log
            ClientAuditLog.objects.create(
                client=client,
                action=ClientAuditLog.ACTION_SAVINGS_TX,
                changed_data={
                    'action': 'REVERSAL',
                    'original_transaction': str(self.id),
                    'amount': str(self.amount),
                    'balance_after': str(client.savings_balance)
                },
                performed_by=reversed_by_user,
                note=f"Transaction {self.reference_number} reversed. Reason: {reason}"
            )
        
        return True

    @property
    def formatted_amount(self):
        """Return formatted amount with sign"""
        if self.transaction_type == 'DEPOSIT':
            return f"+{self.amount}"
        else:
            return f"-{self.amount}"

    @property
    def transaction_status(self):
        """Return transaction status"""
        if self.is_reversed:
            return "Reversed"
        return "Completed"
    

    @property
    def balance_after(self):
        """Calculate balance after this transaction"""
        # You might want to store this in the model or calculate differently
        # This is a simplified version
        if self.transaction_type == 'DEPOSIT':
            return self.client_account.savings_balance
        else:  # WITHDRAWAL
            return self.client_account.savings_balance + self.amount