from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, ClientAccount, SavingsTransaction, ClientAuditLog, ClientEditRequest


# ------------------------
# Inline admin for UserProfile
# ------------------------
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'
    fk_name = 'user'


# ------------------------
# Custom User Admin
# ------------------------
class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super(CustomUserAdmin, self).get_inline_instances(request, obj)


# ------------------------
# ClientAccount Admin
# ------------------------
class ClientAccountAdmin(admin.ModelAdmin):
    list_display = [
        'account_number', 
        'account_type', 
        'full_account_name',
        'account_status',  # Changed from is_approved
        'savings_balance',
        'loan_officer',
        'registration_date'
    ]
    
    list_filter = [
        'account_type', 
        'account_status',  # Changed from is_approved
        'loan_officer',
        'registration_date'
    ]
    
    search_fields = [
        'account_number',
        'person1_first_name',
        'person1_last_name',
        'person1_nin',
        'person2_first_name',
        'person2_last_name',
        'person2_nin'
    ]
    
    readonly_fields = [
        'account_number',
        'registration_date',
        'created_by',
        'approved_by',
        'approval_date',
        'last_edited_by',
        'last_edited_date',
        'last_savings_date'
    ]
    
    fieldsets = (
        ('Account Information', {
            'fields': ('account_number', 'account_type', 'account_status', 'loan_officer')
        }),
        ('Primary Account Holder', {
            'fields': (
                'person1_first_name', 'person1_last_name', 'person1_contact',
                'person1_address', 'person1_area_code', 'person1_next_of_kin',
                'person1_nin', 'person1_gender', 'person1_photo', 'person1_signature'
            )
        }),
        ('Secondary Account Holder (Joint Accounts)', {
            'fields': (
                'person2_client',
                'person2_first_name', 'person2_last_name', 'person2_contact',
                'person2_address', 'person2_area_code', 'person2_next_of_kin',
                'person2_nin', 'person2_gender', 'person2_photo', 'person2_signature'
            ),
            'classes': ('collapse',)
        }),
        ('Business Information', {
            'fields': ('business_location', 'business_sector')
        }),
        ('Savings Information', {
            'fields': ('savings_balance', 'total_savings_deposited', 'last_savings_date')
        }),
        ('System Information', {
            'fields': (
                'registration_date', 'created_by', 'approved_by', 'approval_date',
                'last_edited_by', 'last_edited_date', 'is_edit_pending'
            ),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # If creating a new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ------------------------
# SavingsTransaction Admin
# ------------------------
class SavingsTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'reference_number',
        'client_account',
        'transaction_type',
        'amount',
        'transaction_date',
        'processed_by',
        'is_reversed'
    ]
    
    list_filter = [
        'transaction_type',
        'is_reversed',
        'transaction_date'
    ]
    
    search_fields = [
        'reference_number',
        'client_account__account_number',
        'client_account__person1_first_name',
        'client_account__person1_last_name'
    ]
    
    readonly_fields = [
        'reference_number',
        'transaction_date',
        'is_reversed',
        'reversed_by',
        'reversal_date',
        'reversal_reason'
    ]
    
    fieldsets = (
        ('Transaction Details', {
            'fields': (
                'reference_number', 'client_account', 'transaction_type', 
                'amount', 'transaction_date', 'processed_by', 'notes'
            )
        }),
        ('Reversal Information', {
            'fields': (
                'is_reversed', 'reversed_by', 'reversal_date', 'reversal_reason'
            ),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.processed_by:
            obj.processed_by = request.user
        super().save_model(request, obj, form, change)


# ------------------------
# ClientEditRequest Admin
# ------------------------
class ClientEditRequestAdmin(admin.ModelAdmin):
    list_display = [
        'client',
        'requested_by',
        'status',
        'created_at',
        'reviewed_by',
        'reviewed_at'
    ]
    
    list_filter = [
        'status',
        'created_at'
    ]
    
    search_fields = [
        'client__account_number',
        'client__person1_first_name',
        'client__person1_last_name',
        'requested_by__username'
    ]
    
    readonly_fields = [
        'created_at',
        'reviewed_at'
    ]
    
    fieldsets = (
        ('Request Information', {
            'fields': ('client', 'requested_by', 'status', 'created_at')
        }),
        ('Change Details', {
            'fields': ('data',)
        }),
        ('Review Information', {
            'fields': ('reviewed_by', 'reviewed_at', 'review_comment')
        })
    )
    
    actions = ['approve_selected_requests', 'reject_selected_requests']
    
    def approve_selected_requests(self, request, queryset):
        for edit_request in queryset.filter(status=ClientEditRequest.STATUS_PENDING):
            try:
                edit_request.approve(request.user, "Approved via admin action")
            except Exception as e:
                self.message_user(request, f"Failed to approve {edit_request}: {str(e)}", level='error')
        self.message_user(request, f"{queryset.count()} edit requests approved.")
    approve_selected_requests.short_description = "Approve selected edit requests"
    
    def reject_selected_requests(self, request, queryset):
        for edit_request in queryset.filter(status=ClientEditRequest.STATUS_PENDING):
            try:
                edit_request.reject(request.user, "Rejected via admin action")
            except Exception as e:
                self.message_user(request, f"Failed to reject {edit_request}: {str(e)}", level='error')
        self.message_user(request, f"{queryset.count()} edit requests rejected.")
    reject_selected_requests.short_description = "Reject selected edit requests"


# ------------------------
# ClientAuditLog Admin
# ------------------------
class ClientAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'client',
        'action',
        'performed_by',
        'timestamp'
    ]
    
    list_filter = [
        'action',
        'timestamp'
    ]
    
    search_fields = [
        'client__account_number',
        'client__person1_first_name',
        'client__person1_last_name',
        'performed_by__username',
        'note'
    ]
    
    readonly_fields = [
        'client',
        'action',
        'changed_data',
        'performed_by',
        'timestamp',
        'note'
    ]
    
    fieldsets = (
        ('Audit Information', {
            'fields': ('client', 'action', 'timestamp', 'performed_by')
        }),
        ('Details', {
            'fields': ('changed_data', 'note')
        })
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ------------------------
# Register models
# ------------------------

# Unregister the default User admin and register with custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Register other models
admin.site.register(ClientAccount, ClientAccountAdmin)
admin.site.register(SavingsTransaction, SavingsTransactionAdmin)
admin.site.register(ClientEditRequest, ClientEditRequestAdmin)
admin.site.register(ClientAuditLog, ClientAuditLogAdmin)
admin.site.register(UserProfile)