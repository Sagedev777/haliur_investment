from decimal import Decimal, ROUND_HALF_UP
import datetime
from dateutil.relativedelta import relativedelta

class InterestCalculationService:
    DAY_COUNT_METHODS = {'ACTUAL_365': {'days_in_year': 365, 'use_actual_days': True}, 'ACTUAL_360': {'days_in_year': 360, 'use_actual_days': True}, '30_360': {'days_in_year': 360, 'use_actual_days': False}}

    @classmethod
    def calculate_days_between(cls, start_date: datetime.date, end_date: datetime.date, method: str='ACTUAL_365') -> int:
        if method == '30_360':
            days = (end_date.year - start_date.year) * 360
            days += (end_date.month - start_date.month) * 30
            days += min(end_date.day, 30) - min(start_date.day, 30)
            return max(days, 0)
        else:
            return max((end_date - start_date).days, 0)

    @classmethod
    def calculate_flat_interest(cls, principal: Decimal, annual_rate: Decimal, days: int, method: str='ACTUAL_365') -> Decimal:
        if days <= 0 or principal <= 0:
            return Decimal('0')
        config = cls.DAY_COUNT_METHODS.get(method, cls.DAY_COUNT_METHODS['ACTUAL_365'])
        rate_decimal = annual_rate / Decimal('100')
        if config['use_actual_days']:
            interest = principal * rate_decimal * Decimal(str(days)) / Decimal(str(config['days_in_year']))
        else:
            interest = principal * rate_decimal * Decimal(str(days)) / Decimal('360')
        return interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_amortized_payment(cls, principal: Decimal, annual_rate: Decimal, term_months: int) -> Decimal:
        if term_months <= 0 or principal <= 0:
            return Decimal('0')
        monthly_rate = annual_rate / Decimal('100') / Decimal('12')
        if monthly_rate == Decimal('0'):
            payment = principal / Decimal(str(term_months))
        else:
            factor = (Decimal('1') + monthly_rate) ** Decimal(str(term_months))
            payment = principal * monthly_rate * factor / (factor - Decimal('1'))
        return payment.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def generate_amortization_schedule(cls, principal: Decimal, annual_rate: Decimal, term_months: int, start_date: datetime.date) -> list:
        monthly_payment = cls.calculate_amortized_payment(principal, annual_rate, term_months)
        monthly_rate = annual_rate / Decimal('100') / Decimal('12')
        schedule = []
        remaining_balance = principal
        for period in range(1, term_months + 1):
            interest_payment = remaining_balance * monthly_rate
            principal_payment = monthly_payment - interest_payment
            remaining_balance -= principal_payment
            due_date = start_date + relativedelta(months=period)
            schedule.append({'period': period, 'due_date': due_date, 'payment': monthly_payment.quantize(Decimal('0.01')), 'principal': principal_payment.quantize(Decimal('0.01')), 'interest': interest_payment.quantize(Decimal('0.01')), 'remaining_balance': max(remaining_balance, Decimal('0')).quantize(Decimal('0.01'))})
        return schedule