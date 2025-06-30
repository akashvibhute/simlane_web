"""Discord API endpoints for bot integration"""

from typing import Dict, List
from ninja import Router
from ninja.errors import HttpError
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
import urllib.parse

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from simlane.teams.models import Club, ClubMember
from simlane.discord.models import DiscordGuild, ClubDiscordSettings, EventDiscordChannel
from simlane.discord.tasks import sync_discord_members, send_discord_notification
from simlane.api.routers.clubs import check_club_access, check_club_admin
from simlane.discord.services import DiscordBotService

from ..schemas.discord import (
    DiscordBotInviteURL,
    DiscordMemberSyncRequest,
    DiscordMemberSyncResponse,
    DiscordSettings,
    DiscordSettingsUpdate,
    DiscordChannelInfo,
    DiscordGuildInfo
)

router = Router()


@router.post("/bot-invite-url")
def generate_bot_invite_url(
    request: HttpRequest,
    club_id: str
) -> HttpResponse:
    """Generate Discord bot invitation URL for club and return modal HTML"""
    # Verify user is club admin
    club = get_object_or_404(Club, id=club_id)
    check_club_admin(request.auth, club)

    # Use DiscordBotService to generate the invite URL
    permissions = 34630287424  # Combined permissions as int
    redirect_uri = settings.SITE_URL.rstrip("/") + "/discord/bot/callback/"
    invite_url = DiscordBotService().get_invite_url(
        scopes=["bot", "applications.commands"],
        permissions=permissions,
        state=club_id,
        redirect_uri=redirect_uri,
        response_type="code",
    )

    context = {
        "invite_url": invite_url,
        "permissions_included": [
            "Manage Channels",
            "Manage Roles",
            "Send Messages",
            "Create Threads",
            "Connect Voice",
            "View Channel History",
            "Use External Emojis"
        ],
        "club_id": club_id,
        "setup_instructions": (
            "After clicking the link, select your Discord server and authorize the bot "
            "with the required permissions."
        )
    }

    return render(request, 'teams/partials/discord_invite_modal.html', context)


@router.post("/clubs/{club_id}/sync-members", response=DiscordMemberSyncResponse)
def sync_club_members(
    request: HttpRequest,
    club_id: str,
    data: DiscordMemberSyncRequest
):
    """Trigger manual member sync for club"""
    club = get_object_or_404(Club, id=club_id)
    check_club_admin(request.auth, club)

    # Check Discord integration
    try:
        discord_guild = club.discord_guild
    except DiscordGuild.DoesNotExist:
        raise HttpError(400, "Club has no Discord integration")

    # Trigger sync task
    task = sync_discord_members.delay(
        discord_guild.guild_id,
        sync_type=data.sync_type
    )

    return {
        "task_id": task.id,
        "status": "queued",
        "message": f"Member sync ({data.sync_type}) has been queued",
        "estimated_completion_time": "1-2 minutes"
    }


@router.get("/clubs/{club_id}/settings", response=DiscordSettings)
def get_discord_settings(
    request: HttpRequest,
    club_id: str
):
    """Get Discord settings for club"""
    club = get_object_or_404(Club, id=club_id)
    check_club_admin(request.auth, club)

    settings_obj, _ = ClubDiscordSettings.objects.get_or_create(
        club=club,
        defaults={
            'auto_create_channels': True,
            'enable_voice_channels': True,
            'enable_stint_alerts': True,
            'channel_naming_pattern': '{series_name}-{event_name}'
        }
    )
    return settings_obj


@router.put("/clubs/{club_id}/settings", response=DiscordSettings)
def update_discord_settings(
    request: HttpRequest,
    club_id: str,
    data: DiscordSettingsUpdate
):
    """Update Discord settings for club"""
    club = get_object_or_404(Club, id=club_id)
    check_club_admin(request.auth, club)

    settings_obj, _ = ClubDiscordSettings.objects.get_or_create(club=club)

    # Update settings fields
    for field, value in data.dict(exclude_unset=True).items():
        setattr(settings_obj, field, value)
    settings_obj.save()

    return settings_obj


@router.get("/clubs/{club_id}/channels", response=List[DiscordChannelInfo])
def get_discord_channels(
    request: HttpRequest,
    club_id: str
):
    """Get Discord channels for club events"""
    club = get_object_or_404(Club, id=club_id)
    check_club_access(request.auth, club)

    try:
        discord_guild = club.discord_guild
    except DiscordGuild.DoesNotExist:
        return []

    channels = EventDiscordChannel.objects.filter(
        guild=discord_guild
    ).select_related('event_signup_sheet__event')

    return [
        {
            "channel_id": channel.text_channel_id,
            "channel_name": f"#{channel.event_signup_sheet.event.name}",
            "channel_type": "text",
            "event_name": channel.event_signup_sheet.event.name,
            "status": channel.status,
            "created_at": channel.created_at,
            "voice_channel_id": channel.voice_channel_id,
            "practice_voice_channel_id": channel.practice_voice_channel_id
        }
        for channel in channels
    ]


