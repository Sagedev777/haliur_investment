# forms.py
from django import forms
from .models import ClientAccount

class ClientAccountForm(forms.ModelForm):
    class Meta:
        model = ClientAccount
        fields = [
            'account_type',
            'person1_first_name', 'person1_last_name', 'person1_contact', 'person1_address',
            'person1_area_code', 'person1_next_of_kin', 'person1_gender', 'person1_nin',
            'person2_first_name', 'person2_last_name', 'person2_contact', 'person2_address',
            'person2_area_code', 'person2_next_of_kin', 'person2_nin', 'person2_gender',
            'business_location', 'business_sector',
        ]
        widgets = {
            'account_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'account-type',
                'onchange': 'toggleAccountType()'
            }),
            # Person 1 fields
            'person1_first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'person1_last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'person1_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'person1_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'person1_area_code': forms.TextInput(attrs={'class': 'form-control'}),
            'person1_next_of_kin': forms.TextInput(attrs={'class': 'form-control'}),
            'person1_gender': forms.Select(attrs={'class': 'form-control'}),
            'person1_nin': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Person 2 fields - with person2-field class for JavaScript control
            'person2_first_name': forms.TextInput(attrs={'class': 'form-control person2-field'}),
            'person2_last_name': forms.TextInput(attrs={'class': 'form-control person2-field'}),
            'person2_contact': forms.TextInput(attrs={'class': 'form-control person2-field'}),
            'person2_address': forms.Textarea(attrs={'class': 'form-control person2-field', 'rows': 3}),
            'person2_area_code': forms.TextInput(attrs={'class': 'form-control person2-field'}),
            'person2_next_of_kin': forms.TextInput(attrs={'class': 'form-control person2-field'}),
            'person2_nin': forms.TextInput(attrs={'class': 'form-control person2-field'}),
            'person2_gender': forms.Select(attrs={'class': 'form-control person2-field'}),
            
            # Business fields
            'business_location': forms.TextInput(attrs={'class': 'form-control'}),
            'business_sector': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make business fields required
        self.fields['business_location'].required = True
        self.fields['business_sector'].required = True
        # Make person1 NIN required (based on your error)
        self.fields['person1_nin'].required = True
        self.fields['person1_gender'].required = True

    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get('account_type')

        # For SINGLE accounts, ensure person2 fields are empty
        if account_type == 'SINGLE':
            person2_fields = [
                'person2_first_name', 'person2_last_name', 'person2_contact',
                'person2_address', 'person2_area_code', 'person2_next_of_kin',
                'person2_nin', 'person2_gender'
            ]
            for field in person2_fields:
                if cleaned_data.get(field):
                    self.add_error(field, 'This field should be empty for single accounts.')

        # For JOINT accounts, make person2 fields required
        elif account_type == 'JOINT':
            required_fields = [
                'person2_first_name', 'person2_last_name', 'person2_contact',
                'person2_address', 'person2_area_code', 'person2_next_of_kin',
                'person2_nin', 'person2_gender'
            ]
            for field in required_fields:
                if not cleaned_data.get(field):
                    self.add_error(field, 'This field is required for joint accounts.')

        return cleaned_data