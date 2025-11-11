from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from .models import SystemReport, ActivityLog
from client_accounts.models import ClientAccount, SavingsTransaction
from loans.models import LoanApplication, LoanPayment
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import csv
from .utils import generate_periodic_report

@login_required
def owner_monitoring(request):
    reports = SystemReport.objects.order_by('-report_date')
    return render(request, 'reports/dashboard.html', {'reports': reports})

# ----- Loan Reports -----
@login_required
def loan_performance_report(request):
    loans = LoanApplication.objects.all()
    return render(request, 'reports/loans/performance.html', {'loans': loans})

@login_required
def loan_portfolio_report(request):
    loans = LoanApplication.objects.all()
    return render(request, 'reports/loans/portfolio.html', {'loans': loans})

@login_required
def loan_defaults_report(request):
    loans = LoanApplication.objects.filter(status='DEFAULTED')
    return render(request, 'reports/loans/defaults.html', {'loans': loans})

@login_required
def loan_collections_report(request):
    payments = LoanPayment.objects.all()
    return render(request, 'reports/loans/collections.html', {'payments': payments})

# ----- Savings Reports -----
@login_required
def savings_report(request):
    accounts = ClientAccount.objects.all()
    return render(request, 'reports/savings/report.html', {'accounts': accounts})

@login_required
def savings_growth_report(request):
    transactions = SavingsTransaction.objects.all()
    return render(request, 'reports/savings/growth.html', {'transactions': transactions})

@login_required
def savings_transactions_report(request):
    transactions = SavingsTransaction.objects.all()
    return render(request, 'reports/savings/transactions.html', {'transactions': transactions})

@login_required
def top_savers_report(request):
    accounts = ClientAccount.objects.order_by('-savings_balance')[:10]
    return render(request, 'reports/savings/top_savers.html', {'accounts': accounts})

# ----- Staff Reports -----
@login_required
def staff_performance_report(request):
    reports = SystemReport.objects.order_by('-report_date')
    return render(request, 'reports/staff/performance.html', {'reports': reports})

@login_required
def staff_loans_report(request):
    users = request.user.__class__.objects.all()
    return render(request, 'reports/staff/loans.html', {'users': users})

@login_required
def staff_savings_report(request):
    users = request.user.__class__.objects.all()
    return render(request, 'reports/staff/savings.html', {'users': users})

# ----- Financial Reports -----
@login_required
def financial_report(request):
    reports = SystemReport.objects.order_by('-report_date')
    return render(request, 'reports/financial/report.html', {'reports': reports})

@login_required
def financial_summary(request):
    reports = SystemReport.objects.order_by('-report_date')
    return render(request, 'reports/financial/summary.html', {'reports': reports})

@login_required
def profit_loss_report(request):
    reports = SystemReport.objects.order_by('-report_date')
    return render(request, 'reports/financial/profit_loss.html', {'reports': reports})

# ----- Export to CSV -----
@login_required
def export_loans_csv(request):
    loans = LoanApplication.objects.all()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="loans.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Client', 'Amount', 'Status', 'Disbursed Date'])
    for loan in loans:
        writer.writerow([loan.id, loan.client, loan.loan_amount, loan.status, loan.disbursed_date])
    return response

@login_required
def export_savings_csv(request):
    accounts = ClientAccount.objects.all()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="savings.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Client', 'Balance'])
    for account in accounts:
        writer.writerow([account.id, account.client, account.savings_balance])
    return response

@login_required
def export_staff_csv(request):
    users = request.user.__class__.objects.all()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="staff.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Username', 'Email'])
    for user in users:
        writer.writerow([user.id, user.username, user.email])
    return response

@login_required
def export_financial_csv(request):
    reports = SystemReport.objects.order_by('-report_date')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="financial_reports.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Report Type', 'Date', 'Total Accounts', 'Active Accounts', 'Total Savings',
        'Total Loans Disbursed', 'Pending', 'Approved', 'Completed', 'Defaulted', 'Interest Earned'
    ])
    for report in reports:
        writer.writerow([
            report.get_report_type_display(),
            report.report_date,
            report.total_accounts,
            report.active_accounts,
            report.total_savings,
            report.total_loans_disbursed,
            report.total_loans_pending,
            report.total_loans_approved,
            report.total_loans_completed,
            report.total_loans_defaulted,
            report.total_interest_earned
        ])
    return response

# ----- Generate Reports -----
@login_required
def generate_daily_report(request):
    generate_periodic_report(user=request.user, period='DAILY')
    return redirect('reports_dashboard')

@login_required
def generate_weekly_report(request):
    generate_periodic_report(user=request.user, period='WEEKLY')
    return redirect('reports_dashboard')

@login_required
def generate_monthly_report(request):
    generate_periodic_report(user=request.user, period='MONTHLY')
    return redirect('reports_dashboard')
