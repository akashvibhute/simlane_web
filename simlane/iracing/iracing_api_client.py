import logging
import pickle

from django.conf import settings
from django.core.cache import cache
from iracingdataapi.client import irDataClient

logger = logging.getLogger(__name__)


class IRacingAPIClient(irDataClient):
    """
    iRacing API client with persistent system session caching.
    Subclasses irDataClient to add cache-based session restoration and validation.
    Phase 1: System account only.
    """

    CACHE_KEY = "iracing_session_system"
    CACHE_TIMEOUT = 86400  # 24 hours

    @classmethod
    def from_system_cache(cls):
        """
        Returns an IRacingAPIClient with a persistent session for the system account.
        Restores session cookies from cache if available and valid, otherwise authenticates and caches.
        """
        if not settings.IRACING_USERNAME or not settings.IRACING_PASSWORD:
            logger.warning("iRacing credentials not configured in settings")
            return None

        session_data = cache.get(cls.CACHE_KEY)
        client = cls(
            username=settings.IRACING_USERNAME,
            password=settings.IRACING_PASSWORD,
        )
        restored = False
        if session_data:
            try:
                client.session.cookies.update(pickle.loads(session_data))
                client.authenticated = True
                # Validate session
                try:
                    client.member_info()
                    logger.info(
                        "iRacing session restored and validated from cache",
                        extra={
                            "auth_type": "system",
                            "cache_hit": True,
                        },
                    )
                    restored = True
                except Exception:
                    logger.warning("Cached session invalid, re-authenticating")
                    cache.delete(cls.CACHE_KEY)
            except Exception:
                logger.exception(
                    "Failed to restore iRacing session from cache; re-authenticating"
                )
                cache.delete(cls.CACHE_KEY)

        if not restored:
            # Authenticate (will login on first API call)
            try:
                client.member_info()
                logger.info("iRacing system account authenticated and session cached")
            except Exception:
                logger.exception("Failed to authenticate iRacing system account")
                return None

        # Always cache the latest cookies after login or restore
        cache.set(
            cls.CACHE_KEY, pickle.dumps(client.session.cookies), cls.CACHE_TIMEOUT
        )
        return client

    def save_to_cache(self):
        """
        Saves the current session cookies to cache. For future extensibility.
        """
        cache.set(
            self.CACHE_KEY, pickle.dumps(self.session.cookies), self.CACHE_TIMEOUT
        )
        logger.info("Saved iRacing session cookies to cache")

    def series_season_schedule(self, season_id: int) -> dict:
        """
        Get the detailed schedule for a specific season.
        
        Args:
            season_id (int): The iRacing season ID
            
        Returns:
            dict: A dict containing the season schedule with race weeks, tracks, and weather
        """
        payload = {"season_id": season_id}
        return self._get_resource("/data/series/season_schedule", payload=payload)
