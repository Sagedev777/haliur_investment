from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Sum

class PaymentProcessingService:

    @classmethod
    @transaction.atomic
    def process_payment(cls, loan, amount: Decimal, payment_date, payment_method: str, received_by, notes: str='') -> dict:
        if amount <= Decimal('0'):
            raise ValueError('Payment amount must be greater than zero')
        allocation = {'principal': Decimal('0'), 'interest': Decimal('0'), 'late_fees': Decimal('0'), 'transactions': []}
        return allocation

    @classmethod
    def update_loan_balances(cls, loan):
        pass