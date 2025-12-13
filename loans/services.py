from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING, ROUND_FLOOR
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q
import datetime
from dateutil.relativedelta import relativedelta
import math
from typing import List, Dict, Tuple, Optional
from .models import Loan, LoanProduct, LoanRepaymentSchedule, LoanTransaction

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
    def calculate_reducing_balance_interest(cls, principal: Decimal, annual_rate: Decimal, start_date: datetime.date, end_date: datetime.date, repayment_dates: List[datetime.date], repayment_amounts: List[Decimal], method: str='ACTUAL_365') -> Decimal:
        if not repayment_dates or len(repayment_dates) != len(repayment_amounts):
            raise ValueError('Repayment dates and amounts must match')
        config = cls.DAY_COUNT_METHODS.get(method, cls.DAY_COUNT_METHODS['ACTUAL_365'])
        rate_decimal = annual_rate / Decimal('100')
        daily_rate = rate_decimal / Decimal(str(config['days_in_year']))
        total_interest = Decimal('0')
        current_principal = principal
        current_date = start_date
        repayments = sorted(zip(repayment_dates, repayment_amounts), key=lambda x: x[0])
        for repayment_date, repayment_amount in repayments:
            if repayment_date <= current_date:
                continue
            days = cls.calculate_days_between(current_date, repayment_date, method)
            period_interest = current_principal * daily_rate * Decimal(str(days))
            total_interest += period_interest
            current_principal -= repayment_amount
            if current_principal < 0:
                current_principal = Decimal('0')
            current_date = repayment_date
        if current_date < end_date:
            days = cls.calculate_days_between(current_date, end_date, method)
            period_interest = current_principal * daily_rate * Decimal(str(days))
            total_interest += period_interest
        return total_interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_amortized_payment(cls, principal: Decimal, annual_rate: Decimal, term_months: int, payment_frequency: str='MONTHLY') -> Decimal:
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
    def generate_amortization_schedule(cls, principal: Decimal, annual_rate: Decimal, term_months: int, start_date: datetime.date, payment_frequency: str='MONTHLY') -> List[Dict]:
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

    @classmethod
    def calculate_early_repayment_savings(cls, loan: Loan, repayment_amount: Decimal, repayment_date: datetime.date) -> Dict:
        remaining_schedule = loan.repayment_schedule.filter(status__in=['PENDING', 'DUE']).order_by('due_date')
        if not remaining_schedule.exists():
            return {'savings': Decimal('0'), 'new_schedule': []}
        total_interest_without_early = sum((installment.interest_amount for installment in remaining_schedule))
        new_principal = loan.remaining_balance - repayment_amount
        if new_principal <= 0:
            savings = total_interest_without_early
            new_schedule = []
        else:
            remaining_months = remaining_schedule.count()
            monthly_rate = loan.interest_rate / Decimal('100') / Decimal('12')
            new_payment = cls.calculate_amortized_payment(new_principal, loan.interest_rate, remaining_months)
            new_schedule = []
            remaining_balance = new_principal
            for i, installment in enumerate(remaining_schedule, 1):
                interest = remaining_balance * monthly_rate
                principal = new_payment - interest
                remaining_balance -= principal
                new_schedule.append({'period': i, 'due_date': installment.due_date, 'payment': new_payment.quantize(Decimal('0.01')), 'principal': principal.quantize(Decimal('0.01')), 'interest': interest.quantize(Decimal('0.01')), 'remaining_balance': max(remaining_balance, Decimal('0')).quantize(Decimal('0.01'))})
            total_interest_with_early = sum((item['interest'] for item in new_schedule))
            savings = total_interest_without_early - total_interest_with_early
        penalty = Decimal('0')
        if loan.loan_product.early_repayment_penalty_percent > 0:
            penalty = repayment_amount * loan.loan_product.early_repayment_penalty_percent / Decimal('100')
        net_savings = savings - penalty
        return {'savings': savings.quantize(Decimal('0.01')), 'penalty': penalty.quantize(Decimal('0.01')), 'net_savings': net_savings.quantize(Decimal('0.01')), 'new_schedule': new_schedule}

