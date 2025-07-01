from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import UpdateView
from django.utils import timezone
from datetime import timedelta

from simlane.iracing.services import IRacingServiceError
from simlane.iracing.services import iracing_service
from simlane.iracing.client import get_iracing_client
from simlane.sim.models import SimProfile

from .forms import SimProfileForm
from .forms import UserUpdateForm

import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    slug_field = "username"
    slug_url_kwarg = "username"


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self):
        # for mypy to know that the user is authenticated
        assert self.request.user.is_authenticated
        return self.request.user.get_absolute_url()

    def get_object(self):
        return self.request.user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse("users:profile")


user_redirect_view = UserRedirectView.as_view()


def sim_profiles_view(request):
    """View and manage user's sim racing profiles with HTMX support."""
    user_profiles = (
        SimProfile.objects.filter(linked_user=request.user)
        .select_related("simulator")
        .order_by("-created_at")
    )

    context = {
        "user_profiles": user_profiles,
        "title": "My Sim Profiles",
    }

    if request.htmx:
        return render(request, "users/sim_profiles_content_partial.html", context)
    return render(request, "users/sim_profiles.html", context)


def sim_profile_add_view(request):
    """Add a new sim racing profile with HTMX support and iRacing integration."""
    # Handle confirmation step
    if request.method == "POST" and "confirm_profile" in request.POST:
        return _handle_profile_confirmation(request)
    
    # Handle initial form submission
    if request.method == "POST":
        form = SimProfileForm(request.POST, user=request.user)
        if form.is_valid():
            simulator = form.cleaned_data["simulator"]
            sim_api_id = form.cleaned_data["sim_api_id"]
            
            # For iRacing, check existing profile first, then fetch if needed
            if simulator.name == "iRacing":
                try:
                    # First, check if profile already exists in our system
                    existing_profile = SimProfile.objects.filter(
                        simulator=simulator,
                        sim_api_id=sim_api_id
                    ).first()
                    
                    # Check if profile is already linked to current user
                    if existing_profile and existing_profile.linked_user == request.user:
                        messages.info(
                            request,
                            f"You already have this iRacing profile linked to your account."
                        )
                        return redirect("users:profile_sim_profiles")
                    
                    # Check if profile is linked to another user
                    if existing_profile and existing_profile.linked_user:
                        messages.error(
                            request,
                            f"This iRacing profile (Customer ID: {sim_api_id}) is already linked to another user's account."
                        )
                        return _render_form_response(request, form)
                    
                    # Check if we need to fetch/update data from iRacing
                    should_fetch_from_api = True
                    if existing_profile:
                        # Check if profile was updated recently (within last 24 hours)
                        time_since_update = timezone.now() - existing_profile.updated_at
                        if time_since_update < timedelta(hours=24):
                            should_fetch_from_api = False
                            logger.info(f"Using existing SimProfile data for {sim_api_id}, updated {time_since_update.total_seconds()/3600:.1f} hours ago")
                    
                    sim_profile = existing_profile
                    member_info = {}
                    iracing_data = {}
                    
                    if should_fetch_from_api:
                        # Fetch profile data from iRacing API using member_profile endpoint
                        logger.info(f"Fetching fresh data from iRacing API for customer ID {sim_api_id}")
                        client = get_iracing_client()
                        iracing_data = client.member_profile(cust_id=int(sim_api_id))
                        
                        if not iracing_data or not iracing_data.get("success"):
                            messages.error(
                                request,
                                f"Could not find iRacing profile with customer ID {sim_api_id}. "
                                "Please check the ID and try again."
                            )
                            return _render_form_response(request, form)
                        
                        # Extract profile information from member_info
                        member_info = iracing_data.get("member_info", {})
                        if not member_info:
                            messages.error(
                                request,
                                "Invalid response from iRacing API. Please try again."
                            )
                            return _render_form_response(request, form)
                        
                        # Create or update the SimProfile with fresh iRacing data
                        if existing_profile:
                            # Update existing profile with latest data
                            existing_profile.profile_name = member_info.get("display_name", "Unknown")
                            existing_profile.profile_data = iracing_data
                            existing_profile.save()
                            sim_profile = existing_profile
                            logger.info(f"Updated existing SimProfile {sim_profile.id} with fresh iRacing data")
                        else:
                            # Create new profile with iRacing data
                            sim_profile = SimProfile.objects.create(
                                simulator=simulator,
                                sim_api_id=sim_api_id,
                                profile_name=member_info.get("display_name", "Unknown"),
                                linked_user=None,  # Not linked yet
                                is_verified=False,
                                profile_data=iracing_data
                            )
                            logger.info(f"Created new SimProfile {sim_profile.id} from iRacing data")
                    else:
                        # Use existing profile data
                        if sim_profile:
                            iracing_data = sim_profile.profile_data or {}
                            member_info = iracing_data.get("member_info", {})
                            
                            # If we don't have proper member_info, we need to fetch from API
                            if not member_info or not member_info.get("display_name"):
                                logger.warning(f"Existing profile {sim_profile.id} has incomplete data, fetching from API")
                                client = get_iracing_client()
                                iracing_data = client.member_profile(cust_id=int(sim_api_id))
                                
                                if iracing_data and iracing_data.get("success"):
                                    member_info = iracing_data.get("member_info", {})
                                    sim_profile.profile_data = iracing_data
                                    sim_profile.save()
                        else:
                            # This shouldn't happen but handle gracefully
                            logger.error(f"Expected existing profile for {sim_api_id} but none found")
                            iracing_data = {}
                            member_info = {}
                    
                    # Show confirmation page for linking
                    context = {
                        "iracing_data": member_info,
                        "full_response": iracing_data,
                        "sim_profile": sim_profile,
                        "form_data": form.cleaned_data,
                        "title": "Link iRacing Profile",
                        "profile_exists": existing_profile is not None,
                        "data_freshness": "recent" if not should_fetch_from_api else "fresh",
                    }
                    
                    if request.htmx:
                        return render(request, "users/sim_profile_confirm_partial.html", context)
                    return render(request, "users/sim_profile_confirm.html", context)
                    
                except IRacingServiceError as e:
                    logger.error(f"iRacing API error for customer ID {sim_api_id}: {e}")
                    messages.error(
                        request,
                        f"Error connecting to iRacing API: {e}. You can still create the profile manually."
                    )
                    return _render_form_response(request, form)
                except Exception as e:
                    logger.error(f"Unexpected error fetching iRacing profile {sim_api_id}: {e}")
                    messages.error(
                        request,
                        "An unexpected error occurred. You can still create the profile manually."
                    )
                    return _render_form_response(request, form)
            
            # For non-iRacing or fallback, create profile directly
            return _create_profile_directly(request, form)
    else:
        form = SimProfileForm(user=request.user)

    return _render_form_response(request, form)


