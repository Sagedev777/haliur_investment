from django.contrib import admin
from django import forms
from django.contrib import messages
from .models import ClientAccount, SavingsTransaction

class ClientAccountForm(forms.ModelForm):
    class Meta:
        model = ClientAccount
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'loan_officer' in self.fields:
            del self.fields['loan_officer']

class SavingsTransactionForm(forms.ModelForm):
    class Meta:
        model = SavingsTransaction
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'processed_by' in self.fields:
            del self.fields['processed_by']

@admin.register(ClientAccount)
class ClientAccountAdmin(admin.ModelAdmin):
    form = ClientAccountForm
    list_display = ['account_number', 'full_account_name', 'account_type', 'savings_balance', 'is_approved', 'registration_date', 'loan_officer']
    list_filter = ['account_type', 'is_approved', 'registration_date']
    search_fields = ['account_number', 'person1_first_name', 'person1_last_name', 'person1_nin']
    readonly_fields = ['account_number', 'registration_date', 'display_loan_officer', 'savings_info', 'loan_eligibility_info']
    
    fieldsets = (
        ('Account Information', {
            'fields': ('account_type', 'account_number', 'is_approved', 'is_active')
        }),
        ('Primary Account Holder', {
            'fields': (
                'person1_first_name', 'person1_last_name', 'person1_contact',
                'person1_address', 'person1_area_code', 'person1_next_of_kin',
                'person1_photo', 'person1_signature', 'person1_nin', 'person1_gender'
            )
        }),
        ('Secondary Account Holder (Joint Accounts Only)', {
            'fields': (
                'person2_first_name', 'person2_last_name', 'person2_contact',
                'person2_address', 'person2_area_code', 'person2_next_of_kin',
                'person2_photo', 'person2_signature', 'person2_nin', 'person2_gender'
            ),
        }),
        ('Business Information', {
            'fields': ('business_location', 'business_sector')
        }),
        ('Savings Information', {
            'fields': ('savings_balance', 'last_savings_date', 'savings_info', 'loan_eligibility_info')
        }),
        ('System Information', {
            'fields': ('display_loan_officer', 'registration_date'),
            'classes': ('collapse',)
        }),
    )
    
    def display_loan_officer(self, obj):
        return f"{obj.loan_officer.get_full_name() or obj.loan_officer.username}"
    display_loan_officer.short_description = 'Loan Officer'
    
    def savings_info(self, obj):
        if obj.last_savings_date:
            return f"Last savings activity: {obj.last_savings_date.strftime('%Y-%m-%d')}"
        return "No savings activity yet"
    savings_info.short_description = 'Savings Activity'
    
    def loan_eligibility_info(self, obj):
        max_loan = obj.get_max_loan_amount()
        return f"Maximum loan eligibility: {max_loan} (based on 5x savings)"
    loan_eligibility_info.short_description = 'Loan Eligibility'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.loan_officer = request.user
        super().save_model(request, obj, form, change)

@admin.register(SavingsTransaction)
class SavingsTransactionAdmin(admin.ModelAdmin):
    form = SavingsTransactionForm
    list_display = ['client_account', 'transaction_type', 'amount', 'transaction_date', 'processed_by']
    list_filter = ['transaction_type', 'transaction_date']
    search_fields = ['client_account__account_number', 'client_account__person1_first_name']
    readonly_fields = ['transaction_date', 'display_processed_by']
    
    def display_processed_by(self, obj):
        return f"{obj.processed_by.get_full_name() or obj.processed_by.username}"
    display_processed_by.short_description = 'Processed By'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.processed_by = request.user
        super().save_model(request, obj, form, change)