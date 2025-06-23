from datetime import datetime

from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import validator


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password1: str
    password2: str
    first_name: str | None = None
    last_name: str | None = None

    @validator("password2")
    def passwords_match(cls, v, values):
        if "password1" in values and v != values["password1"]:
            raise ValueError("Passwords do not match")
        return v

    @validator("username")
    def username_validation(cls, v):
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        return v


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    is_active: bool
    date_joined: datetime
    avatar_url: str | None = None
    bio: str | None = None
    timezone: str = "UTC"
    phone_number: str | None = None
    emergency_contact: str | None = None
    emergency_phone: str | None = None
    preferred_language: str = "en"

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserProfile


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password1: str
    new_password2: str

    @validator("new_password2")
    def passwords_match(cls, v, values):
        if "new_password1" in values and v != values["new_password1"]:
            raise ValueError("New passwords do not match")
        return v


class UserProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    bio: str | None = None
    timezone: str | None = None
    phone_number: str | None = None
    emergency_contact: str | None = None
    emergency_phone: str | None = None
    preferred_language: str | None = None


class DeviceRegistration(BaseModel):
    token: str
    platform: str
    device_id: str | None = None


class SocialAuthURL(BaseModel):
    auth_url: str
    state: str | None = None


class SocialAuthCallback(BaseModel):
    code: str
    state: str | None = None
