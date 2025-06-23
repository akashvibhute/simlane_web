from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from simlane.api.auth import JWTTokenStrategy
from simlane.api.schemas.auth import LoginRequest
from simlane.api.schemas.auth import LoginResponse
from simlane.api.schemas.auth import PasswordChangeRequest
from simlane.api.schemas.auth import PasswordResetRequest
from simlane.api.schemas.auth import RegisterRequest
from simlane.api.schemas.auth import SocialAuthURL
from simlane.api.schemas.auth import TokenRefreshRequest
from simlane.api.schemas.auth import TokenResponse
from simlane.api.schemas.auth import UserProfile
from simlane.api.schemas.auth import UserProfileUpdate

User = get_user_model()
router = Router()


@router.post("/login", response=LoginResponse, auth=None)
def login(request: HttpRequest, credentials: LoginRequest):
    """Authenticate user and return JWT tokens."""
    user = authenticate(
        request=request,
        username=credentials.username,
        password=credentials.password,
    )

    if not user:
        raise HttpError(401, "Invalid credentials")

    if not user.is_active:
        raise HttpError(401, "Account is disabled")

    # Create JWT tokens
    jwt_strategy = JWTTokenStrategy()
    access_token = jwt_strategy.create_access_token(user)
    refresh_token = jwt_strategy.create_refresh_token(user)

    # Get user profile
    user_profile = UserProfile.from_orm(user)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,  # 1 hour
        user=user_profile,
    )


@router.post("/register", response=LoginResponse, auth=None)
def register(request: HttpRequest, user_data: RegisterRequest):
    """Register a new user and return JWT tokens."""
    try:
        with transaction.atomic():
            # Validate password
            try:
                validate_password(user_data.password1)
            except DjangoValidationError as e:
                raise HttpError(400, {"password": list(e.messages)})

            # Check if username already exists
            if User.objects.filter(username=user_data.username).exists():
                raise HttpError(400, {"username": "Username already exists"})

            # Check if email already exists
            if User.objects.filter(email=user_data.email).exists():
                raise HttpError(400, {"email": "Email already exists"})

            # Create user
            user = User.objects.create_user(
                username=user_data.username,
                email=user_data.email,
                password=user_data.password1,
                first_name=user_data.first_name or "",
                last_name=user_data.last_name or "",
            )

            # Create email address for allauth
            email_address = EmailAddress.objects.create(
                user=user,
                email=user_data.email,
                primary=True,
                verified=False,
            )

            # Send confirmation email
            send_email_confirmation(request, user, email=user_data.email)

            # Create JWT tokens
            jwt_strategy = JWTTokenStrategy()
            access_token = jwt_strategy.create_access_token(user)
            refresh_token = jwt_strategy.create_refresh_token(user)

            # Get user profile
            user_profile = UserProfile.from_orm(user)

            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=3600,  # 1 hour
                user=user_profile,
            )

    except Exception as e:
        if isinstance(e, HttpError):
            raise e
        raise HttpError(500, "Registration failed")


@router.post("/refresh", response=TokenResponse, auth=None)
def refresh_token(request: HttpRequest, token_data: TokenRefreshRequest):
    """Refresh JWT access token using refresh token."""
    jwt_strategy = JWTTokenStrategy()

    try:
        # Verify refresh token
        payload = jwt_strategy.verify_token(token_data.refresh_token)

        if payload.get("token_type") != "refresh":
            raise HttpError(401, "Invalid token type")

        # Get user
        user_id = payload.get("user_id")
        if not user_id:
            raise HttpError(401, "Invalid token payload")

        user = User.objects.get(id=user_id, is_active=True)

        # Create new tokens
        access_token = jwt_strategy.create_access_token(user)
        refresh_token = jwt_strategy.create_refresh_token(user)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600,  # 1 hour
        )

    except User.DoesNotExist:
        raise HttpError(401, "User not found")
    except ValueError as e:
        raise HttpError(401, str(e))


@router.get("/me", response=UserProfile)
def get_current_user(request: HttpRequest):
    """Get current user profile."""
    return UserProfile.from_orm(request.auth)


@router.patch("/me", response=UserProfile)
def update_current_user(request: HttpRequest, updates: UserProfileUpdate):
    """Update current user profile."""
    user = request.auth

    # Update user fields
    for field, value in updates.dict(exclude_unset=True).items():
        if hasattr(user, field) and value is not None:
            setattr(user, field, value)

    user.save()
    return UserProfile.from_orm(user)


@router.post("/change-password")
def change_password(request: HttpRequest, password_data: PasswordChangeRequest):
    """Change user password."""
    user = request.auth

    # Verify old password
    if not user.check_password(password_data.old_password):
        raise HttpError(400, {"old_password": "Invalid current password"})

    # Validate new password
    try:
        validate_password(password_data.new_password1, user)
    except DjangoValidationError as e:
        raise HttpError(400, {"new_password": list(e.messages)})

    # Set new password
    user.set_password(password_data.new_password1)
    user.save()

    return {"message": "Password changed successfully"}


@router.post("/reset-password", auth=None)
def reset_password(request: HttpRequest, reset_data: PasswordResetRequest):
    """Request password reset."""
    try:
        user = User.objects.get(email=reset_data.email, is_active=True)
        # TODO: Implement password reset email sending
        # This would typically use allauth's password reset functionality
        return {"message": "Password reset email sent"}
    except User.DoesNotExist:
        # Don't reveal if email exists or not
        return {"message": "Password reset email sent"}


@router.post("/logout")
def logout(request: HttpRequest):
    """Logout user (client-side token invalidation)."""
    # JWT tokens are stateless, so logout is handled client-side
    # In a production app, you might want to implement a token blacklist
    return {"message": "Logged out successfully"}


@router.get("/social/discord/url", response=SocialAuthURL, auth=None)
def get_discord_auth_url(request: HttpRequest):
    """Get Discord OAuth URL for social authentication."""
    # TODO: Implement Discord OAuth URL generation
    # This would generate the OAuth URL for Discord login
    return SocialAuthURL(
        auth_url="https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&response_type=code&scope=identify%20email",
        state="generated_state_token",
    )


@router.get("/social/garage61/url", response=SocialAuthURL, auth=None)
def get_garage61_auth_url(request: HttpRequest):
    """Get Garage61 OAuth URL for social authentication."""
    # TODO: Implement Garage61 OAuth URL generation
    return SocialAuthURL(
        auth_url="https://garage61.net/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&response_type=code&scope=read",
        state="generated_state_token",
    )


@router.get("/verify-token", auth=None)
def verify_token(request: HttpRequest):
    """Verify JWT token validity."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HttpError(401, "Missing or invalid authorization header")

    token = auth_header.split(" ")[1]
    jwt_strategy = JWTTokenStrategy()

    try:
        payload = jwt_strategy.verify_token(token)
        user = jwt_strategy.get_user_from_token(token)

        if not user:
            raise HttpError(401, "Invalid token")

        return {
            "valid": True,
            "user_id": user.id,
            "username": user.username,
            "expires_at": payload.get("exp"),
        }
    except ValueError as e:
        raise HttpError(401, str(e))
