"""
Django management command for cache operations.

This command provides utilities for:
- Clearing all caches
- Warming popular caches
- Showing cache statistics
- Testing cache connectivity
"""

import logging

from django.core.cache import caches
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Manage application cache operations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear all caches",
        )
        parser.add_argument(
            "--warm",
            action="store_true",
            help="Warm popular caches",
        )
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Show cache statistics",
        )
        parser.add_argument(
            "--test",
            action="store_true",
            help="Test cache connectivity",
        )
        parser.add_argument(
            "--cache-alias",
            type=str,
            default="all",
            help="Specific cache alias to operate on (default: all)",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.clear_caches(options["cache_alias"])
        elif options["warm"]:
            self.warm_caches()
        elif options["stats"]:
            self.show_stats(options["cache_alias"])
        elif options["test"]:
            self.test_connectivity(options["cache_alias"])
        else:
            self.stdout.write(
                self.style.ERROR(
                    "Please specify an action: --clear, --warm, --stats, or --test"
                ),
            )

    def clear_caches(self, cache_alias="all"):
        """Clear cache(s)"""
        try:
            if cache_alias == "all":
                cache_aliases = ["default", "sessions", "query_cache", "api_cache"]
            else:
                cache_aliases = [cache_alias]

            for alias in cache_aliases:
                try:
                    cache = caches[alias]
                    cache.clear()
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Cleared {alias} cache"),
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Failed to clear {alias} cache: {e}"),
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCache clearing completed for: {', '.join(cache_aliases)}"
                ),
            )

        except Exception as e:
            raise CommandError(f"Cache clearing failed: {e}")

    def warm_caches(self):
        """Warm frequently accessed cache entries"""
        try:
            self.stdout.write("Starting cache warming...")

            # Import here to avoid circular imports
            from django.contrib.auth import get_user_model

            from simlane.sim.models import SimProfile
            from simlane.sim.models import Simulator
            from simlane.teams.models import Club

            User = get_user_model()

            # Warm popular public profiles
            self.stdout.write("Warming public sim profiles...")
            popular_profiles = (
                SimProfile.objects.filter(
                    is_public=True,
                )
                .select_related("simulator")
                .order_by("-created_at")[:20]
            )

            profiles_warmed = 0
            for profile in popular_profiles:
                try:
                    # This will cache the profile detail view
                    cache_key = f"profile:{profile.simulator.slug}:{profile.sim_api_id}"
                    # Pre-compute profile data that would be expensive
                    profile_data = {
                        "id": profile.id,
                        "name": profile.profile_name,
                        "simulator": profile.simulator.name,
                        "is_verified": profile.is_verified,
                    }
                    caches["default"].set(cache_key, profile_data, 600)  # 10 minutes
                    profiles_warmed += 1
                except Exception as e:
                    logger.warning(f"Failed to warm profile {profile.id}: {e}")

            self.stdout.write(f"✓ Warmed {profiles_warmed} sim profiles")

            # Warm active simulators
            self.stdout.write("Warming simulators...")
            simulators = Simulator.objects.filter(is_active=True).order_by("name")
            simulators_warmed = 0
            for simulator in simulators:
                try:
                    cache_key = f"simulator:{simulator.slug}"
                    simulator_data = {
                        "id": simulator.id,
                        "name": simulator.name,
                        "slug": simulator.slug,
                        "is_active": simulator.is_active,
                    }
                    caches["default"].set(cache_key, simulator_data, 1800)  # 30 minutes
                    simulators_warmed += 1
                except Exception as e:
                    logger.warning(f"Failed to warm simulator {simulator.id}: {e}")

            self.stdout.write(f"✓ Warmed {simulators_warmed} simulators")

            # Warm active clubs
            self.stdout.write("Warming active clubs...")
            active_clubs = Club.objects.filter(is_active=True).order_by("-created_at")[
                :10
            ]
            clubs_warmed = 0
            for club in active_clubs:
                try:
                    cache_key = f"club:{club.id}:basic"
                    club_data = {
                        "id": club.id,
                        "name": club.name,
                        "slug": club.slug,
                        "is_active": club.is_active,
                        "member_count": club.members.count(),
                    }
                    caches["default"].set(cache_key, club_data, 600)  # 10 minutes
                    clubs_warmed += 1
                except Exception as e:
                    logger.warning(f"Failed to warm club {club.id}: {e}")

            self.stdout.write(f"✓ Warmed {clubs_warmed} clubs")

            self.stdout.write(
                self.style.SUCCESS("\nCache warming completed!"),
            )

        except Exception as e:
            raise CommandError(f"Cache warming failed: {e}")

    def show_stats(self, cache_alias="all"):
        """Show cache statistics"""
        try:
            if cache_alias == "all":
                cache_aliases = ["default", "sessions", "query_cache", "api_cache"]
            else:
                cache_aliases = [cache_alias]

            self.stdout.write("Cache Statistics:")
            self.stdout.write("-" * 50)

            for alias in cache_aliases:
                try:
                    cache = caches[alias]
                    self.stdout.write(f"\n{alias.upper()} Cache:")

                    # Test cache connectivity
                    test_key = f"test_key_{alias}"
                    cache.set(test_key, "test_value", 10)
                    retrieved = cache.get(test_key)
                    cache.delete(test_key)

                    if retrieved == "test_value":
                        self.stdout.write("  Status: ✓ Connected")
                    else:
                        self.stdout.write("  Status: ✗ Not working")

                    # Try to get Redis-specific stats if available
                    try:
                        from django_redis import get_redis_connection

                        redis_conn = get_redis_connection(alias)
                        info = redis_conn.info()

                        self.stdout.write(
                            f"  Used Memory: {info.get('used_memory_human', 'N/A')}"
                        )
                        self.stdout.write(
                            f"  Connected Clients: {info.get('connected_clients', 'N/A')}"
                        )
                        self.stdout.write(
                            f"  Total Commands: {info.get('total_commands_processed', 'N/A')}"
                        )
                        self.stdout.write(
                            f"  Keyspace Hits: {info.get('keyspace_hits', 'N/A')}"
                        )
                        self.stdout.write(
                            f"  Keyspace Misses: {info.get('keyspace_misses', 'N/A')}"
                        )

                        # Calculate hit rate
                        hits = info.get("keyspace_hits", 0)
                        misses = info.get("keyspace_misses", 0)
                        if hits + misses > 0:
                            hit_rate = (hits / (hits + misses)) * 100
                            self.stdout.write(f"  Hit Rate: {hit_rate:.2f}%")

                    except (ImportError, Exception) as e:
                        self.stdout.write(
                            f"  Redis stats unavailable: {str(e)[:50]}..."
                        )

                except Exception as e:
                    self.stdout.write(f"\n{alias.upper()} Cache: ✗ Error - {e}")

            self.stdout.write("\n" + "-" * 50)

        except Exception as e:
            raise CommandError(f"Failed to show cache stats: {e}")

    def test_connectivity(self, cache_alias="all"):
        """Test cache connectivity"""
        try:
            if cache_alias == "all":
                cache_aliases = ["default", "sessions", "query_cache", "api_cache"]
            else:
                cache_aliases = [cache_alias]

            self.stdout.write("Testing cache connectivity...")
            self.stdout.write("-" * 40)

            all_working = True

            for alias in cache_aliases:
                try:
                    cache = caches[alias]

                    # Test basic operations
                    test_key = f"connectivity_test_{alias}"
                    test_value = f"test_value_for_{alias}"

                    # Set
                    cache.set(test_key, test_value, 60)

                    # Get
                    retrieved = cache.get(test_key)

                    # Delete
                    cache.delete(test_key)

                    # Verify
                    deleted_check = cache.get(test_key)

                    if retrieved == test_value and deleted_check is None:
                        self.stdout.write(f"✓ {alias}: All operations working")
                    else:
                        self.stdout.write(f"✗ {alias}: Operations failed")
                        all_working = False

                except Exception as e:
                    self.stdout.write(f"✗ {alias}: Connection failed - {e}")
                    all_working = False

            self.stdout.write("-" * 40)
            if all_working:
                self.stdout.write(
                    self.style.SUCCESS("✓ All cache backends are working correctly!"),
                )
            else:
                self.stdout.write(
                    self.style.ERROR("✗ Some cache backends have issues!"),
                )

        except Exception as e:
            raise CommandError(f"Cache connectivity test failed: {e}")
