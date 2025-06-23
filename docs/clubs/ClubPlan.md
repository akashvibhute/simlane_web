I have created the following plan after thorough exploration and analysis of the codebase. Follow the below plan verbatim. Trust the files and references. Do not re-verify what's written in the plan. Explore only when aboslutely necessary. First implement all the proposed file changes and then I'll review all the changes together at the end.

### Observations

Based on my exploration of the codebase, I have a comprehensive understanding of the Django application structure. The project uses Django with HTMX for dynamic interactions, Tailwind CSS for styling, and follows established patterns for models, views, templates, and services. The existing teams app provides a solid foundation with Club, Team, EventEntry, and related models already in place. The UI uses Cotton components and follows consistent styling patterns. Email services are already implemented in the core app, providing a template for notification systems.

### Approach

I'll build upon the existing teams app structure to implement the complete club management and event planning workflow. The approach will extend current models with new invitation and signup models, create comprehensive forms and views for each workflow step, implement business logic services for team splitting and stint planning, and build responsive UI components that integrate seamlessly with the existing HTMX-powered dashboard system. The implementation will follow Django best practices and maintain consistency with existing code patterns.

### Reasoning

I analyzed the existing codebase structure by examining the teams and sim models to understand the data relationships, reviewed the current views and templates to understand the UI patterns and HTMX integration, checked the admin configurations and form patterns to understand the established conventions, examined the service layer structure to understand business logic organization, and reviewed the base templates and component structure to understand the styling and component patterns used throughout the application.

## Mermaid Diagram

sequenceDiagram
    participant Admin as Club Admin
    participant System as SimLane System
    participant Member as Club Member
    participant Email as Email Service
    participant Team as Team Dashboard

    Note over Admin, Team: Club Management & Event Planning Workflow

    Admin->>System: Create Club
    System->>Admin: Club Dashboard Access

    Admin->>System: Invite Members (email)
    System->>Email: Send Invitation
    Email->>Member: Invitation Email
    Member->>System: Accept Invitation
    System->>Admin: Member Joined Notification

    Admin->>System: Create Event Signup Sheet
    System->>Member: Signup Available Notification
    Member->>System: Sign Up (car choice, availability)
    System->>Email: Signup Confirmation
    Email->>Member: Confirmation Email

    Admin->>System: Close Signup & Allocate Teams
    System->>Admin: Team Allocation Wizard
    Admin->>System: Finalize Team Allocations
    System->>Member: Team Assignment Notification
    System->>Team: Create Team Planning Dashboard

    Member->>Team: Access Team Dashboard
    Team->>Member: Stint Planning Interface
    Member->>Team: Update Stint Plans
    Team->>System: Save Stint Plans
    System->>Member: Race Day Schedule

## Proposed File Changes

### simlane/teams/models.py(MODIFY)

References: 

- simlane/sim/models.py

Add new models to support the club management workflow:

1. **ClubInvitation model** - Track invitations sent to users to join clubs

   - Fields: id, club (FK), inviter (FK to User), invitee_email, invitee_user (FK to User, nullable), role, token (unique), status (pending/accepted/declined/expired), expires_at, created_at, updated_at
   - Methods: is_expired(), accept(), decline()

2. **EventSignup model** - Aggregate signup information for events

   - Fields: id, event (FK), club (FK), created_by (FK to User), title, description, signup_deadline, max_participants, is_active, created_at, updated_at
   - This acts as a container for organizing signups for a specific event

3. **EventSignupEntry model** - Individual member signups for events

   - Fields: id, signup (FK to EventSignup), user (FK), preferred_sim_car (FK to SimCar), backup_sim_car (FK to SimCar, nullable), role_preference (driver/spectator), notes, created_at, updated_at
   - This replaces/extends the current EventEntry for the signup phase

4. **EventSignupAvailability model** - Member availability for event instances

   - Fields: id, signup_entry (FK), event_instance (FK), available (boolean), preferred_stint_duration (integer, nullable), notes, created_at, updated_at

5. **TeamAllocation model** - Admin's allocation of members to teams

   - Fields: id, event_signup (FK), team (FK), assigned_sim_car (FK to SimCar), created_by (FK to User), created_at, updated_at

6. **TeamAllocationMember model** - Members assigned to each team allocation

   - Fields: id, team_allocation (FK), user (FK), role (driver/spectator), created_at, updated_at

Add indexes and constraints for performance and data integrity. Update existing models if needed to support the new workflow.

