from django import template
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string

register = template.Library()


@register.simple_tag
def get_club_subscription(club):
    """
    Retrieve subscription information for a club.
    Returns the ClubSubscription object or None if no subscription exists.
    
    Usage: {% get_club_subscription club as subscription %}
    """
    try:
        from simlane.billing.models import ClubSubscription
        return ClubSubscription.objects.select_related('plan').get(
            club=club,
            status__in=['active', 'trialing', 'past_due']
        )
    except ClubSubscription.DoesNotExist:
        return None
    except Exception:
        # Handle case where billing models don't exist yet
        return None


@register.simple_tag
def subscription_feature_enabled(club, feature_name):
    """
    Check if a specific feature is enabled for a club's subscription.
    
    Usage: {% subscription_feature_enabled club 'race_planning' %}
    """
    try:
        from simlane.billing.models import ClubSubscription
        
        subscription = ClubSubscription.objects.select_related('plan').filter(
            club=club,
            status__in=['active', 'trialing', 'past_due']
        ).first()
        
        if not subscription:
            # No subscription means Free plan - only basic features
            return feature_name in ['basic_club_management', 'member_management']
        
        # Check if feature is in the plan's features
        plan_features = subscription.plan.get_features()
        return feature_name in plan_features
        
    except Exception:
        # Handle case where billing models don't exist yet
        # Default to allowing basic features
        return feature_name in ['basic_club_management', 'member_management']


@register.inclusion_tag('billing/components/subscription_usage_bar.html', takes_context=True)
def subscription_usage_bar(context, club):
    """
    Display a usage bar showing member count vs subscription limits.
    
    Usage: {% subscription_usage_bar club %}
    """
    try:
        from simlane.billing.models import ClubSubscription
        
        # Get current member count
        member_count = club.members.filter(role__in=['admin', 'teams_manager', 'member']).count()
        
        # Get subscription info
        subscription = ClubSubscription.objects.select_related('plan').filter(
            club=club,
            status__in=['active', 'trialing', 'past_due']
        ).first()
        
        if subscription:
            max_members = subscription.plan.max_members
            plan_name = subscription.plan.name
            is_unlimited = max_members == -1
        else:
            # Default to Free plan limits
            max_members = 5
            plan_name = "Free"
            is_unlimited = False
        
        # Calculate usage percentage
        if is_unlimited:
            usage_percentage = 0
            usage_class = "success"
        else:
            usage_percentage = min((member_count / max_members) * 100, 100)
            if usage_percentage >= 90:
                usage_class = "danger"
            elif usage_percentage >= 75:
                usage_class = "warning"
            else:
                usage_class = "success"
        
        return {
            'club': club,
            'subscription': subscription,
            'member_count': member_count,
            'max_members': max_members,
            'plan_name': plan_name,
            'is_unlimited': is_unlimited,
            'usage_percentage': usage_percentage,
            'usage_class': usage_class,
            'is_over_limit': member_count > max_members if not is_unlimited else False,
            'request': context.get('request'),
        }
        
    except Exception:
        # Fallback for when billing system isn't set up yet
        member_count = club.members.count()
        return {
            'club': club,
            'subscription': None,
            'member_count': member_count,
            'max_members': 5,
            'plan_name': "Free",
            'is_unlimited': False,
            'usage_percentage': min((member_count / 5) * 100, 100),
            'usage_class': "warning" if member_count > 5 else "success",
            'is_over_limit': member_count > 5,
            'request': context.get('request'),
        }


@register.inclusion_tag('billing/components/upgrade_prompt.html', takes_context=True)
def upgrade_prompt(context, club, feature_name=None, size="normal"):
    """
    Display an upgrade prompt when subscription limits are reached.
    
    Usage: {% upgrade_prompt club %}
    Usage: {% upgrade_prompt club feature_name='race_planning' %}
    Usage: {% upgrade_prompt club size='compact' %}
    """
    try:
        from simlane.billing.models import ClubSubscription, SubscriptionPlan
        
        # Get current subscription
        subscription = ClubSubscription.objects.select_related('plan').filter(
            club=club,
            status__in=['active', 'trialing', 'past_due']
        ).first()
        
        # Get available plans for upgrade
        if subscription:
            current_plan = subscription.plan
            available_plans = SubscriptionPlan.objects.filter(
                is_active=True,
                monthly_price__gt=current_plan.monthly_price
            ).order_by('monthly_price')
        else:
            current_plan = None
            available_plans = SubscriptionPlan.objects.filter(
                is_active=True
            ).exclude(name__iexact='free').order_by('monthly_price')
        
        # Determine the reason for upgrade prompt
        member_count = club.members.count()
        max_members = current_plan.max_members if current_plan else 5
        
        reasons = []
        if feature_name:
            if feature_name == 'race_planning':
                reasons.append("Access race planning and strategy tools")
            elif feature_name == 'advanced_analytics':
                reasons.append("View detailed analytics and reports")
            else:
                reasons.append(f"Access {feature_name.replace('_', ' ').title()}")
        
        if max_members != -1 and member_count >= max_members:
            reasons.append(f"Add more than {max_members} members")
        
        # Get the recommended plan (next tier up)
        recommended_plan = available_plans.first() if available_plans.exists() else None
        
        return {
            'club': club,
            'current_subscription': subscription,
            'current_plan': current_plan,
            'recommended_plan': recommended_plan,
            'available_plans': available_plans,
            'feature_name': feature_name,
            'reasons': reasons,
            'size': size,
            'member_count': member_count,
            'max_members': max_members,
            'request': context.get('request'),
        }
        
    except Exception:
        # Fallback when billing system isn't available
        return {
            'club': club,
            'current_subscription': None,
            'current_plan': None,
            'recommended_plan': None,
            'available_plans': [],
            'feature_name': feature_name,
            'reasons': ["Upgrade to unlock premium features"],
            'size': size,
            'member_count': club.members.count(),
            'max_members': 5,
            'request': context.get('request'),
        }


