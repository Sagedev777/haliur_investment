from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import random
import string

# NOTE: adjust import if using older Django where JSONField lives in contrib.postgres
# from django.contrib.postgres.fields import JSONField  # older versions
# For modern Django (3.1+):
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

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    # convenience properties
    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN or self.user.is_superuser

    @property
    def is_staff_role(self):
        return self.role == self.ROLE_STAFF or self.user.is_staff

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER

    @property
    def is_accountant(self):
        return self.role == self.ROLE_ACCOUNTANT

    @property
    def is_loan_officer(self):
        return self.role == self.ROLE_LOAN_OFFICER


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

    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_EDIT_REQUEST, 'Edit Request Submitted'),
        (ACTION_APPROVE_EDIT, 'Edit Request Approved'),
        (ACTION_REJECT_EDIT, 'Edit Request Rejected'),
        (ACTION_SAVINGS_TX, 'Savings Transaction'),
    ]

    client = models.ForeignKey('ClientAccount', on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    changed_data = JSONField(blank=True, null=True)  # stores {field: {'old': x, 'new': y}, ...}
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Audit: {self.client.account_number} - {self.get_action_display()} @ {self.timestamp}"


# ------------------------
# Client Edit Request (soft workflow)
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

    client = models.ForeignKey('ClientAccount', on_delete=models.CASCADE, related_name='edit_requests')
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

    def __str__(self):
        return f"EditRequest({self.client.account_number}) by {self.requested_by} [{self.status}]"

    def approve(self, reviewer: User, comment: str = ""):
        """Apply the changes to the client account, create audit log, and mark approved."""
        if self.status != self.STATUS_PENDING:
            raise ValueError("Only pending requests can be approved.")

        client = self.client
        changed = {}
        # apply changes field-by-field
        for field, new_value in (self.data or {}).items():
            old_value = getattr(client, field, None)
            # attempt type-correct assignment; keep as-is for simplicity
            setattr(client, field, new_value)
            changed[field] = {'old': old_value, 'new': new_value}

        # save client (note: we expect calling code to enforce permissions)
        # use save() which runs validation
        client.is_edit_pending = False
        client.save()

        # mark request approved
        self.status = self.STATUS_APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_comment = comment or ""
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_comment'])

        # audit log
        ClientAuditLog.objects.create(
            client=client,
            action=ClientAuditLog.ACTION_APPROVE_EDIT,
            changed_data=changed,
            performed_by=reviewer,
            note=f"EditRequest approved. {comment or ''}"
        )

    def reject(self, reviewer: User, comment: str = ""):
        """Reject the request and keep client unchanged."""
        if self.status != self.STATUS_PENDING:
            raise ValueError("Only pending requests can be rejected.")
        self.status = self.STATUS_REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_comment = comment or ""
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_comment'])

        # audit log
        ClientAuditLog.objects.create(
            client=self.client,
            action=ClientAuditLog.ACTION_REJECT_EDIT,
            changed_data=self.data,
            performed_by=reviewer,
            note=f"EditRequest rejected. {comment or ''}"
        )


# ------------------------
# ClientAccount
# ------------------------
class ClientAccount(models.Model):
    ACCOUNT_TYPES = [
        ('SINGLE', 'Single Account'),
        ('JOINT', 'Joint Account'),
    ]

    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    # Account Identification
    account_number = models.CharField(max_length=30, unique=True, blank=True)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)

    # Person 1 Information (Required for all accounts)
    person1_first_name = models.CharField(max_length=100)
    person1_last_name = models.CharField(max_length=100)
    person1_contact = models.CharField(max_length=20)
    person1_address = models.TextField()
    person1_area_code = models.CharField(max_length=10)
    person1_next_of_kin = models.CharField(max_length=100)
    person1_photo = models.ImageField(upload_to='photos/', blank=True, null=True)
    person1_signature = models.ImageField(upload_to='signatures/', blank=True, null=True)
    person1_nin = models.CharField(max_length=20, unique=True)
    person1_gender = models.CharField(max_length=1, choices=GENDER_CHOICES)

    # Person 2 Information (Required only for joint accounts)
    person2_first_name = models.CharField(max_length=100, blank=True, null=True)
    person2_last_name = models.CharField(max_length=100, blank=True, null=True)
    person2_contact = models.CharField(max_length=20, blank=True, null=True)
    person2_address = models.TextField(blank=True, null=True)
    person2_area_code = models.CharField(max_length=10, blank=True, null=True)
    person2_next_of_kin = models.CharField(max_length=100, blank=True, null=True)
    person2_photo = models.ImageField(upload_to='photos/', blank=True, null=True)
    person2_signature = models.ImageField(upload_to='signatures/', blank=True, null=True)
    person2_nin = models.CharField(max_length=20, blank=True, null=True, unique=True)
    person2_gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)

    # Business Information
    business_location = models.CharField(max_length=100)
    business_sector = models.CharField(max_length=100)

    # Savings Information
    savings_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    last_savings_date = models.DateTimeField(null=True, blank=True)

    # System Fields
    registration_date = models.DateTimeField(auto_now_add=True)
    loan_officer = models.ForeignKey(User, on_delete=models.CASCADE, editable=False, related_name='client_accounts')
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=True)

    # Soft-edit workflow fields
    is_edit_pending = models.BooleanField(default=False)

    class Meta:
        ordering = ['-registration_date']
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['person1_nin']),
        ]

    def generate_account_number(self):
        """Generate HIL25YYYYXXXXXXX format account number"""
        year = timezone.now().year
        random_digits = ''.join(random.choices(string.digits, k=7))
        return f"HIL25{year}{random_digits}"

    def can_take_loan(self, loan_amount):
        """Check if customer can take a loan based on savings"""
        required_savings = Decimal(loan_amount) * Decimal('0.2')
        return self.savings_balance >= required_savings

    def get_max_loan_amount(self):
        """Calculate maximum loan amount based on savings"""
        return self.savings_balance * Decimal('5')

    def clean(self):
        """Validate business rules"""
        super().clean()

        # Check if this is a joint account
        if self.account_type == 'JOINT':
            if not self.person2_nin:
                raise ValidationError({'person2_nin': 'NIN is required for joint accounts.'})

            existing_person2 = ClientAccount.objects.filter(
                models.Q(person1_nin=self.person2_nin) | models.Q(person2_nin=self.person2_nin)
            ).exclude(pk=self.pk)

            if existing_person2.exists():
                existing_account = existing_person2.first()
                if not existing_account.is_approved:
                    raise ValidationError({
                        'person2_nin': f'Person with NIN {self.person2_nin} exists but their account is not approved.'
                    })
            else:
                if not all([self.person2_first_name, self.person2_last_name, self.person2_contact,
                           self.person2_address, self.person2_nin]):
                    raise ValidationError({
                        'person2_first_name': 'All Person 2 details are required for new joint account members.'
                    })

        if self.person1_nin and self.is_active:
            existing_person1 = ClientAccount.objects.filter(
                models.Q(person1_nin=self.person1_nin) | models.Q(person2_nin=self.person1_nin),
                is_active=True
            ).exclude(pk=self.pk)

            if existing_person1.exists():
                raise ValidationError({
                    'person1_nin': f'Person with NIN {self.person1_nin} already has an active account.'
                })

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = self.generate_account_number()

        # Full clean before saving (keeps your existing validation)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.account_type == 'SINGLE':
            return f"{self.account_number} - {self.person1_first_name} {self.person1_last_name}"
        else:
            return f"{self.account_number} - {self.person1_first_name} & {self.person2_first_name or '—'}"

    @property
    def full_account_name(self):
        if self.account_type == 'SINGLE':
            return f"{self.person1_first_name} {self.person1_last_name}"
        else:
            return f"{self.person1_first_name} {self.person1_last_name} & {self.person2_first_name} {self.person2_last_name or ''}"

    @property
    def can_create_joint_account(self):
        return self.is_active and self.is_approved

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
        # audit log
        ClientAuditLog.objects.create(
            client=self,
            action=ClientAuditLog.ACTION_EDIT_REQUEST,
            changed_data=changes,
            performed_by=requested_by,
            note="Edit request submitted"
        )
        return req