### simlane/teams/migrations/0003_add_club_management_models.py(NEW)

References: 

- simlane/teams/models.py(MODIFY)

Create Django migration file for the new models added to `simlane/teams/models.py`. This migration will:

1. Create ClubInvitation table with proper foreign key relationships
2. Create EventSignup table
3. Create EventSignupEntry table
4. Create EventSignupAvailability table
5. Create TeamAllocation table
6. Create TeamAllocationMember table
7. Add necessary indexes for performance
8. Add unique constraints where appropriate

Generate this migration using Django's makemigrations command after adding the models to models.py.

### simlane/teams/forms.py(NEW)

References: 

- simlane/users/forms.py
- simlane/templates/cotton/form_field.html

Create comprehensive forms for the club management workflow following the patterns established in `simlane/users/forms.py`:

1. **ClubCreateForm** - Form for creating new clubs
   - Fields: name, description, logo_url, website, social_links
   - Custom validation for unique club names
   - Tailwind CSS styling consistent with existing forms

2. **ClubUpdateForm** - Form for updating club information
   - Same fields as ClubCreateForm
   - Additional validation for admin permissions

3. **ClubInvitationForm** - Form for inviting members to clubs
   - Fields: email, role, personal_message
   - Email validation and role selection
   - Check if user is already a member

4. **EventSignupCreateForm** - Form for creating event signup sheets
   - Fields: event (dropdown), title, description, signup_deadline, max_participants
   - Event selection filtered by club's accessible events
   - Date validation for signup deadline

5. **EventSignupEntryForm** - Form for members to sign up for events
   - Fields: preferred_sim_car, backup_sim_car, role_preference, notes
   - Dynamic car selection based on event requirements
   - Validation for car availability

6. **EventSignupAvailabilityFormSet** - Formset for availability across multiple event instances
   - Dynamic forms for each event instance
   - Boolean availability with optional stint duration preferences

7. **TeamAllocationForm** - Form for admins to create team allocations
   - Fields: team, assigned_sim_car, selected_members
   - Multi-select for members with JavaScript enhancement
   - Validation for team capacity and car assignments

All forms will include proper error handling, help text, and consistent styling using the patterns from `simlane/templates/cotton/form_field.html`.

### simlane/teams/services.py(NEW)

References: 

- simlane/core/services.py

Create business logic services following the pattern established in `simlane/core/services.py`:

1. **ClubInvitationService** - Handle club invitation workflow
   - `send_invitation(club, inviter, email, role, message)` - Create and send invitation emails
   - `accept_invitation(token, user)` - Process invitation acceptance
   - `decline_invitation(token)` - Process invitation decline
   - `cleanup_expired_invitations()` - Remove expired invitations

2. **EventSignupService** - Manage event signup workflows
   - `create_signup_sheet(club, event, creator, details)` - Create new signup sheet
   - `process_member_signup(signup, user, preferences, availability)` - Handle member signups
   - `get_signup_summary(signup_id)` - Generate signup statistics and summaries
   - `close_signup(signup_id)` - Close signup and prepare for team allocation

3. **TeamAllocationService** - Handle team splitting and allocation
   - `suggest_team_allocations(signup_id, criteria)` - AI-assisted team splitting based on availability, car preferences, and skill levels
   - `create_team_allocation(signup_id, allocations)` - Create team allocations from admin decisions
   - `validate_allocation(allocation_data)` - Ensure allocations meet event requirements
   - `finalize_allocations(signup_id)` - Convert allocations to actual EventEntry records

4. **StintPlanningService** - Generate stint plans and pit strategies
   - `generate_stint_plan(team_allocation, event_instance)` - Create initial stint assignments
   - `calculate_pit_windows(event_instance, sim_car)` - Use PitData to suggest optimal pit stops
   - `optimize_driver_rotation(team_allocation, availability)` - Balance driving time based on availability
   - `export_stint_plan(team_allocation)` - Generate exportable stint plan

5. **NotificationService** - Handle email and future Discord notifications
   - `send_invitation_email(invitation)` - Send club invitation emails
   - `send_signup_confirmation(signup_entry)` - Confirm event signup
   - `send_team_allocation_notification(allocation)` - Notify members of team assignments
   - `send_stint_plan_update(team_allocation)` - Notify team of stint plan changes

All services will include proper error handling, logging, and transaction management.

### simlane/teams/views.py(MODIFY)

Extend the existing views in `simlane/teams/views.py` to support the complete club management workflow. Add new view functions and classes while maintaining the existing HTMX patterns:

