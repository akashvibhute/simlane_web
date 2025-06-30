"""Discord integration Celery tasks"""

import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import DiscordGuild, EventDiscordChannel, ClubDiscordSettings
from .services import DiscordMemberSyncService, DiscordChannelService, DiscordNotificationService
from simlane.teams.models import ClubEventSignupSheet

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_discord_members(self, guild_id: str, sync_type: str = 'manual'):
    """Sync Discord guild members with club members"""
    try:
        guild = DiscordGuild.objects.select_related('club').get(guild_id=guild_id)
        sync_service = DiscordMemberSyncService(guild)

        # Run sync operation (this is an async operation)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        sync_result = loop.run_until_complete(sync_service.sync_guild_members(sync_type))

        logger.info(
            f"Member sync completed for guild {guild_id}: "
            f"{sync_result.matched_members} matched, "
            f"{sync_result.new_club_members} new members"
        )

        return {
            'success': sync_result.success,
            'matched_members': sync_result.matched_members,
            'new_club_members': sync_result.new_club_members,
            'total_discord_members': sync_result.total_discord_members,
            'sync_id': sync_result.id,
            'timestamp': timezone.now().isoformat(),
            'sync_type': sync_type,
        }

    except DiscordGuild.DoesNotExist:
        logger.error(f"Discord guild {guild_id} not found")
        raise
    except Exception as exc:
        logger.exception(f"Member sync failed for guild {guild_id}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            'success': False,
            'error': str(exc),
            'guild_id': guild_id,
            'sync_type': sync_type,
            'timestamp': timezone.now().isoformat(),
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def create_event_channels(self, signup_sheet_id: int):
    """Create Discord channels for event signup sheet"""
    try:
        signup_sheet = ClubEventSignupSheet.objects.select_related(
            'club', 'club__discord_guild', 'event'
        ).get(id=signup_sheet_id)

        if not hasattr(signup_sheet.club, 'discord_guild'):
            logger.info(f"Club {signup_sheet.club.name} has no Discord integration")
            return {'success': False, 'reason': 'No Discord integration', 'timestamp': timezone.now().isoformat()}

        with transaction.atomic():
            settings, _ = ClubDiscordSettings.objects.get_or_create(
                club=signup_sheet.club,
                defaults={'auto_create_channels': True}
            )

            if not settings.auto_create_channels:
                logger.info(f"Auto-create disabled for club {signup_sheet.club.name}")
                return {'success': False, 'reason': 'Auto-create disabled', 'timestamp': timezone.now().isoformat()}

            channel_service = DiscordChannelService(signup_sheet.club.discord_guild)

            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            discord_channel = loop.run_until_complete(
                channel_service.create_event_channels(signup_sheet)
            )

        logger.info(
            f"Created Discord channels for event {signup_sheet.event.name}: "
            f"Channel ID {discord_channel.text_channel_id}"
        )
        return {
            'success': True,
            'discord_channel_id': discord_channel.id,
            'category_id': discord_channel.category_id,
            'text_channel_id': discord_channel.text_channel_id,
            'voice_channel_id': discord_channel.voice_channel_id,
            'practice_voice_channel_id': discord_channel.practice_voice_channel_id,
            'timestamp': timezone.now().isoformat(),
        }

    except ClubEventSignupSheet.DoesNotExist:
        logger.error(f"Signup sheet {signup_sheet_id} not found")
        raise
    except Exception as exc:
        logger.exception(f"Channel creation failed for signup {signup_sheet_id}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            'success': False,
            'error': str(exc),
            'signup_sheet_id': signup_sheet_id,
            'timestamp': timezone.now().isoformat(),
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def update_event_channels(self, event_id: int, update_type: str = 'signup_progress'):
    """Send periodic updates to event channels"""
    try:
        from simlane.sim.models import Event

        event = Event.objects.get(id=event_id)
        signup_sheets = ClubEventSignupSheet.objects.filter(event=event)

        updated = []
        for sheet in signup_sheets:
            try:
                channel = EventDiscordChannel.objects.get(
                    event_signup_sheet=sheet,
                    status='active'
                )
                count = sheet.get_signups().count()
                update_data = {
                    'total_signups': count,
                    'target_teams': sheet.max_teams,
                    'time_remaining': _calculate_time_remaining(sheet.signup_closes),
                    'event_name': event.name
                }

                notification_service = DiscordNotificationService(channel.guild)

                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                loop.run_until_complete(
                    notification_service.send_event_update(channel, update_type, update_data)
                )
                updated.append(channel.text_channel_id)

            except EventDiscordChannel.DoesNotExist:
                continue
            except Exception:
                logger.exception(f"Failed to update channel for signup {sheet.id}")
                continue

        logger.info(f"Updated {len(updated)} Discord channels for event {event_id}")
        return {
            'success': True,
            'updated_channels': updated,
            'update_type': update_type,
            'event_id': event_id,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.exception(f"Channel update failed for event {event_id}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            'success': False,
            'error': str(exc),
            'event_id': event_id,
            'timestamp': timezone.now().isoformat(),
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cleanup_expired_channels(self, guild_id: str):
    """Clean up expired event channels"""
    try:
        guild = DiscordGuild.objects.get(guild_id=guild_id)
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=7)

        expired = EventDiscordChannel.objects.filter(
            guild=guild,
            status='active',
            event_signup_sheet__event__start_time__lt=cutoff
        )

        cleaned = 0
        for ch in expired:
            try:
                ch.status = 'completed'
                ch.save(update_fields=['status'])
                cleaned += 1
                # Archival would go here
            except Exception:
                logger.exception(f"Failed to cleanup channel {ch.text_channel_id}")
                continue

        logger.info(f"Cleaned up {cleaned} expired channels for guild {guild_id}")
        return {
            'success': True,
            'cleaned_channels': cleaned,
            'guild_id': guild_id,
            'timestamp': timezone.now().isoformat(),
        }

    except DiscordGuild.DoesNotExist:
        logger.error(f"Discord guild {guild_id} not found")
        raise
    except Exception as exc:
        logger.exception(f"Channel cleanup failed for guild {guild_id}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            'success': False,
            'error': str(exc),
            'guild_id': guild_id,
            'timestamp': timezone.now().isoformat(),
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_discord_notification(self, channel_id: str, notification_type: str, data: dict):
    """Send notification to Discord channel"""
    try:
        channel = EventDiscordChannel.objects.select_related('guild').get(
            text_channel_id=channel_id
        )
        service = DiscordNotificationService(channel.guild)

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(
            service.send_event_update(channel, notification_type, data)
        )

        logger.info(f"Sent {notification_type} notification to channel {channel_id}")
        return {
            'success': True,
            'channel_id': channel_id,
            'notification_type': notification_type,
            'timestamp': timezone.now().isoformat(),
        }

    except EventDiscordChannel.DoesNotExist:
        logger.error(f"Discord channel {channel_id} not found")
        raise
    except Exception as exc:
        logger.exception(f"Notification failed for channel {channel_id}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            'success': False,
            'error': str(exc),
            'channel_id': channel_id,
            'notification_type': notification_type,
            'timestamp': timezone.now().isoformat(),
        }


@shared_task(bind=True)
def periodic_discord_maintenance(self):
    """Periodic maintenance tasks for Discord integration"""
    try:
        results = {
            'guilds_processed': 0,
            'syncs_scheduled': 0,
            'errors': [],
            'timestamp': timezone.now().isoformat(),
        }

        active = DiscordGuild.objects.filter(is_active=True)
        for guild in active:
            try:
                cleanup_expired_channels.apply_async(
                    args=[guild.guild_id],
                    countdown=5
                )
                results['guilds_processed'] += 1

                last = guild.discordmembersync_set.filter(sync_type='scheduled').first()
                if not last or (timezone.now() - last.sync_timestamp).days >= 1:
                    sync_discord_members.apply_async(
                        args=[guild.guild_id, 'scheduled'],
                        countdown=10
                    )
                    results['syncs_scheduled'] += 1

            except Exception:
                err = f"Maintenance failed for guild {guild.guild_id}"
                logger.exception(err)
                results['errors'].append(err)
                continue

        logger.info(
            f"Discord maintenance completed: "
            f"{results['guilds_processed']} guild(s), "
            f"{results['syncs_scheduled']} sync(s) scheduled"
        )
        return results

    except Exception:
        logger.exception("Discord maintenance failed")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_stint_alert(self, stint_plan_id: int, driver_id: int, minutes_before: int = 15):
    """Send stint change alert to Discord"""
    try:
        from simlane.teams.models import StintPlan
        from simlane.users.models import User

        plan = StintPlan.objects.select_related(
            'strategy__team', 'strategy__event', 'driver'
        ).get(id=stint_plan_id)
        driver = User.objects.get(id=driver_id)

        try:
            sheet = ClubEventSignupSheet.objects.get(
                event=plan.strategy.event,
                club=plan.strategy.team.club
            )
            channel = EventDiscordChannel.objects.get(
                event_signup_sheet=sheet, status='active'
            )
        except (ClubEventSignupSheet.DoesNotExist, EventDiscordChannel.DoesNotExist):
            logger.warning(f"No Discord channel for stint alert {stint_plan_id}")
            return {'success': False, 'reason': 'No Discord channel', 'timestamp': timezone.now().isoformat()}

        alert = {
            'driver_name': driver.get_full_name() or driver.username,
            'stint_number': plan.stint_number,
            'team_name': plan.strategy.team.name,
            'minutes_before': minutes_before,
            'planned_start_time': plan.planned_start_time,
            'planned_duration': plan.planned_duration,
        }

        service = DiscordNotificationService(channel.guild)
        bot_service = service.bot_service  # assume DiscordNotificationService exposes DiscordBotService

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        embed = loop.run_until_complete(
            bot_service.create_embed(
                title=f"⚠️ Stint Alert - {minutes_before} Minutes!",
                description=f"{alert['driver_name']}, your stint is starting soon!",
                color=0xff9500,
                fields=[
                    {'name': '🏁 Team', 'value': alert['team_name'], 'inline': True},
                    {'name': '🔄 Stint #', 'value': str(alert['stint_number']), 'inline': True},
                    {'name': '⏱️ Duration', 'value': str(alert['planned_duration']), 'inline': True},
                ]
            )
        )
        message_id = loop.run_until_complete(
            bot_service.post_message(channel.text_channel_id, embed=embed)
        )

        logger.info(f"Sent stint alert for driver {driver.username}, stint {plan.stint_number}")
        return {
            'success': True,
            'message_id': message_id,
            'stint_plan_id': stint_plan_id,
            'driver_id': driver_id,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.exception(f"Stint alert failed for stint {stint_plan_id}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            'success': False,
            'error': str(exc),
            'stint_plan_id': stint_plan_id,
            'driver_id': driver_id,
            'timestamp': timezone.now().isoformat(),
        }


# Helper functions
def _calculate_time_remaining(target_time):
    """Calculate human-readable time remaining until target time"""
    if not target_time:
        return "N/A"
    now = timezone.now()
    if target_time <= now:
        return "Closed"
    delta = target_time - now
    if delta.days > 0:
        return f"{delta.days} days"
    elif delta.seconds > 3600:
        hours = delta.seconds // 3600
        return f"{hours} hours"
    elif delta.seconds > 60:
        minutes = delta.seconds // 60
        return f"{minutes} minutes"
    else:
        return "Less than 1 minute"