# Sim Profiles Architecture

## Overview

Sim profiles exist as independent entities that can be discovered publicly and optionally linked to a single user account. This architecture supports public discovery while maintaining user privacy and ownership control.

## Core Principles

1. **Profiles exist independently** - A sim profile exists whether or not it's linked to a user
2. **One profile, one user maximum** - Each profile can be linked to at most one user account
3. **Public by default** - Profiles are discoverable unless explicitly made private
4. **User linking is optional** - Users can claim/link profiles they own, but profiles remain discoverable
5. **Verification matters** - Linked profiles can be verified to prove ownership

## Data Model Architecture

### Current Model Issues
The existing `SimProfile` model incorrectly assumes profiles belong to users:
```python
# CURRENT (INCORRECT)
class SimProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # ❌ Forces ownership
    # ... other fields
```

### Proposed Model Structure

```python
# simlane/sim/models.py
class SimProfile(models.Model):
    """
    Independent sim racing profile that can optionally be linked to a user.
    Profiles exist regardless of user association and are publicly discoverable.
    """
    # Core identity (platform-specific)
    simulator = models.ForeignKey(Simulator, on_delete=models.CASCADE)
    profile_identifier = models.CharField(max_length=255, help_text="Platform-specific unique ID (e.g., iRacing customer ID)")
    profile_name = models.CharField(max_length=255, help_text="Display name on the platform")
    
    # User relationship (optional one-to-one)
    linked_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='linked_sim_profiles',
        help_text="User who has claimed this profile"
    )
    
    # Verification and metadata
    is_verified = models.BooleanField(
        default=False, 
        help_text="True if the linked user has verified ownership of this profile"
    )
    is_public = models.BooleanField(
        default=True, 
        help_text="Whether this profile appears in public searches and listings"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
          linked_at = models.DateTimeField(
          null=True, 
          blank=True, 
          help_text="When this profile was linked to the current user"
      )
      
      # Flexible data storage for platform-specific information
      profile_data = models.JSONField(
          default=dict, 
          help_text="Platform-specific profile data (stats, achievements, etc.)"
      )
      
      class Meta:
        unique_together = ['simulator', 'profile_identifier']
        indexes = [
            models.Index(fields=['simulator', 'profile_identifier']),
            models.Index(fields=['linked_user']),
            models.Index(fields=['is_public']),
            models.Index(fields=['profile_name']),
        ]
    
    def __str__(self):
        return f"{self.simulator.name}: {self.profile_name}"
    
    def get_absolute_url(self):
        """Public URL for this profile"""
        return reverse('profiles:detail', kwargs={
            'simulator_slug': self.simulator.slug,
            'profile_identifier': self.profile_identifier
        })
    
    def get_user_management_url(self):
        """URL for user to manage this profile (if they own it)"""
        if self.linked_user:
            return reverse('users:profile_sim_profile_manage', kwargs={'profile_id': self.pk})
        return None
    
    @property
    def is_owned(self):
        """Returns True if this profile is linked to a user"""
        return self.linked_user is not None
    
    @property
    def display_name(self):
        """Returns the best display name for this profile"""
        if self.linked_user and self.linked_user.get_full_name():
            return f"{self.profile_name} ({self.linked_user.get_full_name()})"
        return self.profile_name
    
    def can_user_link(self, user):
        """Check if a user can link this profile"""
        if self.linked_user is None:
            return True
        return self.linked_user == user
    
    def link_to_user(self, user, verified=False):
        """Link this profile to a user"""
        if self.linked_user and self.linked_user != user:
            raise ValueError(f"Profile already linked to {self.linked_user}")
        
        self.linked_user = user
        self.is_verified = verified
        self.linked_at = timezone.now()
        self.save(update_fields=['linked_user', 'is_verified', 'linked_at'])
    
    def unlink_from_user(self):
        """Remove user link from this profile"""
        self.linked_user = None
        self.is_verified = False
        self.linked_at = None
        self.save(update_fields=['linked_user', 'is_verified', 'linked_at'])
```

## URL Architecture

### Public Profile URLs
```
/profiles/                                           # Browse all public profiles
/profiles/search/?q=<query>                         # Search profiles
/profiles/<simulator_slug>/                         # Browse profiles by simulator
/profiles/<simulator_slug>/<profile_identifier>/    # Individual profile view
```

### User Management URLs
```
/users/profile/sim-profiles/                        # User's linked profiles
/users/profile/sim-profiles/search/                 # Search profiles to link
/users/profile/sim-profiles/link/<profile_id>/      # Link an existing profile
/users/profile/sim-profiles/unlink/<profile_id>/    # Unlink a profile
/users/profile/sim-profiles/verify/<profile_id>/    # Verify ownership
/users/profile/sim-profiles/manage/<profile_id>/    # Manage linked profile settings
```

### Integration URLs
```
/events/<event_id>/results/                         # Race results with profile links
/teams/<team_slug>/members/                         # Team member profiles
/api/profiles/<simulator_slug>/<profile_id>/stats/  # Profile statistics API
```

## User Experience Flows

### 1. Public Discovery Flow
```
Visitor → /profiles/iracing/ → Browse iRacing profiles
Visitor → /profiles/search/?q=john → Find profiles matching "john"
Visitor → /profiles/iracing/123456/ → View John Doe's public profile
```

### 2. Profile Linking Flow
```
User → /users/profile/sim-profiles/ → "Link Profile" button
User → /users/profile/sim-profiles/search/ → Search for their profile
User → Select profile → /users/profile/sim-profiles/link/123/ → Confirm link
System → Profile now linked to user, awaiting verification
```