1. **Club Management Views**
   - `club_create(request)` - GET/POST for creating new clubs
   - `club_update(request, club_id)` - GET/POST for updating club details
   - `club_members(request, club_id)` - List and manage club members
   - `club_invite_member(request, club_id)` - GET/POST for sending invitations
   - `club_invitation_accept(request, token)` - Process invitation acceptance
   - `club_invitation_decline(request, token)` - Process invitation decline

2. **Event Signup Views**
   - `event_signup_create(request, club_id)` - Create new event signup sheet
   - `event_signup_detail(request, signup_id)` - View signup sheet details and entries
   - `event_signup_join(request, signup_id)` - Member signup form
   - `event_signup_update(request, signup_id, entry_id)` - Update existing signup
   - `event_signup_close(request, signup_id)` - Close signup for team allocation

3. **Team Allocation Views**
   - `team_allocation_wizard(request, signup_id)` - Multi-step team allocation interface
   - `team_allocation_preview(request, signup_id)` - Preview suggested allocations
   - `team_allocation_create(request, signup_id)` - Finalize team allocations
   - `team_allocation_update(request, allocation_id)` - Modify existing allocations

4. **Team Planning Views**
   - `team_planning_dashboard(request, allocation_id)` - Team-specific planning interface
   - `stint_planning(request, allocation_id)` - Stint planning and pit strategy
   - `stint_plan_update(request, allocation_id)` - Update stint assignments
   - `stint_plan_export(request, allocation_id)` - Export stint plan as PDF/CSV

5. **HTMX Partial Views**
   - `club_members_partial(request, club_id)` - Dynamic member list updates
   - `signup_entries_partial(request, signup_id)` - Dynamic signup list
   - `team_allocation_partial(request, signup_id)` - Dynamic team allocation interface
   - `stint_plan_partial(request, allocation_id)` - Dynamic stint plan updates

All views will include proper permission checks using decorators, error handling, and HTMX response patterns established in the existing code. Update the existing `club_dashboard_section` view to include new sections for event signups and team allocations.

### simlane/teams/urls.py(MODIFY)

Extend the existing URL patterns in `simlane/teams/urls.py` to include all new views while maintaining the current structure:

1. **Club Management URLs**
   - `path("clubs/create/", views.club_create, name="club_create")`
   - `path("clubs/<uuid:club_id>/update/", views.club_update, name="club_update")`
   - `path("clubs/<uuid:club_id>/members/", views.club_members, name="club_members")`
   - `path("clubs/<uuid:club_id>/invite/", views.club_invite_member, name="club_invite_member")`
   - `path("invite/<str:token>/accept/", views.club_invitation_accept, name="club_invitation_accept")`
   - `path("invite/<str:token>/decline/", views.club_invitation_decline, name="club_invitation_decline")`

2. **Event Signup URLs**
   - `path("clubs/<uuid:club_id>/signups/create/", views.event_signup_create, name="event_signup_create")`
   - `path("signups/<uuid:signup_id>/", views.event_signup_detail, name="event_signup_detail")`
   - `path("signups/<uuid:signup_id>/join/", views.event_signup_join, name="event_signup_join")`
   - `path("signups/<uuid:signup_id>/entries/<uuid:entry_id>/update/", views.event_signup_update, name="event_signup_update")`
   - `path("signups/<uuid:signup_id>/close/", views.event_signup_close, name="event_signup_close")`

3. **Team Allocation URLs**
   - `path("signups/<uuid:signup_id>/allocate/", views.team_allocation_wizard, name="team_allocation_wizard")`
   - `path("signups/<uuid:signup_id>/allocate/preview/", views.team_allocation_preview, name="team_allocation_preview")`
   - `path("signups/<uuid:signup_id>/allocate/create/", views.team_allocation_create, name="team_allocation_create")`
   - `path("allocations/<uuid:allocation_id>/update/", views.team_allocation_update, name="team_allocation_update")`

4. **Team Planning URLs**
   - `path("allocations/<uuid:allocation_id>/planning/", views.team_planning_dashboard, name="team_planning_dashboard")`
   - `path("allocations/<uuid:allocation_id>/stints/", views.stint_planning, name="stint_planning")`
   - `path("allocations/<uuid:allocation_id>/stints/update/", views.stint_plan_update, name="stint_plan_update")`
   - `path("allocations/<uuid:allocation_id>/stints/export/", views.stint_plan_export, name="stint_plan_export")`

