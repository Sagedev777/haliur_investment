from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import random
import string
from django.utils import timezone
from decimal import Decimal

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
    account_number = models.CharField(max_length=20, unique=True, blank=True)
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
    savings_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_savings_date = models.DateTimeField(null=True, blank=True)
    
    # System Fields
    registration_date = models.DateTimeField(auto_now_add=True)
    loan_officer = models.ForeignKey(User, on_delete=models.CASCADE, editable=False)
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=True)
    
    def generate_account_number(self):
        """Generate HIL25YYYYXXXXXXX format account number"""
        year = timezone.now().year
        random_digits = ''.join(random.choices(string.digits, k=7))
        return f"HIL25{year}{random_digits}"
    
    def can_take_loan(self, loan_amount):
        """Check if customer can take a loan based on savings"""
        required_savings = loan_amount * Decimal('0.2')
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
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.account_type == 'SINGLE':
            return f"{self.account_number} - {self.person1_first_name} {self.person1_last_name}"
        else:
            return f"{self.account_number} - {self.person1_first_name} & {self.person2_first_name}"

    @property
    def full_account_name(self):
        if self.account_type == 'SINGLE':
            return f"{self.person1_first_name} {self.person1_last_name}"
        else:
            return f"{self.person1_first_name} {self.person1_last_name} & {self.person2_first_name} {self.person2_last_name}"
    
    @property
    def can_create_joint_account(self):
        return self.is_active and self.is_approved

class SavingsTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
    ]
    
    client_account = models.ForeignKey(ClientAccount, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_date = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    notes = models.TextField(blank=True)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        if self.transaction_type == 'DEPOSIT':
            self.client_account.savings_balance += self.amount
        else:
            self.client_account.savings_balance -= self.amount
        
        self.client_account.last_savings_date = timezone.now()
        self.client_account.save()
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.client_account.account_number}"