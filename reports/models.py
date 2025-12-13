from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
import os

def report_chart_path(instance, filename):
    return os.path.join('reports', instance.report_type.lower(), str(instance.report_date), filename)

class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    extra_info = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f'{self.user.username} - {self.action} ({self.timestamp})'

class SystemReport(models.Model):
    REPORT_TYPES = [('DAILY', 'Daily Report'), ('WEEKLY', 'Weekly Report'), ('MONTHLY', 'Monthly Report'), ('YEARLY', 'Yearly Report')]
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    report_date = models.DateField(default=timezone.now)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    total_accounts = models.IntegerField(default=0)
    active_accounts = models.IntegerField(default=0)
    total_savings = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_loans_disbursed = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_loans_pending = models.IntegerField(default=0)
    total_loans_approved = models.IntegerField(default=0)
    total_loans_completed = models.IntegerField(default=0)
    total_loans_defaulted = models.IntegerField(default=0)
    total_interest_earned = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    staff_loan_counts = models.JSONField(default=dict)
    staff_savings_counts = models.JSONField(default=dict)
    chart_image = models.ImageField(upload_to=report_chart_path, null=True, blank=True)
    pdf_file = models.FileField(upload_to='reports/pdfs/', null=True, blank=True)
    total_guarantors = models.IntegerField(default=0)
    total_transactions = models.IntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-report_date', '-generated_at']
        verbose_name = 'System Report'
        verbose_name_plural = 'System Reports'

    def __str__(self):
        return f'{self.get_report_type_display()} - {self.report_date}'

    def summary_dict(self):
        return {'total_accounts': self.total_accounts, 'active_accounts': self.active_accounts, 'total_savings': float(self.total_savings), 'total_loans_disbursed': float(self.total_loans_disbursed), 'total_loans_pending': self.total_loans_pending, 'total_loans_approved': self.total_loans_approved, 'total_loans_completed': self.total_loans_completed, 'total_loans_defaulted': self.total_loans_defaulted, 'total_interest_earned': float(self.total_interest_earned), 'total_guarantors': self.total_guarantors, 'total_transactions': self.total_transactions}