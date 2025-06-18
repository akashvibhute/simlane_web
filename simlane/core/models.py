from django.db import models
from django.utils import timezone


class ContactMessage(models.Model):
    """Model to store contact form submissions."""

    SUBJECT_CHOICES = [
        ("general", "General Inquiry"),
        ("support", "Technical Support"),
        ("feature", "Feature Request"),
        ("bug", "Bug Report"),
        ("account", "Account Issues"),
        ("privacy", "Privacy Concerns"),
        ("business", "Business Inquiry"),
        ("other", "Other"),
    ]

    PLATFORM_CHOICES = [
        ("", "Not specified"),
        ("iracing", "iRacing"),
        ("acc", "Assetto Corsa Competizione"),
        ("rf2", "rFactor 2"),
        ("other", "Other"),
        ("none", "Not applicable"),
    ]

    STATUS_CHOICES = [
        ("new", "New"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    # Contact Information
    name = models.CharField(max_length=100, verbose_name="Full Name")
    email = models.EmailField(verbose_name="Email Address")

    # Message Details
    subject = models.CharField(
        max_length=20,
        choices=SUBJECT_CHOICES,
        verbose_name="Subject",
    )
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        blank=True,
        verbose_name="Racing Platform",
    )
    message = models.TextField(verbose_name="Message")

    # Tracking Information
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    user = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who submitted this message (if authenticated)",
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Admin fields
    admin_notes = models.TextField(blank=True, help_text="Internal notes for staff")
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"

    def __str__(self):
        timestamp = self.created_at.strftime("%Y-%m-%d %H:%M")
        return f"{self.name} - {self.get_subject_display()} ({timestamp})"

    def mark_as_responded(self):
        """Mark the message as responded to."""
        self.responded_at = timezone.now()
        if self.status == "new":
            self.status = "in_progress"
        self.save()

    @property
    def is_responded(self):
        """Check if the message has been responded to."""
        return self.responded_at is not None
