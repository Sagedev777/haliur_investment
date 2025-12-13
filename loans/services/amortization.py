from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from dateutil.relativedelta import relativedelta

class AmortizationService:

    @staticmethod
    def generate_schedule(principal, annual_rate, term_months, start_date, frequency='monthly'):
        principal = Decimal(str(principal))
        annual_rate = Decimal(str(annual_rate))
        if frequency == 'monthly':
            periodic_rate = annual_rate / Decimal('12') / Decimal('100')
            num_payments = term_months
        elif frequency == 'weekly':
            periodic_rate = annual_rate / Decimal('52') / Decimal('100')
            num_payments = int(term_months * Decimal('4.33'))
        elif frequency == 'daily':
            periodic_rate = annual_rate / Decimal('365') / Decimal('100')
            num_payments = int(term_months * Decimal('30'))
        else:
            periodic_rate = annual_rate / Decimal('12') / Decimal('100')
            num_payments = term_months
        if periodic_rate == 0:
            payment_amount = principal / Decimal(str(num_payments))
        else:
            payment_amount = principal * (periodic_rate * (1 + periodic_rate) ** num_payments) / ((1 + periodic_rate) ** num_payments - 1)
        payment_amount = payment_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        schedule = []
        balance = principal
        current_date = start_date
        for payment_num in range(1, num_payments + 1):
            interest = (balance * periodic_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            principal_payment = payment_amount - interest
            if payment_num == num_payments:
                principal_payment = balance
                payment_amount = balance + interest
            new_balance = balance - principal_payment
            if frequency == 'monthly':
                payment_date = current_date + relativedelta(months=1)
            elif frequency == 'weekly':
                payment_date = current_date + timedelta(weeks=1)
            elif frequency == 'daily':
                payment_date = current_date + timedelta(days=1)
            else:
                payment_date = current_date + relativedelta(months=1)
            schedule.append({'payment_number': payment_num, 'payment_date': payment_date, 'payment_amount': payment_amount, 'principal_amount': principal_payment, 'interest_amount': interest, 'balance': new_balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)})
            balance = new_balance
            current_date = payment_date
        return schedule

    @staticmethod
    def calculate_payment(principal, annual_rate, term_months, frequency='monthly'):
        principal = Decimal(str(principal))
        annual_rate = Decimal(str(annual_rate))
        if frequency == 'monthly':
            periodic_rate = annual_rate / Decimal('12') / Decimal('100')
            num_payments = term_months
        elif frequency == 'weekly':
            periodic_rate = annual_rate / Decimal('52') / Decimal('100')
            num_payments = int(term_months * Decimal('4.33'))
        elif frequency == 'daily':
            periodic_rate = annual_rate / Decimal('365') / Decimal('100')
            num_payments = int(term_months * Decimal('30'))
        else:
            periodic_rate = annual_rate / Decimal('12') / Decimal('100')
            num_payments = term_months
        if periodic_rate == 0:
            return (principal / Decimal(str(num_payments))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        payment = principal * (periodic_rate * (1 + periodic_rate) ** num_payments) / ((1 + periodic_rate) ** num_payments - 1)
        return payment.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_total_interest(principal, annual_rate, term_months, frequency='monthly'):
        payment = AmortizationService.calculate_payment(principal, annual_rate, term_months, frequency)
        if frequency == 'monthly':
            num_payments = term_months
        elif frequency == 'weekly':
            num_payments = int(term_months * Decimal('4.33'))
        elif frequency == 'daily':
            num_payments = int(term_months * Decimal('30'))
        else:
            num_payments = term_months
        total_paid = payment * Decimal(str(num_payments))
        total_interest = total_paid - Decimal(str(principal))
        return total_interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)