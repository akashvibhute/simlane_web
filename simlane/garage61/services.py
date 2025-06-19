"""Garage61 API client and services"""

import time
from typing import Any

import requests
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.models import SocialToken
from django.contrib.auth import get_user_model

from .models import Garage61SyncLog

User = get_user_model()


class Garage61APIClient:
    """
    Comprehensive Garage61 API client supporting all endpoints from:
    https://garage61.net/developer/endpoints
    """

    BASE_URL = "https://garage61.net/api"

    def __init__(self, user: User | None = None, api_key: str | None = None):
        """
        Initialize API client with either OAuth2 user token or API key

        Args:
            user: Django user with linked Garage61 OAuth account
            api_key: Garage61 API key for server-to-server auth
        """
        self.user = user
        self.api_key = api_key
        self._headers = self._get_headers()

    def _get_headers(self) -> dict[str, str]:
        """Get authentication headers"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Simlane/1.0",
        }

        if self.user:
            # Use OAuth2 token from allauth
            token = self._get_oauth_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif self.api_key:
            # Use API key authentication
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _get_oauth_token(self) -> str | None:
        """Get OAuth2 token for the user"""
        try:
            social_account = SocialAccount.objects.get(
                user=self.user,
                provider="garage61",
            )
            token = SocialToken.objects.get(
                account=social_account,
                app__provider="garage61",
            )
        except (SocialAccount.DoesNotExist, SocialToken.DoesNotExist):
            return None
        else:
            return token.token

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | None = None,
    ) -> dict | None:
        """Make API request with logging"""
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        start_time = time.time()

        try:
            if method.upper() == "GET":
                response = requests.get(
                    url,
                    headers=self._headers,
                    params=params,
                    timeout=30,
                )
            elif method.upper() == "POST":
                response = requests.post(
                    url,
                    headers=self._headers,
                    json=data,
                    timeout=30,
                )
            elif method.upper() == "PUT":
                response = requests.put(
                    url,
                    headers=self._headers,
                    json=data,
                    timeout=30,
                )
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=self._headers, timeout=30)
            else:
                return None

            response_time = int((time.time() - start_time) * 1000)

            # Log the request
            self._log_request(
                endpoint=endpoint,
                method=method,
                status_code=response.status_code,
                success=True,
                error="",
                response_time=response_time,
            )

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            response_time = int((time.time() - start_time) * 1000)
            self._log_request(
                endpoint=endpoint,
                method=method,
                status_code=getattr(e.response, "status_code", None),
                success=False,
                error=str(e),
                response_time=response_time,
            )
            return None

    def _log_request(  # noqa: PLR0913
        self,
        *,
        endpoint: str,
        method: str,
        status_code: int | None,
        success: bool,
        error: str,
        response_time: int,
    ):
        """Log API request"""
        Garage61SyncLog.objects.create(
            user=self.user,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            success=success,
            error_message=error,
            response_time_ms=response_time,
        )

    # =====================================
    # GENERAL INFORMATION ENDPOINTS
    # =====================================

    def get_user_profile(self) -> dict | None:
        """Get user profile information"""
        return self._make_request("user")

    def get_user_statistics(self) -> dict | None:
        """Get user driving statistics"""
        return self._make_request("user/statistics")

    def get_user_achievements(self) -> dict | None:
        """Get user achievements and badges"""
        return self._make_request("user/achievements")

    def get_user_preferences(self) -> dict | None:
        """Get user preferences and settings"""
        return self._make_request("user/preferences")

    def update_user_preferences(self, preferences: dict) -> dict | None:
        """Update user preferences"""
        return self._make_request("user/preferences", method="PUT", data=preferences)

    # =====================================
    # CONTENT ENDPOINTS
    # =====================================

    def get_vehicles(self, category: str | None = None) -> dict | None:
        """Get available vehicles"""
        params = {"category": category} if category else None
        return self._make_request("vehicles", params=params)

    def get_vehicle_details(self, vehicle_id: str) -> dict | None:
        """Get detailed information about a specific vehicle"""
        return self._make_request(f"vehicles/{vehicle_id}")

    def get_vehicle_specifications(self, vehicle_id: str) -> dict | None:
        """Get technical specifications for a vehicle"""
        return self._make_request(f"vehicles/{vehicle_id}/specifications")

    def get_tracks(self, country: str | None = None) -> dict | None:
        """Get available tracks"""
        params = {"country": country} if country else None
        return self._make_request("tracks", params=params)

    def get_track_details(self, track_id: str) -> dict | None:
        """Get detailed information about a specific track"""
        return self._make_request(f"tracks/{track_id}")

    def get_track_layouts(self, track_id: str) -> dict | None:
        """Get available layouts for a track"""
        return self._make_request(f"tracks/{track_id}/layouts")

    def get_track_records(
        self,
        track_id: str,
        vehicle_id: str | None = None,
    ) -> dict | None:
        """Get lap records for a track"""
        params = {"vehicle_id": vehicle_id} if vehicle_id else None
        return self._make_request(f"tracks/{track_id}/records", params=params)

    def get_weather_conditions(self, track_id: str) -> dict | None:
        """Get current and forecasted weather for a track"""
        return self._make_request(f"tracks/{track_id}/weather")

    # =====================================
    # DRIVING DATA ENDPOINTS
    # =====================================

    def get_driving_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        vehicle_id: str | None = None,
        track_id: str | None = None,
    ) -> dict | None:
        """Get user's driving sessions"""
        params = {
            "limit": limit,
            "offset": offset,
        }
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if track_id:
            params["track_id"] = track_id

        return self._make_request("driving/sessions", params=params)

    def get_session_details(self, session_id: str) -> dict | None:
        """Get detailed information about a specific session"""
        return self._make_request(f"driving/sessions/{session_id}")

    def get_session_telemetry(
        self,
        session_id: str,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> dict | None:
        """Get telemetry data for a session"""
        params: dict[str, float] = {}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return self._make_request(
            f"driving/sessions/{session_id}/telemetry",
            params=params,
        )

    def get_session_laps(self, session_id: str) -> dict | None:
        """Get lap data for a session"""
        return self._make_request(f"driving/sessions/{session_id}/laps")

    def get_lap_details(self, session_id: str, lap_number: int) -> dict | None:
        """Get detailed information about a specific lap"""
        return self._make_request(f"driving/sessions/{session_id}/laps/{lap_number}")

    def get_lap_telemetry(self, session_id: str, lap_number: int) -> dict | None:
        """Get telemetry data for a specific lap"""
        return self._make_request(
            f"driving/sessions/{session_id}/laps/{lap_number}/telemetry",
        )

    def get_personal_bests(
        self,
        track_id: str | None = None,
        vehicle_id: str | None = None,
    ) -> dict | None:
        """Get user's personal best lap times"""
        params = {}
        if track_id:
            params["track_id"] = track_id
        if vehicle_id:
            params["vehicle_id"] = vehicle_id

        return self._make_request("driving/personal-bests", params=params)

    def get_driving_analysis(self, session_id: str) -> dict | None:
        """Get AI-powered driving analysis for a session"""
        return self._make_request(f"driving/sessions/{session_id}/analysis")

    def get_comparison_data(self, session_id: str, compare_with: str) -> dict | None:
        """Compare session with another session or best lap"""
        params = {"compare_with": compare_with}
        return self._make_request(
            f"driving/sessions/{session_id}/compare",
            params=params,
        )

    def get_sector_times(
        self,
        session_id: str,
        lap_number: int | None = None,
    ) -> dict | None:
        """Get sector times for a session or specific lap"""
        endpoint = f"driving/sessions/{session_id}/sectors"
        if lap_number:
            endpoint += f"?lap={lap_number}"
        return self._make_request(endpoint)

    def get_fuel_consumption(self, session_id: str) -> dict | None:
        """Get fuel consumption data for a session"""
        return self._make_request(f"driving/sessions/{session_id}/fuel")

    def get_tire_data(self, session_id: str) -> dict | None:
        """Get tire wear and temperature data for a session"""
        return self._make_request(f"driving/sessions/{session_id}/tires")

    def export_session_data(
        self,
        session_id: str,
        data_format: str = "json",
    ) -> dict | None:
        """Export session data in various formats (json, csv, motec)"""
        params = {"format": data_format}
        return self._make_request(
            f"driving/sessions/{session_id}/export",
            params=params,
        )


class Garage61Service:
    """High-level service for Garage61 integration"""

    @staticmethod
    def get_api_client(user: User | None = None) -> Garage61APIClient:
        """Get API client with OAuth authentication"""
        if user:
            return Garage61APIClient(user=user)

        msg = "No user provided for Garage61 OAuth authentication"
        raise ValueError(msg)

    @staticmethod
    def sync_user_data(user: User) -> dict[str, Any]:
        """Sync all user data from Garage61"""
        client = Garage61Service.get_api_client(user)

        results = {
            "profile": client.get_user_profile(),
            "statistics": client.get_user_statistics(),
            "achievements": client.get_user_achievements(),
            "sessions": client.get_driving_sessions(limit=100),
            "personal_bests": client.get_personal_bests(),
        }

        return {k: v for k, v in results.items() if v is not None}

    @staticmethod
    def is_user_connected(user: User) -> bool:
        """Check if user has connected Garage61 account"""
        try:
            return SocialAccount.objects.filter(
                user=user,
                provider="garage61",
            ).exists()
        except SocialAccount.DoesNotExist:
            return False
