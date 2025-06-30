# Discord Integration Requirements

## Overview

This document defines the comprehensive requirements for Discord bot integration with the Simlane racing platform. The integration automates event management, team coordination, and member communication throughout the racing workflow.

## User Stories & Flows

### **1. Club Admin Authentication Flow** ✅ *IMPLEMENTED*

**As a club admin**, I want to login using Discord so that I can link my Discord account to my Simlane profile.

**Acceptance Criteria:**
- ✅ Users can login via Discord OAuth
- ✅ Link Discord to existing Simlane accounts  
- ✅ Social account integration via allauth
- ✅ Profile information sync from Discord

**Technical Implementation:**
- Django allauth social provider for Discord
- SocialAccount model linking Discord UID to User
- OAuth2 flow with proper scope permissions

---

### **2. Bot Server Integration Flow** 🔴 *NOT STARTED*

**As a club admin**, I want to invite the Simlane bot to my Discord server so that it can manage club events and members.

**User Flow:**
1. Club admin accesses Discord settings in club dashboard  
2. Admin clicks "Add Bot to Discord Server"  
3. System generates Discord OAuth URL with required permissions  
4. Admin authorizes bot in Discord with guild permissions  
5. Bot automatically detects guild and links to club  
6. Admin configures Discord integration settings  

**Acceptance Criteria:**
- [ ] Dashboard provides Discord bot invitation link
- [ ] OAuth flow includes all required permissions
- [ ] Bot automatically links guild to club on join
- [ ] Permission validation during setup
- [ ] Error handling for invalid/insufficient permissions
- [ ] Setup wizard for initial configuration

**Required Discord Permissions:**
- Manage Channels (create/edit/delete)
- Manage Roles (team assignments)
- Send Messages (notifications)
- Create Threads (team communication)
- Connect/Speak Voice (voice management)
- View Channel History (context)

---

### **3. Member Synchronization Flow** 🔴 *NOT STARTED*

**As a club admin**, I want Discord guild members automatically added to my club so that they can participate in events.

**User Flow:**
1. Bot detects Discord guild members with linked Simlane accounts  
2. System automatically creates ClubMember records for matched users  
3. Admin can trigger manual sync operations  
4. System handles member join/leave events in real-time  
5. Conflict resolution for duplicate or invalid accounts  

**Acceptance Criteria:**
- [ ] Automatic member detection on bot join
- [ ] Real-time sync on Discord member events
- [ ] Manual sync trigger in admin dashboard
- [ ] >95% sync accuracy with conflict resolution
- [ ] Audit trail of sync operations
- [ ] Handling of unlinked Discord users

**Technical Requirements:**
- Discord guild member enumeration
- SocialAccount matching algorithm
- Bulk ClubMember creation with validation
- Real-time event handlers for member changes
- Sync conflict resolution logic

---

### **4. Event Management Flow** 🔴 *NOT STARTED*

**As a club admin**, I want Discord channels automatically created for events so that members can coordinate and receive updates.

**User Flow:**
1. Admin creates ClubEventSignupSheet in dashboard  
2. System automatically creates Discord text channel for event  
3. Channels organized by racing series categories  
4. Bot posts signup sheet link to event channel  
5. Periodic signup updates until registration closes  
6. Final signup announcement with participant data  

**Acceptance Criteria:**
- [ ] Auto-channel creation on signup sheet creation
- [ ] Series-based channel categorization
- [ ] Signup link posting with rich embeds
- [ ] Periodic progress updates (configurable frequency)
- [ ] Final signup summary with participant list
- [ ] Channel cleanup after event completion

**Channel Organization:**
```
📁 Series Name (Category)
  ├── 🏁 event-name-signup
  ├── 🎧 event-name-practice-voice
  └── 🏆 event-name-race-voice
```

---

### **5. Team Formation Flow** 🔴 *NOT STARTED*

