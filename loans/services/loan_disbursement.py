from django.db import transaction
from django.utils import timezone
from decimal import Decimal

class LoanDisbursementService:

    @staticmethod
    @transaction.atomic
    def disburse_loan(loan, disbursement_method='cash', reference_number=None, notes=None):
        from loans.models import Loan
        if loan.status != 'approved':
            return {'success': False, 'error': 'Loan must be approved before disbursement'}
        if loan.disbursement_date:
            return {'success': False, 'error': 'Loan has already been disbursed'}
        try:
            loan.status = 'active'
            loan.disbursement_date = timezone.now().date()
            loan.disbursement_method = disbursement_method
            loan.disbursement_reference = reference_number
            if not loan.first_payment_date:
                loan.first_payment_date = loan.calculate_first_payment_date()
            loan.save()
            return {'success': True, 'message': f'Loan {loan.loan_number} disbursed successfully', 'loan': loan}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def validate_disbursement(loan):
        errors = []
        if loan.status != 'approved':
            errors.append('Loan must be in approved status')
        if loan.disbursement_date:
            errors.append('Loan has already been disbursed')
        if not loan.client:
            errors.append('Loan must have a client')
        if loan.principal_amount <= 0:
            errors.append('Loan principal amount must be greater than zero')
        return {'success': len(errors) == 0, 'errors': errors}

    @staticmethod
    def get_disbursement_summary(start_date=None, end_date=None):
        from loans.models import Loan
        from django.db.models import Sum, Count
        queryset = Loan.objects.filter(disbursement_date__isnull=False)
        if start_date:
            queryset = queryset.filter(disbursement_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(disbursement_date__lte=end_date)
        summary = queryset.aggregate(total_amount=Sum('principal_amount'), loan_count=Count('id'))
        return {'total_disbursed': summary['total_amount'] or Decimal('0.00'), 'number_of_loans': summary['loan_count'] or 0, 'loans': queryset}