def _handle_profile_confirmation(request):
    """Handle the profile linking confirmation step."""
    try:
        # Get the profile ID from POST
        profile_id = request.POST.get("profile_id")
        
        if not profile_id:
            messages.error(request, "Missing profile information.")
            return redirect("users:sim_profile_add")
        
        # Get the SimProfile
        try:
            sim_profile = SimProfile.objects.get(id=profile_id)
        except SimProfile.DoesNotExist:
            messages.error(request, "Profile not found.")
            return redirect("users:sim_profile_add")
        
        # Check if profile is already linked
        if sim_profile.linked_user:
            if sim_profile.linked_user == request.user:
                messages.info(request, "This profile is already linked to your account.")
            else:
                messages.error(request, "This profile is already linked to another user.")
            return redirect("users:profile_sim_profiles")
        
        # Link the profile to the user
        sim_profile.link_to_user(request.user, verified=False)
        
        messages.success(
            request,
            f"Successfully linked iRacing profile: {sim_profile.profile_name}"
        )
        
        if request.htmx:
            # Return updated profiles list
            user_profiles = (
                SimProfile.objects.filter(linked_user=request.user)
                .select_related("simulator")
                .order_by("-created_at")
            )
            context = {"user_profiles": user_profiles}
            return render(request, "users/sim_profiles_list_partial.html", context)
        
        return redirect("users:profile_sim_profiles")
        
    except Exception as e:
        logger.error(f"Error linking profile: {e}")
        messages.error(request, "An error occurred while linking the profile.")
        return redirect("users:sim_profile_add")


def _create_profile_directly(request, form):
    """Create profile directly without API fetch."""
    sim_profile = form.save(commit=False)
    sim_profile.linked_user = request.user
    sim_profile.save()

    messages.success(
        request,
        f"Successfully added {sim_profile.simulator.name} profile: {sim_profile.profile_name}"
    )

    if request.htmx:
        # Return updated profiles list
        user_profiles = (
            SimProfile.objects.filter(linked_user=request.user)
            .select_related("simulator")
            .order_by("-created_at")
        )
        context = {"user_profiles": user_profiles}
        return render(request, "users/sim_profiles_list_partial.html", context)

    return redirect("users:profile_sim_profiles")


def _render_form_response(request, form):
    """Render the form response."""
    context = {
        "form": form,
        "title": "Add iRacing Profile",
        "action_url": reverse("users:sim_profile_add"),
    }

    if request.htmx:
        return render(request, "users/sim_profile_form_partial.html", context)
    return render(request, "users/sim_profile_form.html", context)