5. **HTMX Partial URLs**
   - `path("clubs/<uuid:club_id>/members/partial/", views.club_members_partial, name="club_members_partial")`
   - `path("signups/<uuid:signup_id>/entries/partial/", views.signup_entries_partial, name="signup_entries_partial")`
   - `path("signups/<uuid:signup_id>/allocate/partial/", views.team_allocation_partial, name="team_allocation_partial")`
   - `path("allocations/<uuid:allocation_id>/stints/partial/", views.stint_plan_partial, name="stint_plan_partial")`

Maintain the existing URL structure and naming conventions. Ensure all URLs use UUID parameters for security and consistency.

### simlane/teams/admin.py(MODIFY)

Extend the existing admin configuration in `simlane/teams/admin.py` to include the new models following the established patterns:

1. **ClubInvitationAdmin** - Admin interface for managing club invitations
   - List display: invitee_email, club, role, status, created_at, expires_at
   - List filters: status, role, club, created_at
   - Search fields: invitee_email, club__name, inviter__username
   - Actions: resend_invitation, mark_as_expired
   - Readonly fields: token, created_at, updated_at

2. **EventSignupAdmin** - Admin interface for event signups
   - List display: title, event, club, created_by, signup_deadline, is_active
   - List filters: club, event__simulator, is_active, created_at
   - Search fields: title, event__name, club__name
   - Readonly fields: created_at, updated_at

3. **EventSignupEntryAdmin** - Admin interface for signup entries
   - List display: user, signup, preferred_sim_car, role_preference, created_at
   - List filters: signup__club, role_preference, preferred_sim_car, created_at
   - Search fields: user__username, signup__title
   - Raw ID fields: user, signup, preferred_sim_car, backup_sim_car

4. **EventSignupAvailabilityAdmin** - Admin interface for availability
   - List display: signup_entry, event_instance, available, preferred_stint_duration
   - List filters: available, event_instance__event, created_at
   - Search fields: signup_entry__user__username

5. **TeamAllocationAdmin** - Admin interface for team allocations
   - List display: event_signup, team, assigned_sim_car, created_by, created_at
   - List filters: team__club, assigned_sim_car, created_at
   - Search fields: team__name, event_signup__title
   - Raw ID fields: event_signup, team, assigned_sim_car, created_by

6. **TeamAllocationMemberAdmin** - Admin interface for allocation members
   - List display: team_allocation, user, role, created_at
   - List filters: role, team_allocation__team__club, created_at
   - Search fields: user__username, team_allocation__team__name

All admin classes will use the Unfold admin theme consistent with existing admin configurations and include proper permissions and validation.

### simlane/templates/teams/club_create.html(NEW)

References: 

- simlane/templates/teams/clubs_dashboard.html
- simlane/templates/teams/club_dashboard.html
- simlane/templates/components/form.html

Create a template for club creation following the design patterns from `simlane/templates/teams/clubs_dashboard.html` and `simlane/templates/teams/club_dashboard.html`:

1. **Layout Structure**
   - Extend base.html with consistent header and navigation
   - Use the same Tailwind CSS classes and component structure
   - Include breadcrumb navigation back to clubs dashboard

2. **Form Section**
   - Use the form component pattern from `simlane/templates/components/form.html`
   - Include all club creation fields with proper validation display
   - Add file upload preview for logo (if implementing file upload)
   - Include social links as a dynamic form section

3. **UI Elements**
   - Form validation messages using the existing message component
   - Submit and cancel buttons with consistent styling
   - Help text and field descriptions
   - Responsive design for mobile and desktop

4. **JavaScript Integration**
   - Form validation enhancements
   - Dynamic social links addition/removal
   - Logo preview functionality
   - HTMX integration for form submission if needed

The template will maintain visual consistency with existing club dashboard pages and provide a smooth user experience for club creation.

### simlane/templates/teams/club_members.html(NEW)

References: 

- simlane/templates/teams/club_dashboard.html

Create a template for club member management following the existing dashboard patterns:

1. **Header Section**
   - Club information display with logo and basic details
   - Action buttons for inviting new members (admin/teams_manager only)
   - Member count and role distribution statistics

2. **Members List**
   - Table or card layout showing all club members
   - Display: avatar, name, username, role, join date, last active
   - Role badges with different colors for admin/teams_manager/member
   - Action buttons for role changes (admin only) and member removal

3. **Invitation Management Section**
   - List of pending invitations with status
   - Resend and cancel invitation actions
   - Invitation history and tracking