class CreditScoringService:

    @classmethod
    def calculate_credit_score(cls, client, loan_amount: Decimal, existing_loans: List[Loan]=None) -> Decimal:
        score = Decimal('0')
        account_age_days = (timezone.now().date() - client.created_at.date()).days
        if account_age_days >= 365:
            score += Decimal('20')
        elif account_age_days >= 180:
            score += Decimal('16')
        elif account_age_days >= 90:
            score += Decimal('12')
        elif account_age_days >= 30:
            score += Decimal('8')
        else:
            score += Decimal('4')
        avg_balance = client.current_balance
        if avg_balance >= loan_amount * Decimal('0.5'):
            score += Decimal('10')
        elif avg_balance >= loan_amount * Decimal('0.3'):
            score += Decimal('8')
        elif avg_balance >= loan_amount * Decimal('0.2'):
            score += Decimal('6')
        elif avg_balance >= loan_amount * Decimal('0.1'):
            score += Decimal('4')
        else:
            score += Decimal('2')
        score += Decimal('8')
        if client.current_balance >= client.minimum_balance_required:
            score += Decimal('7')
        else:
            score += Decimal('3')
        transaction_score = Decimal('15')
        score += transaction_score
        if existing_loans:
            total_existing_debt = sum((loan.remaining_balance for loan in existing_loans))
            total_proposed_debt = total_existing_debt + loan_amount
            if hasattr(client, 'monthly_income') and client.monthly_income:
                dti_ratio = total_proposed_debt / (client.monthly_income * Decimal('12'))
                if dti_ratio <= Decimal('0.3'):
                    score += Decimal('15')
                elif dti_ratio <= Decimal('0.4'):
                    score += Decimal('12')
                elif dti_ratio <= Decimal('0.5'):
                    score += Decimal('8')
                elif dti_ratio <= Decimal('0.6'):
                    score += Decimal('4')
                else:
                    score += Decimal('0')
            else:
                savings_coverage = client.current_balance / total_proposed_debt
                if savings_coverage >= Decimal('1.0'):
                    score += Decimal('15')
                elif savings_coverage >= Decimal('0.5'):
                    score += Decimal('10')
                elif savings_coverage >= Decimal('0.3'):
                    score += Decimal('6')
                elif savings_coverage >= Decimal('0.2'):
                    score += Decimal('3')
                else:
                    score += Decimal('0')
            defaulted_loans = sum((1 for loan in existing_loans if loan.status == 'DEFAULTED'))
            if defaulted_loans == 0:
                score += Decimal('10')
            elif defaulted_loans == 1:
                score += Decimal('5')
            else:
                score += Decimal('0')
        else:
            score += Decimal('25')
        collateral_score = Decimal('7')
        score += collateral_score
        return max(Decimal('0'), min(score, Decimal('100'))).quantize(Decimal('0.01'))

    @classmethod
    def determine_risk_rating(cls, credit_score: Decimal) -> str:
        if credit_score >= Decimal('80'):
            return 'A'
        elif credit_score >= Decimal('60'):
            return 'B'
        elif credit_score >= Decimal('40'):
            return 'C'
        else:
            return 'D'

    @classmethod
    def calculate_max_loan_amount(cls, client, existing_loans: List[Loan]=None) -> Decimal:
        savings_multiplier = Decimal('3')
        max_from_savings = client.current_balance * savings_multiplier
        max_from_income = Decimal('0')
        if hasattr(client, 'monthly_income') and client.monthly_income:
            max_annual_debt = client.monthly_income * Decimal('12') * Decimal('0.6')
            if existing_loans:
                existing_annual_payments = sum((loan.total_repayment_amount / Decimal(str(loan.term_days)) * Decimal('365') for loan in existing_loans if loan.status in ['ACTIVE', 'OVERDUE']))
                max_from_income = max_annual_debt - existing_annual_payments
            else:
                max_from_income = max_annual_debt
        if max_from_income > Decimal('0'):
            return min(max_from_savings, max_from_income).quantize(Decimal('1000'), rounding=ROUND_FLOOR)
        else:
            return max_from_savings.quantize(Decimal('1000'), rounding=ROUND_FLOOR)

