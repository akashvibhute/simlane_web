# Sim Profiles Migration Plan

## Overview

This document outlines the migration from the current user-owned sim profile system to the new independent profile system with optional user linking.

## Current State Analysis

### Current Data Model Issues
```python
# CURRENT MODEL (problematic)
class SimProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # ❌ Forced ownership
    simulator = models.ForeignKey(Simulator, on_delete=models.CASCADE)
    profile_name = models.CharField(max_length=255)
    profile_data = models.JSONField(default=dict)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Current URL Issues
- `/users/sim-profiles/` - Legacy standalone system
- `/users/profile/sim-profiles/` - New unified system  
- Both systems use same CRUD URLs causing conflicts
- Public discovery not possible
- Race results can't link to profiles

## Migration Strategy

### Phase 1: Data Model Migration (Breaking Changes)
**Duration**: 1-2 days  
**Downtime**: Required for schema changes

#### 1.1 Create New Model Fields
```python
# Migration 001: Add new fields
class Migration(migrations.Migration):
    dependencies = [
        ('sim', '0008_alter_event_event_source'),
    ]
    
    operations = [
        # Add new fields for independent profile system
        migrations.AddField(
            model_name='simprofile',
            name='profile_identifier',
            field=models.CharField(max_length=255, help_text='Platform-specific unique ID'),
        ),
        migrations.AddField(
            model_name='simprofile',
            name='linked_user',
            field=models.ForeignKey(
                'users.User', 
                on_delete=models.SET_NULL, 
                null=True, 
                blank=True,
                related_name='linked_sim_profiles'
            ),
        ),
        migrations.AddField(
            model_name='simprofile',
            name='is_public',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='simprofile',
            name='linked_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        
        # Add indexes
        migrations.AddIndex(
            model_name='simprofile',
            index=models.Index(fields=['linked_user'], name='sim_profile_linked_user_idx'),
        ),
        migrations.AddIndex(
            model_name='simprofile',
            index=models.Index(fields=['is_public'], name='sim_profile_public_idx'),
        ),
    ]
```

#### 1.2 Migrate Existing Data
```python
# Migration 002: Migrate existing data
def migrate_existing_profiles(apps, schema_editor):
    SimProfile = apps.get_model('sim', 'SimProfile')
    
    for profile in SimProfile.objects.all():
        # Generate profile_identifier from existing data
        if not profile.profile_identifier:
            # Use profile name + ID as fallback identifier
            profile.profile_identifier = f"{profile.profile_name.lower().replace(' ', '-')}-{profile.id}"
        
        # Migrate user ownership to linking
        if profile.user:
            profile.linked_user = profile.user
            profile.linked_at = profile.created_at
            # Mark existing profiles as verified (they were created by users)
            profile.is_verified = True
        
        profile.save()

def reverse_migration(apps, schema_editor):
    # Reverse migration logic
    SimProfile = apps.get_model('sim', 'SimProfile')
    
    for profile in SimProfile.objects.all():
        if profile.linked_user:
            profile.user = profile.linked_user
            profile.save()

class Migration(migrations.Migration):
    dependencies = [
        ('sim', '0009_add_profile_fields'),
    ]
    
    operations = [
        migrations.RunPython(migrate_existing_profiles, reverse_migration),
    ]
```

#### 1.3 Add Unique Constraint
```python
# Migration 003: Add unique constraint
class Migration(migrations.Migration):
    dependencies = [
        ('sim', '0010_migrate_profile_data'),
    ]
    
    operations = [
        migrations.AlterUniqueTogether(
            name='simprofile',
            unique_together={('simulator', 'profile_identifier')},
        ),
    ]
```

#### 1.4 Remove Old User Field
```python
# Migration 004: Remove old user field (BREAKING)
class Migration(migrations.Migration):
    dependencies = [
        ('sim', '0011_add_unique_constraint'),
    ]
    
    operations = [
        migrations.RemoveField(
            model_name='simprofile',
            name='user',
        ),
    ]
```

### Phase 2: Create Public Profiles App (No Downtime)
**Duration**: 2-3 days  
**Downtime**: None

#### 2.1 Create Profiles App
```bash
python manage.py startapp profiles
```

#### 2.2 Create Views and Templates
```python
# simlane/profiles/views.py
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from simlane.sim.models import SimProfile, Simulator

def profile_browse(request):
    """Browse all public profiles"""
    profiles = SimProfile.objects.filter(is_public=True).select_related('simulator', 'linked_user')
    
    paginator = Paginator(profiles, 24)
    page = request.GET.get('page')
    profiles_page = paginator.get_page(page)
    
    context = {
        'profiles': profiles_page,
        'simulators': Simulator.objects.all(),
    }
    return render(request, 'profiles/browse.html', context)

def profile_search(request):
    """Search profiles"""
    query = request.GET.get('q', '')
    simulator_filter = request.GET.get('sim', '')
    
    profiles = SimProfile.objects.filter(is_public=True)
    
    if query:
        profiles = profiles.filter(
            Q(profile_name__icontains=query) |
            Q(linked_user__username__icontains=query) |
            Q(linked_user__first_name__icontains=query) |
            Q(linked_user__last_name__icontains=query)
        )
    
    if simulator_filter:
        profiles = profiles.filter(simulator__slug=simulator_filter)
    
    paginator = Paginator(profiles, 24)
    page = request.GET.get('page')
    profiles_page = paginator.get_page(page)
    
    context = {
        'profiles': profiles_page,
        'query': query,
        'simulator_filter': simulator_filter,
        'simulators': Simulator.objects.all(),
    }
    return render(request, 'profiles/search.html', context)

def profile_detail(request, simulator_slug, profile_identifier):
    """Individual profile view"""
    simulator = get_object_or_404(Simulator, slug=simulator_slug)
    profile = get_object_or_404(
        SimProfile, 
        simulator=simulator, 
        profile_identifier=profile_identifier,
        is_public=True
    )
    
    # Check if current user owns this profile
    is_owner = (
        request.user.is_authenticated and 
        profile.linked_user == request.user
    )
    
    context = {
        'profile': profile,
        'simulator': simulator,
        'is_owner': is_owner,
    }
    return render(request, 'profiles/detail.html', context)
```

### Phase 3: Update User Management System (No Downtime)
**Duration**: 2-3 days  
**Downtime**: None

#### 3.1 Create New User Management Views
```python
# simlane/users/views.py - Add new views

@login_required
def profile_sim_profile_search(request):
    """Search for profiles to link to user account"""
    query = request.GET.get('q', '')
    
    profiles = SimProfile.objects.filter(
        linked_user__isnull=True,  # Only unlinked profiles
        is_public=True
    )
    
    if query:
        profiles = profiles.filter(
            Q(profile_name__icontains=query) |
            Q(profile_identifier__icontains=query)
        )
    
    context = {
        'profiles': profiles[:20],  # Limit results
        'query': query,
        'active_section': 'sim_profiles',
    }
    
    if request.htmx:
        return render(request, 'users/profile/sim_profile_search_partial.html', context)
    return render(request, 'users/profile/profile.html', context)

@login_required
def profile_sim_profile_link(request, profile_id):
    """Link an existing profile to user account"""
    profile = get_object_or_404(SimProfile, id=profile_id)
    
    # Check if user can link this profile
    if not profile.can_user_link(request.user):
        messages.error(request, "This profile is already linked to another user.")
        return redirect('users:profile_sim_profiles')
    
    if request.method == 'POST':
        try:
            profile.link_to_user(request.user, verified=False)
            messages.success(
                request, 
                f"Successfully linked {profile.simulator.name} profile: {profile.profile_name}. "
                "Please verify your ownership to complete the process."
            )
            return redirect('users:profile_sim_profiles')
        except ValueError as e:
            messages.error(request, str(e))
    
    context = {
        'profile': profile,
        'active_section': 'sim_profiles',
    }
    
    if request.htmx:
        return render(request, 'users/profile/sim_profile_link_partial.html', context)
    return render(request, 'users/profile/profile.html', context)

@login_required
def profile_sim_profile_unlink(request, profile_id):
    """Unlink a profile from user account"""
    profile = get_object_or_404(
        SimProfile, 
        id=profile_id, 
        linked_user=request.user
    )
    
    if request.method == 'POST':
        profile_name = profile.profile_name
        simulator_name = profile.simulator.name
        profile.unlink_from_user()
        
        messages.success(
            request, 
            f"Successfully unlinked {simulator_name} profile: {profile_name}. "
            "The profile is now available for other users to claim."
        )
        return redirect('users:profile_sim_profiles')
    
    context = {
        'profile': profile,
        'active_section': 'sim_profiles',
    }
    
    if request.htmx:
        return render(request, 'users/profile/sim_profile_unlink_partial.html', context)
    return render(request, 'users/profile/profile.html', context)
```

### Phase 4: Update All References (No Downtime)
**Duration**: 1 day  
**Downtime**: None

#### 4.1 Update Template References
Replace all instances of:
```html
<!-- Old references -->
{% url 'users:sim_profiles' %}

<!-- New references -->
{% url 'users:profile_sim_profiles' %}
```

#### 4.2 Update Python Redirects
```python
# In simlane/users/views.py - Update redirects
# Old:
return redirect("users:sim_profiles")

# New:
return redirect("users:profile_sim_profiles")
```

#### 4.3 Update Navigation
```html
<!-- In templates/components/navbar.html -->
<!-- Change from: -->
<a href="{% url 'users:sim_profiles' %}">Sim Profiles</a>

<!-- To: -->
<a href="{% url 'users:profile_sim_profiles' %}">My Sim Profiles</a>

<!-- Add new public profiles link: -->
<a href="{% url 'profiles:browse' %}">Driver Profiles</a>
```

### Phase 5: Remove Legacy System (No Downtime)
**Duration**: 1 day  
**Downtime**: None

#### 5.1 Remove Legacy URLs
Remove from `simlane/users/urls.py`:
```python
# REMOVE these patterns:
path("sim-profiles/", view=sim_profiles_view, name="sim_profiles"),
path("sim-profiles/add/", view=sim_profile_add_view, name="sim_profile_add"),
path("sim-profiles/<uuid:profile_id>/edit/", view=sim_profile_edit_view, name="sim_profile_edit"),
path("sim-profiles/<uuid:profile_id>/disconnect/", view=sim_profile_disconnect_view, name="sim_profile_disconnect"),
```

#### 5.2 Remove Legacy Views
Remove from `simlane/users/views.py`:
- `sim_profiles_view`
- `sim_profile_add_view`
- `sim_profile_edit_view`
- `sim_profile_disconnect_view`

#### 5.3 Remove Legacy Templates
Remove these files:
- `templates/users/sim_profiles.html`
- `templates/users/sim_profiles_content_partial.html`
- `templates/users/sim_profiles_list_partial.html`
- `templates/users/sim_profile_form.html`
- `templates/users/sim_profile_form_partial.html`
- `templates/users/sim_profile_disconnect.html`
- `templates/users/sim_profile_disconnect_partial.html`

## Risk Mitigation

### Database Backup
```bash
# Before Phase 1 migration
python manage.py dumpdata sim.SimProfile > profile_backup.json
python manage.py dumpdata users.User > user_backup.json
```

### Rollback Plan
```python
# Rollback migration if needed
python manage.py migrate sim 0008_alter_event_event_source
```

### Feature Flags
```python
# Use feature flags for gradual rollout
if settings.ENABLE_PUBLIC_PROFILES:
    # Show new public profile features
else:
    # Fall back to legacy behavior
```

### Monitoring
- Monitor 404 errors for broken profile links
- Track user adoption of new linking system
- Monitor performance of profile search queries

## Post-Migration Verification

### Data Integrity Checks
```python
# Management command to verify migration
class Command(BaseCommand):
    def handle(self, *args, **options):
        # Check all profiles have valid profile_identifiers
        invalid_profiles = SimProfile.objects.filter(
            profile_identifier__isnull=True
        ).count()
        
        if invalid_profiles > 0:
            self.stdout.write(
                self.style.ERROR(f"Found {invalid_profiles} profiles without identifiers")
            )
        
        # Check user linking consistency
        # Verify all linked_users exist
        # Check for duplicate profile_identifiers
```

### User Communication
1. **Email notification** about new profile system
2. **In-app notification** about linking existing profiles
3. **Help documentation** for profile verification process
4. **FAQ section** about profile privacy and discovery

## Timeline Summary

| Phase | Duration | Downtime | Description |
|-------|----------|----------|-------------|
| 1 | 1-2 days | Required | Data model migration |
| 2 | 2-3 days | None | Create public profiles app |
| 3 | 2-3 days | None | Update user management |
| 4 | 1 day | None | Update all references |
| 5 | 1 day | None | Remove legacy system |

**Total Estimated Time**: 7-10 days  
**Total Downtime**: 2-4 hours (Phase 1 only)

This migration plan ensures a smooth transition while preserving all existing data and maintaining backward compatibility during the transition period. 