4. **HTMX Integration**
   - Dynamic member list updates
   - Inline role editing
   - Real-time invitation status updates
   - Modal dialogs for confirmations

5. **Responsive Design**
   - Mobile-friendly member cards
   - Collapsible sections for better mobile experience
   - Consistent with existing dashboard styling

Include proper permission checks in the template to show/hide admin-only features.

### simlane/templates/teams/event_signup_create.html(NEW)

References: 

- simlane/templates/components/form.html

Create a template for creating event signup sheets:

1. **Form Layout**
   - Multi-step form wizard for signup sheet creation
   - Step 1: Event selection with filtering by simulator and date
   - Step 2: Signup details (title, description, deadline, max participants)
   - Step 3: Configuration (car restrictions, role requirements)
   - Step 4: Review and confirmation

2. **Event Selection Interface**
   - Searchable dropdown or card layout for event selection
   - Event details preview with track, car classes, and schedule
   - Event instance selection for multi-session events

3. **Configuration Options**
   - Car class restrictions and allowed vehicles
   - Driver/spectator role requirements
   - Signup deadline with date/time picker
   - Maximum participant limits

4. **Preview Section**
   - Live preview of how the signup sheet will appear to members
   - Summary of all selected options and restrictions
   - Validation warnings and recommendations

5. **HTMX Enhancements**
   - Dynamic event filtering and search
   - Real-time form validation
   - Step navigation without page reloads
   - Auto-save draft functionality

Use consistent styling with existing forms and maintain the established UI patterns.

### simlane/templates/teams/event_signup_detail.html(NEW)

References: 

- simlane/templates/teams/club_dashboard.html

Create a comprehensive template for viewing and managing event signup sheets:

1. **Signup Overview Section**
   - Event details with track image, schedule, and requirements
   - Signup statistics: total signups, drivers vs spectators, car preferences
   - Signup deadline countdown and status indicators
   - Admin actions: edit signup, close signup, create teams

2. **Signups List**
   - Tabular or card view of all member signups
   - Display: member name, preferred car, backup car, role, availability summary
   - Filtering and sorting options: by role, car preference, availability
   - Export functionality for signup data

3. **Availability Matrix**
   - Visual grid showing member availability across event instances
   - Color-coded availability status (available/unavailable/partial)
   - Stint duration preferences where applicable
   - Quick overview for team allocation planning

4. **Member Actions**
   - Join signup button for eligible members
   - Edit existing signup entries
   - Withdraw from signup with confirmation
   - Availability updates

5. **Admin Tools** (for club admins/teams_managers)
   - Team allocation wizard launch
   - Signup management (approve/reject entries)
   - Communication tools (message all participants)
   - Signup analytics and reports

6. **HTMX Features**
   - Real-time signup updates
   - Dynamic availability editing
   - Inline signup modifications
   - Live statistics updates

Include responsive design for mobile viewing and maintain consistency with dashboard styling.

### simlane/templates/teams/team_allocation_wizard.html(NEW)

References: 

- simlane/templates/teams/club_dashboard.html

Create an interactive team allocation wizard template:

1. **Wizard Steps Layout**
   - Step indicator showing progress through allocation process
   - Step 1: Review signups and requirements
   - Step 2: Configure allocation criteria
   - Step 3: Auto-suggest teams or manual allocation
   - Step 4: Review and finalize allocations

2. **Signup Review Section**
   - Summary of all signups with key information
   - Availability matrix for quick reference
   - Car preference distribution
   - Skill level indicators (if available from sim profiles)

3. **Allocation Criteria Configuration**
   - Team size preferences (min/max drivers per team)
   - Car distribution strategy (one car per team vs mixed)
   - Skill balancing options
   - Availability optimization settings

4. **Team Allocation Interface**
   - Drag-and-drop interface for manual team assignment
   - Auto-suggest button with algorithm-generated teams
   - Team cards showing assigned members and cars
   - Validation warnings for unbalanced teams

5. **Review and Finalization**
   - Final team roster with all assignments
   - Validation checks for event requirements
   - Member notification preview
   - Confirmation and creation buttons

6. **Interactive Features**
   - Drag-and-drop member assignment
   - Real-time validation feedback
   - Team balance indicators
   - Undo/redo functionality

Implement with HTMX for smooth interactions and maintain visual consistency with existing dashboard components.

### simlane/templates/teams/team_planning_dashboard.html(NEW)

References: 

