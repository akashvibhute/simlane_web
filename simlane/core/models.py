import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
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


class MediaGallery(models.Model):
    """
    Generic gallery model for storing images related to any model.
    Can be used for cars, tracks, events, teams, etc.
    """
    
    GALLERY_TYPE_CHOICES = [
        ("screenshots", "Screenshots"),
        ("photos", "Photos"),
        ("logos", "Logos"),
        ("promotional", "Promotional Images"),
        ("technical", "Technical Diagrams"),
        ("liveries", "Car Liveries"),
        ("track_maps", "Track SVG Maps"),
        ("other", "Other"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Generic foreign key to link to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Gallery details
    gallery_type = models.CharField(
        max_length=20,
        choices=GALLERY_TYPE_CHOICES,
        default="photos",
        help_text="Type of gallery/images"
    )
    image = models.ImageField(
        upload_to="gallery/%Y/%m/",
        help_text="Gallery image file"
    )
    caption = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional image caption"
    )
    order = models.IntegerField(
        default=0,
        help_text="Display order (lower numbers first)"
    )
    
    # Metadata from external APIs
    original_filename = models.CharField(
        max_length=255,
        blank=True,
        help_text="Original filename from external source"
    )
    original_url = models.URLField(
        blank=True,
        help_text="Original URL where image was downloaded from"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id', 'order']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['gallery_type']),
        ]
        verbose_name = "Media Gallery Item"
        verbose_name_plural = "Media Gallery Items"

    def __str__(self):
        return f"{self.content_object} - {self.get_gallery_type_display()} ({self.order})"