**As a club member**, I want team assignments reflected in Discord so that I can communicate with my teammates.

**User Flow:**
1. Event organizer finalizes team assignments  
2. System creates team-specific threads in event channels  
3. Discord roles assigned for team members  
4. Team members notified of assignments  
5. Practice voice channels created for teams  

**Acceptance Criteria:**
- [ ] Team threads created on assignment completion
- [ ] Dynamic Discord role creation for teams
- [ ] Member role assignment/revocation automation
- [ ] Team assignment notifications
- [ ] Practice voice channel creation
- [ ] Thread permissions match team membership

**Discord Structure:**
```
🏁 event-name-signup
  ├── 🧵 Team Alpha Thread
  ├── 🧵 Team Bravo Thread
  └── 🧵 Team Charlie Thread
```

---

### **6. Race Day Management Flow** 🔴 *NOT STARTED*

**As a team member**, I want race day coordination through Discord so that I can participate effectively in the event.

**User Flow:**
1. 24 hours before event: Race voice channels created  
2. Voice channel access restricted to team members  
3. Race strategies announced in team threads  
4. 15-minute stint alerts sent to drivers  
5. Live telemetry updates (future scope)  
6. Race results posted after completion  

**Acceptance Criteria:**
- [ ] Race voice channels with restricted access
- [ ] Strategy announcements with rich formatting
- [ ] Automated stint alerts 15 minutes before driver changes
- [ ] Live race updates (placeholder for iTelemetry)
- [ ] Result announcements with performance data
- [ ] Post-race statistics and highlights

**Alert System:**
- Stint change alerts: 15 minutes before
- Strategy updates: Real-time during race
- Incident notifications: Immediate
- Result announcements: Post-race

---

### **7. Series Lifecycle Flow** 🔴 *NOT STARTED*

**As a club admin**, I want Discord channels archived when series complete so that the server stays organized.

**User Flow:**
1. Series completion detected (all events finished)  
2. System archives channel groups automatically  
3. Historical data preserved for reference  
4. Unused channels and roles cleaned up  
5. Series statistics posted to archive  

**Acceptance Criteria:**
- [ ] Automatic series completion detection
- [ ] Channel archival with historical preservation
- [ ] Role cleanup for completed teams
- [ ] Archive channel with series statistics
- [ ] Configurable retention policies
- [ ] Manual archive triggers for admins

---

## Technical Requirements

### **Data Models**

```python
# New Models Required
EventDiscordChannel:
    - event_signup_sheet: FK to ClubEventSignupSheet
    - category_id: Discord category ID
    - text_channel_id: Main event channel ID
    - voice_channel_id: Race voice channel ID
    - practice_voice_channel_id: Practice voice channel ID
    - signup_message_id: Pinned signup message ID
    - status: Channel lifecycle status

DiscordMemberSync:
    - guild: FK to DiscordGuild
    - sync_timestamp: When sync occurred
    - sync_type: manual/automatic/scheduled
    - results: JSON with sync statistics
    - success_count: Successful matches
    - error_count: Failed matches

ClubDiscordSettings:
    - club: OneToOne with Club
    - auto_create_channels: Boolean
    - channel_naming_pattern: Template string
    - notification_preferences: JSON config
    - enable_voice_channels: Boolean
    - enable_stint_alerts: Boolean
```

### **Service Layer Architecture**

```python
DiscordBotService:
    - Guild management operations
    - Channel creation and organization
    - Member sync coordination
    - Permission validation

DiscordMemberSyncService:
    - Guild member enumeration
    - SocialAccount matching
    - ClubMember creation
    - Conflict resolution

DiscordChannelService:
    - Event channel lifecycle
    - Series categorization
    - Voice channel management
    - Archive operations

DiscordNotificationService:
    - Event updates and announcements
    - Stint alerts and reminders
    - Strategy announcements
    - Result notifications
```

### **API Endpoints**

