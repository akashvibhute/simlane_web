"""Discord service classes for bot operations and integration"""

import logging
from typing import List, Dict, Optional, Union
import asyncio
import discord
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from allauth.socialaccount.models import SocialAccount

from .models import DiscordGuild, EventDiscordChannel, DiscordMemberSync, ClubDiscordSettings
from simlane.teams.models import Club, ClubMember, ClubEventSignupSheet

logger = logging.getLogger(__name__)


class DiscordBotService:
    """Core Discord bot operations following teams.services pattern"""

    def __init__(self):
        self.intents = discord.Intents.default()
        self.intents.guilds = True
        self.intents.members = True
        self.intents.message_content = True

    def get_invite_url(
        self,
        scopes: Optional[List[str]] = None,
        permissions: Optional[int] = None
    ) -> str:
        """
        Generate the OAuth2 invite URL for the bot.
        Uses DISCORD_CLIENT_ID and DISCORD_BOT_PERMISSIONS from settings.
        """
        client_id = getattr(settings, 'DISCORD_CLIENT_ID', None)
        if not client_id:
            raise ValueError("DISCORD_CLIENT_ID not configured in settings")
        scopes = scopes or ['bot', 'applications.commands']
        permissions = permissions or getattr(settings, 'DISCORD_BOT_PERMISSIONS', 0)
        scope_param = '%20'.join(scopes)
        return (
            f"https://discord.com/oauth2/authorize?"
            f"client_id={client_id}&permissions={permissions}&scope={scope_param}"
        )

    async def get_guild_info(self, guild_id: str) -> Dict:
        """Get Discord guild information"""
        try:
            client = discord.Client(intents=self.intents)
            await client.login(settings.DISCORD_BOT_TOKEN)
            guild = await client.fetch_guild(int(guild_id))

            result = {
                'id': str(guild.id),
                'name': guild.name,
                'member_count': guild.member_count,
                'owner_id': str(guild.owner_id),
                'permissions': guild.me.guild_permissions.value if guild.me else None,
                'icon_url': str(guild.icon.url) if guild.icon else None,
                'channels_count': len(guild.channels) if hasattr(guild, 'channels') else 0,
                'roles_count': len(guild.roles) if hasattr(guild, 'roles') else 0,
            }

            await client.close()
            return result

        except discord.NotFound:
            raise ValueError(f"Guild {guild_id} not found")
        except discord.Forbidden:
            raise PermissionError(f"Bot lacks access to guild {guild_id}")
        except Exception as e:
            logger.error(f"Error fetching guild info for {guild_id}: {e}")
            raise

    async def create_channel(
        self,
        guild_id: str,
        name: str,
        category_name: Optional[str] = None,
        channel_type: str = 'text',
        permission_overwrites: Optional[Dict] = None
    ) -> Dict:
        """Create Discord channel with optional category and permission overwrites"""
        try:
            client = discord.Client(intents=self.intents)
            await client.login(settings.DISCORD_BOT_TOKEN)
            guild = await client.fetch_guild(int(guild_id))

            # Find or create category
            category = None
            if category_name:
                category = discord.utils.get(guild.categories, name=category_name)
                if not category:
                    category = await guild.create_category(category_name)

            # Create channel based on type
            if channel_type == 'voice':
                channel = await guild.create_voice_channel(
                    name, category=category, overwrites=permission_overwrites or {}
                )
            else:
                channel = await guild.create_text_channel(
                    name, category=category, overwrites=permission_overwrites or {}
                )

            result = {
                'channel_id': str(channel.id),
                'category_id': str(category.id) if category else None,
                'name': channel.name,
                'type': channel_type,
                'url': f"https://discord.com/channels/{guild_id}/{channel.id}"
            }

            await client.close()
            return result

        except discord.HTTPException as e:
            logger.error(f"HTTP error creating channel in guild {guild_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating channel in guild {guild_id}: {e}")
            raise

    async def delete_channel(self, guild_id: str, channel_id: str) -> None:
        """Delete a Discord channel by ID"""
        try:
            client = discord.Client(intents=self.intents)
            await client.login(settings.DISCORD_BOT_TOKEN)
            guild = await client.fetch_guild(int(guild_id))

            # Try to get from cache or fetch
            channel = guild.get_channel(int(channel_id))
            if channel is None:
                channel = await client.fetch_channel(int(channel_id))
            await channel.delete()
            await client.close()

        except Exception as e:
            logger.error(f"Error deleting channel {channel_id} in guild {guild_id}: {e}")
            raise

    async def list_channels(self, guild_id: str) -> List[Dict]:
        """List all channels in a guild"""
        try:
            client = discord.Client(intents=self.intents)
            await client.login(settings.DISCORD_BOT_TOKEN)
            guild = await client.fetch_guild(int(guild_id))

            channels_info = []
            for channel in guild.channels:
                channels_info.append({
                    'channel_id': str(channel.id),
                    'name': channel.name,
                    'type': str(channel.type),
                    'category_id': str(channel.category_id) if getattr(channel, 'category_id', None) else None
                })

            await client.close()
            return channels_info

        except Exception as e:
            logger.error(f"Error listing channels for guild {guild_id}: {e}")
            raise

    async def post_message(self, channel_id: str, content: Optional[str] = None, embed: discord.Embed = None) -> str:
        """Post a message to a Discord channel"""
        try:
            client = discord.Client(intents=self.intents)
            await client.login(settings.DISCORD_BOT_TOKEN)
            channel = await client.fetch_channel(int(channel_id))
            message = await channel.send(content=content, embed=embed)
            await client.close()
            return str(message.id)

        except Exception as e:
            logger.error(f"Error posting message to channel {channel_id}: {e}")
            raise

    async def create_embed(
        self,
        title: str,
        description: str,
        color: int = 0x3498db,
        fields: Optional[List[Dict]] = None
    ) -> discord.Embed:
        """Create a Discord embed for rich messaging"""
        embed = discord.Embed(title=title, description=description, color=color)
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get('name', ''),
                    value=field.get('value', ''),
                    inline=field.get('inline', False)
                )
        embed.timestamp = timezone.now()
        return embed


