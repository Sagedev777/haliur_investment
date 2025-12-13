from .models import SystemReport, ActivityLog
from client_accounts.models import ClientAccount, SavingsTransaction
from loans.models import LoanApplication, LoanPayment, Guarantor
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
import matplotlib.pyplot as plt
import io
from django.core.files.base import ContentFile
from django.db import models

def generate_periodic_report(user=None, period='DAILY'):
    today = timezone.now().date()
    if period == 'DAILY':
        start_date = today
    elif period == 'WEEKLY':
        start_date = today - timezone.timedelta(days=today.weekday())
    elif period == 'MONTHLY':
        start_date = today.replace(day=1)
    elif period == 'YEARLY':
        start_date = today.replace(month=1, day=1)
    else:
        start_date = today
    accounts = ClientAccount.objects.all()
    loans = LoanApplication.objects.all()
    total_savings = accounts.aggregate(total=models.Sum('savings_balance'))['total'] or Decimal('0')
    total_loans_disbursed = loans.filter(status='DISBURSED').aggregate(total=models.Sum('loan_amount'))['total'] or Decimal('0')
    total_loans_pending = loans.filter(status='PENDING').count()
    total_loans_approved = loans.filter(status='APPROVED').count()
    total_loans_completed = loans.filter(status='COMPLETED').count()
    total_loans_defaulted = loans.filter(status='DEFAULTED').count()
    total_interest_earned = LoanPayment.objects.filter(payment_date__gte=start_date).aggregate(total=models.Sum('payment_amount'))['total'] or Decimal('0')
    total_guarantors = Guarantor.objects.count()
    total_savings_transactions = SavingsTransaction.objects.filter(transaction_date__gte=start_date).count()
    total_loan_payments = LoanPayment.objects.filter(payment_date__gte=start_date).count()
    total_transactions = total_savings_transactions + total_loan_payments
    staff_loan_counts = {str(u.id): loans.filter(loan_officer=u).count() for u in User.objects.all()}
    staff_savings_counts = {str(u.id): SavingsTransaction.objects.filter(processed_by=u).count() for u in User.objects.all()}
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(staff_loan_counts.keys(), staff_loan_counts.values(), label='Loans', color='#4CAF50')
    ax.bar(staff_savings_counts.keys(), staff_savings_counts.values(), bottom=list(staff_loan_counts.values()), label='Savings', color='#2196F3')
    ax.set_xlabel('Staff ID')
    ax.set_ylabel('Count')
    ax.set_title(f'{period} Staff Performance')
    ax.legend()
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    buf.seek(0)
    report = SystemReport.objects.create(report_type=period, report_date=today, generated_by=user, total_accounts=accounts.count(), active_accounts=accounts.filter(is_active=True).count(), total_savings=total_savings, total_loans_disbursed=total_loans_disbursed, total_loans_pending=total_loans_pending, total_loans_approved=total_loans_approved, total_loans_completed=total_loans_completed, total_loans_defaulted=total_loans_defaulted, total_interest_earned=total_interest_earned, total_guarantors=total_guarantors, total_transactions=total_transactions, staff_loan_counts=staff_loan_counts, staff_savings_counts=staff_savings_counts)
    report.chart_image.save(f'{period}_{today}.png', ContentFile(buf.read()))
    report.save()
    if user:
        ActivityLog.objects.create(user=user, action=f'Generated {period} report')
    buf.close()
    plt.close()
    return report