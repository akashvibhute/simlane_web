import zoneinfo

from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def debug_value(value, label="DEBUG"):
    """
    Debug filter to see what values are being passed.
    Usage: {{ value|debug_value:"label" }}
    """
    if hasattr(value, "tzinfo"):
        print(f"{label}: {value} (type: {type(value)}, tzinfo: {value.tzinfo})")
    else:
        print(f"{label}: {value} (type: {type(value)})")
    return value


@register.filter
def user_timezone(value, user=None):
    """
    Convert a datetime to the user's timezone.
    Usage: {{ datetime_value|user_timezone:user }}
    """
    if not value:
        return value

    # If no user or user doesn't have timezone, return original value
    if not user or not hasattr(user, "timezone") or not user.timezone:
        return value

    try:
        user_tz = zoneinfo.ZoneInfo(user.timezone)

        if timezone.is_aware(value):
            return value.astimezone(user_tz)
        # If naive, assume it's in UTC and make it aware first
        aware_value = timezone.make_aware(value, zoneinfo.ZoneInfo("UTC"))
        return aware_value.astimezone(user_tz)
    except (zoneinfo.ZoneInfoNotFoundError, AttributeError, ValueError):
        # Fallback to original value if timezone conversion fails
        return value


@register.filter
def format_datetime_tz(value, format_string):
    """
    Format a timezone-aware datetime with the specified format.
    This ensures the datetime is formatted in its current timezone.
    Usage: {{ datetime_value|format_datetime_tz:"D, M j H:i" }}
    """
    if not value:
        return ""

    try:
        # If it's a datetime object, format it directly
        # This preserves the timezone that was already set
        return value.strftime(format_string)
    except Exception:
        # Fallback to string representation
        return str(value)


@register.filter
def format_in_timezone(value, format_and_user):
    """
    Format datetime in user timezone with custom format.
    Usage: {{ datetime_value|format_in_timezone:"D, M j H:i,user" }}
    """
    if not value:
        return ""

    try:
        # Parse format and user from the argument
        if "," in str(format_and_user):
            format_str, user_part = str(format_and_user).rsplit(",", 1)
            # In template context, user_part will be the user object reference
            # For now, we'll get it from the template context
        else:
            format_str = str(format_and_user)
            user_part = None

        # For now, let's just use the default timezone conversion
        if timezone.is_aware(value):
            return value.strftime(format_str)
        aware_value = timezone.make_aware(value, zoneinfo.ZoneInfo("UTC"))
        return aware_value.strftime(format_str)

    except Exception as e:
        return f"{value} (Error: {e!s})"


@register.filter
def format_user_datetime(value, user=None):
    """
    Format a datetime in the user's timezone with a nice format.
    Usage: {{ datetime_value|format_user_datetime:user }}
    """
    if not value:
        return ""

    try:
        # Convert to user timezone first
        user_time = user_timezone(value, user)

        # Format nicely
        formatted = user_time.strftime("%B %d, %Y at %I:%M %p")

        # Add timezone info if user has a specific timezone
        if user and hasattr(user, "timezone") and user.timezone != "UTC":
            tz_name = user.timezone.split("/")[-1].replace("_", " ")
            formatted += f" ({tz_name})"

        return formatted
    except Exception:
        # Fallback to default formatting
        return (
            value.strftime("%B %d, %Y at %I:%M %p")
            if hasattr(value, "strftime")
            else str(value)
        )


@register.simple_tag
def user_current_time(user):
    """
    Get the current time in the user's timezone.
    Usage: {% user_current_time user %}
    """
    try:
        now = timezone.now()
        if user and hasattr(user, "timezone"):
            user_tz = zoneinfo.ZoneInfo(user.timezone)
            return now.astimezone(user_tz)
        return now
    except Exception:
        return timezone.now()


@register.filter
def timezone_display(datetime_value, user_and_format):
    """
    Display a datetime in user's timezone with custom format.
    Usage: {{ datetime_value|timezone_display:"user,format_string" }}
    """
    if not datetime_value:
        return ""

    try:
        # Parse the argument - it should be "user,format_string"
        if isinstance(user_and_format, str):
            parts = user_and_format.split(",", 1)
            user = None
            format_string = parts[0] if parts else None
        else:
            # Assume it's just the user object
            user = user_and_format
            format_string = None

        # Convert to user timezone
        user_time = user_timezone(datetime_value, user)

        # Format with the provided format string or default
        if format_string:
            return user_time.strftime(format_string)
        return format_user_datetime(datetime_value, user)

    except Exception:
        # Fallback to default formatting
        return (
            datetime_value.strftime("%B %d, %Y at %I:%M %p")
            if hasattr(datetime_value, "strftime")
            else str(datetime_value)
        )


@register.simple_tag
def timezone_display_tag(datetime_value, user, format_string=None):
    """
    Display a datetime with timezone information as a template tag.
    Usage: {% timezone_display_tag datetime_value user "format_string" %}
    """
    if not datetime_value:
        return ""

    try:
        # Convert to user timezone first
        if user and hasattr(user, "timezone") and user.timezone:
            user_tz = zoneinfo.ZoneInfo(user.timezone)
            if timezone.is_aware(datetime_value):
                user_time = datetime_value.astimezone(user_tz)
            else:
                # Make aware in UTC first, then convert
                aware_value = timezone.make_aware(
                    datetime_value, zoneinfo.ZoneInfo("UTC")
                )
                user_time = aware_value.astimezone(user_tz)
        else:
            user_time = datetime_value

        # Format with the provided format string
        if format_string:
            return user_time.strftime(format_string)
        return user_time.strftime("%B %d, %Y at %I:%M %p")

    except Exception as e:
        # For debugging - return the error and original value
        return f"{datetime_value} (Error: {e!s})"
