"""Pydantic schemas for Discord API endpoints"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class DiscordBotInviteURL(BaseModel):
    """Discord bot invitation URL response"""
    invite_url: str = Field(..., description="Discord OAuth URL for bot invitation")
    permissions_included: List[str] = Field(..., description="List of required permissions")
    club_id: str = Field(..., description="Club ID for state tracking")
    setup_instructions: str = Field(..., description="Setup instructions for admins")

    class Config:
        schema_extra = {
            "example": {
                "invite_url": "https://discord.com/oauth2/authorize?client_id=123&permissions=34630287424&scope=bot%20applications.commands&state=club-uuid",
                "permissions_included": [
                    "Manage Channels",
                    "Manage Roles",
                    "Send Messages",
                    "Create Threads",
                    "Connect Voice",
                    "View Channel History"
                ],
                "club_id": "550e8400-e29b-41d4-a716-446655440000",
                "setup_instructions": "After clicking the link, select your Discord server and authorize the bot with the required permissions."
            }
        }


class DiscordWebhookPayload(BaseModel):
    """Discord webhook event payload"""
    type: int = Field(..., description="Interaction type")
    token: str = Field(..., description="Interaction token")
    id: str = Field(..., description="Interaction ID")
    application_id: str = Field(..., description="Application ID")
    data: Optional[Dict] = Field(None, description="Interaction data")
    guild_id: Optional[str] = Field(None, description="Guild ID where interaction occurred")
    channel_id: Optional[str] = Field(None, description="Channel ID where interaction occurred")
    member: Optional[Dict] = Field(None, description="Guild member who triggered interaction")
    user: Optional[Dict] = Field(None, description="User who triggered interaction")

    class Config:
        schema_extra = {
            "example": {
                "type": 2,
                "token": "webhook_token_here",
                "id": "interaction_id_here",
                "application_id": "bot_application_id",
                "data": {
                    "name": "sync",
                    "type": 1
                },
                "guild_id": "9876543210987654321",
                "channel_id": "1234567890123456789"
            }
        }


class DiscordMemberSyncRequest(BaseModel):
    """Request for member sync operation"""
    sync_type: str = Field(default="manual", description="Type of sync operation")

    class Config:
        schema_extra = {
            "example": {
                "sync_type": "manual"
            }
        }


class DiscordMemberSyncResponse(BaseModel):
    """Response for member sync operation"""
    task_id: str = Field(..., description="Celery task ID")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Human readable message")
    estimated_completion_time: Optional[str] = Field(None, description="Estimated time to completion")

    class Config:
        schema_extra = {
            "example": {
                "task_id": "abc123-def456-ghi789",
                "status": "queued",
                "message": "Member sync (manual) has been queued",
                "estimated_completion_time": "1-2 minutes"
            }
        }


class DiscordMemberSyncResult(BaseModel):
    """Detailed result of member sync operation"""
    sync_id: int = Field(..., description="Database sync record ID")
    guild_id: str = Field(..., description="Discord guild ID")
    sync_type: str = Field(..., description="Type of sync performed")
    total_discord_members: int = Field(..., description="Total Discord members found")
    matched_members: int = Field(..., description="Members matched to Simlane accounts")
    new_club_members: int = Field(..., description="New club members created")
    errors_count: int = Field(..., description="Number of errors during sync")
    success: bool = Field(..., description="Whether sync was successful")
    sync_timestamp: datetime = Field(..., description="When sync was performed")
    details: Dict = Field(..., description="Detailed sync results")

    class Config:
        schema_extra = {
            "example": {
                "sync_id": 123,
                "guild_id": "9876543210987654321",
                "sync_type": "manual",
                "total_discord_members": 50,
                "matched_members": 35,
                "new_club_members": 3,
                "errors_count": 0,
                "success": True,
                "sync_timestamp": "2024-12-01T10:30:00Z",
                "details": {
                    "matched_users": [
                        {"discord_id": "123", "username": "racer1"},
                        {"discord_id": "456", "username": "racer2"}
                    ],
                    "new_members": [
                        {"user_id": 789, "username": "newracer"}
                    ],
                    "unmatched_discord_users": [
                        {"discord_id": "999", "discord_username": "unlinked_user"}
                    ]
                }
            }
        }


class DiscordSettings(BaseModel):
    """Discord settings for a club"""
    auto_create_channels: bool = Field(default=True, description="Auto-create event channels")
    channel_naming_pattern: str = Field(default="{series_name}-{event_name}", description="Channel naming template")
    enable_voice_channels: bool = Field(default=True, description="Create voice channels")
    enable_practice_voice: bool = Field(default=True, description="Create practice voice channels")
    enable_stint_alerts: bool = Field(default=True, description="Send stint change alerts")
    signup_update_frequency: int = Field(default=6, description="Hours between signup updates")
    notification_preferences: Dict = Field(default_factory=dict, description="Advanced notification settings")

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "auto_create_channels": True,
                "channel_naming_pattern": "{series_name}-{event_name}",
                "enable_voice_channels": True,
                "enable_practice_voice": True,
                "enable_stint_alerts": True,
                "signup_update_frequency": 6,
                "notification_preferences": {
                    "ping_on_signup": True,
                    "ping_on_team_assignment": True
                }
            }
        }


class DiscordSettingsUpdate(BaseModel):
    """Update request for Discord settings"""
    auto_create_channels: Optional[bool] = Field(None, description="Toggle auto-creation of event channels")
    channel_naming_pattern: Optional[str] = Field(None, description="Override channel naming template")
    enable_voice_channels: Optional[bool] = Field(None, description="Toggle voice channel creation")
    enable_practice_voice: Optional[bool] = Field(None, description="Toggle practice voice channel creation")
    enable_stint_alerts: Optional[bool] = Field(None, description="Toggle stint change alerts")
    signup_update_frequency: Optional[int] = Field(None, description="Hours between signup updates")
    notification_preferences: Optional[Dict] = Field(None, description="Advanced notification preferences")

    class Config:
        schema_extra = {
            "example": {
                "enable_stint_alerts": False,
                "signup_update_frequency": 12
            }
        }


class DiscordChannelInfo(BaseModel):
    """Information about a Discord channel"""
    channel_id: str = Field(..., description="Discord channel ID")
    channel_name: str = Field(..., description="Channel name")
    channel_type: str = Field(..., description="Channel type (text/voice)")
    event_name: str = Field(..., description="Associated event name")
    status: str = Field(..., description="Channel status")
    created_at: datetime = Field(..., description="Creation timestamp")
    voice_channel_id: Optional[str] = Field(None, description="Associated race voice channel ID")
    practice_voice_channel_id: Optional[str] = Field(None, description="Associated practice voice channel ID")

    class Config:
        schema_extra = {
            "example": {
                "channel_id": "1234567890123456789",
                "channel_name": "#endurance-le-mans-2024",
                "channel_type": "text",
                "event_name": "Le Mans 24 Hours 2024",
                "status": "active",
                "created_at": "2024-12-01T10:00:00Z",
                "voice_channel_id": "1234567890123456790",
                "practice_voice_channel_id": "1234567890123456791"
            }
        }


class DiscordGuildInfo(BaseModel):
    """Discord guild information for a club"""
    guild_id: str = Field(..., description="Discord guild ID")
    guild_name: str = Field(..., description="Guild name")
    is_active: bool = Field(..., description="Whether guild integration is active")
    member_count: int = Field(..., description="Total Discord members")
    linked_members: int = Field(..., description="Members linked to Simlane accounts")
    last_sync: Optional[datetime] = Field(None, description="Last member sync timestamp")
    channels_count: int = Field(..., description="Active Discord channels managed by bot")

    class Config:
        schema_extra = {
            "example": {
                "guild_id": "9876543210987654321",
                "guild_name": "Racing Club Discord",
                "is_active": True,
                "member_count": 50,
                "linked_members": 35,
                "last_sync": "2024-12-01T08:00:00Z",
                "channels_count": 3
            }
        }


class DiscordEventChannelsRequest(BaseModel):
    """Request to create/manage Discord event channels"""
    signup_sheet_id: int = Field(..., description="ID of the event signup sheet")
    create_voice_channels: Optional[bool] = Field(None, description="Override voice channel creation setting")

    class Config:
        schema_extra = {
            "example": {
                "signup_sheet_id": 42,
                "create_voice_channels": True
            }
        }


class DiscordEventChannelsResponse(BaseModel):
    """Response for event channels creation task"""
    task_id: str = Field(..., description="Celery task ID")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Human readable message")

    class Config:
        schema_extra = {
            "example": {
                "task_id": "task-abc123",
                "status": "queued",
                "message": "Event channels creation has been queued"
            }
        }


class DiscordNotificationRequest(BaseModel):
    """Request to send Discord notification"""
    notification_type: str = Field(..., description="Type of notification to send")
    data: Dict = Field(..., description="Notification data payload")
    target_channels: Optional[List[str]] = Field(None, description="Specific channels to target")

    class Config:
        schema_extra = {
            "example": {
                "notification_type": "signup_progress",
                "data": {
                    "total_signups": 25,
                    "target_teams": 6,
                    "time_remaining": "2 days"
                },
                "target_channels": ["1234567890123456789"]
            }
        }


class DiscordNotificationResponse(BaseModel):
    """Response for Discord notification task"""
    task_id: str = Field(..., description="Celery task ID")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Human readable message")

    class Config:
        schema_extra = {
            "example": {
                "task_id": "notify-xyz789",
                "status": "queued",
                "message": "Notification has been queued to send"
            }
        }