- simlane/sim/models.py
- simlane/templates/teams/club_dashboard.html

Create a comprehensive team planning dashboard template:

1. **Team Overview Section**
   - Team name, assigned car, and event details
   - Team member roster with roles and contact information
   - Event schedule and track information
   - Quick statistics: total driving time, pit stops, fuel requirements

2. **Stint Planning Interface**
   - Timeline view of the race with stint assignments
   - Driver rotation schedule with time slots
   - Pit stop planning with fuel and tire strategies
   - Driver availability overlay on timeline

3. **Pit Strategy Section**
   - Calculated pit windows based on PitData from `simlane/sim/models.py`
   - Fuel consumption estimates and refueling schedules
   - Tire strategy recommendations
   - Minimum pit stop requirements compliance

4. **Driver Management**
   - Individual driver stint assignments
   - Driving time distribution and fairness indicators
   - Driver preferences and availability constraints
   - Substitute driver assignments

5. **Communication Tools**
   - Team chat or message board
   - Important announcements section
   - Contact information for all team members
   - Integration with Discord (future enhancement)

6. **Export and Sharing**
   - Export stint plan as PDF or spreadsheet
   - Share planning link with team members
   - Print-friendly race day schedule
   - Mobile-optimized view for race day

7. **Real-time Updates**
   - HTMX-powered live updates to stint plans
   - Collaborative editing indicators
   - Auto-save functionality
   - Change history and rollback options

Integrate with PitData model to provide accurate pit strategy calculations and maintain consistency with existing dashboard styling.

### simlane/templates/teams/club_dashboard_content_partial.html(MODIFY)

Extend the existing club dashboard content partial to include new sections for event signups and team management:

1. **Add Event Signups Section**
   - List of active and past event signups for the club
   - Quick actions: create new signup, view signup details
   - Signup status indicators and participant counts
   - Recent signup activity feed

2. **Add Team Allocations Section**
   - Current team allocations for upcoming events
   - Team allocation status (draft, finalized, active)
   - Quick links to team planning dashboards
   - Allocation management tools for admins

3. **Enhance Members Section**
   - Add invitation management for admins
   - Show pending invitations count
   - Member activity indicators
   - Quick member search and filtering

4. **Update Events Section**
   - Integration with signup sheets
   - Show events with active signups
   - Event participation statistics
   - Links to create signups for upcoming events

5. **Add Settings Section** (for admins/teams_managers)
   - Club configuration options
   - Invitation settings and permissions
   - Event signup defaults and templates
   - Member role management

Maintain the existing HTMX structure and ensure all new sections integrate seamlessly with the current navigation and content loading patterns.

### simlane/templates/emails/club_invitation.html(NEW)

References: 

- simlane/templates/core/emails/contact_confirmation.html

Create email templates for club invitations following the pattern from `simlane/templates/core/emails/contact_confirmation.html`:

1. **HTML Email Template**
   - Professional email design consistent with SimLane branding
   - Club logo and information display
   - Clear invitation message with inviter details
   - Prominent accept/decline action buttons
   - Club description and member benefits
   - Footer with unsubscribe and contact information

2. **Email Content Structure**
   - Personalized greeting with invitee name/email
   - Club invitation details (club name, role, inviter)
   - Custom message from inviter (if provided)
   - Clear call-to-action buttons
   - Invitation expiry information
   - Alternative text links for email clients without HTML support

3. **Responsive Design**
   - Mobile-friendly email layout
   - Proper fallbacks for different email clients
   - Accessible design with proper contrast and font sizes
   - Compatible with major email providers

4. **Security Features**
   - Secure invitation token handling
   - Clear indication of invitation authenticity
   - Warning about phishing attempts
   - Contact information for support

Create both HTML and plain text versions of the email template for maximum compatibility.

### simlane/templates/emails/event_signup_confirmation.html(NEW)

References: 

- simlane/templates/core/emails/contact_confirmation.html

Create email templates for event signup confirmations:

1. **HTML Email Template**
   - Event details with track image and schedule
   - Signup confirmation details (car choice, role, availability)
   - Next steps information (team allocation timeline)
   - Event preparation checklist
   - Contact information for questions

2. **Email Content**
   - Personalized confirmation message
   - Event summary (name, date, track, car class)
   - Member's signup details recap
   - Important dates and deadlines
   - Links to update signup or view event details

3. **Team Allocation Notification**
   - Separate template for when teams are finalized
   - Team assignment details
   - Team member contact information
   - Link to team planning dashboard
   - Race day preparation information

