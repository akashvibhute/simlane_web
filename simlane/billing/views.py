import json
import logging
from datetime import datetime

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from simlane.teams.decorators import club_admin_required
from simlane.teams.decorators import club_member_required
from simlane.teams.models import Club

from .models import BillingEventLog
from .models import ClubSubscription
from .models import SubscriptionPlan
from .services import StripeService
from .services import SubscriptionService

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@club_member_required
def subscription_dashboard(request, club_slug):
    """Subscription management dashboard for club members."""
    club = request.club
    
    # Get current subscription
    try:
        subscription = ClubSubscription.objects.get(club=club)
    except ClubSubscription.DoesNotExist:
        # Create a free subscription if none exists
        free_plan = SubscriptionPlan.objects.filter(name="Free").first()
        if free_plan:
            subscription = ClubSubscription.objects.create(
                club=club,
                plan=free_plan,
                status="active"
            )
        else:
            subscription = None

    # Get available plans for upgrade
    available_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('monthly_price')
    
    # Calculate usage
    current_member_count = club.members.count()
    usage_percentage = 0
    if subscription and subscription.plan.max_members > 0:
        usage_percentage = min(100, (current_member_count / subscription.plan.max_members) * 100)
    
    # Get billing history
    billing_events = BillingEventLog.objects.filter(
        club_subscription=subscription
    ).order_by('-processed_at')[:10] if subscription else []

    # Check if user can manage billing
    can_manage_billing = request.club_member.is_admin()

    context = {
        'club': club,
        'subscription': subscription,
        'available_plans': available_plans,
        'current_member_count': current_member_count,
        'usage_percentage': usage_percentage,
        'billing_events': billing_events,
        'can_manage_billing': can_manage_billing,
        'user_role': request.club_member.role,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'billing/subscription_dashboard_partial.html', context)

    return render(request, 'billing/subscription_dashboard.html', context)


@club_admin_required
@require_POST
def start_checkout(request, club_slug):
    """Create Stripe checkout session and redirect to Stripe."""
    club = request.club
    plan_id = request.POST.get('plan_id')
    
    if not plan_id:
        messages.error(request, "No subscription plan selected.")
        return redirect('billing:subscription_dashboard', club_slug=club.slug)

    try:
        plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        messages.error(request, "Invalid subscription plan selected.")
        return redirect('billing:subscription_dashboard', club_slug=club.slug)

    try:
        # Get or create subscription record
        subscription, created = ClubSubscription.objects.get_or_create(
            club=club,
            defaults={
                'plan': plan,
                'status': 'pending'
            }
        )

        # Create Stripe customer if needed
        stripe_service = StripeService()
        if not subscription.stripe_customer_id:
            customer = stripe_service.create_customer(
                email=request.user.email,
                name=club.name,
                metadata={
                    'club_id': str(club.id),
                    'club_name': club.name,
                }
            )
            subscription.stripe_customer_id = customer.id
            subscription.save()

        # Create checkout session
        success_url = request.build_absolute_uri(
            reverse('billing:subscription_success', kwargs={'club_slug': club.slug})
        )
        cancel_url = request.build_absolute_uri(
            reverse('billing:subscription_cancel', kwargs={'club_slug': club.slug})
        )

        checkout_session = stripe_service.create_checkout_session(
            customer_id=subscription.stripe_customer_id,
            price_id=plan.stripe_price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'club_id': str(club.id),
                'subscription_id': str(subscription.id),
                'plan_id': str(plan.id),
            }
        )

        # Log the checkout initiation
        BillingEventLog.objects.create(
            club_subscription=subscription,
            stripe_event_id=f"checkout_created_{checkout_session.id}",
            event_type="checkout.session.created",
            data_json={
                'checkout_session_id': checkout_session.id,
                'plan_name': plan.name,
                'amount': plan.monthly_price,
            }
        )

        return redirect(checkout_session.url)

    except Exception as e:
        logger.error(f"Error creating checkout session for club {club.id}: {str(e)}")
        messages.error(request, "Failed to start checkout process. Please try again.")
        return redirect('billing:subscription_dashboard', club_slug=club.slug)