### 3. Profile Verification Flow
```
User → /users/profile/sim-profiles/ → See "Unverified" status
User → /users/profile/sim-profiles/verify/123/ → Instructions for verification
User → Follow platform-specific verification steps
System → Profile marked as verified
```

### 4. Race Results Integration Flow
```
Visitor → /events/race-123/results/ → See race results
Visitor → Click driver name → /profiles/iracing/123456/ → Driver's public profile
If logged in and owns profile → Additional management options visible
```

## Database Constraints & Business Rules

### Constraints
1. **Unique Profile Identity**: `(simulator, profile_identifier)` must be unique
2. **Optional User Link**: `linked_user` can be NULL (profile exists without user)
3. **Single User Link**: Each profile can link to at most one user
4. **User Can Link Multiple**: A user can link multiple profiles across different simulators

### Business Rules
1. **Profile Creation**: Profiles can be created by system imports or user claiming
2. **Linking**: Users can only link unclaimed profiles or profiles they already own
3. **Unlinking**: Users can unlink their own profiles (profile remains, becomes unclaimed)
4. **Verification**: Only linked profiles can be verified
5. **Privacy**: Users can make their linked profiles private (hidden from public search)

## Data Migration Strategy

### Phase 1: Schema Migration
```python
# Migration to add new fields
class Migration(migrations.Migration):
    operations = [
        migrations.AddField('SimProfile', 'linked_user', models.ForeignKey(...)),
        migrations.AddField('SimProfile', 'is_verified', models.BooleanField(default=False)),
        migrations.AddField('SimProfile', 'is_public', models.BooleanField(default=True)),
        migrations.AddField('SimProfile', 'linked_at', models.DateTimeField(null=True)),
        migrations.AddField('SimProfile', 'profile_data', models.JSONField(default=dict)),
    ]
```

### Phase 2: Data Migration
```python
# Migrate existing user-owned profiles
def migrate_existing_profiles(apps, schema_editor):
    SimProfile = apps.get_model('sim', 'SimProfile')
    
    for profile in SimProfile.objects.filter(user__isnull=False):
        profile.linked_user = profile.user
        profile.is_verified = True  # Assume existing links are verified
        profile.linked_at = profile.created_at
        profile.save()
```

### Phase 3: Schema Cleanup
```python
# Remove old user field after migration
class Migration(migrations.Migration):
    operations = [
        migrations.RemoveField('SimProfile', 'user'),
    ]
```

## Security Considerations

### Profile Privacy
- **Public profiles**: Visible to all, searchable, appear in results
- **Private profiles**: Only visible to linked user and in results they participated in
- **Unlinked profiles**: Always public (no privacy controls without user)

### Verification Security
- **Platform-specific verification**: Each simulator requires different verification methods
- **Verification persistence**: Once verified, remains verified unless explicitly reset
- **False claims**: System should detect and prevent false profile claims

### Data Protection
- **User data**: Only linked user's data is protected under privacy regulations
- **Public data**: Profile performance data is considered public (racing results)
- **Right to be forgotten**: Users can unlink profiles but cannot delete racing history

## Performance Considerations

### Database Indexes
```sql
-- Core lookup indexes
CREATE INDEX sim_profile_simulator_identifier ON sim_simprofile(simulator_id, profile_identifier);
CREATE INDEX sim_profile_linked_user ON sim_simprofile(linked_user_id);
CREATE INDEX sim_profile_public ON sim_simprofile(is_public);
CREATE INDEX sim_profile_name_search ON sim_simprofile(profile_name);

-- Search optimization
CREATE INDEX sim_profile_search ON sim_simprofile USING GIN(to_tsvector('english', profile_name));
```

### Caching Strategy
- **Profile data**: Cache individual profile views (high read, low write)
- **Search results**: Cache search results with reasonable TTL
- **User profile lists**: Cache user's linked profiles
- **Statistics**: Cache computed statistics with longer TTL

### API Rate Limiting
- **Public API**: Rate limit by IP for profile viewing
- **User API**: Rate limit by user for profile management
- **Search API**: More restrictive rate limiting to prevent abuse

## Future Extensibility

### Social Features
- **Following**: Users can follow other profiles (separate table)
- **Teams**: Profile membership in teams
- **Achievements**: Platform-specific achievements and milestones

### Enhanced Verification
- **Multiple verification methods**: Email, SMS, platform API
- **Verification levels**: Basic, platform-verified, identity-verified
- **Verification badges**: Different badges for different verification levels

### Analytics
- **Profile views**: Track public profile view counts
- **Search analytics**: Track popular searches and profiles
- **Performance trends**: Historical performance tracking

## Implementation Notes

### App Structure
```
simlane/
├── sim/                    # Existing sim app
│   ├── models.py          # Updated SimProfile model
│   └── urls.py           # Dashboard URLs (existing)
├── profiles/              # New public profiles app
│   ├── models.py         # No models (uses sim.SimProfile)
│   ├── views.py          # Public profile views
│   ├── urls.py           # Public profile URLs
│   └── templates/
└── users/                 # Updated user management
    ├── views.py          # Updated profile management views
    └── templates/
```

### Template Organization
```
templates/
├── profiles/              # Public profile templates
│   ├── browse.html       # Browse all profiles
│   ├── detail.html       # Individual profile view
│   └── search.html       # Search results
├── users/profile/         # User profile management
│   ├── sim_profiles.html # User's linked profiles
│   └── sim_profile_*.html # Link/unlink/verify templates
└── components/            # Reusable components
    └── profile_card.html  # Profile display card
```

This architecture provides a clean separation between public profile discovery and user profile management while maintaining data integrity and supporting future growth. 