class DiscordMemberSyncService:
    """Member synchronization between Discord and Simlane"""

    def __init__(self, guild: DiscordGuild):
        self.guild = guild
        self.club = guild.club
        self.intents = discord.Intents.default()
        self.intents.guilds = True
        self.intents.members = True

    async def sync_guild_members(self, sync_type: str = 'manual') -> DiscordMemberSync:
        """Sync Discord guild members with club members"""
        sync_record = DiscordMemberSync.objects.create(
            guild=self.guild,
            sync_type=sync_type,
            started_at=timezone.now()
        )
        try:
            client = discord.Client(intents=self.intents)
            await client.login(settings.DISCORD_BOT_TOKEN)
            discord_guild = await client.fetch_guild(int(self.guild.guild_id))

            members = []
            async for member in discord_guild.fetch_members(limit=None):
                if not member.bot:
                    members.append(member)
            sync_record.total_discord_members = len(members)

            matches = await self._match_discord_users(members)
            sync_record.matched_members = len(matches)

            new_members = await self._create_club_memberships(matches)
            sync_record.new_club_members = len(new_members)

            # Optionally assign a default Discord role to matched members
            await self._assign_default_role(matches)

            unmatched = [
                {'discord_id': str(m.id), 'discord_username': str(m)}
                for m in members
                if not any(str(m.id) == str(match['discord_member'].id) for match in matches)
            ]

            sync_record.results = {
                'matched_users': [
                    {
                        'discord_id': str(m['discord_member'].id),
                        'discord_username': str(m['discord_member']),
                        'user_id': m['simlane_user'].id,
                        'username': m['simlane_user'].username
                    } for m in matches
                ],
                'new_members': [
                    {'user_id': m.user.id, 'username': m.user.username}
                    for m in new_members
                ],
                'unmatched_discord_users': unmatched,
                'errors': []
            }
            sync_record.success = True
            await client.close()

        except Exception as e:
            logger.error(f"Member sync failed for guild {self.guild.guild_id}: {e}")
            sync_record.success = False
            sync_record.error_message = str(e)
            sync_record.errors_count = 1
            sync_record.results = {'errors': [str(e)]}

        finally:
            sync_record.completed_at = timezone.now()
            sync_record.save()

        return sync_record

    async def _match_discord_users(self, discord_members: List) -> List[Dict]:
        """Match Discord members to Simlane users via SocialAccount"""
        matches = []
        for member in discord_members:
            try:
                social_account = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: SocialAccount.objects.select_related('user').get(
                        provider='discord',
                        uid=str(member.id)
                    )
                )
                matches.append({
                    'discord_member': member,
                    'simlane_user': social_account.user,
                    'social_account': social_account
                })
            except SocialAccount.DoesNotExist:
                continue
            except Exception as e:
                logger.warning(f"Error matching Discord user {member.id}: {e}")
                continue
        return matches

    async def _create_club_memberships(self, matches: List[Dict]) -> List[ClubMember]:
        """Create ClubMember records for matched users"""
        new_members = []

        def create_memberships():
            nonlocal new_members
            with transaction.atomic():
                for match in matches:
                    user = match['simlane_user']
                    if not ClubMember.objects.filter(club=self.club, user=user).exists():
                        member = ClubMember.objects.create(
                            club=self.club,
                            user=user,
                            role='member'
                        )
                        new_members.append(member)

        await asyncio.get_event_loop().run_in_executor(None, create_memberships)
        return new_members

    async def _assign_default_role(self, matches: List[Dict], role_id: Optional[str] = None):
        """Assign a default Discord role to matched members if configured"""
        role_id = role_id or getattr(settings, 'DISCORD_MEMBER_ROLE_ID', None)
        if not role_id:
            return
        try:
            client = discord.Client(intents=self.intents)
            await client.login(settings.DISCORD_BOT_TOKEN)
            discord_guild = await client.fetch_guild(int(self.guild.guild_id))
            for match in matches:
                member_obj = discord_guild.get_member(match['discord_member'].id)
                if member_obj:
                    await member_obj.add_roles(discord.Object(id=int(role_id)))
            await client.close()
        except Exception as e:
            logger.warning(f"Failed to assign default role in guild {self.guild.guild_id}: {e}")


