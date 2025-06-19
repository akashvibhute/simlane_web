import logging

from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.generic import FormView

from .forms import ContactForm
from .services import ContactEmailService

logger = logging.getLogger(__name__)


@method_decorator(csrf_protect, name="dispatch")
class ContactView(FormView):
    """View for handling contact form submissions."""

    template_name = "core/contact.html"
    form_class = ContactForm

    def get_form_kwargs(self):
        """Pass the current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Handle successful form submission."""
        try:
            # Save the contact message
            contact_message = form.save()

            # Send notification emails
            notification_sent = ContactEmailService.send_contact_notification(
                contact_message,
            )
            confirmation_sent = ContactEmailService.send_confirmation_email(
                contact_message,
            )

            # Log the submission
            logger.info(
                "Contact form submitted by %s (%s) - Message ID: %s",
                contact_message.name,
                contact_message.email,
                contact_message.pk,
            )

            # Prepare success message
            success_msg = (
                "Thank you for your message! We've received your inquiry and "
                "will respond within 24-48 hours."
            )

            if not confirmation_sent:
                success_msg += (
                    " Note: We couldn't send a confirmation email, "
                    "but your message was received."
                )
                logger.warning(
                    "Confirmation email failed for contact message %s",
                    contact_message.pk,
                )

            if not notification_sent:
                logger.error(
                    "Staff notification email failed for contact message %s",
                    contact_message.pk,
                )

            messages.success(self.request, success_msg)

            # Redirect to contact page with success message
            return redirect("core:contact_success")

        except Exception:
            logger.exception("Error processing contact form submission")
            messages.error(
                self.request,
                (
                    "We're sorry, but there was an error processing your message. "
                    "Please try again or contact us directly."
                ),
            )
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Handle form validation errors."""
        logger.warning("Contact form submission failed validation: %s", form.errors)
        messages.error(
            self.request,
            "Please correct the errors below and try again.",
        )
        return super().form_invalid(form)


def contact_success(request):
    """Success page after contact form submission."""
    return render(request, "core/contact_success.html")


def contact_view(request):
    """Function-based view for contact form with HTMX support."""
    if request.method == "POST":
        form = ContactForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                # Save the contact message
                contact_message = form.save()

                # Send notification emails
                notification_sent = ContactEmailService.send_contact_notification(
                    contact_message,
                )
                confirmation_sent = ContactEmailService.send_confirmation_email(
                    contact_message,
                )

                # Log the submission
                logger.info(
                    "Contact form submitted by %s (%s) - Message ID: %s",
                    contact_message.name,
                    contact_message.email,
                    contact_message.pk,
                )

                # Prepare success message
                success_msg = (
                    "Thank you for your message! We've received your inquiry and "
                    "will respond within 24-48 hours."
                )

                if not confirmation_sent:
                    success_msg += (
                        " Note: We couldn't send a confirmation email, "
                        "but your message was received."
                    )
                    logger.warning(
                        "Confirmation email failed for contact message %s",
                        contact_message.pk,
                    )

                if not notification_sent:
                    logger.error(
                        "Staff notification email failed for contact message %s",
                        contact_message.pk,
                    )

                messages.success(request, success_msg)

                # For HTMX requests, return partial template with fresh form
                if request.htmx:
                    # Return a fresh form for the next submission
                    form = ContactForm(user=request.user)
                    return render(
                        request,
                        "core/contact_form_partial.html",
                        {"form": form},
                    )

                # Regular redirect for non-HTMX requests
                return redirect("core:contact")

            except Exception:
                logger.exception("Error processing contact form submission")
                messages.error(
                    request,
                    (
                        "We're sorry, but there was an error processing your message. "
                        "Please try again or contact us directly."
                    ),
                )
        else:
            messages.error(
                request,
                "Please correct the errors below and try again.",
            )

        # For HTMX requests with form errors, return partial template
        if request.htmx:
            return render(request, "core/contact_form_partial.html", {"form": form})
    else:
        form = ContactForm(user=request.user)

    # Handle different types of HTMX requests
    if request.htmx:
        # Navigation request - return content partial (page content without nav)
        return render(request, "core/contact_content_partial.html", {"form": form})

    # Direct page visit - return full page with base template
    return render(request, "core/contact.html", {"form": form})


def htmx_static_page_view(template_name):
    """Factory function to create HTMX-aware static page views."""

    def view(request):
        if request.htmx:
            # For HTMX requests, return only the content block from the template
            # We'll create a simple approach - render the template and extract content
            return render(request, template_name)
        return render(request, template_name)

    return view


def home_view(request):
    """Home page view that handles HTMX requests."""
    # If this is an HTMX request for navigation, return content partial
    if request.htmx:
        return render(request, "core/home_content_partial.html")

    # Otherwise return the full page
    return render(request, "core/home.html")


def about_view(request):
    """About page view that handles HTMX requests."""
    # If this is an HTMX request for navigation, return content partial
    if request.htmx:
        return render(request, "core/about_content_partial.html")

    # Otherwise return the full page
    return render(request, "core/about.html")


def privacy_view(request):
    """Privacy page view that handles HTMX requests."""
    # If this is an HTMX request for navigation, return content partial
    if request.htmx:
        return render(request, "core/privacy_content_partial.html")

    # Otherwise return the full page
    return render(request, "core/privacy.html")


def terms_view(request):
    """Terms page view that handles HTMX requests."""
    # If this is an HTMX request for navigation, return content partial
    if request.htmx:
        return render(request, "core/terms_content_partial.html")

    # Otherwise return the full page
    return render(request, "core/terms.html")