class PaymentProcessingService:

    @classmethod
    @transaction.atomic
    def process_payment(cls, loan: Loan, amount: Decimal, payment_date: datetime.date, payment_method: str, received_by, notes: str='', allocation_strategy: str='AUTO') -> Dict:
        if amount <= Decimal('0'):
            raise ValueError('Payment amount must be greater than zero')
        if amount > loan.remaining_balance:
            raise ValueError(f'Payment exceeds remaining balance: {loan.remaining_balance}')
        overdue_installments = loan.repayment_schedule.filter(Q(status='OVERDUE') | Q(status='DUE', due_date__lt=payment_date)).order_by('due_date')
        current_installments = loan.repayment_schedule.filter(status__in=['PENDING', 'DUE'], due_date__gte=payment_date).order_by('due_date')
        remaining_amount = amount
        allocation = {'late_fees': Decimal('0'), 'principal': Decimal('0'), 'interest': Decimal('0'), 'transactions': []}
        if allocation_strategy in ['AUTO', 'LATE_FEES_FIRST']:
            total_late_fees = sum((installment.late_fee_amount for installment in overdue_installments if installment.late_fee_amount > 0))
            if total_late_fees > 0 and remaining_amount > 0:
                late_fee_payment = min(total_late_fees, remaining_amount)
                for installment in overdue_installments:
                    if installment.late_fee_amount <= 0 or remaining_amount <= 0:
                        continue
                    installment_share = installment.late_fee_amount / total_late_fees
                    installment_payment = late_fee_payment * installment_share
                    installment_payment = min(installment_payment, installment.late_fee_amount)
                    if installment_payment > 0:
                        transaction = LoanTransaction.objects.create(loan=loan, installment=installment, transaction_type='LATE_FEE_PAYMENT', payment_method=payment_method, amount=installment_payment, fee_amount=installment_payment, transaction_date=payment_date, notes=f'Late fee payment: {notes}', recorded_by=received_by)
                        allocation['late_fees'] += installment_payment
                        allocation['transactions'].append(transaction)
                        installment.paid_late_fee += installment_payment
                        installment.total_paid += installment_payment
                        installment.save()
                        remaining_amount -= installment_payment
        if allocation_strategy in ['AUTO', 'PRINCIPAL_FIRST', 'INTEREST_FIRST']:
            for installment in overdue_installments:
                if remaining_amount <= 0:
                    break
                installment_balance = installment.total_amount - installment.total_paid
                if installment_balance <= 0:
                    continue
                payment_for_installment = min(installment_balance, remaining_amount)
                if allocation_strategy == 'PRINCIPAL_FIRST':
                    principal_payment = min(payment_for_installment, installment.principal_amount - installment.paid_principal)
                    interest_payment = payment_for_installment - principal_payment
                elif allocation_strategy == 'INTEREST_FIRST':
                    interest_payment = min(payment_for_installment, installment.interest_amount - installment.paid_interest)
                    principal_payment = payment_for_installment - interest_payment
                else:
                    principal_ratio = installment.principal_amount / installment.total_amount
                    interest_ratio = installment.interest_amount / installment.total_amount
                    principal_payment = payment_for_installment * principal_ratio
                    interest_payment = payment_for_installment * interest_ratio
                if principal_payment > 0:
                    transaction = LoanTransaction.objects.create(loan=loan, installment=installment, transaction_type='PRINCIPAL_PAYMENT', payment_method=payment_method, amount=principal_payment, principal_amount=principal_payment, transaction_date=payment_date, notes=f'Principal payment: {notes}', recorded_by=received_by)
                    allocation['principal'] += principal_payment
                    allocation['transactions'].append(transaction)
                if interest_payment > 0:
                    transaction = LoanTransaction.objects.create(loan=loan, installment=installment, transaction_type='INTEREST_PAYMENT', payment_method=payment_method, amount=interest_payment, interest_amount=interest_payment, transaction_date=payment_date, notes=f'Interest payment: {notes}', recorded_by=received_by)
                    allocation['interest'] += interest_payment
                    allocation['transactions'].append(transaction)
                installment.paid_principal += principal_payment
                installment.paid_interest += interest_payment
                installment.total_paid += payment_for_installment
                if installment.total_paid >= installment.total_amount:
                    installment.status = 'PAID'
                    installment.payment_date = payment_date
                installment.save()
                remaining_amount -= payment_for_installment
        if remaining_amount > 0 and allocation_strategy in ['AUTO', 'PRINCIPAL_FIRST', 'INTEREST_FIRST']:
            for installment in current_installments:
                if remaining_amount <= 0:
                    break
                installment_balance = installment.total_amount - installment.total_paid
                if installment_balance <= 0:
                    continue
                payment_for_installment = min(installment_balance, remaining_amount)
                if allocation_strategy == 'PRINCIPAL_FIRST':
                    principal_payment = min(payment_for_installment, installment.principal_amount - installment.paid_principal)
                    interest_payment = payment_for_installment - principal_payment
                elif allocation_strategy == 'INTEREST_FIRST':
                    interest_payment = min(payment_for_installment, installment.interest_amount - installment.paid_interest)
                    principal_payment = payment_for_installment - interest_payment
                else:
                    principal_ratio = installment.principal_amount / installment.total_amount
                    interest_ratio = installment.interest_amount / installment.total_amount
                    principal_payment = payment_for_installment * principal_ratio
                    interest_payment = payment_for_installment * interest_ratio
                if principal_payment > 0:
                    transaction = LoanTransaction.objects.create(loan=loan, installment=installment, transaction_type='PRINCIPAL_PAYMENT', payment_method=payment_method, amount=principal_payment, principal_amount=principal_payment, transaction_date=payment_date, notes=f'Principal payment: {notes}', recorded_by=received_by)
                    allocation['principal'] += principal_payment
                    allocation['transactions'].append(transaction)
                if interest_payment > 0:
                    transaction = LoanTransaction.objects.create(loan=loan, installment=installment, transaction_type='INTEREST_PAYMENT', payment_method=payment_method, amount=interest_payment, interest_amount=interest_payment, transaction_date=payment_date, notes=f'Interest payment: {notes}', recorded_by=received_by)
                    allocation['interest'] += interest_payment
                    allocation['transactions'].append(transaction)
                installment.paid_principal += principal_payment
                installment.paid_interest += interest_payment
                installment.total_paid += payment_for_installment
                if installment.total_paid >= installment.total_amount:
                    installment.status = 'PAID'
                    installment.payment_date = payment_date
                installment.save()
                remaining_amount -= payment_for_installment
        if remaining_amount > 0:
            next_installment = loan.repayment_schedule.filter(status__in=['PENDING', 'DUE']).order_by('due_date').first()
            if next_installment:
                transaction = LoanTransaction.objects.create(loan=loan, installment=next_installment, transaction_type='PRINCIPAL_PAYMENT', payment_method=payment_method, amount=remaining_amount, principal_amount=remaining_amount, transaction_date=payment_date, notes=f'Advance payment: {notes}', recorded_by=received_by)
                allocation['principal'] += remaining_amount
                allocation['transactions'].append(transaction)
                next_installment.paid_principal += remaining_amount
                next_installment.total_paid += remaining_amount
                next_installment.save()
            else:
                transaction = LoanTransaction.objects.create(loan=loan, transaction_type='PRINCIPAL_PAYMENT', payment_method=payment_method, amount=remaining_amount, principal_amount=remaining_amount, transaction_date=payment_date, notes=f'Principal reduction: {notes}', recorded_by=received_by)
                allocation['principal'] += remaining_amount
                allocation['transactions'].append(transaction)
        cls.update_loan_balances(loan)
        allocation['remaining_amount'] = remaining_amount
        allocation['total_paid'] = amount
        return allocation

    @classmethod
    def update_loan_balances(cls, loan: Loan):
        total_paid = loan.transactions.filter(transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT']).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        loan.total_paid_amount = total_paid
        loan.remaining_balance = max(Decimal('0'), loan.total_repayment_amount - total_paid)
        overdue_installments = loan.repayment_schedule.filter(status__in=['DUE', 'OVERDUE'], due_date__lt=timezone.now().date())
        loan.overdue_amount = sum((installment.total_amount - installment.total_paid for installment in overdue_installments))
        if loan.status == 'OVERDUE' and loan.next_payment_date:
            loan.days_overdue = max(0, (timezone.now().date() - loan.next_payment_date).days)
        if loan.remaining_balance <= Decimal('0'):
            loan.status = 'CLOSED'
            loan.closed_at = timezone.now()
        elif loan.overdue_amount > Decimal('0') and loan.status == 'ACTIVE':
            loan.status = 'OVERDUE'
        elif loan.overdue_amount <= Decimal('0') and loan.status == 'OVERDUE':
            loan.status = 'ACTIVE'
        next_due_installment = loan.repayment_schedule.filter(status__in=['PENDING', 'DUE']).order_by('due_date').first()
        if next_due_installment:
            loan.next_payment_date = next_due_installment.due_date
        else:
            loan.next_payment_date = None
        loan.save()

class LoanDisbursementService:

    @classmethod
    @transaction.atomic
    def disburse_loan(cls, loan: Loan, disbursement_date: datetime.date, disbursed_by, payment_method: str, transaction_reference: str='', notes: str='') -> LoanTransaction:
        if loan.status != 'PENDING_DISBURSEMENT':
            raise ValueError(f'Loan must be in PENDING_DISBURSEMENT status. Current: {loan.status}')
        loan.disbursement_date = disbursement_date
        loan.disbursed_by = disbursed_by
        loan.status = 'ACTIVE'
        if disbursement_date and loan.term_days:
            loan.maturity_date = disbursement_date + datetime.timedelta(days=loan.term_days)
        loan.save()
        if not loan.repayment_schedule.exists():
            amortization_service = AmortizationService()
            amortization_service.create_repayment_schedule(loan)
        disbursement = LoanTransaction.objects.create(loan=loan, transaction_type='DISBURSEMENT', payment_method=payment_method, amount=loan.principal_amount, principal_amount=loan.principal_amount, transaction_date=disbursement_date, reference_number=transaction_reference, notes=notes, recorded_by=disbursed_by)
        cls.update_client_account(loan.client, loan.principal_amount, disbursement_date)
        return disbursement

    @classmethod
    def update_client_account(cls, client, amount: Decimal, disbursement_date: datetime.date):
        try:
            client.current_balance += amount
            client.save()
        except Exception as e:
            import logging
            logging.error(f'Failed to update client account: {str(e)}')

class AmortizationService:

    @classmethod
    def create_repayment_schedule(cls, loan: Loan):
        if loan.loan_product.interest_type == 'FLAT':
            return cls.create_flat_interest_schedule(loan)
        else:
            return cls.create_reducing_balance_schedule(loan)

    @classmethod
    def create_flat_interest_schedule(cls, loan: Loan) -> List[LoanRepaymentSchedule]:
        interest_service = InterestCalculationService()
        total_interest = interest_service.calculate_flat_interest(loan.principal_amount, loan.interest_rate, loan.term_days, method=loan.loan_product.interest_calculation_method)
        total_repayment = loan.principal_amount + total_interest
        if loan.term_days <= 30:
            installments = 4
            days_per_installment = 7
        elif loan.term_days <= 90:
            installments = 12
            days_per_installment = loan.term_days // installments
        else:
            installments = loan.term_days // 30
            days_per_installment = 30
        installment_amount = total_repayment / Decimal(str(installments))
        installment_principal = loan.principal_amount / Decimal(str(installments))
        installment_interest = total_interest / Decimal(str(installments))
        schedule_entries = []
        current_date = loan.disbursement_date
        for i in range(1, installments + 1):
            due_date = current_date + datetime.timedelta(days=days_per_installment)
            schedule_entry = LoanRepaymentSchedule.objects.create(loan=loan, installment_number=i, due_date=due_date, principal_amount=installment_principal.quantize(Decimal('0.01')), interest_amount=installment_interest.quantize(Decimal('0.01')), total_amount=installment_amount.quantize(Decimal('0.01')), status='PENDING', grace_period_days=5)
            schedule_entries.append(schedule_entry)
            current_date = due_date
        if schedule_entries:
            loan.first_payment_date = schedule_entries[0].due_date
            loan.next_payment_date = schedule_entries[0].due_date
            loan.save()
        return schedule_entries

    @classmethod
    def create_reducing_balance_schedule(cls, loan: Loan) -> List[LoanRepaymentSchedule]:
        monthly_rate = loan.interest_rate / Decimal('100') / Decimal('12')
        months = loan.term_days // 30
        if months <= 0:
            months = 1
        if monthly_rate == Decimal('0'):
            monthly_payment = loan.principal_amount / Decimal(str(months))
        else:
            factor = (Decimal('1') + monthly_rate) ** Decimal(str(months))
            monthly_payment = loan.principal_amount * monthly_rate * factor / (factor - Decimal('1'))
        schedule_entries = []
        remaining_balance = loan.principal_amount
        current_date = loan.disbursement_date
        for i in range(1, months + 1):
            due_date = current_date + relativedelta(months=1)
            interest_amount = remaining_balance * monthly_rate
            principal_amount = monthly_payment - interest_amount
            if principal_amount < Decimal('0'):
                principal_amount = Decimal('0')
            remaining_balance -= principal_amount
            if i == months:
                principal_amount += remaining_balance
                remaining_balance = Decimal('0')
            total_amount = principal_amount + interest_amount
            schedule_entry = LoanRepaymentSchedule.objects.create(loan=loan, installment_number=i, due_date=due_date, principal_amount=principal_amount.quantize(Decimal('0.01')), interest_amount=interest_amount.quantize(Decimal('0.01')), total_amount=total_amount.quantize(Decimal('0.01')), status='PENDING', grace_period_days=5)
            schedule_entries.append(schedule_entry)
            current_date = due_date
        if schedule_entries:
            loan.first_payment_date = schedule_entries[0].due_date
            loan.next_payment_date = schedule_entries[0].due_date
            loan.save()
        return schedule_entries

    @classmethod
    def reschedule_loan(cls, loan: Loan, new_term_days: int, new_interest_rate: Decimal=None, reschedule_date: datetime.date=None) -> Dict:
        if not reschedule_date:
            reschedule_date = timezone.now().date()
        old_schedule = list(loan.repayment_schedule.all())
        outstanding_principal = loan.remaining_balance
        if new_interest_rate is None:
            new_interest_rate = loan.interest_rate
        loan.term_days = new_term_days
        loan.interest_rate = new_interest_rate
        loan.repayment_schedule.filter(due_date__gt=reschedule_date).delete()
        new_schedule = cls.create_repayment_schedule(loan)
        return {'old_schedule': old_schedule, 'new_schedule': new_schedule, 'outstanding_principal': outstanding_principal, 'new_term_days': new_term_days, 'new_interest_rate': new_interest_rate}

class LateFeeService:

    @classmethod
    def calculate_late_fees(cls, loan: Loan, as_of_date: datetime.date=None) -> Decimal:
        if not as_of_date:
            as_of_date = timezone.now().date()
        total_late_fees = Decimal('0')
        overdue_installments = loan.repayment_schedule.filter(due_date__lt=as_of_date, status__in=['PENDING', 'DUE'])
        for installment in overdue_installments:
            grace_end_date = installment.due_date + datetime.timedelta(days=installment.grace_period_days)
            if as_of_date > grace_end_date:
                days_late = (as_of_date - grace_end_date).days
                overdue_amount = installment.total_amount - installment.total_paid
                if overdue_amount > Decimal('0'):
                    late_fee_rate = loan.loan_product.late_payment_fee_percent / Decimal('100')
                    late_fee = overdue_amount * late_fee_rate
                    total_late_fees += late_fee
        return total_late_fees.quantize(Decimal('0.01'))

    @classmethod
    @transaction.atomic
    def apply_late_fees(cls, loan: Loan, as_of_date: datetime.date=None) -> List[LoanTransaction]:
        if not as_of_date:
            as_of_date = timezone.now().date()
        transactions = []
        overdue_installments = loan.repayment_schedule.filter(due_date__lt=as_of_date, status__in=['PENDING', 'DUE'])
        for installment in overdue_installments:
            grace_end_date = installment.due_date + datetime.timedelta(days=installment.grace_period_days)
            if as_of_date > grace_end_date:
                overdue_amount = installment.total_amount - installment.total_paid
                if overdue_amount > Decimal('0'):
                    late_fee_rate = loan.loan_product.late_payment_fee_percent / Decimal('100')
                    late_fee = overdue_amount * late_fee_rate
                    transaction = LoanTransaction.objects.create(loan=loan, installment=installment, transaction_type='PENALTY_CHARGE', payment_method='SYSTEM', amount=late_fee, fee_amount=late_fee, transaction_date=as_of_date, notes=f'Late fee for installment #{installment.installment_number}', recorded_by=None)
                    transactions.append(transaction)
                    installment.late_fee_applied = True
                    installment.late_fee_amount += late_fee
                    installment.save()
        PaymentProcessingService.update_loan_balances(loan)
        return transactions

class ReportService:

    @classmethod
    def generate_portfolio_report(cls, start_date: datetime.date=None, end_date: datetime.date=None, status_filter: List[str]=None) -> Dict:
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            start_date = end_date - datetime.timedelta(days=30)
        loans = Loan.objects.all()
        if start_date and end_date:
            loans = loans.filter(disbursement_date__range=[start_date, end_date])
        if status_filter:
            loans = loans.filter(status__in=status_filter)
        total_loans = loans.count()
        total_principal = sum((loan.principal_amount for loan in loans))
        total_interest = sum((loan.total_interest_amount for loan in loans))
        total_outstanding = sum((loan.remaining_balance for loan in loans))
        by_product = {}
        for loan in loans:
            product_name = loan.loan_product.name
            if product_name not in by_product:
                by_product[product_name] = {'count': 0, 'principal': Decimal('0'), 'interest': Decimal('0'), 'outstanding': Decimal('0')}
            by_product[product_name]['count'] += 1
            by_product[product_name]['principal'] += loan.principal_amount
            by_product[product_name]['interest'] += loan.total_interest_amount
            by_product[product_name]['outstanding'] += loan.remaining_balance
        by_status = {}
        for loan in loans:
            status = loan.status
            if status not in by_status:
                by_status[status] = {'count': 0, 'principal': Decimal('0'), 'outstanding': Decimal('0')}
            by_status[status]['count'] += 1
            by_status[status]['principal'] += loan.principal_amount
            by_status[status]['outstanding'] += loan.remaining_balance
        return {'period': {'start': start_date, 'end': end_date}, 'summary': {'total_loans': total_loans, 'total_principal': total_principal, 'total_interest': total_interest, 'total_outstanding': total_outstanding, 'average_loan_size': total_principal / total_loans if total_loans > 0 else Decimal('0')}, 'by_product': by_product, 'by_status': by_status, 'generated_at': timezone.now()}

    @classmethod
    def generate_repayment_collection_report(cls, start_date: datetime.date, end_date: datetime.date) -> Dict:
        payments = LoanTransaction.objects.filter(transaction_type__in=['PRINCIPAL_PAYMENT', 'INTEREST_PAYMENT', 'LATE_FEE_PAYMENT'], transaction_date__date__range=[start_date, end_date])
        total_collected = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        by_method = {}
        for payment in payments:
            method = payment.payment_method
            if method not in by_method:
                by_method[method] = Decimal('0')
            by_method[method] += payment.amount
        by_day = {}
        current_date = start_date
        while current_date <= end_date:
            day_payments = payments.filter(transaction_date__date=current_date)
            day_total = day_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
            by_day[current_date.isoformat()] = float(day_total)
            current_date += datetime.timedelta(days=1)
        by_officer = {}
        for payment in payments:
            officer = payment.recorded_by
            if officer:
                officer_name = f'{officer.first_name} {officer.last_name}'
                if officer_name not in by_officer:
                    by_officer[officer_name] = Decimal('0')
                by_officer[officer_name] += payment.amount
        return {'period': {'start': start_date, 'end': end_date}, 'summary': {'total_collected': total_collected, 'total_transactions': payments.count(), 'average_collection': total_collected / (end_date - start_date).days if (end_date - start_date).days > 0 else Decimal('0')}, 'by_method': by_method, 'by_day': by_day, 'by_officer': by_officer, 'generated_at': timezone.now()}

    @classmethod
    def generate_overdue_loans_report(cls, as_of_date: datetime.date=None) -> Dict:
        if not as_of_date:
            as_of_date = timezone.now().date()
        overdue_loans = Loan.objects.filter(status='OVERDUE').select_related('client', 'loan_product')
        report_data = []
        total_overdue = Decimal('0')
        for loan in overdue_loans:
            days_overdue = max(0, (as_of_date - loan.next_payment_date).days) if loan.next_payment_date else 0
            late_fees = LateFeeService.calculate_late_fees(loan, as_of_date)
            report_data.append({'loan_number': loan.loan_number, 'client_name': loan.client.full_account_name, 'client_phone': loan.client.phone_number, 'disbursement_date': loan.disbursement_date, 'due_date': loan.next_payment_date, 'principal': loan.principal_amount, 'overdue_amount': loan.overdue_amount, 'days_overdue': days_overdue, 'late_fees': late_fees, 'loan_officer': f'{loan.loan_officer.first_name} {loan.loan_officer.last_name}'})
            total_overdue += loan.overdue_amount + late_fees
        aging = {'1_30_days': Decimal('0'), '31_60_days': Decimal('0'), '61_90_days': Decimal('0'), 'over_90_days': Decimal('0')}
        for item in report_data:
            days = item['days_overdue']
            amount = item['overdue_amount'] + item['late_fees']
            if days <= 30:
                aging['1_30_days'] += amount
            elif days <= 60:
                aging['31_60_days'] += amount
            elif days <= 90:
                aging['61_90_days'] += amount
            else:
                aging['over_90_days'] += amount
        return {'as_of_date': as_of_date, 'total_overdue_loans': len(report_data), 'total_overdue_amount': total_overdue, 'aging_analysis': aging, 'loans': report_data, 'generated_at': timezone.now()}

class NotificationService:

    @classmethod
    def send_payment_reminder(cls, installment: LoanRepaymentSchedule):
        loan = installment.loan
        client = loan.client
        reminder_sent_today = False
        if not reminder_sent_today:
            sms_message = f'Dear {client.full_account_name}, Your loan payment of {installment.total_amount} for loan {loan.loan_number} is due on {installment.due_date}. Please make payment to avoid late fees.'
            cls.send_sms(client.phone_number, sms_message)
            if hasattr(client, 'email') and client.email:
                email_subject = f'Payment Reminder - Loan {loan.loan_number}'
                email_body = f'\n                Dear {client.full_account_name},\n                \n                This is a reminder that your payment for loan {loan.loan_number} is due.\n                \n                Payment Due: {installment.due_date}\n                Amount Due: {installment.total_amount}\n                Installment: #{installment.installment_number}\n                \n                Please make payment before the due date to avoid late fees.\n                \n                Thank you,\n                Haliqua Investment\n                '
                cls.send_email(client.email, email_subject, email_body)

    @classmethod
    def send_late_payment_notification(cls, installment: LoanRepaymentSchedule, days_late: int):
        loan = installment.loan
        client = loan.client
        late_fee = LateFeeService.calculate_late_fees(loan)
        sms_message = f'Dear {client.full_account_name}, Your loan payment of {installment.total_amount} for loan {loan.loan_number} is {days_late} days overdue. Late fee: {late_fee}. Please make immediate payment.'
        cls.send_sms(client.phone_number, sms_message)
        loan_officer = loan.loan_officer
        if hasattr(loan_officer, 'phone_number') and loan_officer.phone_number:
            officer_message = f'Loan {loan.loan_number} for {client.full_account_name} is {days_late} days overdue. Amount: {installment.total_amount}'
            cls.send_sms(loan_officer.phone_number, officer_message)

    @classmethod
    def send_sms(cls, phone_number: str, message: str):
        print(f'[SMS to {phone_number}]: {message}')

    @classmethod
    def send_email(cls, email: str, subject: str, body: str):
        from django.core.mail import send_mail
        send_mail(subject, body, 'loans@haliqua.com', [email], fail_silently=False)

def format_currency(amount: Decimal) -> str:
    return f'UGX {amount:,.2f}'

def calculate_age_in_days(date_from: datetime.date) -> int:
    return (timezone.now().date() - date_from).days

def is_valid_phone_number(phone: str) -> bool:
    import re
    pattern = '^(\\+256|0)[7|8][0-9]{8}$'
    return bool(re.match(pattern, phone))

def generate_reference_number(prefix: str='REF') -> str:
    import uuid
    import time
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:6].upper()
    return f'{prefix}-{timestamp}-{unique_id}'
__all__ = ['InterestCalculationService', 'CreditScoringService', 'PaymentProcessingService', 'LoanDisbursementService', 'AmortizationService', 'LateFeeService', 'ReportService', 'NotificationService']