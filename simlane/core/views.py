import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.generic import FormView
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.template.loader import render_to_string

from simlane.sim.models import SimProfile

from .forms import ContactForm
from .services import ContactEmailService
from .search import get_search_service, SearchFilters

logger = logging.getLogger(__name__)


@method_decorator(csrf_protect, name="dispatch")
class ContactView(FormView):
    """View for handling contact form submissions."""

    template_name = "core/contact.html"
    form_class = ContactForm

    def get_form_kwargs(self):
        """Pass the current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Handle successful form submission."""
        try:
            # Save the contact message
            contact_message = form.save()

            # Send notification emails
            notification_sent = ContactEmailService.send_contact_notification(
                contact_message,
            )
            confirmation_sent = ContactEmailService.send_confirmation_email(
                contact_message,
            )

            # Log the submission
            logger.info(
                "Contact form submitted by %s (%s) - Message ID: %s",
                contact_message.name,
                contact_message.email,
                contact_message.pk,
            )

            # Prepare success message
            success_msg = (
                "Thank you for your message! We've received your inquiry and "
                "will respond within 24-48 hours."
            )

            if not confirmation_sent:
                success_msg += (
                    " Note: We couldn't send a confirmation email, "
                    "but your message was received."
                )
                logger.warning(
                    "Confirmation email failed for contact message %s",
                    contact_message.pk,
                )

            if not notification_sent:
                logger.error(
                    "Staff notification email failed for contact message %s",
                    contact_message.pk,
                )

            messages.success(self.request, success_msg)

            # Redirect to contact page with success message
            return redirect("core:contact_success")

        except Exception:
            logger.exception("Error processing contact form submission")
            messages.error(
                self.request,
                (
                    "We're sorry, but there was an error processing your message. "
                    "Please try again or contact us directly."
                ),
            )
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Handle form validation errors."""
        logger.warning("Contact form submission failed validation: %s", form.errors)
        messages.error(
            self.request,
            "Please correct the errors below and try again.",
        )
        return super().form_invalid(form)


def contact_success(request):
    """Success page after contact form submission."""
    return render(request, "core/contact_success.html")


def contact_view(request):
    """Function-based view for contact form with HTMX support."""
    if request.method == "POST":
        form = ContactForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                # Save the contact message
                contact_message = form.save()

                # Send notification emails
                notification_sent = ContactEmailService.send_contact_notification(
                    contact_message,
                )
                confirmation_sent = ContactEmailService.send_confirmation_email(
                    contact_message,
                )

                # Log the submission
                logger.info(
                    "Contact form submitted by %s (%s) - Message ID: %s",
                    contact_message.name,
                    contact_message.email,
                    contact_message.pk,
                )

                # Prepare success message
                success_msg = (
                    "Thank you for your message! We've received your inquiry and "
                    "will respond within 24-48 hours."
                )

                if not confirmation_sent:
                    success_msg += (
                        " Note: We couldn't send a confirmation email, "
                        "but your message was received."
                    )
                    logger.warning(
                        "Confirmation email failed for contact message %s",
                        contact_message.pk,
                    )

                if not notification_sent:
                    logger.error(
                        "Staff notification email failed for contact message %s",
                        contact_message.pk,
                    )

                messages.success(request, success_msg)

                # For HTMX requests, return partial template with fresh form
                if request.htmx:
                    # Return a fresh form for the next submission
                    form = ContactForm(user=request.user)
                    return render(
                        request,
                        "core/contact_form_partial.html",
                        {"form": form},
                    )

                # Regular redirect for non-HTMX requests
                return redirect("core:contact")

            except Exception:
                logger.exception("Error processing contact form submission")
                messages.error(
                    request,
                    (
                        "We're sorry, but there was an error processing your message. "
                        "Please try again or contact us directly."
                    ),
                )
        else:
            messages.error(
                request,
                "Please correct the errors below and try again.",
            )

        # For HTMX requests with form errors, return partial template
        if request.htmx:
            return render(request, "core/contact_form_partial.html", {"form": form})
    else:
        form = ContactForm(user=request.user)

    # Handle different types of HTMX requests
    if request.htmx:
        # Navigation request - return content partial (page content without nav)
        return render(request, "core/contact_content_partial.html", {"form": form})

    # Direct page visit - return full page with base template
    return render(request, "core/contact.html", {"form": form})


def htmx_static_page_view(template_name):
    """Factory function to create HTMX-aware static page views."""

    def view(request):
        if request.htmx:
            # For HTMX requests, return only the content block from the template
            # We'll create a simple approach - render the template and extract content
            return render(request, template_name)
        return render(request, template_name)

    return view


def home_view(request):
    """Home page view that handles HTMX requests."""
    # If this is an HTMX request for navigation, return content partial
    if request.htmx:
        return render(request, "core/home_content_partial.html")

    # Otherwise return the full page
    return render(request, "core/home.html")


def about_view(request):
    """About page view that handles HTMX requests."""
    # If this is an HTMX request for navigation, return content partial
    if request.htmx:
        return render(request, "core/about_content_partial.html")

    # Otherwise return the full page
    return render(request, "core/about.html")


def privacy_view(request):
    """Privacy page view that handles HTMX requests."""
    # If this is an HTMX request for navigation, return content partial
    if request.htmx:
        return render(request, "core/privacy_content_partial.html")

    # Otherwise return the full page
    return render(request, "core/privacy.html")


def terms_view(request):
    """Terms page view that handles HTMX requests."""
    # If this is an HTMX request for navigation, return content partial
    if request.htmx:
        return render(request, "core/terms_content_partial.html")

    # Otherwise return the full page
    return render(request, "core/terms.html")


@login_required
def dashboard_view(request):
    """Main dashboard view showing sim profiles and clubs overview."""

    # Get user's sim profiles grouped by simulator
    user_profiles = (
        SimProfile.objects.filter(user=request.user)
        .select_related("simulator")
        .order_by("simulator__name", "-last_active")
    )

    # Group profiles by simulator
    profiles_by_sim = {}
    for profile in user_profiles:
        sim_name = profile.simulator.name
        if sim_name not in profiles_by_sim:
            profiles_by_sim[sim_name] = []
        profiles_by_sim[sim_name].append(profile)

    # Get user's teams/clubs (if teams app has this model)
    user_teams = []
    total_clubs = 0
    try:
        from simlane.teams.models import ClubMember
        from simlane.teams.models import TeamMember

        # Get teams through TeamMember relationships
        team_memberships = TeamMember.objects.filter(user=request.user).select_related(
            "team",
        )
        user_teams = [tm.team for tm in team_memberships]

        # Get clubs count through ClubMember relationships
        total_clubs = ClubMember.objects.filter(user=request.user).count()
    except:
        pass  # Teams model might not exist yet

    context = {
        "profiles_by_sim": profiles_by_sim,
        "user_teams": user_teams,
        "total_profiles": user_profiles.count(),
        "total_teams": len(user_teams),
        "total_clubs": total_clubs,
    }

    return render(request, "core/dashboard.html", context)


@require_http_methods(["GET"])
def search_api(request):
    """
    Universal search API endpoint
    
    Query parameters:
    - q: Search query (required)
    - types: Comma-separated list of types to search (optional)
    - simulator: Filter by simulator slug (optional)
    - limit: Number of results (default: 20, max: 100)
    - offset: Pagination offset (default: 0)
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({
            'error': 'Query parameter "q" is required',
            'results': [],
            'total_count': 0
        }, status=400)
    
    # Parse filters
    filters = SearchFilters()
    
    if request.GET.get('types'):
        filters.types = [t.strip() for t in request.GET.get('types').split(',')]
    
    if request.GET.get('simulator'):
        filters.simulator = request.GET.get('simulator')
    
    # Parse pagination
    try:
        limit = min(int(request.GET.get('limit', 20)), 100)
        offset = max(int(request.GET.get('offset', 0)), 0)
    except ValueError:
        limit, offset = 20, 0
    
    # Perform search
    search_service = get_search_service()
    results = search_service.search(query, filters, limit, offset)
    
    # Convert SearchResult objects to dicts for JSON serialization
    serialized_results = []
    for result in results['results']:
        serialized_results.append({
            'id': result.id,
            'type': result.type,
            'title': result.title,
            'description': result.description,
            'url': result.url,
            'image_url': result.image_url,
            'metadata': result.metadata,
            'relevance_score': result.relevance_score
        })
    
    return JsonResponse({
        'results': serialized_results,
        'total_count': results['total_count'],
        'facets': results['facets'],
        'query_time_ms': results['query_time_ms'],
        'query': query,
        'filters': {
            'types': filters.types,
            'simulator': filters.simulator
        },
        'pagination': {
            'limit': limit,
            'offset': offset,
            'has_more': results['total_count'] > offset + limit
        }
    })