@club_member_required
def subscription_success(request, club_slug):
    """Handle successful subscription checkout."""
    club = request.club
    session_id = request.GET.get('session_id')

    if session_id:
        try:
            # Retrieve the checkout session from Stripe
            stripe_service = StripeService()
            session = stripe_service.get_checkout_session(session_id)
            
            if session.payment_status == 'paid':
                messages.success(
                    request, 
                    "Payment successful! Your subscription is now active."
                )
            else:
                messages.warning(
                    request,
                    "Payment is being processed. Your subscription will be activated shortly."
                )
        except Exception as e:
            logger.error(f"Error retrieving checkout session {session_id}: {str(e)}")
            messages.info(
                request,
                "Payment completed. Your subscription status will be updated shortly."
            )
    else:
        messages.success(request, "Subscription updated successfully!")

    return redirect('billing:subscription_dashboard', club_slug=club.slug)


@club_member_required
def subscription_cancel(request, club_slug):
    """Handle cancelled subscription checkout."""
    club = request.club
    
    messages.info(request, "Subscription checkout was cancelled. No changes were made.")
    return redirect('billing:subscription_dashboard', club_slug=club.slug)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhook events securely."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    if not endpoint_secret:
        logger.error("Stripe webhook secret not configured")
        return HttpResponse(status=400)

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        logger.error("Invalid payload in Stripe webhook")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook")
        return HttpResponse(status=400)

    # Handle the event
    try:
        stripe_service = StripeService()
        subscription_service = SubscriptionService()
        
        event_type = event['type']
        event_data = event['data']['object']

        # Log the webhook event
        logger.info(f"Received Stripe webhook: {event_type}")

        if event_type == 'checkout.session.completed':
            # Handle successful checkout
            session = event_data
            customer_id = session.get('customer')
            subscription_id = session.get('subscription')
            
            # Find the club subscription
            try:
                club_subscription = ClubSubscription.objects.get(
                    stripe_customer_id=customer_id
                )
                
                # Update subscription with Stripe subscription ID
                if subscription_id:
                    club_subscription.stripe_subscription_id = subscription_id
                    club_subscription.status = 'active'
                    club_subscription.current_period_start = timezone.now()
                    
                    # Get subscription details from Stripe
                    stripe_subscription = stripe_service.get_subscription(subscription_id)
                    if stripe_subscription:
                        club_subscription.current_period_end = datetime.fromtimestamp(
                            stripe_subscription.current_period_end,
                            tz=timezone.utc
                        )
                    
                    club_subscription.save()
                    
                    # Log the event
                    BillingEventLog.objects.create(
                        club_subscription=club_subscription,
                        stripe_event_id=event['id'],
                        event_type=event_type,
                        data_json=event_data
                    )
                    
                    logger.info(f"Activated subscription for club {club_subscription.club.id}")
                
            except ClubSubscription.DoesNotExist:
                logger.error(f"Club subscription not found for customer {customer_id}")

        elif event_type == 'customer.subscription.updated':
            # Handle subscription updates
            subscription = event_data
            subscription_id = subscription['id']
            
            try:
                club_subscription = ClubSubscription.objects.get(
                    stripe_subscription_id=subscription_id
                )
                
                # Update subscription status and period
                club_subscription.status = subscription['status']
                club_subscription.current_period_start = datetime.fromtimestamp(
                    subscription['current_period_start'],
                    tz=timezone.utc
                )
                club_subscription.current_period_end = datetime.fromtimestamp(
                    subscription['current_period_end'],
                    tz=timezone.utc
                )
                club_subscription.save()
                
                # Log the event
                BillingEventLog.objects.create(
                    club_subscription=club_subscription,
                    stripe_event_id=event['id'],
                    event_type=event_type,
                    data_json=event_data
                )
                
                logger.info(f"Updated subscription for club {club_subscription.club.id}")
                
            except ClubSubscription.DoesNotExist:
                logger.error(f"Club subscription not found for subscription {subscription_id}")

        elif event_type == 'customer.subscription.deleted':
            # Handle subscription cancellation
            subscription = event_data
            subscription_id = subscription['id']
            
            try:
                club_subscription = ClubSubscription.objects.get(
                    stripe_subscription_id=subscription_id
                )
                
                # Downgrade to free plan
                free_plan = SubscriptionPlan.objects.filter(name="Free").first()
                if free_plan:
                    club_subscription.plan = free_plan
                    club_subscription.status = 'active'
                    club_subscription.stripe_subscription_id = None
                    club_subscription.save()
                    
                    # Log the event
                    BillingEventLog.objects.create(
                        club_subscription=club_subscription,
                        stripe_event_id=event['id'],
                        event_type=event_type,
                        data_json=event_data
                    )
                    
                    logger.info(f"Downgraded club {club_subscription.club.id} to free plan")
                
            except ClubSubscription.DoesNotExist:
                logger.error(f"Club subscription not found for subscription {subscription_id}")

        elif event_type == 'invoice.payment_failed':
            # Handle failed payments
            invoice = event_data
            subscription_id = invoice.get('subscription')
            
            if subscription_id:
                try:
                    club_subscription = ClubSubscription.objects.get(
                        stripe_subscription_id=subscription_id
                    )
                    
                    club_subscription.status = 'past_due'
                    club_subscription.save()
                    
                    # Log the event
                    BillingEventLog.objects.create(
                        club_subscription=club_subscription,
                        stripe_event_id=event['id'],
                        event_type=event_type,
                        data_json=event_data
                    )
                    
                    logger.warning(f"Payment failed for club {club_subscription.club.id}")
                    
                except ClubSubscription.DoesNotExist:
                    logger.error(f"Club subscription not found for subscription {subscription_id}")

        else:
            # Log unhandled events
            logger.info(f"Unhandled Stripe webhook event: {event_type}")

    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        return HttpResponse(status=500)

    return HttpResponse(status=200)


