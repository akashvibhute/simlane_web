from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import UpdateView

from simlane.sim.models import SimProfile

from .forms import SimProfileForm
from .forms import UserUpdateForm

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
        SimProfile.objects.filter(user=request.user)
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
    """Add a new sim racing profile with HTMX support."""
    if request.method == "POST":
        form = SimProfileForm(request.POST, user=request.user)
        if form.is_valid():
            sim_profile = form.save(commit=False)
            sim_profile.user = request.user
            sim_profile.save()

            messages.success(
                request,
                (
                    f"Successfully added {sim_profile.simulator.name} profile: "
                    f"{sim_profile.profile_name}"
                ),
            )

            if request.htmx:
                # Return updated profiles list
                user_profiles = (
                    SimProfile.objects.filter(user=request.user)
                    .select_related("simulator")
                    .order_by("-created_at")
                )
                context = {"user_profiles": user_profiles}
                return render(request, "users/sim_profiles_list_partial.html", context)

            return redirect("users:sim_profiles")
    else:
        form = SimProfileForm(user=request.user)

    context = {
        "form": form,
        "title": "Add Sim Profile",
        "action_url": reverse("users:sim_profile_add"),
    }

    if request.htmx:
        return render(request, "users/sim_profile_form_partial.html", context)
    return render(request, "users/sim_profile_form.html", context)


def sim_profile_edit_view(request, profile_id):
    """Edit an existing sim racing profile with HTMX support."""
    sim_profile = get_object_or_404(SimProfile, id=profile_id, user=request.user)

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
                    SimProfile.objects.filter(user=request.user)
                    .select_related("simulator")
                    .order_by("-created_at")
                )
                context = {"user_profiles": user_profiles}
                return render(request, "users/sim_profiles_list_partial.html", context)

            return redirect("users:sim_profiles")
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
    sim_profile = get_object_or_404(SimProfile, id=profile_id, user=request.user)

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
                SimProfile.objects.filter(user=request.user)
                .select_related("simulator")
                .order_by("-created_at")
            )
            context = {"user_profiles": user_profiles}
            return render(request, "users/sim_profiles_list_partial.html", context)

        return redirect("users:sim_profiles")

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
    """Main profile dashboard - redirects to general settings by default."""
    return redirect("users:profile_general")


@login_required
def profile_general_view(request):
    """General profile settings."""
    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Profile updated successfully"))

            if request.htmx:
                context = {
                    "form": form,
                    "active_section": "general",
                }
                return render(request, "users/profile/general_partial.html", context)
            return redirect("users:profile_general")
    else:
        form = UserUpdateForm(instance=request.user)

    context = {
        "form": form,
        "active_section": "general",
    }

    if request.htmx:
        return render(request, "users/profile/general_partial.html", context)
    return render(request, "users/profile/profile.html", context)


@login_required
def profile_sim_profiles_view(request):
    """Sim profiles management in profile area."""
    user_profiles = (
        SimProfile.objects.filter(user=request.user)
        .select_related("simulator")
        .order_by("-created_at")
    )

    context = {
        "user_profiles": user_profiles,
        "active_section": "sim_profiles",
    }

    if request.htmx:
        return render(request, "users/profile/sim_profiles_partial.html", context)
    return render(request, "users/profile/profile.html", context)


@login_required
def profile_emails_view(request):
    """Email management in profile area."""
    email_addresses = EmailAddress.objects.filter(user=request.user)

    context = {
        "email_addresses": email_addresses,
        "active_section": "emails",
    }

    if request.htmx:
        return render(request, "users/profile/emails_partial.html", context)
    return render(request, "users/profile/profile.html", context)


@login_required
def profile_social_accounts_view(request):
    """Social accounts management in profile area."""
    social_accounts = SocialAccount.objects.filter(user=request.user)

    context = {
        "social_accounts": social_accounts,
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
    """Session management in profile area."""
    context = {
        "active_section": "sessions",
    }

    if request.htmx:
        return render(request, "users/profile/sessions_partial.html", context)
    return render(request, "users/profile/profile.html", context)