Use consistent branding and responsive design patterns from existing email templates.

### simlane/teams/decorators.py(NEW)

References: 

- simlane/teams/views.py(MODIFY)

Create custom decorators for permission checking in the teams app:

1. **club_admin_required** - Decorator to ensure user is club admin
   - Check if user has admin role in the specified club
   - Return 403 error or redirect if not authorized
   - Support for both function and class-based views

2. **club_manager_required** - Decorator for admin or teams_manager roles
   - Allow both admin and teams_manager roles
   - Used for most club management functions
   - Flexible club identification (URL parameter, form data, etc.)

3. **club_member_required** - Decorator to ensure user is club member
   - Basic membership check for any role
   - Used for viewing club content and participating in events
   - Support for invitation token access

4. **event_signup_access** - Decorator for event signup permissions
   - Check if user can access specific signup sheets
   - Validate signup is open and user is eligible
   - Handle different access levels (view, participate, manage)

5. **team_allocation_access** - Decorator for team allocation permissions
   - Ensure user can view or modify team allocations
   - Check if user is team member or club manager
   - Validate allocation status and permissions

All decorators will include proper error handling, logging, and integration with Django's permission system.

### simlane/teams/utils.py(NEW)

Create utility functions for the teams app:

1. **Token Generation and Validation**
   - `generate_invitation_token()` - Create secure invitation tokens
   - `validate_invitation_token(token)` - Verify token validity and expiry
   - `generate_secure_slug()` - Create URL-safe identifiers

2. **Team Allocation Algorithms**
   - `balance_teams_by_skill(signups, team_count)` - Distribute members by skill level
   - `optimize_car_distribution(signups, available_cars)` - Assign cars based on preferences
   - `calculate_availability_overlap(members, event_instances)` - Find optimal driver rotations
   - `suggest_team_compositions(signups, criteria)` - AI-assisted team suggestions

3. **Stint Planning Calculations**
   - `calculate_stint_duration(event_length, driver_count, pit_stops)` - Optimal stint lengths
   - `estimate_fuel_consumption(car, track, stint_duration)` - Fuel planning
   - `calculate_pit_windows(event_instance, pit_data)` - Optimal pit stop timing
   - `generate_driver_rotation(team_members, availability, event_duration)` - Fair time distribution

4. **Data Export Utilities**
   - `export_signup_data(signup_id, format)` - Export signup sheets as CSV/Excel
   - `generate_stint_plan_pdf(team_allocation)` - Create printable stint plans
   - `export_team_roster(allocation_id)` - Generate team contact lists

5. **Notification Helpers**
   - `prepare_invitation_context(invitation)` - Email template context
   - `format_event_details(event)` - Consistent event formatting
   - `generate_notification_summary(signup)` - Signup summary for emails

Include comprehensive error handling and logging for all utility functions.

### simlane/teams/tests(NEW)

Create a comprehensive test directory structure for the teams app:

1. **test_models.py** - Test all model functionality
   - Test model creation, validation, and relationships
   - Test custom model methods and properties
   - Test model constraints and unique together fields
   - Test invitation token generation and validation

2. **test_views.py** - Test all view functionality
   - Test GET and POST requests for all views
   - Test permission checking and access control
   - Test HTMX partial responses
   - Test form validation and error handling

3. **test_forms.py** - Test form validation and behavior
   - Test form field validation
   - Test custom form logic and clean methods
   - Test formset functionality
   - Test form rendering and widget behavior

4. **test_services.py** - Test business logic services
   - Test invitation workflow
   - Test team allocation algorithms
   - Test stint planning calculations
   - Test notification sending

5. **test_utils.py** - Test utility functions
   - Test token generation and validation
   - Test calculation functions
   - Test export functionality
   - Test data formatting helpers

6. **factories.py** - Test data factories using factory_boy
   - Factories for all new models
   - Realistic test data generation
   - Support for complex object relationships

Use Django's TestCase and follow testing best practices with proper setup, teardown, and assertion methods.

### simlane/static/js/team_allocation.js(NEW)

Create JavaScript functionality for the team allocation wizard:

1. **Drag and Drop Interface**
   - Implement drag-and-drop for member assignment to teams
   - Visual feedback during drag operations
   - Validation during drop operations
   - Undo/redo functionality for allocation changes

2. **Real-time Validation**
   - Check team size constraints
   - Validate car assignments and availability
   - Show warnings for unbalanced teams
   - Highlight conflicts and issues

