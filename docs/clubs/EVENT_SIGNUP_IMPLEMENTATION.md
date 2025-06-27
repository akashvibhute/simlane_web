# Club Event Signup Implementation

## Overview

This document describes the implementation of the club event signup system that allows clubs to create signup sheets for existing events without duplicating the events themselves.

## Key Components

### 1. Enhanced EventParticipation Model

The `EventParticipation` model has been enhanced with:
- **`signup_context_club`**: Links participation to a specific club's signup sheet
- **Instance-level constraint**: Users can only participate in one event instance with one club at a time

```python
class EventParticipation(models.Model):
    # Club context for signup
    signup_context_club = models.ForeignKey(
        Club, 
        null=True, 
        blank=True,
        related_name='event_signups',
        help_text="Which club this signup is associated with"
    )
```

### 2. ClubEventSignupSheet Model

A new model to manage club-specific signup sheets:

```python
class ClubEventSignupSheet(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    signup_opens = models.DateTimeField()
    signup_closes = models.DateTimeField()
    status = models.CharField(choices=...)
    # Team formation settings
    max_teams = models.IntegerField(null=True, blank=True)
    target_team_size = models.IntegerField(default=3)
    # ... other fields
```

## How It Works

### Phase 1: Interest Collection
1. Club admin creates a `ClubEventSignupSheet` for an existing event
2. Members see the signup sheet and can express interest
3. `EventParticipation` records are created with:
   - `signup_context_club` = the club
   - `status` = 'signed_up'
   - No team assignment yet

### Phase 2: Team Formation
1. When signups close, club admins can form teams
2. Teams are created and members assigned
3. `EventParticipation` records are updated with team assignments

### Phase 3: Event Registration
1. Teams commit to specific event instances
2. Instance-level constraint ensures no double-booking

## User Scenarios

### Scenario: Multiple Clubs, Same Event

```
Event: 24 Hours of Le Mans Virtual
├── Club A creates signup sheet
│   ├── Member John signs up via Club A
│   └── Member Jane signs up via Club A
└── Club B creates signup sheet
    ├── Member John signs up via Club B (allowed!)
    └── Member Bob signs up via Club B
```

### Instance Commitment

- John (via Club A) → Assigned to March instance ✓
- John (via Club B) → Cannot be assigned to March instance ✗
- John (via Club B) → Can be assigned to June instance ✓

## Implementation Status

### ✅ Completed
- Enhanced `EventParticipation` model with club context
- Created `ClubEventSignupSheet` model
- Added migrations
- Created admin interface
- Views and forms for creating signup sheets
- URL routing
- Template integration
- Club dashboard integration
- Navigation links for admins

### 🚧 TODO
- Member signup flow (individual signup forms)
- Team formation interface
- Availability window integration
- Email notifications
- Advanced management features

## Usage

### For Club Admins
1. Navigate to club dashboard
2. Go to "Event Signups" section
3. Click "Create Signup Sheet"
4. Select event and configure settings
5. Open signups when ready

### For Club Members
1. View open signup sheets in club
2. Click to sign up for event
3. Provide availability windows
4. Wait for team assignment

## Benefits

1. **No Event Duplication**: Uses existing events from the system
2. **Multi-Club Support**: Members can sign up via multiple clubs
3. **Flexible Teams**: Teams formed after interest is gathered
4. **Instance Protection**: Prevents double-booking at instance level
5. **Club Autonomy**: Each club manages their own signups independently 