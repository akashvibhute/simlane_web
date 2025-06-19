"""Utility functions for Garage61 API integration"""

from typing import Any

import requests
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.models import SocialToken
from django.contrib.auth import get_user_model

User = get_user_model()


def get_garage61_social_account(user: User) -> SocialAccount | None:
    """Get Garage61 social account for a Django user"""
    try:
        return SocialAccount.objects.get(
            user=user,
            provider="garage61",
        )
    except SocialAccount.DoesNotExist:
        return None


def get_garage61_token(user: User) -> str | None:
    """Get active Garage61 access token for a user"""
    social_account = get_garage61_social_account(user)
    if not social_account:
        return None

    try:
        token = SocialToken.objects.get(
            account=social_account,
            app__provider="garage61",
        )
    except SocialToken.DoesNotExist:
        return None
    else:
        return token.token


def make_garage61_api_request(
    user: User,
    endpoint: str,
    method: str = "GET",
    data: dict | None = None,
) -> dict[Any, Any] | None:
    """Make an authenticated API request to Garage61"""
    token = get_garage61_token(user)
    if not token:
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    url = f"https://garage61.net/api/{endpoint.lstrip('/')}"

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        else:
            return None

        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def get_user_driving_data(user: User) -> dict[Any, Any] | None:
    """Get driving data for a user from Garage61 API"""
    return make_garage61_api_request(user, "driving-data")


def get_user_profile(user: User) -> dict[Any, Any] | None:
    """Get user profile from Garage61 API"""
    return make_garage61_api_request(user, "user")


def get_user_vehicles(user: User) -> dict[Any, Any] | None:
    """Get user's vehicles from Garage61 API"""
    return make_garage61_api_request(user, "vehicles")


def get_user_sessions(user: User, limit: int = 10) -> dict[Any, Any] | None:
    """Get user's recent driving sessions from Garage61 API"""
    return make_garage61_api_request(user, f"sessions?limit={limit}")


def is_garage61_connected(user: User) -> bool:
    """Check if user has connected their Garage61 account"""
    return get_garage61_social_account(user) is not None