# ------------------------
# SavingsTransaction
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

    class Meta:
        ordering = ['-transaction_date']

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.client_account.account_number}"

    def save(self, *args, **kwargs):
        # Validate amount
        try:
            amount = Decimal(self.amount)
        except (InvalidOperation, TypeError):
            raise ValidationError("Invalid amount for SavingsTransaction.")

        if amount <= 0:
            raise ValidationError("Transaction amount must be greater than zero.")

        # Enforce withdrawal limit and update balance atomically
        with transaction.atomic():
            # lock the row to prevent concurrent updates
            client = ClientAccount.objects.select_for_update().get(pk=self.client_account.pk)

            if self.transaction_type == 'WITHDRAWAL' and amount > client.savings_balance:
                raise ValidationError("Insufficient balance for withdrawal.")

            # Save transaction first (so there's a record even if balance adjustment fails)
            super().save(*args, **kwargs)

            # Apply balance change
            if self.transaction_type == 'DEPOSIT':
                client.savings_balance = (client.savings_balance or Decimal('0.00')) + amount
            else:
                client.savings_balance = client.savings_balance - amount

            client.last_savings_date = timezone.now()
            client.save(update_fields=['savings_balance', 'last_savings_date'])

            # Audit log for savings operation
            ClientAuditLog.objects.create(
                client=client,
                action=ClientAuditLog.ACTION_SAVINGS_TX,
                changed_data={
                    'transaction_type': self.transaction_type,
                    'amount': str(amount),
                    'balance_after': str(client.savings_balance)
                },
                performed_by=self.processed_by,
                note=f"Savings {self.transaction_type} of {amount}"
            )