@login_required
def upgrade_required(request):
    """Show upgrade required page when features are blocked."""
    club_slug = request.GET.get('club_slug')
    feature = request.GET.get('feature', 'this feature')
    
    club = None
    if club_slug:
        try:
            club = Club.objects.get(slug=club_slug)
            # Check if user is a member
            if not club.members.filter(user=request.user).exists():
                return HttpResponseForbidden("You must be a club member to view this page.")
        except Club.DoesNotExist:
            raise Http404("Club not found")

    # Get available plans
    available_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('monthly_price')
    
    # Get current subscription if club exists
    current_subscription = None
    if club:
        try:
            current_subscription = ClubSubscription.objects.get(club=club)
        except ClubSubscription.DoesNotExist:
            pass

    context = {
        'club': club,
        'feature': feature,
        'available_plans': available_plans,
        'current_subscription': current_subscription,
        'title': f'Upgrade Required - {feature.title()}',
    }

    return render(request, 'billing/upgrade_required.html', context)


@club_admin_required
@require_POST
def cancel_subscription(request, club_slug):
    """Cancel the club's subscription."""
    club = request.club
    
    try:
        subscription = ClubSubscription.objects.get(club=club)
        
        if subscription.stripe_subscription_id:
            # Cancel the Stripe subscription
            stripe_service = StripeService()
            stripe_service.cancel_subscription(subscription.stripe_subscription_id)
            
            messages.success(
                request,
                "Subscription cancelled successfully. You will retain access until the end of your billing period."
            )
        else:
            # Already on free plan
            messages.info(request, "You are already on the free plan.")
            
    except ClubSubscription.DoesNotExist:
        messages.error(request, "No active subscription found.")
    except Exception as e:
        logger.error(f"Error cancelling subscription for club {club.id}: {str(e)}")
        messages.error(request, "Failed to cancel subscription. Please try again.")

    return redirect('billing:subscription_dashboard', club_slug=club.slug)


@club_admin_required
def manage_subscription(request, club_slug):
    """Redirect to Stripe customer portal for subscription management."""
    club = request.club
    
    try:
        subscription = ClubSubscription.objects.get(club=club)
        
        if not subscription.stripe_customer_id:
            messages.error(request, "No billing account found. Please contact support.")
            return redirect('billing:subscription_dashboard', club_slug=club.slug)
        
        # Create customer portal session
        stripe_service = StripeService()
        return_url = request.build_absolute_uri(
            reverse('billing:subscription_dashboard', kwargs={'club_slug': club.slug})
        )
        
        portal_session = stripe_service.create_customer_portal_session(
            customer_id=subscription.stripe_customer_id,
            return_url=return_url
        )
        
        return redirect(portal_session.url)
        
    except ClubSubscription.DoesNotExist:
        messages.error(request, "No subscription found.")
        return redirect('billing:subscription_dashboard', club_slug=club.slug)
    except Exception as e:
        logger.error(f"Error creating customer portal session for club {club.id}: {str(e)}")
        messages.error(request, "Failed to access billing portal. Please try again.")
        return redirect('billing:subscription_dashboard', club_slug=club.slug)