class DiscordChannelService:
    """Discord channel lifecycle management"""

    def __init__(self, guild: DiscordGuild):
        self.guild = guild
        self.bot_service = DiscordBotService()

    async def create_event_channels(self, signup_sheet: ClubEventSignupSheet) -> EventDiscordChannel:
        """Create Discord channels for an event signup sheet"""
        series_name = self._get_series_name(signup_sheet.event)
        event_name = self._clean_name(signup_sheet.title or signup_sheet.event.name)
        channel_name = f"{series_name.lower().replace(' ', '-')}-{event_name.lower().replace(' ', '-')}"
        category_name = f"📁 {series_name}"

        try:
            text_info = await self.bot_service.create_channel(
                self.guild.guild_id,
                channel_name,
                category_name,
                'text'
            )

            settings_obj, _ = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: ClubDiscordSettings.objects.get_or_create(
                    club=self.guild.club,
                    defaults={'auto_create_channels': True}
                )
            )

            voice_id = None
            practice_id = None
            if settings_obj[0].enable_voice_channels:
                try:
                    voice_info = await self.bot_service.create_channel(
                        self.guild.guild_id,
                        f"🏆 {channel_name}-race",
                        category_name,
                        'voice'
                    )
                    voice_id = voice_info['channel_id']
                except Exception as e:
                    logger.warning(f"Failed to create race voice channel: {e}")

            if settings_obj[0].enable_practice_voice:
                try:
                    practice_info = await self.bot_service.create_channel(
                        self.guild.guild_id,
                        f"🎧 {channel_name}-practice",
                        category_name,
                        'voice'
                    )
                    practice_id = practice_info['channel_id']
                except Exception as e:
                    logger.warning(f"Failed to create practice voice channel: {e}")

            def create_record():
                return EventDiscordChannel.objects.create(
                    event_signup_sheet=signup_sheet,
                    guild=self.guild,
                    category_id=text_info['category_id'],
                    text_channel_id=text_info['channel_id'],
                    voice_channel_id=voice_id,
                    practice_voice_channel_id=practice_id,
                    status='active'
                )

            discord_channel = await asyncio.get_event_loop().run_in_executor(None, create_record)
            await self._post_signup_message(discord_channel, signup_sheet)
            return discord_channel

        except Exception as e:
            logger.error(f"Failed to create event channels for {signup_sheet.event.name}: {e}")
            raise

    async def update_event_channels(self, discord_channel: EventDiscordChannel, updates: Dict):
        """Update existing event channels settings or permissions"""
        try:
            # Placeholder for updates: e.g., rename channel, adjust perms
            # Example: await self.bot_service.edit_channel_name(...)
            pass
        except Exception as e:
            logger.error(f"Failed to update event channels {discord_channel.id}: {e}")
            raise

    async def cleanup_expired_channels(self, older_than: timezone.timedelta):
        """Cleanup event channels that are expired or past their signup close time"""
        cutoff = timezone.now() - older_than
        expired = EventDiscordChannel.objects.filter(
            status='active',
            event_signup_sheet__signup_closes__lt=cutoff
        )
        for channel in expired:
            try:
                await self.bot_service.delete_channel(self.guild.guild_id, channel.text_channel_id)
                channel.status = 'archived'
                channel.save(update_fields=['status'])
            except Exception as e:
                logger.warning(f"Failed to cleanup channel {channel.text_channel_id}: {e}")

    async def _post_signup_message(self, discord_channel: EventDiscordChannel, signup_sheet: ClubEventSignupSheet):
        """Post initial signup message to event channel"""
        try:
            embed = await self.bot_service.create_embed(
                title=f"🏁 {signup_sheet.event.name}",
                description=signup_sheet.description or "Event signup is now open!",
                color=0x00ff00,
                fields=[
                    {
                        'name': '📅 Event Date',
                        'value': signup_sheet.event.start_time.strftime('%Y-%m-%d %H:%M UTC'),
                        'inline': True
                    },
                    {
                        'name': '🏁 Series',
                        'value': self._get_series_name(signup_sheet.event),
                        'inline': True
                    },
                    {
                        'name': '🔗 Sign Up',
                        'value': f"[Sign Up Here]({self._get_signup_url(signup_sheet)})",
                        'inline': False
                    },
                    {
                        'name': '⏰ Signup Closes',
                        'value': signup_sheet.signup_closes.strftime('%Y-%m-%d %H:%M UTC'),
                        'inline': True
                    },
                    {
                        'name': '👥 Target Teams',
                        'value': str(signup_sheet.max_teams or 'Unlimited'),
                        'inline': True
                    }
                ]
            )
            message_id = await self.bot_service.post_message(
                discord_channel.text_channel_id,
                embed=embed
            )

            def update_msg():
                discord_channel.signup_message_id = message_id
                discord_channel.save(update_fields=['signup_message_id'])

            await asyncio.get_event_loop().run_in_executor(None, update_msg)

        except Exception as e:
            logger.error(f"Failed to post signup message: {e}")

    def _get_series_name(self, event) -> str:
        """Extract series name from event"""
        if hasattr(event, 'series') and event.series:
            return event.series.name
        if hasattr(event, 'series_name') and event.series_name:
            return event.series_name
        if hasattr(event, 'name') and event.name:
            parts = event.name.split(' - ')
            if len(parts) > 1:
                return parts[0]
        return 'General Racing'

    def _clean_name(self, name: str) -> str:
        """Clean name for Discord channel slug"""
        if not name:
            return 'event'
        cleaned = ''.join(c for c in name if c.isalnum() or c in ' -_').strip()
        return cleaned[:50] if cleaned else 'event'

    def _get_signup_url(self, signup_sheet: ClubEventSignupSheet) -> str:
        """Generate signup URL for the event"""
        base = getattr(settings, 'SITE_URL', 'https://simlane.app')
        return f"{base}/clubs/{signup_sheet.club.slug}/events/{signup_sheet.event.id}/signup/"


