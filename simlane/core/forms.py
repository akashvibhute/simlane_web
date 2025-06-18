from django import forms
from django.core.exceptions import ValidationError

from .models import ContactMessage

# Constants for validation
MIN_MESSAGE_LENGTH = 10
VALIDATION_MESSAGES = {
    "message_too_short": (
        "Please provide a more detailed message (at least 10 characters)."
    ),
    "spam_detected": "Your message contains content that appears to be spam.",
    "invalid_email": "Please use a valid email address.",
}


class ContactForm(forms.ModelForm):
    """Form for submitting contact messages."""

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "platform", "message"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": (
                        "w-full px-4 py-3 border border-gray-300 rounded-lg "
                        "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 "
                        "transition-colors"
                    ),
                    "placeholder": "Your full name",
                },
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": (
                        "w-full px-4 py-3 border border-gray-300 rounded-lg "
                        "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 "
                        "transition-colors"
                    ),
                    "placeholder": "your.email@example.com",
                },
            ),
            "subject": forms.Select(
                attrs={
                    "class": (
                        "w-full px-4 py-3 border border-gray-300 rounded-lg "
                        "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 "
                        "transition-colors"
                    ),
                },
            ),
            "platform": forms.Select(
                attrs={
                    "class": (
                        "w-full px-4 py-3 border border-gray-300 rounded-lg "
                        "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 "
                        "transition-colors"
                    ),
                },
            ),
            "message": forms.Textarea(
                attrs={
                    "class": (
                        "w-full px-4 py-3 border border-gray-300 rounded-lg "
                        "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 "
                        "transition-colors resize-vertical"
                    ),
                    "rows": 6,
                    "placeholder": "Please provide details about your inquiry...",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Pre-fill name and email if user is authenticated
        if self.user and self.user.is_authenticated:
            self.fields["name"].initial = (
                self.user.get_full_name() or self.user.username
            )
            self.fields["email"].initial = self.user.email

    def clean_message(self):
        """Validate message length and content."""
        message = self.cleaned_data.get("message")
        if message:
            # Minimum length check
            if len(message.strip()) < MIN_MESSAGE_LENGTH:
                msg = VALIDATION_MESSAGES["message_too_short"]
                raise ValidationError(msg)

            # Basic spam detection
            spam_indicators = ["buy now", "click here", "free money", "lottery winner"]
            message_lower = message.lower()
            for indicator in spam_indicators:
                if indicator in message_lower:
                    msg = VALIDATION_MESSAGES["spam_detected"]
                    raise ValidationError(msg)

        return message

    def clean_email(self):
        """Additional email validation."""
        email = self.cleaned_data.get("email")
        if email:
            # Basic domain validation
            blocked_domains = ["tempmail.com", "10minutemail.com", "guerrillamail.com"]
            domain = email.split("@")[-1].lower()
            if domain in blocked_domains:
                msg = VALIDATION_MESSAGES["invalid_email"]
                raise ValidationError(msg)

        return email

    def save(self, commit=True):  # noqa: FBT002
        """Save the contact message with optional user association."""
        instance = super().save(commit=False)

        # Associate with user if authenticated
        if self.user and self.user.is_authenticated:
            instance.user = self.user

        if commit:
            instance.save()

        return instance
