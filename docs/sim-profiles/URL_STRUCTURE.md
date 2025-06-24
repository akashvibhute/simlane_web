# Sim Profiles URL Structure

## Overview

This document defines the complete URL structure for the sim profiles system, supporting both public discovery and user management workflows.

## URL Hierarchy

```
SimLane URLs
├── /profiles/                          # Public profile discovery
│   ├── /                              # Browse all profiles  
│   ├── /search/                       # Search profiles
│   ├── /<simulator_slug>/             # Browse by simulator
│   └── /<simulator_slug>/<profile_id>/ # Individual profile
├── /users/profile/sim-profiles/        # User profile management
│   ├── /                              # User's linked profiles
│   ├── /search/                       # Search to link
│   ├── /link/<profile_id>/            # Link existing profile
│   ├── /unlink/<profile_id>/          # Unlink profile
│   ├── /verify/<profile_id>/          # Verify ownership
│   └── /manage/<profile_id>/          # Manage profile settings
└── /dashboard/iracing/                 # Sim-specific dashboards (existing)
    ├── /                              # Dashboard overview
    └── /<section>/                    # Dashboard sections
```

## Public Profile URLs

### Profile Discovery
| URL Pattern | View | Template | Purpose | Auth Required |
|-------------|------|----------|---------|---------------|
| `/profiles/` | `profile_browse` | `profiles/browse.html` | Browse all public profiles | No |
| `/profiles/search/?q=<query>` | `profile_search` | `profiles/search.html` | Search profiles globally | No |
| `/profiles/<simulator_slug>/` | `profile_browse_by_sim` | `profiles/browse_by_sim.html` | Browse profiles by simulator | No |

### Individual Profile
| URL Pattern | View | Template | Purpose | Auth Required |
|-------------|------|----------|---------|---------------|
| `/profiles/<simulator_slug>/<profile_id>/` | `profile_detail` | `profiles/detail.html` | View individual profile | No |
| `/profiles/<simulator_slug>/<profile_id>/stats/` | `profile_stats` | `profiles/stats.html` | Detailed statistics | No |
| `/profiles/<simulator_slug>/<profile_id>/races/` | `profile_races` | `profiles/races.html` | Race history | No |

### API Endpoints
| URL Pattern | View | Response | Purpose | Auth Required |
|-------------|------|----------|---------|---------------|
| `/api/profiles/<simulator_slug>/<profile_id>/stats/` | `profile_stats_api` | JSON | Profile statistics | No |
| `/api/profiles/<simulator_slug>/<profile_id>/recent/` | `profile_recent_api` | JSON | Recent activity | No |

## User Management URLs

### Profile Management Dashboard
| URL Pattern | View | Template | Purpose | Auth Required |
|-------------|------|----------|---------|---------------|
| `/users/profile/sim-profiles/` | `profile_sim_profiles_view` | `users/profile/sim_profiles.html` | User's linked profiles | Yes |

### Profile Linking
| URL Pattern | View | Template | Purpose | Auth Required |
|-------------|------|----------|---------|---------------|
| `/users/profile/sim-profiles/search/` | `profile_sim_profile_search` | `users/profile/sim_profile_search.html` | Search profiles to link | Yes |
| `/users/profile/sim-profiles/link/<profile_id>/` | `profile_sim_profile_link` | `users/profile/sim_profile_link.html` | Link existing profile | Yes |
| `/users/profile/sim-profiles/unlink/<profile_id>/` | `profile_sim_profile_unlink` | `users/profile/sim_profile_unlink.html` | Unlink profile | Yes |

### Profile Verification
| URL Pattern | View | Template | Purpose | Auth Required |
|-------------|------|----------|---------|---------------|
| `/users/profile/sim-profiles/verify/<profile_id>/` | `profile_sim_profile_verify` | `users/profile/sim_profile_verify.html` | Verify ownership | Yes |
| `/users/profile/sim-profiles/manage/<profile_id>/` | `profile_sim_profile_manage` | `users/profile/sim_profile_manage.html` | Manage profile settings | Yes |

## Integration URLs

### Race Results Integration
| URL Pattern | Purpose | Profile Links |
|-------------|---------|---------------|
| `/events/<event_id>/results/` | Race results page | Links to `/profiles/<sim>/<profile_id>/` |
| `/teams/<team_slug>/members/` | Team member listing | Links to member profiles |

### Navigation Integration
| Context | Link | Destination |
|---------|------|-------------|
| Main navigation | "Driver Profiles" | `/profiles/` |
| User dropdown | "My Sim Profiles" | `/users/profile/sim-profiles/` |
| Search bar | Global search | `/profiles/search/?q=<query>` |

## URL Configuration Files

### Main URLs (`config/urls.py`)
```python
urlpatterns = [
    # ... existing URLs ...
    path("profiles/", include("simlane.profiles.urls", namespace="profiles")),
    path("users/", include("simlane.users.urls", namespace="users")),
    path("dashboard/iracing/", include("simlane.sim.urls", namespace="sim_dashboard")),
    # ... rest of URLs ...
]
```

