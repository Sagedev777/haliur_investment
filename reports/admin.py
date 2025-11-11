from django.contrib import admin
from django.http import HttpResponse
from .models import SystemReport, ActivityLog
from client_accounts.models import ClientAccount, SavingsTransaction
from loans.models import LoanApplication, LoanPayment
from django.contrib.auth.models import User
from decimal import Decimal
import csv
from django.utils import timezone
from .utils import generate_periodic_report

@admin.register(SystemReport)
class SystemReportAdmin(admin.ModelAdmin):
    list_display = [
        'report_type', 'report_date', 'total_accounts', 'total_savings',
        'total_loans_disbursed', 'total_loans_pending', 'total_loans_approved',
        'total_loans_completed', 'total_loans_defaulted', 'total_interest_earned',
        'generated_by', 'generated_at'
    ]
    list_filter = ['report_type', 'report_date', 'generated_by']
    readonly_fields = ['generated_at', 'chart_image', 'staff_loan_counts', 'staff_savings_counts']
    actions = ['generate_daily_report', 'generate_weekly_report', 'generate_monthly_report', 'export_to_csv']

    # Display summary in admin detail view
    def report_details(self, obj):
        details = [
            f"📊 {obj.get_report_type_display()} Report for {obj.report_date}",
            f"👥 Accounts: {obj.total_accounts} total, {obj.active_accounts} active",
            f"💰 Savings: {obj.total_savings}",
            f"🏠 Loans: {obj.total_loans_disbursed} disbursed",
            f"📋 Status: Pending {obj.total_loans_pending}, Approved {obj.total_loans_approved}",
            f"✅ Completed {obj.total_loans_completed}, ❌ Defaulted {obj.total_loans_defaulted}",
            f"💵 Interest Earned: {obj.total_interest_earned}",
        ]
        return "\n".join(details)
    report_details.short_description = "Report Summary"

    # Generate Reports
    def generate_daily_report(self, request, queryset):
        generate_periodic_report(user=request.user, period='DAILY')
        self.message_user(request, "Daily report generated successfully.")
    generate_daily_report.short_description = "Generate Daily Report"

    def generate_weekly_report(self, request, queryset):
        generate_periodic_report(user=request.user, period='WEEKLY')
        self.message_user(request, "Weekly report generated successfully.")
    generate_weekly_report.short_description = "Generate Weekly Report"

    def generate_monthly_report(self, request, queryset):
        generate_periodic_report(user=request.user, period='MONTHLY')
        self.message_user(request, "Monthly report generated successfully.")
    generate_monthly_report.short_description = "Generate Monthly Report"

    # Export CSV
    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="system_reports.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Report Type', 'Date', 'Total Accounts', 'Active Accounts', 'Total Savings',
            'Total Loans Disbursed', 'Pending Loans', 'Approved Loans', 'Completed Loans',
            'Defaulted Loans', 'Interest Earned'
        ])
        for report in queryset:
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
    export_to_csv.short_description = "Export Selected Reports to CSV"


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'timestamp']
    list_filter = ['user', 'timestamp']
    readonly_fields = ['user', 'action', 'timestamp']
