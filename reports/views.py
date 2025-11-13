from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from .models import SystemReport, ActivityLog
from client_accounts.models import ClientAccount, SavingsTransaction
from loans.models import LoanApplication, LoanPayment
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from django.http import FileResponse
from io import BytesIO
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



@login_required
def export_financial_pdf(request):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    p.setTitle("Financial Report")

    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(420, 560, "Haliur Investments - Financial Report")

    p.setFont("Helvetica", 12)
    y = 520
    p.drawString(50, y, "Report Type")
    p.drawString(180, y, "Date")
    p.drawString(280, y, "Total Accounts")
    p.drawString(420, y, "Total Savings (UGX)")
    p.drawString(580, y, "Loans Disbursed (UGX)")
    p.drawString(760, y, "Interest Earned (UGX)")
    y -= 20

    reports = SystemReport.objects.order_by('-report_date')
    for report in reports:
        if y <= 60:  # Start new page when reaching the bottom
            p.showPage()
            y = 550
        p.drawString(50, y, str(report.get_report_type_display()))
        p.drawString(180, y, report.report_date.strftime("%b %d, %Y"))
        p.drawString(280, y, str(report.total_accounts))
        p.drawString(420, y, f"{report.total_savings:,.2f}")
        p.drawString(580, y, f"{report.total_loans_disbursed:,.2f}")
        p.drawString(760, y, f"{report.total_interest_earned:,.2f}")
        y -= 20

    p.showPage()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="financial_report.pdf")


@login_required
def export_summary_pdf(request):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setTitle("Financial Summary")

    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(300, 800, "Haliur Investments - Financial Summary")

    reports = SystemReport.objects.order_by('-report_date')
    if reports.exists():
        latest = reports.first()
        y = 750
        p.setFont("Helvetica", 12)
        summary = [
            ("Report Date:", latest.report_date.strftime("%B %d, %Y")),
            ("Total Accounts:", latest.total_accounts),
            ("Active Accounts:", latest.active_accounts),
            ("Total Savings (UGX):", f"{latest.total_savings:,.2f}"),
            ("Total Loans Disbursed (UGX):", f"{latest.total_loans_disbursed:,.2f}"),
            ("Interest Earned (UGX):", f"{latest.total_interest_earned:,.2f}"),
            ("Defaulted Loans:", latest.total_loans_defaulted),
        ]

        for label, value in summary:
            p.drawString(80, y, f"{label}")
            p.drawRightString(500, y, str(value))
            y -= 25
    else:
        p.drawCentredString(300, 700, "No summary data available.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="financial_summary.pdf")


@login_required
def export_profit_loss_pdf(request):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    p.setTitle("Profit and Loss Report")

    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(420, 560, "Haliur Investments - Profit & Loss Report")

    p.setFont("Helvetica", 12)
    y = 520
    p.drawString(60, y, "Date")
    p.drawString(200, y, "Total Income (UGX)")
    p.drawString(400, y, "Total Expenses (UGX)")
    p.drawString(600, y, "Net Profit (UGX)")
    y -= 20

    reports = SystemReport.objects.order_by('-report_date')
    for report in reports:
        total_income = float(report.total_interest_earned or 0) + float(getattr(report, 'other_income', 0))
        total_expenses = float(getattr(report, 'total_expenses', 0))
        net_profit = total_income - total_expenses

        if y <= 60:
            p.showPage()
            y = 550
        p.drawString(60, y, report.report_date.strftime("%b %d, %Y"))
        p.drawString(200, y, f"{total_income:,.2f}")
        p.drawString(400, y, f"{total_expenses:,.2f}")
        p.drawString(600, y, f"{net_profit:,.2f}")
        y -= 20

    p.showPage()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="profit_loss_report.pdf")

# Financial Summary Report
@login_required
def financial_summary(request):
    reports = SystemReport.objects.order_by('-report_date')
    return render(request, 'reports/financial/summary.html', {'reports': reports})

# Profit & Loss Report
@login_required
def profit_loss_report(request):
    reports = SystemReport.objects.order_by('-report_date')
    return render(request, 'reports/financial/profit_loss.html', {'reports': reports})
