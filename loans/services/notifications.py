from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class NotificationService:

    @staticmethod
    def send_loan_approval_notification(loan):
        try:
            client = loan.client
            subject = f'Loan Approved - {loan.loan_number}'
            message = f'\nDear {client.person1_first_name} {client.person1_last_name},\n\nYour loan application ({loan.loan_number}) has been approved!\n\nLoan Details:\n- Amount: {loan.principal_amount}\n- Interest Rate: {loan.interest_rate}%\n- Term: {loan.term_months} months\n- Monthly Payment: {loan.monthly_payment}\n\nPlease contact us to arrange disbursement.\n\nBest regards,\nHaliur Investments\n            '
            if hasattr(client, 'email') and client.email:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [client.email], fail_silently=True)
            if client.person1_contact:
                NotificationService.send_sms(client.person1_contact, f'Your loan {loan.loan_number} has been approved for {loan.principal_amount}. Contact us for disbursement.')
            return True
        except Exception as e:
            logger.error(f'Error sending loan approval notification: {e}')
            return False

    @staticmethod
    def send_loan_rejection_notification(loan, reason=''):
        try:
            client = loan.client
            subject = f'Loan Application Update - {loan.loan_number}'
            message = f"\nDear {client.person1_first_name} {client.person1_last_name},\n\nWe regret to inform you that your loan application ({loan.loan_number}) could not be approved at this time.\n\n{(f'Reason: {reason}' if reason else '')}\n\nYou may reapply after addressing the issues or contact us for more information.\n\nBest regards,\nHaliur Investments\n            "
            if hasattr(client, 'email') and client.email:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [client.email], fail_silently=True)
            return True
        except Exception as e:
            logger.error(f'Error sending loan rejection notification: {e}')
            return False

    @staticmethod
    def send_payment_reminder(loan, days_until_due=7):
        try:
            client = loan.client
            subject = f'Payment Reminder - {loan.loan_number}'
            message = f'\nDear {client.person1_first_name} {client.person1_last_name},\n\nThis is a reminder that your loan payment is due in {days_until_due} days.\n\nLoan Number: {loan.loan_number}\nNext Payment Date: {loan.next_payment_date}\nPayment Amount: {loan.monthly_payment}\n\nPlease ensure payment is made on time to avoid late fees.\n\nBest regards,\nHaliur Investments\n            '
            if hasattr(client, 'email') and client.email:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [client.email], fail_silently=True)
            if client.person1_contact:
                NotificationService.send_sms(client.person1_contact, f'Reminder: Loan {loan.loan_number} payment of {loan.monthly_payment} due in {days_until_due} days.')
            return True
        except Exception as e:
            logger.error(f'Error sending payment reminder: {e}')
            return False

    @staticmethod
    def send_overdue_notification(loan, days_overdue):
        try:
            client = loan.client
            subject = f'URGENT: Overdue Payment - {loan.loan_number}'
            message = f'\nDear {client.person1_first_name} {client.person1_last_name},\n\nYour loan payment is now {days_overdue} days overdue.\n\nLoan Number: {loan.loan_number}\nDue Date: {loan.next_payment_date}\nAmount Due: {loan.monthly_payment}\nOutstanding Balance: {loan.outstanding_balance}\n\nLate fees may apply. Please make payment immediately to avoid further penalties.\n\nContact us immediately to discuss payment arrangements.\n\nBest regards,\nHaliur Investments\n            '
            if hasattr(client, 'email') and client.email:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [client.email], fail_silently=True)
            if client.person1_contact:
                NotificationService.send_sms(client.person1_contact, f'URGENT: Loan {loan.loan_number} payment is {days_overdue} days overdue. Pay {loan.monthly_payment} now.')
            return True
        except Exception as e:
            logger.error(f'Error sending overdue notification: {e}')
            return False

    @staticmethod
    def send_payment_confirmation(payment):
        try:
            loan = payment.loan
            client = loan.client
            subject = f'Payment Received - {loan.loan_number}'
            message = f'\nDear {client.person1_first_name} {client.person1_last_name},\n\nWe have received your payment. Thank you!\n\nPayment Details:\n- Loan Number: {loan.loan_number}\n- Payment Amount: {payment.amount}\n- Payment Date: {payment.payment_date}\n- Reference: {payment.reference_number}\n- Remaining Balance: {loan.outstanding_balance}\n\nBest regards,\nHaliur Investments\n            '
            if hasattr(client, 'email') and client.email:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [client.email], fail_silently=True)
            if client.person1_contact:
                NotificationService.send_sms(client.person1_contact, f'Payment of {payment.amount} received for loan {loan.loan_number}. Balance: {loan.outstanding_balance}')
            return True
        except Exception as e:
            logger.error(f'Error sending payment confirmation: {e}')
            return False

    @staticmethod
    def send_sms(phone_number, message):
        try:
            # Mock SMS sending
            logger.info(f'SMS to {phone_number}: {message}')
            return True
        except Exception as e:
            logger.error(f'Error sending SMS: {e}')
            return False

    @staticmethod
    def send_bulk_reminders(loans):
        success_count = 0
        failed_count = 0
        for loan in loans:
            if loan.next_payment_date:
                days_until_due = (loan.next_payment_date - timezone.now().date()).days
                if NotificationService.send_payment_reminder(loan, days_until_due):
                    success_count += 1
                else:
                    failed_count += 1
        return {'total': loans.count(), 'success': success_count, 'failed': failed_count}