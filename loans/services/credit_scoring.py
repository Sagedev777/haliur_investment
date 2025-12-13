from decimal import Decimal
from django.utils import timezone

class CreditScoringService:

    @classmethod
    def calculate_credit_score(cls, client, loan_amount: Decimal) -> Decimal:
        score = Decimal('70')
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