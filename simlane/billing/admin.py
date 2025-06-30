from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .models import BillingEventLog, ClubSubscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(ModelAdmin):
    """Admin interface for SubscriptionPlan model."""
    
    list_display = [
        'name',
        'monthly_price_display',
        'max_members_display',
        'is_active',
        'created_at',
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'stripe_price_id']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['monthly_price', 'name']
    
    fieldsets = (
        (_('Plan Details'), {
            'fields': ('name', 'stripe_price_id', 'monthly_price', 'is_active')
        }),
        (_('Limits & Features'), {
            'fields': ('max_members', 'features_json')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def monthly_price_display(self, obj):
        """Display monthly price with currency formatting."""
        if obj.monthly_price == 0:
            return format_html('<span style="color: #10b981; font-weight: bold;">Free</span>')
        return format_html('${:.2f}', obj.monthly_price)
    monthly_price_display.short_description = _('Monthly Price')
    monthly_price_display.admin_order_field = 'monthly_price'
    
    def max_members_display(self, obj):
        """Display max members with unlimited formatting."""
        if obj.max_members == -1:
            return format_html('<span style="color: #9333ea; font-weight: bold;">Unlimited</span>')
        return obj.max_members
    max_members_display.short_description = _('Max Members')
    max_members_display.admin_order_field = 'max_members'


@admin.register(ClubSubscription)
class ClubSubscriptionAdmin(ModelAdmin):
    """Admin interface for ClubSubscription model."""
    
    list_display = [
        'club_name',
        'plan_name',
        'status_display',
        'seats_used_display',
        'current_period_display',
        'created_at',
    ]
    list_filter = [
        'status',
        'plan__name',
        'current_period_start',
        'current_period_end',
        'created_at',
    ]
    search_fields = [
        'club__name',
        'club__slug',
        'stripe_customer_id',
        'stripe_subscription_id',
    ]
    readonly_fields = [
        'stripe_customer_id',
        'stripe_subscription_id',
        'seats_used',
        'created_at',
        'updated_at',
    ]
    raw_id_fields = ['club']
    ordering = ['-created_at']
    
    fieldsets = (
        (_('Subscription Details'), {
            'fields': ('club', 'plan', 'status')
        }),
        (_('Stripe Information'), {
            'fields': ('stripe_customer_id', 'stripe_subscription_id'),
            'classes': ('collapse',)
        }),
        (_('Billing Period'), {
            'fields': ('current_period_start', 'current_period_end')
        }),
        (_('Usage'), {
            'fields': ('seats_used',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def club_name(self, obj):
        """Display club name with link to club admin."""
        if obj.club:
            return format_html(
                '<a href="/admin/teams/club/{}/change/">{}</a>',
                obj.club.id,
                obj.club.name
            )
        return '-'
    club_name.short_description = _('Club')
    club_name.admin_order_field = 'club__name'
    
    def plan_name(self, obj):
        """Display plan name with color coding."""
        if not obj.plan:
            return '-'
        
        color_map = {
            'Free': '#6b7280',  # gray
            'Basic': '#3b82f6',  # blue
            'Pro': '#9333ea',  # purple
        }
        color = color_map.get(obj.plan.name, '#6b7280')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.plan.name
        )
    plan_name.short_description = _('Plan')
    plan_name.admin_order_field = 'plan__name'
    
    def status_display(self, obj):
        """Display subscription status with color coding."""
        status_colors = {
            'active': '#10b981',  # green
            'past_due': '#f59e0b',  # amber
            'canceled': '#ef4444',  # red
            'unpaid': '#ef4444',  # red
            'incomplete': '#6b7280',  # gray
            'incomplete_expired': '#6b7280',  # gray
            'trialing': '#3b82f6',  # blue
        }
        color = status_colors.get(obj.status, '#6b7280')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = _('Status')
    status_display.admin_order_field = 'status'
    
    def seats_used_display(self, obj):
        """Display seats used vs max members."""
        if not obj.plan:
            return '-'
        
        seats_used = obj.seats_used
        max_members = obj.plan.max_members
        
        if max_members == -1:
            return format_html('{} / Unlimited', seats_used)
        
        # Color code based on usage percentage
        usage_percent = (seats_used / max_members) * 100 if max_members > 0 else 0
        
        if usage_percent >= 90:
            color = '#ef4444'  # red
        elif usage_percent >= 75:
            color = '#f59e0b'  # amber
        else:
            color = '#10b981'  # green
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} / {}</span>',
            color,
            seats_used,
            max_members
        )
    seats_used_display.short_description = _('Seats Used')
    
    def current_period_display(self, obj):
        """Display current billing period."""
        if obj.current_period_start and obj.current_period_end:
            return format_html(
                '{} - {}',
                obj.current_period_start.strftime('%Y-%m-%d'),
                obj.current_period_end.strftime('%Y-%m-%d')
            )
        return '-'
    current_period_display.short_description = _('Current Period')


@admin.register(BillingEventLog)
class BillingEventLogAdmin(ModelAdmin):
    """Admin interface for BillingEventLog model."""
    
    list_display = [
        'stripe_event_id',
        'event_type',
        'club_subscription_display',
        'processed_at',
        'created_at',
    ]
    list_filter = [
        'event_type',
        'processed_at',
        'created_at',
    ]
    search_fields = [
        'stripe_event_id',
        'event_type',
        'club_subscription__club__name',
    ]
    readonly_fields = [
        'stripe_event_id',
        'event_type',
        'processed_at',
        'data_json',
        'club_subscription',
        'created_at',
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        (_('Event Details'), {
            'fields': ('stripe_event_id', 'event_type', 'processed_at')
        }),
        (_('Related Subscription'), {
            'fields': ('club_subscription',)
        }),
        (_('Event Data'), {
            'fields': ('data_json',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at',)
        }),
    )
    
    def club_subscription_display(self, obj):
        """Display related club subscription with link."""
        if obj.club_subscription and obj.club_subscription.club:
            return format_html(
                '<a href="/admin/billing/clubsubscription/{}/change/">{}</a>',
                obj.club_subscription.id,
                obj.club_subscription.club.name
            )
        return '-'
    club_subscription_display.short_description = _('Club Subscription')
    
    def has_add_permission(self, request):
        """Disable adding billing event logs manually."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Make billing event logs read-only."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Disable deleting billing event logs."""
        return False