```
POST /api/discord/bot-invite-url
    - Generate bot invitation URL for guild

POST /api/clubs/{club_id}/discord/sync-members
    - Trigger manual member sync operation

GET /api/clubs/{club_id}/discord/settings
PUT /api/clubs/{club_id}/discord/settings
    - Manage club Discord configuration

GET /api/clubs/{club_id}/discord/channels
    - List Discord channels for club events

POST /api/discord/webhooks/interactions
    - Handle Discord webhook events
```

### **Bot Commands**

```
Slash Commands:
/sync           - Trigger member sync (admin only)
/events         - List upcoming club events
/teams          - Show team assignments
/schedule       - Display event schedule
/availability   - Link to availability form

Text Commands:
!ping           - Bot health check
!info           - Bot and server statistics
!club           - Display club information
!help           - Command documentation
!link           - Account linking instructions
```

### **Background Tasks**

```python
# Celery Tasks
@shared_task
def sync_discord_members(guild_id)
    - Periodic member synchronization

@shared_task
def create_event_channels(signup_sheet_id)
    - Auto-create channels for new events

@shared_task
def update_event_channels(event_id)
    - Send periodic signup updates

@shared_task
def cleanup_expired_channels(guild_id)
    - Archive completed event channels

@shared_task
def send_stint_alerts(stint_plan_id)
    - Driver change notifications
```

## Integration Points

### **Django Signals**

```python
# Signal Handlers
post_save.connect(ClubEventSignupSheet)
    → create_event_channels.delay()

post_save.connect(EventParticipation)
    → handle_team_assignment()

post_save.connect(RaceStrategy)
    → announce_strategy.delay()

post_save.connect(StintPlan)
    → schedule_stint_alerts.delay()
```

### **Discord Events**

```python
# Bot Event Handlers
on_guild_join(guild)
    → link_guild_to_club()

on_member_join(member)
    → check_club_membership()

on_member_remove(member)
    → update_club_membership()

on_message(message)
    → process_commands()
```

## Performance Requirements

### **Response Times**
- Bot command response: < 2 seconds
- Channel creation: < 5 seconds
- Member sync (100 members): < 30 seconds
- API endpoint response: < 1 second

### **Scalability**
- Support 100+ Discord guilds
- Handle 1000+ concurrent members per guild
- Process 50+ events simultaneously
- Support 10+ racing series per club

### **Reliability**
- 99.9% bot uptime
- 95%+ member sync accuracy
- Automatic error recovery
- Graceful degradation on Discord API failures

## Security Requirements

### **Authentication & Authorization**
- Bot token secure storage in Django settings
- Discord webhook signature verification
- User permission validation for admin operations
- Role-based access control for bot commands

### **Data Protection**
- Minimal Discord data retention
- User consent for data processing
- GDPR compliance for EU users
- Secure API communication (HTTPS/WSS)

### **Rate Limiting**
- Discord API rate limit compliance
- Request queuing and retry logic
- Circuit breaker for API failures
- Graceful degradation strategies

## Future Enhancements

### **Phase 4: iTelemetry Integration**
- Live race data webhooks
- Real-time leaderboard updates
- Dynamic stint timing adjustments
- Performance analytics integration

### **Advanced Features**
- Multi-language support for international clubs
- Custom bot branding per club
- Advanced analytics and reporting
- Mobile app push notification coordination

## Success Metrics

### **Technical KPIs**
- Bot guild join success rate: >99%
- Member sync accuracy: >95%
- Channel creation success rate: >99%
- Event notification delivery: >95%
- Average API response time: <2s

### **User Experience KPIs**
- Club adoption rate of Discord integration: >70%
- User engagement in Discord channels: >80%
- Reduction in manual coordination effort: >50%
- Event participation increase: >20%
- User satisfaction score: >4.5/5

---

*Document Version: 1.0*  
*Last Updated: December 2024*  
*Status: Requirements Approved - Ready for Implementation*