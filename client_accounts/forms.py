# forms.py
from django import forms
from .models import ClientAccount

class ClientAccountForm(forms.ModelForm):
    class Meta:
        model = ClientAccount
        fields = [
            'account_type',
            'person1_first_name', 'person1_last_name', 'person1_contact', 'person1_address',
            'person1_area_code', 'person1_next_of_kin', 'person1_gender',
            'person2_first_name', 'person2_last_name', 'person2_contact', 'person2_address',
            'person2_area_code', 'person2_next_of_kin', 'person2_nin', 'person2_gender',
            'business_location', 'business_sector',
        ]

    def clean(self):
        cleaned_data = super().clean()
        account_type = cleaned_data.get('account_type')

        # Make person2 fields required only for joint accounts
        if account_type == 'JOINT':
            required_fields = [
                'person2_first_name', 'person2_last_name', 'person2_contact',
                'person2_address', 'person2_area_code', 'person2_next_of_kin',
                'person2_nin', 'person2_gender'
            ]
            for field in required_fields:
                if not cleaned_data.get(field):
                    self.add_error(field, 'This field is required for joint accounts.')
        return cleaned_data
