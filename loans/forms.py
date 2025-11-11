from django import forms
from .models import LoanProduct, LoanApplication, Guarantor, LoanPayment

class LoanProductForm(forms.ModelForm):
    class Meta:
        model = LoanProduct
        fields = '__all__'

class LoanApplicationForm(forms.ModelForm):
    class Meta:
        model = LoanApplication
        fields = '__all__'

class GuarantorForm(forms.ModelForm):
    class Meta:
        model = Guarantor
        fields = '__all__'

class LoanPaymentForm(forms.ModelForm):
    class Meta:
        model = LoanPayment
        fields = '__all__'