### Public Profiles (`simlane/profiles/urls.py`)
```python
from django.urls import path
from . import views

app_name = "profiles"

urlpatterns = [
    # Browse and search
    path("", views.profile_browse, name="browse"),
    path("search/", views.profile_search, name="search"),
    path("<slug:simulator_slug>/", views.profile_browse_by_sim, name="browse_by_sim"),
    
    # Individual profiles
    path("<slug:simulator_slug>/<str:profile_identifier>/", views.profile_detail, name="detail"),
    path("<slug:simulator_slug>/<str:profile_identifier>/stats/", views.profile_stats, name="stats"),
    path("<slug:simulator_slug>/<str:profile_identifier>/races/", views.profile_races, name="races"),
    
    # API endpoints
    path("api/<slug:simulator_slug>/<str:profile_identifier>/stats/", views.profile_stats_api, name="stats_api"),
    path("api/<slug:simulator_slug>/<str:profile_identifier>/recent/", views.profile_recent_api, name="recent_api"),
]
```

### User Management (`simlane/users/urls.py`)
```python
# Add to existing users/urls.py
urlpatterns = [
    # ... existing URLs ...
    
    # Sim profile management
    path("profile/sim-profiles/", view=profile_sim_profiles_view, name="profile_sim_profiles"),
    path("profile/sim-profiles/search/", view=profile_sim_profile_search, name="profile_sim_profile_search"),
    path("profile/sim-profiles/link/<uuid:profile_id>/", view=profile_sim_profile_link, name="profile_sim_profile_link"),
    path("profile/sim-profiles/unlink/<uuid:profile_id>/", view=profile_sim_profile_unlink, name="profile_sim_profile_unlink"),
    path("profile/sim-profiles/verify/<uuid:profile_id>/", view=profile_sim_profile_verify, name="profile_sim_profile_verify"),
    path("profile/sim-profiles/manage/<uuid:profile_id>/", view=profile_sim_profile_manage, name="profile_sim_profile_manage"),
    
    # ... rest of URLs ...
]
```

### Sim Dashboard (`simlane/sim/urls.py`) - Existing
```python
# Keep existing dashboard URLs
app_name = "sim"

urlpatterns = [
    path("", views.iracing_dashboard, name="iracing_dashboard"),
    path("<str:section>/", views.iracing_dashboard_section, name="iracing_dashboard_section"),
]
```

## URL Parameter Formats

### Profile Identifier
- **Format**: String, platform-specific
- **Examples**: 
  - iRacing: `123456` (customer ID)
  - ACC: `S76561198123456789` (Steam ID)
- **Constraints**: Must be unique within simulator

### Simulator Slug
- **Format**: Lowercase, hyphenated
- **Examples**: `iracing`, `assetto-corsa-competizione`, `rf2`
- **Source**: `Simulator.slug` field

### Profile ID (UUID)
- **Format**: UUID4
- **Usage**: Internal database primary key
- **Context**: User management URLs only

## SEO and URL Optimization

### Public Profile URLs
- **SEO-friendly**: `/profiles/iracing/john-doe-123456/`
- **Canonical URLs**: Each profile has single canonical URL
- **Meta tags**: Profile name, simulator, recent achievements
- **Schema markup**: Person/Athlete structured data

### Search Optimization
- **Clean parameters**: `/profiles/search/?q=john+doe&sim=iracing`
- **Pagination**: `/profiles/search/?q=john&page=2`
- **Filtering**: `/profiles/search/?q=john&verified=true&sim=iracing`

## Redirects and Aliases

### Legacy URL Support
During migration, support legacy URLs temporarily:
```python
# Legacy redirect patterns
path("users/sim-profiles/", RedirectView.as_view(url="/users/profile/sim-profiles/", permanent=True)),
path("sim/", RedirectView.as_view(url="/dashboard/iracing/", permanent=True)),
```

### Profile Aliases
Support multiple URL formats for profiles:
```python
# Alternative formats
path("<slug:simulator_slug>/<str:profile_name>-<str:profile_id>/", views.profile_detail_alias, name="detail_alias"),
```

## Error Handling

### Profile Not Found (404)
- **URL**: `/profiles/iracing/nonexistent/`
- **Template**: `profiles/profile_not_found.html`
- **Suggestions**: Similar profiles, search suggestions

### Simulator Not Found (404)  
- **URL**: `/profiles/nonexistent-sim/`
- **Template**: `profiles/simulator_not_found.html`
- **Suggestions**: Available simulators

### Access Denied (403)
- **URL**: `/users/profile/sim-profiles/manage/other-users-profile/`
- **Template**: `403.html`
- **Action**: Redirect to login or profile list

## Performance Considerations

### Caching Strategy
```python
# URL-based caching
@cache_page(60 * 15)  # 15 minutes
def profile_detail(request, simulator_slug, profile_identifier):
    # Profile detail view

@cache_page(60 * 5)   # 5 minutes  
def profile_search(request):
    # Search results
```

### Database Optimization
- **Profile lookups**: Index on `(simulator, profile_identifier)`
- **Search queries**: Full-text search index on profile names
- **User profiles**: Index on `linked_user` for fast user profile lists

## Security Considerations

### Public URL Security
- **Rate limiting**: Prevent profile scraping
- **Access logs**: Monitor suspicious access patterns
- **Data exposure**: Only show public profile data

### User Management Security
- **Authentication**: All user management URLs require login
- **Authorization**: Users can only manage their own linked profiles
- **CSRF protection**: All POST operations protected

### Profile Verification Security
- **Verification tokens**: Time-limited verification links
- **Platform integration**: Use platform APIs where possible
- **Audit logging**: Track verification attempts and changes

This URL structure provides a clear separation between public discovery and user management while maintaining SEO optimization and security best practices. 