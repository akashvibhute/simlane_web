"""Garage61 OAuth2 Provider for django-allauth"""

from allauth.socialaccount import providers
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.models import SocialLogin
from allauth.socialaccount.providers.base import ProviderAccount
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider
from django.apps import AppConfig


class Garage61Account(ProviderAccount):
    """Account class for Garage61 provider"""

    def get_profile_url(self):
        """Return profile URL for the user"""
        return f"https://garage61.net/profile/{self.account.uid}"

    def get_avatar_url(self):
        """Return avatar URL if available"""
        return self.account.extra_data.get("avatar_url")

    def to_str(self):
        """String representation of the account"""
        dflt = super().to_str()
        return self.account.extra_data.get("username", dflt)


class Garage61Provider(OAuth2Provider):
    """OAuth2 Provider for Garage61"""

    id = "garage61"
    name = "Garage61"
    account_class = Garage61Account

    def get_default_scope(self):
        """Default OAuth2 scopes"""
        return ["driving_data"]

    def get_auth_params(self, request, action):
        """Additional auth parameters"""
        return super().get_auth_params(request, action)

    def extract_uid(self, data):
        """Extract unique identifier from user data"""
        return str(data["id"])

    def extract_common_fields(self, data):
        """Extract common user fields from OAuth2 user data"""
        return {
            "email": data.get("email"),
            "username": data.get("username"),
            "first_name": data.get("first_name", ""),
            "last_name": data.get("last_name", ""),
        }

    def extract_extra_data(self, data):
        """Extract extra data to store with the social account"""
        return data

    def sociallogin_from_response(self, request, response):
        """Create a SocialLogin from OAuth2 response data"""
        account = SocialAccount(
            provider=self.id,
            uid=self.extract_uid(response),
            extra_data=self.extract_extra_data(response),
        )

        return SocialLogin(account=account)


class Garage61ProviderConfig(AppConfig):
    """Django app config for Garage61 provider"""

    name = "simlane.garage61_provider"
    verbose_name = "Garage61 OAuth2 Provider"

    def ready(self):
        # Register the provider when Django starts
        providers.registry.register(Garage61Provider)
