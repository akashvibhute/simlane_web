from django.contrib import admin
from django.forms import ModelForm
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html
from django_celery_beat.admin import PeriodicTaskAdmin as BasePeriodicTaskAdmin
from django_celery_beat.admin import PeriodicTaskForm
from django_celery_beat.admin import TaskSelectWidget

# Django Celery Beat Integration for Unfold
# Based on: https://unfoldadmin.com/docs/integrations/django-celery-beat/
from django_celery_beat.models import ClockedSchedule
from django_celery_beat.models import CrontabSchedule
from django_celery_beat.models import IntervalSchedule
from django_celery_beat.models import PeriodicTask
from django_celery_beat.models import SolarSchedule
from unfold.admin import ModelAdmin
from unfold.widgets import UnfoldAdminSelectWidget
from unfold.widgets import UnfoldAdminTextInputWidget

from .models import ContactMessage

# Unregister the default django-celery-beat admin classes
admin.site.unregister(PeriodicTask)
admin.site.unregister(IntervalSchedule)
admin.site.unregister(CrontabSchedule)
admin.site.unregister(SolarSchedule)
admin.site.unregister(ClockedSchedule)


class UnfoldTaskSelectWidget(UnfoldAdminSelectWidget, TaskSelectWidget):
    pass


class UnfoldPeriodicTaskForm(PeriodicTaskForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["task"].widget = UnfoldAdminTextInputWidget()
        self.fields["regtask"].widget = UnfoldTaskSelectWidget()


class UnfoldCompatibleForm(ModelForm):
    """Form that strips out Unfold-specific kwargs."""

    def __init__(self, *args, **kwargs):
        # Remove Unfold-specific kwargs that ModelForm doesn't expect
        kwargs.pop("request", None)
        super().__init__(*args, **kwargs)


class UnfoldBaseInlineFormSet(BaseInlineFormSet):
    """Custom formset that handles Unfold's additional parameters."""

    def __init__(self, *args, **kwargs):
        # Remove Unfold-specific kwargs that BaseInlineFormSet doesn't expect
        kwargs.pop("request", None)
        super().__init__(*args, **kwargs)


class IntervalScheduleForm(UnfoldCompatibleForm):
    """Custom form for IntervalSchedule that works with Unfold popups."""

    class Meta:
        model = IntervalSchedule
        fields = "__all__"


@admin.register(PeriodicTask)
class PeriodicTaskAdmin(BasePeriodicTaskAdmin, ModelAdmin):
    form = UnfoldPeriodicTaskForm

    def get_formsets_with_inlines(self, request, obj=None):
        """Override to handle Unfold compatibility."""
        for inline in self.get_inline_instances(request, obj):
            # Set custom formset for compatibility
            if hasattr(inline, "formset"):
                inline.formset = UnfoldBaseInlineFormSet
            yield inline.get_formset(request, obj), inline


@admin.register(IntervalSchedule)
class IntervalScheduleAdmin(ModelAdmin):
    form = IntervalScheduleForm
    list_display = ["every", "period"]
    list_filter = ["period"]
    search_fields = ["every"]


class CrontabScheduleForm(UnfoldCompatibleForm):
    """Custom form for CrontabSchedule that works with Unfold popups."""

    class Meta:
        model = CrontabSchedule
        fields = "__all__"


class SolarScheduleForm(UnfoldCompatibleForm):
    """Custom form for SolarSchedule that works with Unfold popups."""

    class Meta:
        model = SolarSchedule
        fields = "__all__"


class ClockedScheduleForm(UnfoldCompatibleForm):
    """Custom form for ClockedSchedule that works with Unfold popups."""

    class Meta:
        model = ClockedSchedule
        fields = "__all__"


@admin.register(CrontabSchedule)
class CrontabScheduleAdmin(ModelAdmin):
    form = CrontabScheduleForm
    list_display = [
        "minute",
        "hour",
        "day_of_week",
        "day_of_month",
        "month_of_year",
        "timezone",
    ]
    list_filter = ["timezone"]
    search_fields = ["minute", "hour", "day_of_week", "day_of_month", "month_of_year"]


@admin.register(SolarSchedule)
class SolarScheduleAdmin(ModelAdmin):
    form = SolarScheduleForm
    list_display = ["event", "latitude", "longitude"]
    search_fields = ["event", "latitude", "longitude"]


@admin.register(ClockedSchedule)
class ClockedScheduleAdmin(ModelAdmin):
    form = ClockedScheduleForm
    list_display = ["clocked_time"]
    list_filter = ["clocked_time"]
    search_fields = ["clocked_time"]


@admin.register(ContactMessage)
class ContactMessageAdmin(ModelAdmin):
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