@require_http_methods(["GET"])
def search_suggestions(request):
    """
    Search suggestions/autocomplete API
    
    Query parameters:
    - q: Partial search query (required)
    - limit: Number of suggestions (default: 5, max: 10)
    """
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    try:
        limit = min(int(request.GET.get('limit', 5)), 10)
    except ValueError:
        limit = 5
    
    search_service = get_search_service()
    suggestions = search_service.get_suggestions(query, limit)
    
    return JsonResponse({'suggestions': suggestions})


@require_http_methods(["GET"])
def search_page(request):
    """
    Full-page search results
    """
    query = request.GET.get('q', '').strip()
    selected_types = request.GET.getlist('types')
    simulator = request.GET.get('simulator', '')
    
    context = {
        'query': query,
        'selected_types': selected_types,
        'simulator': simulator,
        'available_types': [
            {'key': 'user', 'label': 'Users'},
            {'key': 'sim_profile', 'label': 'Sim Profiles'},
            {'key': 'event', 'label': 'Events'},
            {'key': 'team', 'label': 'Teams'},
            {'key': 'club', 'label': 'Clubs'},
            {'key': 'simulator', 'label': 'Simulators'},
            {'key': 'track', 'label': 'Tracks'},
            {'key': 'car', 'label': 'Cars'},
        ]
    }
    
    if query:
        # Parse filters
        filters = SearchFilters()
        if selected_types:
            filters.types = selected_types
        if simulator:
            filters.simulator = simulator
        
        # Get page number
        page = request.GET.get('page', 1)
        try:
            page = int(page)
        except ValueError:
            page = 1
        
        # Calculate offset
        limit = 20
        offset = (page - 1) * limit
        
        # Perform search
        search_service = get_search_service()
        search_results = search_service.search(query, filters, limit, offset)
        
        # Add pagination info
        total_pages = (search_results['total_count'] + limit - 1) // limit
        context.update({
            'results': search_results['results'],
            'total_count': search_results['total_count'],
            'facets': search_results['facets'],
            'query_time_ms': search_results['query_time_ms'],
            'page': page,
            'total_pages': total_pages,
            'has_previous': page > 1,
            'has_next': page < total_pages,
            'previous_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < total_pages else None,
        })
    
    return render(request, 'core/search/search_page.html', context)


@require_http_methods(["GET"])
def search_htmx(request):
    """
    HTMX-powered search results for live search
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        return render(request, 'core/search/search_results_partial.html', {
            'results': [],
            'total_count': 0,
            'query': ''
        })
    
    # Parse filters from request
    filters = SearchFilters()
    if request.GET.get('types'):
        filters.types = [t.strip() for t in request.GET.get('types').split(',')]
    
    # Limit results for live search
    search_service = get_search_service()
    search_results = search_service.search(query, filters, limit=8)
    
    context = {
        'results': search_results['results'],
        'total_count': search_results['total_count'],
        'query': query,
        'query_time_ms': search_results['query_time_ms'],
        'show_more_url': f"/search/?q={query}" if search_results['total_count'] > 8 else None
    }
    
    return render(request, 'core/search/search_results_partial.html', context)
