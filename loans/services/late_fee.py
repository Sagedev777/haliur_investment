from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from django.utils import timezone

class LateFeeService:

    @staticmethod
    def calculate_late_fee(loan, overdue_amount, days_overdue):
        overdue_amount = Decimal(str(overdue_amount))
        if hasattr(loan, 'loan_product') and loan.loan_product:
            product = loan.loan_product
            if hasattr(product, 'late_fee_percentage') and product.late_fee_percentage:
                late_fee_rate = Decimal(str(product.late_fee_percentage)) / Decimal('100')
                late_fee = overdue_amount * late_fee_rate
            elif hasattr(product, 'late_fee_amount') and product.late_fee_amount:
                late_fee = Decimal(str(product.late_fee_amount))
            else:
                late_fee = overdue_amount * Decimal('0.05')
        else:
            late_fee = overdue_amount * Decimal('0.05')
        grace_period = getattr(loan.loan_product, 'grace_period_days', 0) if hasattr(loan, 'loan_product') else 0
        if days_overdue <= grace_period:
            return Decimal('0.00')
        return late_fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_penalty_interest(loan, overdue_amount, days_overdue):
        overdue_amount = Decimal(str(overdue_amount))
        if hasattr(loan, 'loan_product') and loan.loan_product:
            product = loan.loan_product
            if hasattr(product, 'penalty_interest_rate') and product.penalty_interest_rate:
                annual_penalty_rate = Decimal(str(product.penalty_interest_rate))
            else:
                annual_penalty_rate = Decimal('24.0')
        else:
            annual_penalty_rate = Decimal('24.0')
        daily_rate = annual_penalty_rate / Decimal('365') / Decimal('100')
        penalty_interest = overdue_amount * daily_rate * Decimal(str(days_overdue))
        return penalty_interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def get_total_penalties(loan):
        return {'late_fees': Decimal('0.00'), 'penalty_interest': Decimal('0.00'), 'total_penalties': Decimal('0.00')}

    @staticmethod
    def apply_late_fee(loan, amount, reason='Late payment'):
        from django.db import transaction
        try:
            with transaction.atomic():
                if hasattr(loan, 'outstanding_fees'):
                    loan.outstanding_fees = (loan.outstanding_fees or Decimal('0.00')) + Decimal(str(amount))
                    loan.save()
                return {'success': True, 'message': f'Late fee of {amount} applied successfully', 'amount': amount}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def calculate_days_overdue(due_date, current_date=None):
        if current_date is None:
            current_date = timezone.now().date()
        elif isinstance(current_date, datetime):
            current_date = current_date.date()
        if isinstance(due_date, datetime):
            due_date = due_date.date()
        if current_date <= due_date:
            return 0
        days_overdue = (current_date - due_date).days
        return max(0, days_overdue)