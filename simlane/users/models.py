import zoneinfo

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import CharField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


def get_timezone_choices():
    """Get timezone choices using zoneinfo.available_timezones()"""
    # Get common timezones and format them for display
    common_timezones = [
        "UTC",
        "US/Eastern",
        "US/Central",
        "US/Mountain",
        "US/Pacific",
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Europe/Rome",
        "Europe/Madrid",
        "Asia/Tokyo",
        "Asia/Shanghai",
        "Asia/Kolkata",
        "Asia/Dubai",
        "Australia/Sydney",
        "Australia/Melbourne",
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "America/Toronto",
        "America/Vancouver",
        "America/Mexico_City",
        "America/Sao_Paulo",
        "Africa/Cairo",
        "Africa/Johannesburg",
    ]

    # Validate that all timezones are available and create choices
    choices = []
    for tz in common_timezones:
        try:
            # Validate timezone exists
            zoneinfo.ZoneInfo(tz)
            # Create display name
            display_name = tz.replace("_", " ").replace("/", " - ")
            choices.append((tz, display_name))
        except zoneinfo.ZoneInfoNotFoundError:
            # Skip invalid timezones
            continue

    return choices


class User(AbstractUser):
    """
    Default custom user model for SimLane.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]

    profile_image = models.ImageField(
        upload_to="user_profiles/",
        blank=True,
        null=True,
        help_text="Profile image for the user account",
    )

    timezone = models.CharField(
        _("Timezone"),
        max_length=50,
        choices=get_timezone_choices(),
        default="UTC",
        help_text=_("Your preferred timezone for displaying dates and times"),
    )

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"username": self.username})

    def get_timezone_info(self):
        """Get zoneinfo.ZoneInfo object for user's timezone"""
        try:
            return zoneinfo.ZoneInfo(self.timezone)
        except zoneinfo.ZoneInfoNotFoundError:
            # Fallback to UTC if timezone is invalid
            return zoneinfo.ZoneInfo("UTC")