class DiscordNotificationService:
    """Discord notification and messaging service"""

    def __init__(self, guild: DiscordGuild):
        self.guild = guild
        self.bot_service = DiscordBotService()

    async def send_event_update(self, discord_channel: EventDiscordChannel, update_type: str, data: Dict):
        """Send event update to Discord channel"""
        try:
            if update_type == 'signup_progress':
                embed = await self._create_signup_progress_embed(data)
            elif update_type == 'signup_closed':
                embed = await self._create_signup_closed_embed(data)
            elif update_type == 'teams_formed':
                embed = await self._create_teams_formed_embed(data)
            else:
                embed = await self.bot_service.create_embed(
                    title="Event Update",
                    description=f"Update type: {update_type}",
                    color=0x3498db
                )

            message_id = await self.bot_service.post_message(
                discord_channel.text_channel_id,
                embed=embed
            )

            def update_last():
                discord_channel.last_update_message_id = message_id
                discord_channel.save(update_fields=['last_update_message_id'])

            await asyncio.get_event_loop().run_in_executor(None, update_last)

        except Exception as e:
            logger.error(f"Failed to send event update: {e}")

    async def _create_signup_progress_embed(self, data: Dict) -> discord.Embed:
        """Create embed for signup progress update"""
        return await self.bot_service.create_embed(
            title="📊 Signup Progress Update",
            description="Current signup status for the event",
            color=0x3498db,
            fields=[
                {
                    'name': '👥 Total Signups',
                    'value': str(data.get('total_signups', 0)),
                    'inline': True
                },
                {
                    'name': '🎯 Target Teams',
                    'value': str(data.get('target_teams', 'N/A')),
                    'inline': True
                },
                {
                    'name': '⏰ Time Remaining',
                    'value': data.get('time_remaining', 'N/A'),
                    'inline': True
                }
            ]
        )

    async def _create_signup_closed_embed(self, data: Dict) -> discord.Embed:
        """Create embed for signup closed notification"""
        return await self.bot_service.create_embed(
            title="🔒 Signups Closed",
            description="Event signup period has ended",
            color=0xff9500,
            fields=[
                {
                    'name': '✅ Final Signup Count',
                    'value': str(data.get('final_count', 0)),
                    'inline': True
                },
                {
                    'name': '🏁 Teams to Form',
                    'value': str(data.get('teams_to_form', 0)),
                    'inline': True
                }
            ]
        )

    async def _create_teams_formed_embed(self, data: Dict) -> discord.Embed:
        """Create embed for teams formed notification"""
        return await self.bot_service.create_embed(
            title="🎉 Teams Formed!",
            description="Team assignments have been completed",
            color=0x00ff00,
            fields=[
                {
                    'name': '🏆 Total Teams',
                    'value': str(data.get('total_teams', 0)),
                    'inline': True
                },
                {
                    'name': '👥 Total Drivers',
                    'value': str(data.get('total_drivers', 0)),
                    'inline': True
                }
            ]
        )