def sim_profile_edit_view(request, profile_id):
    """Edit an existing sim racing profile with HTMX support."""
    sim_profile = get_object_or_404(SimProfile, id=profile_id, linked_user=request.user)

    if request.method == "POST":
        form = SimProfileForm(request.POST, instance=sim_profile, user=request.user)
        if form.is_valid():
            sim_profile = form.save()

            messages.success(
                request,
                (
                    f"Successfully updated {sim_profile.simulator.name} profile: "
                    f"{sim_profile.profile_name}"
                ),
            )

            if request.htmx:
                # Return updated profiles list
                user_profiles = (
                    SimProfile.objects.filter(linked_user=request.user)
                    .select_related("simulator")
                    .order_by("-created_at")
                )
                context = {"user_profiles": user_profiles}
                return render(request, "users/sim_profiles_list_partial.html", context)

            return redirect("users:profile_sim_profiles")
    else:
        form = SimProfileForm(instance=sim_profile, user=request.user)

    context = {
        "form": form,
        "sim_profile": sim_profile,
        "title": f"Edit {sim_profile.simulator.name} Profile",
        "action_url": reverse(
            "users:sim_profile_edit",
            kwargs={"profile_id": profile_id},
        ),
    }

    if request.htmx:
        return render(request, "users/sim_profile_form_partial.html", context)
    return render(request, "users/sim_profile_form.html", context)


def sim_profile_disconnect_view(request, profile_id):
    """Disconnect a sim racing profile with HTMX support."""
    sim_profile = get_object_or_404(SimProfile, id=profile_id, linked_user=request.user)

    if request.method == "POST":
        profile_name = sim_profile.profile_name
        simulator_name = sim_profile.simulator.name
        sim_profile.delete()

        messages.success(
            request,
            f"Successfully disconnected {simulator_name} profile: {profile_name}",
        )

        if request.htmx:
            # Return updated profiles list
            user_profiles = (
                SimProfile.objects.filter(linked_user=request.user)
                .select_related("simulator")
                .order_by("-created_at")
            )
            context = {"user_profiles": user_profiles}
            return render(request, "users/sim_profiles_list_partial.html", context)

        return redirect("users:profile_sim_profiles")

    context = {
        "sim_profile": sim_profile,
        "title": f"Disconnect {sim_profile.simulator.name} Profile",
    }

    if request.htmx:
        return render(request, "users/sim_profile_disconnect_partial.html", context)
    return render(request, "users/sim_profile_disconnect.html", context)


# New unified profile views


@login_required
def profile_view(request):
    """Main profile dashboard - shows general settings by default."""
    if request.htmx:
        # For HTMX requests, render just the profile content without base template
        context = {
            "active_section": "general",
            "form": UserUpdateForm(instance=request.user),
        }
        return render(request, "users/profile/profile_content_partial.html", context)
    # For regular requests, redirect to general settings
    return redirect("users:profile_general")


@login_required
def profile_general_view(request):
    """General account settings in profile area."""
    if request.method == "POST":
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserUpdateForm(instance=request.user)

    context = {
        "form": form,
        "active_section": "general",
    }

    # Check if this is an HTMX request from within the profile section
    if request.htmx:
        hx_target = request.headers.get('HX-Target', '')
        if hx_target == '#profile-content':
            # Internal profile navigation - return just the partial
            return render(request, "users/profile/general_partial.html", context)
        elif hx_target == '#main-content':
            # External navigation (navbar) - return full profile page
            return render(request, "users/profile/profile.html", context)
        else:
            # Default HTMX behavior - return partial
            return render(request, "users/profile/general_partial.html", context)
    
    # Non-HTMX request - return full page
    return render(request, "users/profile/profile.html", context)


@login_required
def profile_sim_profiles_view(request):
    """Sim profiles management in profile area."""
    user_profiles = (
        SimProfile.objects.filter(linked_user=request.user)
        .select_related("simulator")
        .order_by("-created_at")
    )

    context = {
        "user_profiles": user_profiles,
        "active_section": "sim_profiles",
    }

    # Check if this is an HTMX request from within the profile section
    # If HX-Target is "#profile-content", return just the partial
    # If HX-Target is "#main-content" (from navbar), return the full page
    if request.htmx:
        hx_target = request.headers.get('HX-Target', '')
        if hx_target == '#profile-content':
            # Internal profile navigation - return just the partial
            return render(request, "users/profile/sim_profiles_partial.html", context)
        elif hx_target == '#main-content':
            # External navigation (navbar) - return full profile page
            return render(request, "users/profile/profile.html", context)
        else:
            # Default HTMX behavior - return partial
            return render(request, "users/profile/sim_profiles_partial.html", context)
    
    # Non-HTMX request - return full page
    return render(request, "users/profile/profile.html", context)