3. **Auto-suggestion Integration**
   - AJAX calls to get algorithm-suggested teams
   - Apply suggestions with animation
   - Compare different suggestion algorithms
   - Save and load allocation presets

4. **Interactive Features**
   - Member search and filtering
   - Team statistics and balance indicators
   - Collapsible team sections
   - Keyboard shortcuts for power users

5. **HTMX Integration**
   - Seamless integration with HTMX responses
   - Partial page updates for allocation changes
   - Real-time collaboration indicators
   - Auto-save functionality

Use modern JavaScript (ES6+) with proper error handling and accessibility features.

### simlane/static/js/stint_planning.js(NEW)

Create JavaScript functionality for stint planning interface:

1. **Timeline Interface**
   - Interactive timeline for race duration
   - Drag-and-drop stint assignment
   - Visual representation of driver rotations
   - Pit stop markers and timing

2. **Calculation Engine**
   - Real-time fuel consumption calculations
   - Pit window optimization
   - Driver time distribution balancing
   - Stint duration validation

3. **Collaborative Features**
   - Real-time updates from other team members
   - Change conflict resolution
   - Comment and annotation system
   - Version history and rollback

4. **Mobile Optimization**
   - Touch-friendly interface for mobile devices
   - Responsive timeline scaling
   - Simplified mobile view for race day
   - Offline capability for race day use

5. **Export Integration**
   - Generate printable schedules
   - Export to calendar applications
   - Share links with team members
   - Integration with external timing systems

Implement with proper error handling, accessibility features, and performance optimization.

### simlane/static/css/teams.css(NEW)

Create additional CSS styles for teams-specific components:

1. **Team Allocation Styles**
   - Drag-and-drop visual feedback
   - Team card layouts and hover effects
   - Member assignment indicators
   - Validation warning styles

2. **Stint Planning Styles**
   - Timeline visualization styles
   - Driver rotation color coding
   - Pit stop markers and indicators
   - Mobile-responsive timeline layout

3. **Signup Sheet Styles**
   - Availability matrix styling
   - Car preference indicators
   - Status badges and icons
   - Responsive table layouts

4. **Animation and Transitions**
   - Smooth drag-and-drop animations
   - Loading states and spinners
   - Success/error state transitions
   - Hover and focus effects

5. **Print Styles**
   - Print-optimized stint plans
   - Clean roster layouts
   - Race day schedule formatting
   - QR code integration for mobile access

Use CSS custom properties for theming and maintain consistency with existing Tailwind CSS classes.

### simlane/teams/management(NEW)

Create management command directory structure for teams app administrative tasks.

### simlane/teams/management/commands/cleanup_expired_invitations.py(NEW)

Create Django management command to clean up expired invitations:

1. **Command Functionality**
   - Find and delete expired club invitations
   - Log cleanup statistics
   - Optional dry-run mode for testing
   - Configurable expiry threshold

2. **Command Options**
   - `--dry-run` - Show what would be deleted without actually deleting
   - `--days` - Override default expiry days
   - `--verbose` - Detailed logging output
   - `--club` - Limit cleanup to specific club

3. **Logging and Reporting**
   - Count of expired invitations found
   - Details of deleted invitations
   - Error handling and reporting
   - Integration with Django logging system

4. **Scheduling Integration**
   - Design for cron job execution
   - Proper exit codes for monitoring
   - Lock file handling to prevent concurrent runs
   - Email notifications for cleanup results

Implement following Django management command best practices with proper argument parsing and error handling.

### simlane/teams/management/commands/generate_sample_data.py(NEW)

Create Django management command to generate sample data for development and testing:

1. **Sample Data Generation**
   - Create sample clubs with realistic names and descriptions
   - Generate club members with different roles
   - Create sample events and signup sheets
   - Generate realistic team allocations and stint plans

2. **Command Options**
   - `--clubs` - Number of clubs to create
   - `--members-per-club` - Average members per club
   - `--events` - Number of events to create
   - `--signups` - Number of signup sheets to create
   - `--clear` - Clear existing sample data first

3. **Realistic Data**
   - Use faker library for realistic names and descriptions
   - Create logical relationships between entities
   - Generate realistic availability patterns
   - Include edge cases and various scenarios

4. **Development Support**
   - Create admin user accounts for testing
   - Generate test invitation tokens
   - Create sample pit data and car configurations
   - Include both active and historical data

Design for easy development environment setup and comprehensive testing scenarios.