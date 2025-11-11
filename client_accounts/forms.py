# client_accounts/forms.py
from django import forms
from .models import ClientAccount, SavingsTransaction

class ClientAccountForm(forms.ModelForm):
    class Meta:
        model = ClientAccount
        fields = [
            'account_type',
            'person1_first_name', 'person1_last_name', 'person1_contact',
            'person1_address', 'person1_area_code', 'person1_next_of_kin',
            'person1_photo', 'person1_signature', 'person1_nin', 'person1_gender',
            'person2_first_name', 'person2_last_name', 'person2_contact',
            'person2_address', 'person2_area_code', 'person2_next_of_kin',
            'person2_photo', 'person2_signature', 'person2_nin', 'person2_gender',
            'business_location', 'business_sector',
            'savings_balance', 'is_active', 'is_approved',
        ]
        widgets = {
            'account_type': forms.Select(attrs={'class': 'form-control'}),
            'person1_first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'person1_last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'person1_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'person1_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'person1_area_code': forms.TextInput(attrs={'class': 'form-control'}),
            'person1_next_of_kin': forms.TextInput(attrs={'class': 'form-control'}),
            'person1_photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'person1_signature': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'person1_nin': forms.TextInput(attrs={'class': 'form-control'}),
            'person1_gender': forms.Select(attrs={'class': 'form-control'}),
            
            'person2_first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'person2_last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'person2_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'person2_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'person2_area_code': forms.TextInput(attrs={'class': 'form-control'}),
            'person2_next_of_kin': forms.TextInput(attrs={'class': 'form-control'}),
            'person2_photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'person2_signature': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'person2_nin': forms.TextInput(attrs={'class': 'form-control'}),
            'person2_gender': forms.Select(attrs={'class': 'form-control'}),
            
            'business_location': forms.TextInput(attrs={'class': 'form-control'}),
            'business_sector': forms.TextInput(attrs={'class': 'form-control'}),
            'savings_balance': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_approved': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
