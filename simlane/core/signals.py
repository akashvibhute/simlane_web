"""
Cache invalidation signals for SimLane application.

This module provides automatic cache invalidation when models are updated,
ensuring cache consistency across the application.
"""

import logging

from django.core.cache import caches
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver

from simlane.core.cache_utils import TaggedCacheService

logger = logging.getLogger(__name__)


@receiver(post_save, sender="teams.Club")
@receiver(post_delete, sender="teams.Club")
def invalidate_club_cache(sender, instance, **kwargs):
    """Invalidate club-related cache entries"""
    try:
        # Invalidate specific club caches
        cache_keys = [
            f"club:{instance.id}:basic",
            f"club:{instance.id}:members",
            f"club:{instance.id}:stats",
            f"club:{instance.slug}:detail",
            "clubs_list",
        ]
        
        caches["default"].delete_many(cache_keys)
        
        # Invalidate tagged caches
        tagged_cache = TaggedCacheService()
        tagged_cache.invalidate_tag(f"club:{instance.id}")
        tagged_cache.invalidate_tag("clubs_list")
        
        logger.info(f"Invalidated cache for club: {instance.name}")
        
    except Exception as e:
        logger.error(f"Failed to invalidate club cache: {e}")


@receiver(post_save, sender="teams.ClubMember")
@receiver(post_delete, sender="teams.ClubMember")
def invalidate_club_member_cache(sender, instance, **kwargs):
    """Invalidate club member related cache entries"""
    try:
        # Invalidate user's clubs and club's members
        cache_keys = [
            f"user:{instance.user.id}:clubs",
            f"club:{instance.club.id}:members",
            f"club:{instance.club.id}:stats",
        ]
        
        caches["default"].delete_many(cache_keys)
        caches["query_cache"].delete_many([
            f"query:get_user_clubs:{instance.user.id}",
            f"query:get_club_members:{instance.club.id}",
        ])
        
        # Invalidate tagged caches
        tagged_cache = TaggedCacheService()
        tagged_cache.invalidate_tag(f"user:{instance.user.id}")
        tagged_cache.invalidate_tag(f"club:{instance.club.id}")
        
        logger.info(f"Invalidated cache for club membership: {instance.user.username} in {instance.club.name}")
        
    except Exception as e:
        logger.error(f"Failed to invalidate club member cache: {e}")


@receiver(post_save, sender="teams.Team")
@receiver(post_delete, sender="teams.Team")
def invalidate_team_cache(sender, instance, **kwargs):
    """Invalidate team-related cache entries"""
    try:
        cache_keys = [
            f"team:{instance.id}:detail",
            f"team:{instance.id}:members",
            f"club:{instance.club.id}:teams",
        ]
        
        caches["default"].delete_many(cache_keys)
        
        # Invalidate tagged caches
        tagged_cache = TaggedCacheService()
        tagged_cache.invalidate_tag(f"team:{instance.id}")
        tagged_cache.invalidate_tag(f"club:{instance.club.id}")
        
        logger.info(f"Invalidated cache for team: {instance.name}")
        
    except Exception as e:
        logger.error(f"Failed to invalidate team cache: {e}")


@receiver(post_save, sender="sim.SimProfile")
@receiver(post_delete, sender="sim.SimProfile")
def invalidate_sim_profile_cache(sender, instance, **kwargs):
    """Invalidate sim profile related cache entries"""
    try:
        cache_keys = [
            f"profile:{instance.simulator.slug}:{instance.sim_api_id}",
            f"user:{instance.user.id}:profiles",
            "profiles_list",
            f"simulator:{instance.simulator.slug}:profiles",
        ]
        
        caches["default"].delete_many(cache_keys)
        
        # Invalidate query cache entries
        caches["query_cache"].delete_many([
            f"query:get_public_profiles",
            f"query:get_user_profiles:{instance.user.id}",
            f"query:get_verified_profiles",
        ])
        
        # Invalidate tagged caches
        tagged_cache = TaggedCacheService()
        tagged_cache.invalidate_tag(f"user:{instance.user.id}")
        tagged_cache.invalidate_tag(f"simulator:{instance.simulator.slug}")
        tagged_cache.invalidate_tag("profiles")
        
        logger.info(f"Invalidated cache for sim profile: {instance.profile_name}")
        
    except Exception as e:
        logger.error(f"Failed to invalidate sim profile cache: {e}")


@receiver(post_save, sender="sim.Event")
@receiver(post_delete, sender="sim.Event") 
def invalidate_event_cache(sender, instance, **kwargs):
    """Invalidate event-related cache entries"""
    try:
        cache_keys = [
            f"event:{instance.id}:detail",
            f"series:{instance.series.id}:events",
            "events_list",
            "upcoming_events",
        ]
        
        caches["default"].delete_many(cache_keys)
        
        # Invalidate tagged caches
        tagged_cache = TaggedCacheService()
        tagged_cache.invalidate_tag(f"event:{instance.id}")
        tagged_cache.invalidate_tag(f"series:{instance.series.id}")
        tagged_cache.invalidate_tag("events")
        
        logger.info(f"Invalidated cache for event: {instance.name}")
        
    except Exception as e:
        logger.error(f"Failed to invalidate event cache: {e}")


@receiver(post_save, sender="teams.EventParticipation")
@receiver(post_delete, sender="teams.EventParticipation")
def invalidate_event_participation_cache(sender, instance, **kwargs):
    """Invalidate event participation cache entries"""
    try:
        cache_keys = [
            f"event:{instance.event.id}:participants",
            f"user:{instance.user.id}:participations",
            f"team:{instance.team.id}:participations" if instance.team else None,
        ]
        
        # Remove None values
        cache_keys = [key for key in cache_keys if key is not None]
        
        caches["default"].delete_many(cache_keys)
        
        # Invalidate tagged caches
        tagged_cache = TaggedCacheService()
        tagged_cache.invalidate_tag(f"event:{instance.event.id}")
        tagged_cache.invalidate_tag(f"user:{instance.user.id}")
        if instance.team:
            tagged_cache.invalidate_tag(f"team:{instance.team.id}")
        
        logger.info(f"Invalidated cache for event participation: {instance.user.username} in {instance.event.name}")
        
    except Exception as e:
        logger.error(f"Failed to invalidate event participation cache: {e}")


@receiver(post_save, sender="users.User")
def invalidate_user_cache(sender, instance, **kwargs):
    """Invalidate user-related cache entries on profile updates"""
    try:
        # Only invalidate on certain field changes to avoid excessive cache clearing
        if hasattr(instance, '_state') and instance._state.adding:
            # New user - no cache to invalidate
            return
            
        cache_keys = [
            f"user:{instance.id}:profile",
            f"user:{instance.id}:clubs",
            f"user:{instance.id}:teams",
        ]
        
        caches["default"].delete_many(cache_keys)
        
        # Invalidate tagged caches
        tagged_cache = TaggedCacheService()
        tagged_cache.invalidate_tag(f"user:{instance.id}")
        
        logger.info(f"Invalidated cache for user: {instance.username}")
        
    except Exception as e:
        logger.error(f"Failed to invalidate user cache: {e}") 