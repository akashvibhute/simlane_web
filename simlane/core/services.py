import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import ContactMessage

logger = logging.getLogger(__name__)


class ContactEmailService:
    """Service for sending contact form related emails."""

    @staticmethod
    def send_contact_notification(contact_message: ContactMessage) -> bool:
        """
        Send email notification to staff when a new contact message is received.

        Args:
            contact_message: The ContactMessage instance

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            # Determine the appropriate staff email based on subject
            staff_email_map = {
                "support": getattr(settings, "SUPPORT_EMAIL", "support@simlane.app"),
                "privacy": getattr(settings, "PRIVACY_EMAIL", "privacy@simlane.app"),
                "business": getattr(settings, "BUSINESS_EMAIL", "business@simlane.app"),
            }

            to_email = staff_email_map.get(
                contact_message.subject,
                getattr(settings, "CONTACT_EMAIL", "hello@simlane.app"),
            )

            # Prepare email context
            context = {
                "message": contact_message,
                "site_name": "SimLane",
                "admin_url": (
                    f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}"
                    f"/admin/core/contactmessage/{contact_message.pk}/change/"
                ),
            }

            # Render email content
            subject_display = contact_message.get_subject_display()
            subject = f"[SimLane Contact] {subject_display} - {contact_message.name}"
            html_content = render_to_string(
                "core/emails/contact_notification.html",
                context,
            )
            text_content = strip_tags(html_content)

            # Send email
            send_mail(
                subject=subject,
                message=text_content,
                from_email=getattr(
                    settings,
                    "DEFAULT_FROM_EMAIL",
                    "noreply@simlane.app",
                ),
                recipient_list=[to_email],
                html_message=html_content,
                fail_silently=False,
            )

            logger.info("Contact notification sent for message %s", contact_message.pk)
        except Exception:
            logger.exception(
                "Failed to send contact notification for message %s",
                contact_message.pk,
            )
            return False
        else:
            return True

    @staticmethod
    def send_confirmation_email(contact_message: ContactMessage) -> bool:
        """
        Send confirmation email to the user who submitted the contact form.

        Args:
            contact_message: The ContactMessage instance

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            # Prepare email context
            context = {
                "message": contact_message,
                "site_name": "SimLane",
            }

            # Render email content
            subject = "Thank you for contacting SimLane"
            html_content = render_to_string(
                "core/emails/contact_confirmation.html",
                context,
            )
            text_content = strip_tags(html_content)

            # Send email
            send_mail(
                subject=subject,
                message=text_content,
                from_email=getattr(
                    settings,
                    "DEFAULT_FROM_EMAIL",
                    "noreply@simlane.app",
                ),
                recipient_list=[contact_message.email],
                html_message=html_content,
                fail_silently=False,
            )

            logger.info(
                "Contact confirmation sent to %s for message %s",
                contact_message.email,
                contact_message.pk,
            )
        except Exception:
            logger.exception(
                "Failed to send contact confirmation for message %s",
                contact_message.pk,
            )
            return False
        else:
            return True
