from .models import SystemReport, ActivityLog
from client_accounts.models import ClientAccount, SavingsTransaction
from loans.models import LoanApplication, LoanPayment
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
import matplotlib.pyplot as plt
import io
from django.core.files.base import ContentFile
from django.db import models  


def generate_periodic_report(user=None, period='DAILY'):
    today = timezone.now().date()
    
    # Determine date range
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

    # Metrics
    accounts = ClientAccount.objects.all()
    loans = LoanApplication.objects.all()
    savings_total = accounts.aggregate(total=models.Sum('savings_balance'))['total'] or Decimal('0')
    loans_disbursed = loans.filter(status='DISBURSED').aggregate(total=models.Sum('loan_amount'))['total'] or Decimal('0')
    loans_pending = loans.filter(status='PENDING').count()
    loans_approved = loans.filter(status='APPROVED').count()
    loans_completed = loans.filter(status='COMPLETED').count()
    loans_defaulted = loans.filter(status='DEFAULTED').count()
    interest_earned = LoanPayment.objects.filter(payment_date__gte=start_date).aggregate(total=models.Sum('payment_amount'))['total'] or Decimal('0')

    # Staff metrics
    staff_loan_counts = {str(u.id): loans.filter(loan_officer=u).count() for u in User.objects.all()}
    staff_savings_counts = {str(u.id): SavingsTransaction.objects.filter(processed_by=u).count() for u in User.objects.all()}

    # Create chart
    fig, ax = plt.subplots()
    ax.bar(staff_loan_counts.keys(), staff_loan_counts.values(), label='Loans')
    ax.bar(staff_savings_counts.keys(), staff_savings_counts.values(), bottom=list(staff_loan_counts.values()), label='Savings')
    ax.set_xlabel('Staff ID')
    ax.set_ylabel('Count')
    ax.set_title(f'{period} Staff Performance')
    ax.legend()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    
    # Save report
    report = SystemReport.objects.create(
        report_type=period,
        report_date=today,
        generated_by=user,
        total_accounts=accounts.count(),
        active_accounts=accounts.filter(is_active=True).count(),
        total_savings=savings_total,
        total_loans_disbursed=loans_disbursed,
        total_loans_pending=loans_pending,
        total_loans_approved=loans_approved,
        total_loans_completed=loans_completed,
        total_loans_defaulted=loans_defaulted,
        total_interest_earned=interest_earned,
        staff_loan_counts=staff_loan_counts,
        staff_savings_counts=staff_savings_counts,
    )

    report.chart_image.save(f'{period}_{today}.png', ContentFile(buf.read()))
    report.save()
    
    # Log activity
    if user:
        ActivityLog.objects.create(user=user, action=f"Generated {period} report")
    
    buf.close()
    plt.close()
    return report
