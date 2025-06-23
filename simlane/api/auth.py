from datetime import datetime
from datetime import timedelta
from typing import Any

import jwt
from allauth.headless.tokens.base import AbstractTokenStrategy
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class JWTTokenStrategy(AbstractTokenStrategy):
    """
    Custom JWT token strategy for django-allauth headless mode.
    Creates JWT tokens for mobile authentication.
    """

    def create_access_token(self, user) -> str:
        """Create a JWT access token for the user."""
        payload = self.create_access_token_payload(user)

        # Use JWT_SECRET_KEY from settings if available, otherwise fallback to SECRET_KEY
        secret_key = getattr(settings, "JWT_SECRET_KEY", settings.SECRET_KEY)
        algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")

        return jwt.encode(payload, secret_key, algorithm=algorithm)

    def create_access_token_payload(self, user) -> dict[str, Any]:
        """Create the payload for the JWT access token."""
        now = datetime.utcnow()
        access_token_lifetime = getattr(settings, "JWT_ACCESS_TOKEN_LIFETIME", 3600)

        payload = {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "iat": now,
            "exp": now + timedelta(seconds=access_token_lifetime),
            "token_type": "access",
        }

        return payload

    def create_refresh_token(self, user) -> str:
        """Create a JWT refresh token for the user."""
        payload = self.create_refresh_token_payload(user)

        # Use JWT_SECRET_KEY from settings if available, otherwise fallback to SECRET_KEY
        secret_key = getattr(settings, "JWT_SECRET_KEY", settings.SECRET_KEY)
        algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")

        return jwt.encode(payload, secret_key, algorithm=algorithm)

    def create_refresh_token_payload(self, user) -> dict[str, Any]:
        """Create the payload for the JWT refresh token."""
        now = datetime.utcnow()
        refresh_token_lifetime = getattr(
            settings,
            "JWT_REFRESH_TOKEN_LIFETIME",
            86400 * 7,
        )

        payload = {
            "user_id": user.id,
            "username": user.username,
            "iat": now,
            "exp": now + timedelta(seconds=refresh_token_lifetime),
            "token_type": "refresh",
        }

        return payload

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode a JWT token."""
        try:
            # Use JWT_SECRET_KEY from settings if available, otherwise fallback to SECRET_KEY
            secret_key = getattr(settings, "JWT_SECRET_KEY", settings.SECRET_KEY)
            algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")

            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")

    def get_user_from_token(self, token: str):
        """Get user instance from JWT token."""
        try:
            payload = self.verify_token(token)
            user_id = payload.get("user_id")

            if user_id:
                return User.objects.get(id=user_id)
            return None
        except (ValueError, User.DoesNotExist):
            return None
