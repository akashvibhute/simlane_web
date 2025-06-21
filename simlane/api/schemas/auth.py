from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password1: str
    password2: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    @validator('password2')
    def passwords_match(cls, v, values):
        if 'password1' in values and v != values['password1']:
            raise ValueError('Passwords do not match')
        return v

    @validator('username')
    def username_validation(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
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
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    timezone: str = "UTC"
    phone_number: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
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

    @validator('new_password2')
    def passwords_match(cls, v, values):
        if 'new_password1' in values and v != values['new_password1']:
            raise ValueError('New passwords do not match')
        return v


class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    timezone: Optional[str] = None
    phone_number: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    preferred_language: Optional[str] = None


class DeviceRegistration(BaseModel):
    token: str
    platform: str
    device_id: Optional[str] = None


class SocialAuthURL(BaseModel):
    auth_url: str
    state: Optional[str] = None


class SocialAuthCallback(BaseModel):
    code: str
    state: Optional[str] = None 