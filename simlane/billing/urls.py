from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    # === SUBSCRIPTION MANAGEMENT ===
    # Club-specific subscription dashboard
    path(
        "<slug:club_slug>/dashboard/",
        views.subscription_dashboard,
        name="subscription_dashboard",
    ),
    
    # Checkout initiation for club subscriptions
    path(
        "<slug:club_slug>/checkout/",
        views.start_checkout,
        name="start_checkout",
    ),
    
    # Post-checkout success and cancel callbacks
    path(
        "<slug:club_slug>/success/",
        views.subscription_success,
        name="subscription_success",
    ),
    path(
        "<slug:club_slug>/cancel/",
        views.subscription_cancel,
        name="subscription_cancel",
    ),
    
    # Upgrade required page when subscription limits are hit
    path(
        "<slug:club_slug>/upgrade-required/",
        views.upgrade_required,
        name="upgrade_required",
    ),
    
    # General upgrade required page (no club context)
    path(
        "upgrade-required/",
        views.upgrade_required,
        name="upgrade_required_general",
    ),
    
    # Generic billing error page
    path(
        "error/",
        views.billing_error,
        name="billing_error",
    ),
    
    # === STRIPE WEBHOOKS ===
    # Webhook endpoint for Stripe to call (no club slug needed)
    path(
        "stripe/webhook/",
        views.stripe_webhook,
        name="stripe_webhook",
    ),
]