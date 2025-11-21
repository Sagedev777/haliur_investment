from django.shortcuts import render, redirect
from django.http import HttpResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from io import BytesIO
import csv
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.platypus import Image

from .models import SystemReport, ActivityLog
from .utils import generate_periodic_report
from client_accounts.models import ClientAccount, SavingsTransaction
from loans.models import LoanApplication, LoanPayment

from io import BytesIO
from django.http import FileResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.contrib.auth.decorators import login_required
from .models import SystemReport

# ------------------- Dashboard -------------------
@login_required
def owner_monitoring(request):
    reports = SystemReport.objects.order_by('-report_date')
    return render(request, 'reports/dashboard.html', {'reports': reports})

# ------------------- Loan Reports -------------------
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

# ------------------- Savings Reports -------------------
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

# ------------------- Staff Reports -------------------
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

# ------------------- Financial Reports -------------------
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

# ------------------- CSV Exports -------------------
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
        'Loans Disbursed', 'Pending', 'Approved', 'Completed', 'Defaulted',
        'Interest Earned', 'Guarantors', 'Transactions'
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
            report.total_interest_earned,
            getattr(report, 'total_guarantors', 0),
            getattr(report, 'total_transactions', 0)
        ])
    return response

# ------------------- PDF Exports with Charts -------------------
@login_required
def export_financial_pdf(request):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    p.setTitle("Financial Report")

    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(420, 560, "Haliur Investments - Financial Report")

    p.setFont("Helvetica", 12)
    y = 520
    headers = ["Report Type", "Date", "Total Accounts", "Total Savings",
               "Loans Disbursed", "Interest Earned", "Guarantors", "Transactions"]
    x_positions = [50, 180, 280, 420, 580, 760, 900, 1020]
    for i, header in enumerate(headers):
        p.drawString(x_positions[i], y, header)
    y -= 20

    reports = SystemReport.objects.order_by('-report_date')
    for report in reports:
        if y <= 120:
            p.showPage()
            y = 550
        # Data
        data = [
            report.get_report_type_display(),
            report.report_date.strftime("%b %d, %Y"),
            str(report.total_accounts),
            f"{report.total_savings:,.2f}",
            f"{report.total_loans_disbursed:,.2f}",
            f"{report.total_interest_earned:,.2f}",
            str(getattr(report, 'total_guarantors', 0)),
            str(getattr(report, 'total_transactions', 0))
        ]
        for i, d in enumerate(data):
            p.drawString(x_positions[i], y, d)
        y -= 20

        # Add chart image if exists
        if report.chart_image:
            try:
                img_path = report.chart_image.path
                p.drawImage(img_path, 50, y-150, width=700, height=150)
                y -= 170
            except:
                pass

    p.showPage()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="financial_report.pdf")

# ------------------- Generate Periodic Reports -------------------
@login_required
def generate_daily_report(request):
    generate_periodic_report(user=request.user, period='DAILY')
    return redirect('reports:reports_dashboard')

@login_required
def generate_weekly_report(request):
    generate_periodic_report(user=request.user, period='WEEKLY')
    return redirect('reports:reports_dashboard')

@login_required
def generate_monthly_report(request):
    generate_periodic_report(user=request.user, period='MONTHLY')
    return redirect('reports:reports_dashboard')


@login_required
def export_summary_pdf(request):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setTitle("Financial Summary")

    # Title
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(300, 800, "Haliur Investments - Financial Summary")

    # Get the latest report
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
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setTitle("Profit & Loss Report")

    # Title
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(300, 800, "Haliur Investments - Profit & Loss Report")

    reports = SystemReport.objects.order_by('-report_date')
    y = 750
    p.setFont("Helvetica", 12)

    if reports.exists():
        for report in reports:
            if y < 100:
                p.showPage()
                y = 750
            p.drawString(50, y, f"Date: {report.report_date.strftime('%B %d, %Y')}")
            p.drawString(200, y, f"Loans Disbursed: {report.total_loans_disbursed:,.2f} UGX")
            p.drawString(400, y, f"Interest Earned: {report.total_interest_earned:,.2f} UGX")
            p.drawString(600, y, f"Defaulted Loans: {report.total_loans_defaulted}")
            y -= 25
    else:
        p.drawCentredString(300, y, "No profit/loss data available.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="profit_loss_report.pdf")
