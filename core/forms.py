from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from client_accounts.models import UserProfile

class StaffCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=True, label="Role")

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        # Set is_staff status for relevant roles
        role = self.cleaned_data['role']
        if role in [UserProfile.ROLE_ADMIN, UserProfile.ROLE_MANAGER, UserProfile.ROLE_STAFF, UserProfile.ROLE_ACCOUNTANT, UserProfile.ROLE_LOAN_OFFICER]:
            user.is_staff = True
        
        if commit:
            user.save()
            # Create or update UserProfile
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'role': role}
            )
        return user
