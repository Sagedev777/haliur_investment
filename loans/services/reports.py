from decimal import Decimal
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta


class ReportService:
    """Service for generating loan reports and analytics"""
    
    @staticmethod
    def generate_portfolio_report(start_date=None, end_date=None, loan_product=None):
        """
        Generate loan portfolio report
        
        Args:
            start_date: Start date for the report
            end_date: End date for the report
            loan_product: Filter by specific loan product
            
        Returns:
            dict: Portfolio report data
        """
        from loans.models import Loan
        
        queryset = Loan.objects.all()
        
        if start_date:
            queryset = queryset.filter(disbursement_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(disbursement_date__lte=end_date)
        if loan_product:
            queryset = queryset.filter(loan_product=loan_product)
        
        # Calculate aggregates
        stats = queryset.aggregate(
            total_loans=Count('id'),
            total_principal=Sum('principal_amount'),
            total_outstanding=Sum('outstanding_balance'),
            avg_loan_size=Avg('principal_amount')
        )
        
        # Count by status
        status_breakdown = {}
        for status_code, status_name in Loan.LOAN_STATUS:
            count = queryset.filter(status=status_code).count()
            status_breakdown[status_name] = count
        
        return {
            'total_loans': stats['total_loans'] or 0,
            'total_principal': stats['total_principal'] or Decimal('0.00'),
            'total_outstanding': stats['total_outstanding'] or Decimal('0.00'),
            'average_loan_size': stats['avg_loan_size'] or Decimal('0.00'),
            'status_breakdown': status_breakdown,
            'loans': queryset
        }
    
    @staticmethod
    def generate_disbursement_report(start_date, end_date, loan_product=None):
        """
        Generate loan disbursement report
        
        Args:
            start_date: Start date
            end_date: End date
            loan_product: Filter by loan product
            
        Returns:
            dict: Disbursement report data
        """
        from loans.models import Loan
        
        queryset = Loan.objects.filter(
            disbursement_date__gte=start_date,
            disbursement_date__lte=end_date,
            disbursement_date__isnull=False
        )
        
        if loan_product:
            queryset = queryset.filter(loan_product=loan_product)
        
        stats = queryset.aggregate(
            total_disbursed=Sum('principal_amount'),
            loan_count=Count('id')
        )
        
        return {
            'period_start': start_date,
            'period_end': end_date,
            'total_disbursed': stats['total_disbursed'] or Decimal('0.00'),
            'number_of_loans': stats['loan_count'] or 0,
            'loans': queryset.order_by('-disbursement_date')
        }
    
    @staticmethod
    def generate_repayment_report(start_date, end_date):
        """
        Generate repayment collection report
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            dict: Repayment report data
        """
        from loans.models import LoanPayment
        
        payments = LoanPayment.objects.filter(
            payment_date__gte=start_date,
            payment_date__lte=end_date
        )
        
        stats = payments.aggregate(
            total_collected=Sum('amount'),
            payment_count=Count('id'),
            principal_collected=Sum('principal_amount'),
            interest_collected=Sum('interest_amount')
        )
        
        return {
            'period_start': start_date,
            'period_end': end_date,
            'total_collected': stats['total_collected'] or Decimal('0.00'),
            'number_of_payments': stats['payment_count'] or 0,
            'principal_collected': stats['principal_collected'] or Decimal('0.00'),
            'interest_collected': stats['interest_collected'] or Decimal('0.00'),
            'payments': payments.order_by('-payment_date')
        }
    
    @staticmethod
    def generate_overdue_report(as_of_date=None):
        """
        Generate overdue loans report
        
        Args:
            as_of_date: Date to check overdue status (defaults to today)
            
        Returns:
            dict: Overdue report data
        """
        from loans.models import Loan
        
        if as_of_date is None:
            as_of_date = timezone.now().date()
        
        # Find loans with payments overdue
        overdue_loans = Loan.objects.filter(
            status='active',
            next_payment_date__lt=as_of_date
        )
        
        stats = overdue_loans.aggregate(
            total_overdue_amount=Sum('outstanding_balance'),
            loan_count=Count('id')
        )
        
        # Categorize by days overdue
        overdue_30 = overdue_loans.filter(
            next_payment_date__gte=as_of_date - timedelta(days=30)
        ).count()
        
        overdue_60 = overdue_loans.filter(
            next_payment_date__lt=as_of_date - timedelta(days=30),
            next_payment_date__gte=as_of_date - timedelta(days=60)
        ).count()
        
        overdue_90_plus = overdue_loans.filter(
            next_payment_date__lt=as_of_date - timedelta(days=60)
        ).count()
        
        return {
            'as_of_date': as_of_date,
            'total_overdue_loans': stats['loan_count'] or 0,
            'total_overdue_amount': stats['total_overdue_amount'] or Decimal('0.00'),
            'overdue_0_30_days': overdue_30,
            'overdue_31_60_days': overdue_60,
            'overdue_over_60_days': overdue_90_plus,
            'loans': overdue_loans
        }
    
    @staticmethod
    def generate_interest_income_report(start_date, end_date):
        """
        Generate interest income report
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            dict: Interest income report
        """
        from loans.models import LoanPayment
        
        payments = LoanPayment.objects.filter(
            payment_date__gte=start_date,
            payment_date__lte=end_date
        )
        
        stats = payments.aggregate(
            total_interest=Sum('interest_amount'),
            payment_count=Count('id')
        )
        
        return {
            'period_start': start_date,
            'period_end': end_date,
            'total_interest_income': stats['total_interest'] or Decimal('0.00'),
            'number_of_payments': stats['payment_count'] or 0,
            'payments': payments.order_by('-payment_date')
        }
    
    @staticmethod
    def generate_risk_analysis_report():
        """
        Generate risk analysis report
        
        Returns:
            dict: Risk analysis data
        """
        from loans.models import Loan
        
        total_loans = Loan.objects.filter(status='active')
        
        stats = total_loans.aggregate(
            total_portfolio=Sum('outstanding_balance'),
            loan_count=Count('id')
        )
        
        # Calculate portfolio at risk (PAR)
        overdue_loans = total_loans.filter(
            next_payment_date__lt=timezone.now().date()
        )
        
        par_stats = overdue_loans.aggregate(
            par_amount=Sum('outstanding_balance'),
            par_count=Count('id')
        )
        
        total_portfolio = stats['total_portfolio'] or Decimal('0.00')
        par_amount = par_stats['par_amount'] or Decimal('0.00')
        
        par_percentage = (par_amount / total_portfolio * 100) if total_portfolio > 0 else Decimal('0.00')
        
        return {
            'total_active_loans': stats['loan_count'] or 0,
            'total_portfolio_value': total_portfolio,
            'portfolio_at_risk_amount': par_amount,
            'portfolio_at_risk_percentage': par_percentage.quantize(Decimal('0.01')),
            'number_of_risky_loans': par_stats['par_count'] or 0,
            'risky_loans': overdue_loans
        }
    
    @staticmethod
    def generate_client_statement(client, start_date=None, end_date=None):
        """
        Generate loan statement for a specific client
        
        Args:
            client: ClientAccount instance
            start_date: Start date for statement
            end_date: End date for statement
            
        Returns:
            dict: Client statement data
        """
        from loans.models import Loan, LoanPayment
        
        loans = Loan.objects.filter(client=client)
        
        if start_date:
            loans = loans.filter(disbursement_date__gte=start_date)
        if end_date:
            loans = loans.filter(disbursement_date__lte=end_date)
        
        loan_stats = loans.aggregate(
            total_borrowed=Sum('principal_amount'),
            total_outstanding=Sum('outstanding_balance'),
            loan_count=Count('id')
        )
        
        # Get payments
        payments = LoanPayment.objects.filter(loan__client=client)
        if start_date:
            payments = payments.filter(payment_date__gte=start_date)
        if end_date:
            payments = payments.filter(payment_date__lte=end_date)
        
        payment_stats = payments.aggregate(
            total_paid=Sum('amount'),
            payment_count=Count('id')
        )
        
        return {
            'client': client,
            'period_start': start_date,
            'period_end': end_date,
            'total_loans': loan_stats['loan_count'] or 0,
            'total_borrowed': loan_stats['total_borrowed'] or Decimal('0.00'),
            'total_outstanding': loan_stats['total_outstanding'] or Decimal('0.00'),
            'total_paid': payment_stats['total_paid'] or Decimal('0.00'),
            'number_of_payments': payment_stats['payment_count'] or 0,
            'loans': loans,
            'payments': payments.order_by('-payment_date')
        }