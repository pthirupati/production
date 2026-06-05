"""
Email Alert System for errors and support notifications.
"""

import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class EmailAlertService:
    """Send alerts and notifications via email."""

    @staticmethod
    def send_payment_error_alert(user, plan_name, error_message, request_payload=None):
        """Send email alert to support when payment fails."""
        try:
            subject = f"[PAYMENT ALERT] Failed payment for {user.email}"
            timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC")

            html_content = f"""
            <h2>Payment Failed Alert</h2>
            <p><strong>Timestamp:</strong> {timestamp}</p>
            <p><strong>User Email:</strong> {user.email}</p>
            <p><strong>User ID:</strong> {user.id}</p>
            <p><strong>Selected Plan:</strong> {plan_name}</p>
            <p><strong>Error Message:</strong> <code>{error_message}</code></p>
            
            <h3>Request Payload:</h3>
            <pre>{request_payload if request_payload else 'N/A'}</pre>
            """

            to_emails = [settings.SUPPORT_EMAIL]
            if hasattr(settings, 'PAYMENT_EMAIL'):
                to_emails.append(settings.PAYMENT_EMAIL)

            msg = EmailMultiAlternatives(
                subject=subject,
                body=f"Payment Error: {error_message}",
                from_email=settings.EMAIL_HOST_USER,
                to=to_emails
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)

            logger.info(f"Payment error alert sent for user {user.id}")

        except Exception as e:
            logger.error(f"Failed to send payment alert email: {e}")

    @staticmethod
    def send_payment_success_email(user, transaction):
        """Send payment success email to user."""
        try:
            subject = "Payment Successful - FixitLab"
            
            html_content = f"""
            <h2>Payment Received!</h2>
            <p>Dear {user.first_name or user.username},</p>
            <p>Your payment has been successfully processed.</p>
            
            <h3>Transaction Details:</h3>
            <ul>
                <li><strong>Transaction ID:</strong> {transaction.id}</li>
                <li><strong>Amount:</strong> ₹{transaction.amount}</li>
                <li><strong>Date:</strong> {transaction.created_at.strftime('%Y-%m-%d %H:%M:%S')}</li>
            </ul>
            
            <p>Thank you for choosing FixitLab!</p>
            """

            msg = EmailMultiAlternatives(
                subject=subject,
                body="Your payment was successful.",
                from_email=settings.EMAIL_HOST_USER,
                to=[user.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)

            logger.info(f"Payment success email sent to {user.email}")

        except Exception as e:
            logger.error(f"Failed to send payment success email: {e}")

    @staticmethod
    def send_gateway_not_configured_alert():
        """Send alert when payment gateway is not configured."""
        try:
            subject = "[CRITICAL] Payment Gateway Not Configured"
            html_content = """
            <h2>Critical Alert: Payment Gateway Missing</h2>
            <p>No payment gateway (Razorpay or Stripe) is configured on this FixitLab instance.</p>
            <p>Users will not be able to make payments. Please configure the payment gateway immediately.</p>
            
            <h3>Configuration Required:</h3>
            <ol>
                <li>Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env, OR</li>
                <li>Set STRIPE_SECRET_KEY in .env</li>
            </ol>
            """

            msg = EmailMultiAlternatives(
                subject=subject,
                body="Payment gateway not configured",
                from_email=settings.EMAIL_HOST_USER,
                to=[settings.PRIMARY_EMAIL]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=True)

            logger.warning("Payment gateway not configured alert sent")

        except Exception as e:
            logger.error(f"Failed to send gateway alert: {e}")