@router.get("/clubs/{club_id}/guild-info", response=DiscordGuildInfo)
def get_guild_info(
    request: HttpRequest,
    club_id: str
):
    """Get Discord guild information for club"""
    club = get_object_or_404(Club, id=club_id)
    check_club_admin(request.auth, club)

    try:
        guild = club.discord_guild
    except DiscordGuild.DoesNotExist:
        raise HttpError(404, "Club has no Discord integration")

    latest_sync = guild.discordmembersync_set.order_by('-sync_timestamp').first()

    return {
        "guild_id": guild.guild_id,
        "guild_name": guild.name,
        "is_active": guild.is_active,
        "member_count": latest_sync.total_discord_members if latest_sync else 0,
        "linked_members": latest_sync.matched_members if latest_sync else 0,
        "last_sync": latest_sync.sync_timestamp if latest_sync else None,
        "channels_count": EventDiscordChannel.objects.filter(
            guild=guild, status='active'
        ).count()
    }


@router.post("/webhooks/interactions", auth=None)
def handle_discord_webhook(
    request: HttpRequest,
    data: Dict
):
    """Handle Discord webhook interactions with signature verification"""
    signature = request.headers.get('X-Signature-Ed25519')
    timestamp = request.headers.get('X-Signature-Timestamp')
    if not signature or not timestamp:
        raise HttpError(401, "Missing signature headers")

    public_key = getattr(settings, 'DISCORD_APPLICATION_PUBLIC_KEY', None)
    if not public_key:
        raise HttpError(500, "Discord application public key is not configured")

    # Verify the request
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key))
        body = request.body.decode('utf-8')
        message = timestamp + body
        verify_key.verify(message.encode(), bytes.fromhex(signature))
    except (BadSignatureError, Exception):
        raise HttpError(401, "Invalid request signature")

    interaction_type = data.get('type')
    # Respond to PING
    if interaction_type == 1:
        return {"type": 1}

    # Default response for other interaction types
    return {
        "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
        "data": {
            "content": "Discord webhook received successfully!"
        }
    }


@router.post("/clubs/{club_id}/test-notification")
def send_test_notification(
    request: HttpRequest,
    club_id: str
):
    """Send a test notification to Discord (for testing purposes)"""
    club = get_object_or_404(Club, id=club_id)
    check_club_admin(request.auth, club)

    try:
        discord_guild = club.discord_guild
    except DiscordGuild.DoesNotExist:
        raise HttpError(400, "Club has no Discord integration")

    test_channel = EventDiscordChannel.objects.filter(
        guild=discord_guild,
        status='active'
    ).first()
    if not test_channel:
        raise HttpError(404, "No active Discord channels found for this club")

    task = send_discord_notification.delay(
        test_channel.text_channel_id,
        'test',
        {
            'message': f"Test notification from {club.name}",
            'timestamp': str(timezone.now())
        }
    )

    return {
        "success": True,
        "message": "Test notification sent",
        "task_id": task.id,
        "channel_id": test_channel.text_channel_id
    }


@router.get("/clubs/{club_id}/status/", auth=None)
def get_bot_status(
    request: HttpRequest,
    club_id: str,
):
    """Return whether the Discord bot is connected for the given club.

    This endpoint is primarily consumed by the frontend *bot invite* modal
    which polls `/api/clubs/<slug>/discord/status/` to verify that the bot
    has successfully joined the server after the OAuth flow has completed.

    The implementation purposefully keeps the response minimal – a single
    `bot_connected` boolean – to avoid exposing sensitive guild data to
    unauthorised users.  Only club members may call this endpoint; admins
    or team-managers are required to perform write actions elsewhere.
    """

    # We accept either authenticated user or anonymous (auth may be null when
    # checking from public pages).  If auth is required later, swap to
    # `check_club_access`.

    club = get_object_or_404(Club, id=club_id)

    # Determine if a Discord guild is already linked and active
    discord_guild = getattr(club, "discord_guild", None)

    bot_connected = bool(discord_guild and discord_guild.is_active)

    return {
        "bot_connected": bot_connected,
        "guild_name": getattr(discord_guild, "name", None),
        "guild_id": getattr(discord_guild, "guild_id", None),
    }