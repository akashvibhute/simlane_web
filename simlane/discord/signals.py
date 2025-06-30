"""Django signal handlers for Discord integration"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from simlane.teams.models import ClubEventSignupSheet, EventParticipation
from .tasks import create_event_channels, sync_discord_members
from .models import ClubDiscordSettings

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ClubEventSignupSheet)
def handle_signup_sheet_created(sender, instance, created, **kwargs):
    """Create Discord channels when signup sheet is created"""
    if created:
        logger.info(f"Signup sheet created for {instance.event.name}, checking Discord integration")
        
        # Check if club has Discord integration enabled
        if hasattr(instance.club, 'discord_guild'):
            try:
                settings = ClubDiscordSettings.objects.get(club=instance.club)
                if settings.auto_create_channels:
                    logger.info(f"Triggering Discord channel creation for {instance.event.name}")
                    create_event_channels.delay(instance.id)
            except ClubDiscordSettings.DoesNotExist:
                # Create default settings and trigger channel creation
                ClubDiscordSettings.objects.create(
                    club=instance.club,
                    auto_create_channels=True
                )
                logger.info(f"Created default Discord settings and triggering channel creation")
                create_event_channels.delay(instance.id)


@receiver(post_save, sender=EventParticipation)
def handle_team_assignment(sender, instance, **kwargs):
    """Handle team assignment changes"""
    if instance.team and instance.status == 'team_assigned':
        logger.info(f"Team assigned for {instance.user}: {instance.team.name}")
        # Future: Trigger team thread creation
        # create_team_thread.delay(instance.id)


@receiver(post_save, sender=ClubEventSignupSheet)
def handle_signup_sheet_status_change(sender, instance, created, **kwargs):
    """Handle signup sheet status changes (opened/closed)"""
    if not created:  # Only for updates, not creation
        # Check if signup status changed to closed
        if instance.status == 'closed':
            logger.info(f"Signup closed for {instance.event.name}, sending Discord notification")
            # Future: Send signup closed notification
            # send_signup_closed_notification.delay(instance.id)


# Additional signal handlers can be added here for other models
# For example:
# - RaceStrategy created -> announce strategy
# - StintPlan created -> schedule stint alerts
# - Event results -> post results to Discord 