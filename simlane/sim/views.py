from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from simlane.sim.models import SimProfile


@login_required
def iracing_dashboard(request):
    """iRacing dashboard main view - defaults to overview section"""
    return iracing_dashboard_section(request, "overview")


@login_required
def iracing_dashboard_section(request, section="overview"):
    """iRacing dashboard section view with HTMX support"""
    # Get user's iRacing profiles
    user_profiles = SimProfile.objects.filter(
        user=request.user,
        simulator__name__icontains="iracing",
    ).select_related("simulator")

    # Handle profile selection
    selected_profile = None
    if request.method == "POST" and "profile_id" in request.POST:
        profile_id = request.POST.get("profile_id")
        if profile_id:
            try:
                selected_profile = user_profiles.get(id=profile_id)
                request.session["selected_iracing_profile_id"] = str(profile_id)
            except SimProfile.DoesNotExist:
                pass
    elif "selected_iracing_profile_id" in request.session:
        try:
            selected_profile = user_profiles.get(
                id=request.session["selected_iracing_profile_id"]
            )
        except SimProfile.DoesNotExist:
            del request.session["selected_iracing_profile_id"]

    # If no profile selected and profiles exist, select the first one
    if not selected_profile and user_profiles.exists():
        selected_profile = user_profiles.first()
        if selected_profile:
            request.session["selected_iracing_profile_id"] = str(selected_profile.id)

    context = {
        "user_profiles": user_profiles,
        "selected_profile": selected_profile,
        "active_section": section,
    }

    # HTMX requests return partial content
    if request.headers.get("HX-Request"):
        return render(request, "sim/iracing/dashboard_content_partial.html", context)

    # Regular requests return full page
    return render(request, "sim/iracing/dashboard.html", context)
