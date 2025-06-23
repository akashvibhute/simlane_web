"""
Custom math template filters for Django templates.
"""

from django import template

register = template.Library()


@register.filter
def mul(value, arg):
    """Multiply the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def div(value, arg):
    """Divide the value by the argument."""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def mod(value, arg):
    """Return the remainder of value divided by arg."""
    try:
        return float(value) % float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def sub(value, arg):
    """Subtract the argument from the value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def abs_filter(value):
    """Return the absolute value."""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return 0


@register.filter
def round_to(value, arg):
    """Round the value to the specified number of decimal places."""
    try:
        return round(float(value), int(arg))
    except (ValueError, TypeError):
        return 0


@register.filter
def percentage(value, total):
    """Calculate percentage of value relative to total."""
    try:
        if float(total) == 0:
            return 0
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, TypeError):
        return 0