@login_required
def profile_emails_view(request):
    """Email management in profile area."""
    email_addresses = EmailAddress.objects.filter(user=request.user)

    context = {
        "email_addresses": email_addresses,
        "active_section": "emails",
    }

    # Check if this is an HTMX request from within the profile section
    if request.htmx:
        hx_target = request.headers.get('HX-Target', '')
        if hx_target == '#profile-content':
            # Internal profile navigation - return just the partial
            return render(request, "users/profile/emails_partial.html", context)
        elif hx_target == '#main-content':
            # External navigation (navbar) - return full profile page
            return render(request, "users/profile/profile.html", context)
        else:
            # Default HTMX behavior - return partial
            return render(request, "users/profile/emails_partial.html", context)
    
    # Non-HTMX request - return full page
    return render(request, "users/profile/profile.html", context)


@login_required
def profile_social_accounts_view(request):
    """Social accounts management in profile area."""
    social_accounts = SocialAccount.objects.filter(user=request.user)

    # Build a list of provider IDs already connected – used to hide duplicate connect buttons
    connected_provider_ids = list(social_accounts.values_list("provider", flat=True))

    context = {
        "social_accounts": social_accounts,
        "connected_provider_ids": connected_provider_ids,
        "active_section": "social_accounts",
    }

    if request.htmx:
        return render(request, "users/profile/social_accounts_partial.html", context)
    return render(request, "users/profile/profile.html", context)


@login_required
def profile_password_view(request):
    """Password management in profile area."""
    context = {
        "active_section": "password",
    }

    if request.htmx:
        return render(request, "users/profile/password_partial.html", context)
    return render(request, "users/profile/profile.html", context)


@login_required
def profile_sessions_view(request):
    """View and manage user sessions."""
    context = {
        "title": "Active Sessions",
    }

    if request.htmx:
        return render(request, "users/profile/sessions_partial.html", context)
    return render(request, "users/profile/sessions.html", context)


def auth_verify_email_view(request, key):
    """
    Handle email verification for both web and API requests.
    Web requests are redirected to standard allauth URLs.
    API requests continue to headless functionality.
    """
    # Detect if this is an API request
    is_api_request = (
        request.headers.get("Accept", "").startswith("application/json")
        or request.headers.get("Content-Type", "").startswith("application/json")
        or "api" in request.path.lower()
    )

    if is_api_request:
        # For API requests, let the headless functionality handle it
        # This would typically be handled by allauth.headless
        from django.http import JsonResponse

        return JsonResponse(
            {"error": "Use /api/auth/ endpoints for API authentication"}, status=400
        )
    # For web requests, redirect to standard allauth email confirmation
    from django.shortcuts import redirect

    return redirect("account_confirm_email", key=key)


def auth_reset_password_view(request):
    """
    Handle password reset for both web and API requests.
    Web requests are redirected to standard allauth URLs.
    """
    # Detect if this is an API request
    is_api_request = (
        request.headers.get("Accept", "").startswith("application/json")
        or request.headers.get("Content-Type", "").startswith("application/json")
        or "api" in request.path.lower()
    )

    if is_api_request:
        from django.http import JsonResponse

        return JsonResponse(
            {"error": "Use /api/auth/ endpoints for API authentication"}, status=400
        )
    from django.shortcuts import redirect

    return redirect("account_reset_password")


def auth_reset_password_from_key_view(request, key):
    """
    Handle password reset from key for both web and API requests.
    """
    # Detect if this is an API request
    is_api_request = (
        request.headers.get("Accept", "").startswith("application/json")
        or request.headers.get("Content-Type", "").startswith("application/json")
        or "api" in request.path.lower()
    )

    if is_api_request:
        from django.http import JsonResponse

        return JsonResponse(
            {"error": "Use /api/auth/ endpoints for API authentication"}, status=400
        )
    from django.shortcuts import redirect

    return redirect("account_reset_password_from_key", key=key)


def auth_signup_view(request):
    """
    Handle signup for both web and API requests.
    """
    # Detect if this is an API request
    is_api_request = (
        request.headers.get("Accept", "").startswith("application/json")
        or request.headers.get("Content-Type", "").startswith("application/json")
        or "api" in request.path.lower()
    )

    if is_api_request:
        from django.http import JsonResponse

        return JsonResponse(
            {"error": "Use /api/auth/ endpoints for API authentication"}, status=400
        )
    from django.shortcuts import redirect

    return redirect("account_signup")


def auth_socialaccount_login_error_view(request):
    """
    Handle social account login errors for both web and API requests.
    """
    # Detect if this is an API request
    is_api_request = (
        request.headers.get("Accept", "").startswith("application/json")
        or request.headers.get("Content-Type", "").startswith("application/json")
        or "api" in request.path.lower()
    )

    if is_api_request:
        from django.http import JsonResponse

        return JsonResponse(
            {"error": "Use /api/auth/ endpoints for API authentication"}, status=400
        )
    from django.shortcuts import redirect

    return redirect("socialaccount_login_error")
