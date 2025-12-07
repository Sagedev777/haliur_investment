from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone


class NotificationService:
    """Service for sending notifications related to loans"""
    
    @staticmethod
    def send_loan_approval_notification(loan):
        """
        Send notification when a loan is approved
        
        Args:
            loan: Loan instance
            
        Returns:
            bool: Success status
        """
        try:
            client = loan.client
            
            subject = f'Loan Approved - {loan.loan_number}'
            message = f"""
Dear {client.person1_first_name} {client.person1_last_name},

Your loan application ({loan.loan_number}) has been approved!

Loan Details:
- Amount: {loan.principal_amount}
- Interest Rate: {loan.interest_rate}%
- Term: {loan.term_months} months
- Monthly Payment: {loan.monthly_payment}

Please contact us to arrange disbursement.

Best regards,
Haliur Investments
            """
            
            # Send email if client has email
            if hasattr(client, 'email') and client.email:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [client.email],
                    fail_silently=True,
                )
            
            # Send SMS if client has phone
            if client.person1_contact:
                NotificationService.send_sms(
                    client.person1_contact,
                    f"Your loan {loan.loan_number} has been approved for {loan.principal_amount}. Contact us for disbursement."
                )
            
            return True
        except Exception as e:
            print(f"Error sending loan approval notification: {e}")
            return False
    
    @staticmethod
    def send_loan_rejection_notification(loan, reason=''):
        """
        Send notification when a loan is rejected
        
        Args:
            loan: Loan instance
            reason: Rejection reason
            
        Returns:
            bool: Success status
        """
        try:
            client = loan.client
            
            subject = f'Loan Application Update - {loan.loan_number}'
            message = f"""
Dear {client.person1_first_name} {client.person1_last_name},

We regret to inform you that your loan application ({loan.loan_number}) could not be approved at this time.

{f'Reason: {reason}' if reason else ''}

You may reapply after addressing the issues or contact us for more information.

Best regards,
Haliur Investments
            """
            
            if hasattr(client, 'email') and client.email:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [client.email],
                    fail_silently=True,
                )
            
            return True
        except Exception as e:
            print(f"Error sending loan rejection notification: {e}")
            return False
    
    @staticmethod
    def send_payment_reminder(loan, days_until_due=7):
        """
        Send payment reminder notification
        
        Args:
            loan: Loan instance
            days_until_due: Number of days until payment is due
            
        Returns:
            bool: Success status
        """
        try:
            client = loan.client
            
            subject = f'Payment Reminder - {loan.loan_number}'
            message = f"""
Dear {client.person1_first_name} {client.person1_last_name},

This is a reminder that your loan payment is due in {days_until_due} days.

Loan Number: {loan.loan_number}
Next Payment Date: {loan.next_payment_date}
Payment Amount: {loan.monthly_payment}

Please ensure payment is made on time to avoid late fees.

Best regards,
Haliur Investments
            """
            
            if hasattr(client, 'email') and client.email:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [client.email],
                    fail_silently=True,
                )
            
            if client.person1_contact:
                NotificationService.send_sms(
                    client.person1_contact,
                    f"Reminder: Loan {loan.loan_number} payment of {loan.monthly_payment} due in {days_until_due} days."
                )
            
            return True
        except Exception as e:
            print(f"Error sending payment reminder: {e}")
            return False
    
    @staticmethod
    def send_overdue_notification(loan, days_overdue):
        """
        Send overdue payment notification
        
        Args:
            loan: Loan instance
            days_overdue: Number of days payment is overdue
            
        Returns:
            bool: Success status
        """
        try:
            client = loan.client
            
            subject = f'URGENT: Overdue Payment - {loan.loan_number}'
            message = f"""
Dear {client.person1_first_name} {client.person1_last_name},

Your loan payment is now {days_overdue} days overdue.

Loan Number: {loan.loan_number}
Due Date: {loan.next_payment_date}
Amount Due: {loan.monthly_payment}
Outstanding Balance: {loan.outstanding_balance}

Late fees may apply. Please make payment immediately to avoid further penalties.

Contact us immediately to discuss payment arrangements.

Best regards,
Haliur Investments
            """
            
            if hasattr(client, 'email') and client.email:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [client.email],
                    fail_silently=True,
                )
            
            if client.person1_contact:
                NotificationService.send_sms(
                    client.person1_contact,
                    f"URGENT: Loan {loan.loan_number} payment is {days_overdue} days overdue. Pay {loan.monthly_payment} now."
                )
            
            return True
        except Exception as e:
            print(f"Error sending overdue notification: {e}")
            return False
    
    @staticmethod
    def send_payment_confirmation(payment):
        """
        Send payment confirmation notification
        
        Args:
            payment: LoanPayment instance
            
        Returns:
            bool: Success status
        """
        try:
            loan = payment.loan
            client = loan.client
            
            subject = f'Payment Received - {loan.loan_number}'
            message = f"""
Dear {client.person1_first_name} {client.person1_last_name},

We have received your payment. Thank you!

Payment Details:
- Loan Number: {loan.loan_number}
- Payment Amount: {payment.amount}
- Payment Date: {payment.payment_date}
- Reference: {payment.reference_number}
- Remaining Balance: {loan.outstanding_balance}

Best regards,
Haliur Investments
            """
            
            if hasattr(client, 'email') and client.email:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [client.email],
                    fail_silently=True,
                )
            
            if client.person1_contact:
                NotificationService.send_sms(
                    client.person1_contact,
                    f"Payment of {payment.amount} received for loan {loan.loan_number}. Balance: {loan.outstanding_balance}"
                )
            
            return True
        except Exception as e:
            print(f"Error sending payment confirmation: {e}")
            return False
    
    @staticmethod
    def send_sms(phone_number, message):
        """
        Send SMS notification
        
        Args:
            phone_number: Recipient phone number
            message: SMS message
            
        Returns:
            bool: Success status
        """
        try:
            # TODO: Integrate with SMS gateway (Twilio, Africa's Talking, etc.)
            # For now, just log the SMS
            print(f"SMS to {phone_number}: {message}")
            return True
        except Exception as e:
            print(f"Error sending SMS: {e}")
            return False
    
    @staticmethod
    def send_bulk_reminders(loans):
        """
        Send payment reminders to multiple loans
        
        Args:
            loans: QuerySet of Loan instances
            
        Returns:
            dict: Summary of sent notifications
        """
        success_count = 0
        failed_count = 0
        
        for loan in loans:
            if loan.next_payment_date:
                days_until_due = (loan.next_payment_date - timezone.now().date()).days
                
                if NotificationService.send_payment_reminder(loan, days_until_due):
                    success_count += 1
                else:
                    failed_count += 1
        
        return {
            'total': loans.count(),
            'success': success_count,
            'failed': failed_count
        }