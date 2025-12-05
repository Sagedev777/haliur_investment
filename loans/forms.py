from django import forms
from .models import LoanProduct, LoanApplication, Guarantor, LoanPayment

# forms.py
from django import forms
from .models import LoanProduct, LoanApplication, Guarantor, LoanPayment
from django.utils import timezone

class LoanApplicationForm(forms.ModelForm):
    class Meta:
        model = LoanApplication
        # Only include fields that should be visible during application
        fields = [
            'client_account',
            'loan_product',
            'loan_amount',
            'collateral_description',
            'collateral_value',
            'collateral_images',
            'guarantor'
        ]
        widgets = {
            'collateral_description': forms.Textarea(attrs={'rows': 3}),
            'loan_amount': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'collateral_value': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the current user as the loan officer automatically
        self.fields['client_account'].label = "Select Client"
        self.fields['loan_product'].label = "Select Loan Product"
        self.fields['loan_amount'].label = "Loan Amount (UGX)"
        self.fields['collateral_value'].label = "Collateral Value (UGX)"
        self.fields['collateral_description'].label = "Collateral Description"
        self.fields['collateral_images'].label = "Collateral Images (Optional)"
        self.fields['guarantor'].label = "Select Guarantor"
        
        # You can also filter querysets if needed
        # self.fields['client_account'].queryset = ClientAccount.objects.filter(is_approved=True)
        # self.fields['loan_product'].queryset = LoanProduct.objects.filter(is_active=True)


class AdminLoanApplicationForm(forms.ModelForm):
    """Form for admin/staff to edit all fields"""
    class Meta:
        model = LoanApplication
        fields = '__all__'
        widgets = {
            'rejection_reason': forms.Textarea(attrs={'rows': 3}),
            'disbursement_notes': forms.Textarea(attrs={'rows': 3}),
        }

class LoanProductForm(forms.ModelForm):
    class Meta:
        model = LoanProduct
        fields = '__all__'

class GuarantorForm(forms.ModelForm):
    class Meta:
        model = Guarantor
        fields = '__all__'

class LoanPaymentForm(forms.ModelForm):
    class Meta:
        model = LoanPayment
        fields = '__all__'

def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make number_of_installments readonly in the form
        self.fields['number_of_installments'].widget.attrs['readonly'] = True