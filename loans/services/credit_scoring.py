# loans/services/credit_scoring.py
from decimal import Decimal
from django.utils import timezone

class CreditScoringService:
    @classmethod
    def calculate_credit_score(cls, client, loan_amount: Decimal) -> Decimal:
        """Calculate credit score (0-100) for a client."""
        score = Decimal('70')  # Base score - implement full logic later
        return max(Decimal('0'), min(score, Decimal('100'))).quantize(Decimal('0.01'))
    
    @classmethod
    def determine_risk_rating(cls, credit_score: Decimal) -> str:
        """Determine risk rating based on credit score."""
        if credit_score >= Decimal('80'):
            return 'A'
        elif credit_score >= Decimal('60'):
            return 'B'
        elif credit_score >= Decimal('40'):
            return 'C'
        else:
            return 'D'