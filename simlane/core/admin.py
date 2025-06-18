from django.contrib import admin
from django.utils.html import format_html

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    """Admin interface for ContactMessage model."""

    list_display = [
        "name",
        "email",
        "subject_display",
        "platform_display",
        "status",
        "created_at",
        "is_responded",
        "user_link",
    ]
    list_filter = [
        "status",
        "subject",
        "platform",
        "created_at",
        "responded_at",
    ]
    search_fields = [
        "name",
        "email",
        "message",
        "user__username",
        "user__email",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "user_link",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Contact Information",
            {
                "fields": ("name", "email", "user_link"),
            },
        ),
        (
            "Message Details",
            {
                "fields": ("subject", "platform", "message"),
            },
        ),
        (
            "Status & Tracking",
            {
                "fields": ("status", "responded_at", "admin_notes"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["mark_as_in_progress", "mark_as_resolved", "mark_as_closed"]

    @admin.display(
        description="Subject",
        ordering="subject",
    )
    def subject_display(self, obj):
        """Display the subject with color coding."""
        colors = {
            "support": "red",
            "bug": "orange",
            "feature": "blue",
            "general": "green",
            "privacy": "purple",
            "business": "indigo",
            "account": "yellow",
            "other": "gray",
        }
        color = colors.get(obj.subject, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_subject_display(),
        )

    @admin.display(
        description="Platform",
        ordering="platform",
    )
    def platform_display(self, obj):
        """Display the platform if specified."""
        if obj.platform:
            return obj.get_platform_display()
        return "-"

    @admin.display(
        description="Responded",
        ordering="responded_at",
    )
    def is_responded(self, obj):
        """Display whether the message has been responded to."""
        if obj.responded_at:
            return format_html(
                '<span style="color: green;">✓ {}</span>',
                obj.responded_at.strftime("%Y-%m-%d %H:%M"),
            )
        return format_html('<span style="color: red;">✗ No</span>')

    @admin.display(
        description="User Account",
        ordering="user__username",
    )
    def user_link(self, obj):
        """Display a link to the user if available."""
        if obj.user:
            return format_html(
                '<a href="/admin/users/user/{}/change/">{}</a>',
                obj.user.pk,
                obj.user.username,
            )
        return "Anonymous"

    @admin.action(
        description="Mark as in progress",
    )
    def mark_as_in_progress(self, request, queryset):
        """Mark selected messages as in progress."""
        queryset.update(status="in_progress")
        self.message_user(
            request,
            f"{queryset.count()} messages marked as in progress.",
        )

    @admin.action(
        description="Mark as resolved",
    )
    def mark_as_resolved(self, request, queryset):
        """Mark selected messages as resolved."""
        queryset.update(status="resolved")
        self.message_user(request, f"{queryset.count()} messages marked as resolved.")

    @admin.action(
        description="Mark as closed",
    )
    def mark_as_closed(self, request, queryset):
        """Mark selected messages as closed."""
        queryset.update(status="closed")
        self.message_user(request, f"{queryset.count()} messages marked as closed.")