@register.simple_tag
def subscription_status_class(subscription):
    """
    Get CSS class for subscription status display.
    
    Usage: {% subscription_status_class subscription %}
    """
    if not subscription:
        return "text-muted"
    
    status_classes = {
        'active': 'text-success',
        'trialing': 'text-info',
        'past_due': 'text-warning',
        'canceled': 'text-danger',
        'unpaid': 'text-danger',
        'incomplete': 'text-warning',
        'incomplete_expired': 'text-danger',
    }
    
    return status_classes.get(subscription.status, 'text-muted')


@register.simple_tag
def subscription_status_text(subscription):
    """
    Get human-readable text for subscription status.
    
    Usage: {% subscription_status_text subscription %}
    """
    if not subscription:
        return "No Subscription"
    
    status_text = {
        'active': 'Active',
        'trialing': 'Trial Period',
        'past_due': 'Payment Overdue',
        'canceled': 'Canceled',
        'unpaid': 'Payment Failed',
        'incomplete': 'Setup Incomplete',
        'incomplete_expired': 'Setup Expired',
    }
    
    return status_text.get(subscription.status, subscription.status.title())


@register.simple_tag
def can_add_members(club):
    """
    Check if club can add more members based on subscription limits.
    
    Usage: {% can_add_members club %}
    """
    try:
        from simlane.billing.models import ClubSubscription
        
        member_count = club.members.count()
        
        subscription = ClubSubscription.objects.select_related('plan').filter(
            club=club,
            status__in=['active', 'trialing', 'past_due']
        ).first()
        
        if subscription:
            max_members = subscription.plan.max_members
            return max_members == -1 or member_count < max_members
        else:
            # Free plan limit
            return member_count < 5
            
    except Exception:
        # Fallback - assume free plan
        return club.members.count() < 5


@register.simple_tag
def members_remaining(club):
    """
    Get number of member slots remaining.
    
    Usage: {% members_remaining club %}
    """
    try:
        from simlane.billing.models import ClubSubscription
        
        member_count = club.members.count()
        
        subscription = ClubSubscription.objects.select_related('plan').filter(
            club=club,
            status__in=['active', 'trialing', 'past_due']
        ).first()
        
        if subscription:
            max_members = subscription.plan.max_members
            if max_members == -1:
                return "Unlimited"
            return max(0, max_members - member_count)
        else:
            # Free plan limit
            return max(0, 5 - member_count)
            
    except Exception:
        # Fallback - assume free plan
        return max(0, 5 - club.members.count())


@register.simple_tag
def subscription_plan_features(plan):
    """
    Get list of features for a subscription plan.
    
    Usage: {% subscription_plan_features plan %}
    """
    if not plan:
        return []
    
    try:
        return plan.get_features()
    except Exception:
        return []


@register.filter
def format_price(amount):
    """
    Format price for display.
    
    Usage: {{ plan.monthly_price|format_price }}
    """
    if amount is None or amount == 0:
        return "Free"
    
    # Convert cents to dollars if needed
    if amount >= 100:
        dollars = amount / 100
        return f"${dollars:.0f}"
    else:
        return f"${amount:.2f}"


@register.simple_tag(takes_context=True)
def billing_checkout_url(context, club, plan_id):
    """
    Generate URL for starting checkout process.
    
    Usage: {% billing_checkout_url club plan.id %}
    """
    try:
        from django.urls import reverse
        return reverse('billing:start_checkout', kwargs={
            'club_slug': club.slug,
            'plan_id': plan_id
        })
    except Exception:
        return "#"


@register.simple_tag(takes_context=True)
def billing_dashboard_url(context, club):
    """
    Generate URL for billing dashboard.
    
    Usage: {% billing_dashboard_url club %}
    """
    try:
        from django.urls import reverse
        return reverse('billing:subscription_dashboard', kwargs={
            'club_slug': club.slug
        })
    except Exception:
        return "#"


@register.filter(name='subscription_feature_enabled')
def subscription_feature_enabled_filter(club, feature_name):
    """Filter alias to allow usage `club|subscription_feature_enabled:'feature'`."""
    return subscription_feature_enabled(club, feature_name)