from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class AuthenticationRequiredMiddleware(MiddlewareMixin):
    """
    Middleware that requires authentication for all URLs except specified public ones.
    """

    def process_request(self, request):
        # Skip authentication for users who are already authenticated
        if request.user.is_authenticated:
            return None

        # Skip authentication for admin URLs (they have their own auth)
        if request.path.startswith("/admin/"):
            return None

        # Skip authentication for static and media files
        if request.path.startswith(("/static/", "/media/")):
            return None

        # Public URLs that don't require authentication
        public_paths = [
            "/",  # home
            "/about/",
            "/privacy/",
            "/terms/",
            "/contact/",
            "/contact/success/",
        ]

        # Check if current path matches any public path
        if request.path in public_paths:
            return None

        # Skip authentication for allauth and headless URLs (login, signup, password reset, etc.)
        if request.path.startswith("/accounts/") or request.path.startswith("/auth/"):
            return None

        if request.path.startswith("/__debug__/"):
            return None

        # Redirect unauthenticated users to login page
        return redirect("account_login")
