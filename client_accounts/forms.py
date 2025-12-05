from django import forms
from .models import ClientAccount, SavingsTransaction, ClientEditRequest
from django.core.exceptions import ValidationError
from decimal import Decimal

class ClientAccountForm(forms.ModelForm):
    """Form for creating/editing client accounts"""
    
    class Meta:
        model = ClientAccount
        fields = [
            'account_type',
            'person1_first_name', 'person1_last_name', 'person1_contact',
            'person1_address', 'person1_area_code', 'person1_next_of_kin',
            'person1_nin', 'person1_gender',
            'person2_client',  # For linking to existing client
            'person2_first_name', 'person2_last_name', 'person2_contact',
            'person2_address', 'person2_area_code', 'person2_next_of_kin',
            'person2_nin', 'person2_gender',
            'business_location', 'business_sector',
        ]
        widgets = {
            'person1_address': forms.Textarea(attrs={'rows': 3}),
            'person2_address': forms.Textarea(attrs={'rows': 3}),
            'person1_gender': forms.RadioSelect(),
            'person2_gender': forms.RadioSelect(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make person2_client queryset only show active accounts
        self.fields['person2_client'].queryset = ClientAccount.objects.filter(
            account_status=ClientAccount.STATUS_ACTIVE
        )
        # Add CSS classes
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
    
    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get('account_type')
        
        if account_type == 'JOINT':
            person2_client = cleaned_data.get('person2_client')
            person2_nin = cleaned_data.get('person2_nin')
            
            # Check: either link to existing client OR provide details
            if not person2_client and not person2_nin:
                raise ValidationError({
                    'person2_nin': 'For joint accounts, either link to an existing client or provide Person 2 NIN.'
                })
        
        return cleaned_data


class SavingsTransactionForm(forms.ModelForm):
    """Form for savings transactions"""
    
    account_number = forms.CharField(
        max_length=30,
        required=True,
        help_text="Enter account number"
    )
    
    class Meta:
        model = SavingsTransaction
        fields = ['transaction_type', 'amount', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
            'transaction_type': forms.RadioSelect(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return amount
    
    def clean(self):
        cleaned_data = super().clean()
        account_number = cleaned_data.get('account_number')
        transaction_type = cleaned_data.get('transaction_type')
        amount = cleaned_data.get('amount')
        
        if account_number:
            try:
                account = ClientAccount.objects.get(account_number=account_number)
                if transaction_type == 'WITHDRAWAL' and amount > account.savings_balance:
                    raise ValidationError({
                        'amount': f"Insufficient balance. Available: {account.savings_balance}"
                    })
            except ClientAccount.DoesNotExist:
                raise ValidationError({
                    'account_number': 'Account not found.'
                })
        
        return cleaned_data


class AccountStatusForm(forms.Form):
    """Form for changing account status"""
    new_status = forms.ChoiceField(
        choices=ClientAccount.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False,
        help_text="Optional reason for status change"
    )


class EditRequestForm(forms.ModelForm):
    """Form for creating edit requests"""
    
    class Meta:
        model = ClientEditRequest
        fields = ['data', 'review_comment']
        widgets = {
            'review_comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def clean_data(self):
        data = self.cleaned_data.get('data')
        if not isinstance(data, dict) or not data:
            raise ValidationError("Edit data must be a non-empty JSON object.")
        return data


class SearchForm(forms.Form):
    """Form for searching accounts"""
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, account number, or NIN...'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(ClientAccount.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )