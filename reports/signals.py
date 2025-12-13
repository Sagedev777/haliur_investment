from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import models
from decimal import Decimal
import matplotlib.pyplot as plt
from io import BytesIO
from django.core.files.base import ContentFile
from .models import SystemReport
from client_accounts.models import ClientAccount, SavingsTransaction, Guarantor
from loans.models import LoanApplication, LoanPayment

@receiver(post_save, sender=User)
def auto_generate_daily_report(sender, instance, created, **kwargs):
    today = timezone.now().date()
    if SystemReport.objects.filter(report_date=today, report_type='DAILY').exists():
        return
    total_accounts = ClientAccount.objects.count()
    active_accounts = ClientAccount.objects.filter(is_active=True).count()
    total_savings = ClientAccount.objects.aggregate(total=models.Sum('savings_balance'))['total'] or Decimal('0')
    loans = LoanApplication.objects.all()
    total_loans_disbursed = loans.filter(status='DISBURSED').aggregate(total=models.Sum('loan_amount'))['total'] or Decimal('0')
    total_loans_pending = loans.filter(status='PENDING').count()
    total_loans_approved = loans.filter(status='APPROVED').count()
    total_loans_completed = loans.filter(status='COMPLETED').count()
    total_loans_defaulted = loans.filter(status='DEFAULTED').count()
    total_interest_earned = LoanPayment.objects.aggregate(total=models.Sum('payment_amount'))['total'] or Decimal('0')
    total_guarantors = Guarantor.objects.count()
    total_savings_transactions = SavingsTransaction.objects.count()
    total_loan_payments = LoanPayment.objects.count()
    total_transactions = total_savings_transactions + total_loan_payments
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = ['Pending', 'Approved', 'Completed', 'Defaulted']
    values = [total_loans_pending, total_loans_approved, total_loans_completed, total_loans_defaulted]
    colors = ['#FFA500', '#4CAF50', '#2196F3', '#F44336']
    ax.bar(labels, values, color=colors)
    ax.set_title('Loan Status Summary')
    ax.set_ylabel('Number of Loans')
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    buffer = BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    report = SystemReport.objects.create(report_type='DAILY', generated_by=instance, total_accounts=total_accounts, active_accounts=active_accounts, total_savings=total_savings, total_loans_disbursed=total_loans_disbursed, total_loans_pending=total_loans_pending, total_loans_approved=total_loans_approved, total_loans_completed=total_loans_completed, total_loans_defaulted=total_loans_defaulted, total_interest_earned=total_interest_earned, total_guarantors=total_guarantors, total_transactions=total_transactions)
    report.chart_image.save(f'report_{today}.png', ContentFile(buffer.getvalue()))
    buffer.close()