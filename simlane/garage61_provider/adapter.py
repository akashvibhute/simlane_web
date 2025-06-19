"""OAuth2 adapter for Garage61 API communication"""

import requests
from allauth.socialaccount.providers.oauth2.client import OAuth2Error


class Garage61OAuth2Adapter:
    """OAuth2 adapter for Garage61"""

    provider_id = "garage61"

    # OAuth2 endpoints based on garage61 documentation
    access_token_url = "https://garage61.net/oauth/token"  # noqa: S105
    authorize_url = "https://garage61.net/oauth/authorize"
    profile_url = "https://garage61.net/api/user"

    def complete_login(self, request, app, token, **kwargs):
        """Complete the OAuth2 login by fetching user data"""
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Accept": "application/json",
        }

        try:
            response = requests.get(self.profile_url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            msg = f"Error fetching user profile: {e}"
            raise OAuth2Error(msg) from e

        try:
            extra_data = response.json()
        except ValueError as e:
            msg = f"Invalid JSON response: {e}"
            raise OAuth2Error(msg) from e

        # Validate required fields
        if "id" not in extra_data:
            msg = "User ID not found in profile data"
            raise OAuth2Error(msg)

        # Create the login instance
        from .provider import Garage61Provider

        provider = Garage61Provider(request)
        login = provider.sociallogin_from_response(request, extra_data)
        login.token = token

        return login
