from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from channels.auth import AuthMiddlewareStack
from simlane.api.auth import JWTTokenStrategy


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
        ]

        # Check if current path matches any public path
        if request.path in public_paths:
            return None

        # Public paths that don't require authentication
        public_prefixes = [
            "/search/",
            "/drivers/",
            "/cars/",
            "/tracks/",
            "/api/",
            "/accounts/",
            "/auth/",
            "/__debug__/",
            "/404/",
            "/500/",
            "/robots.txt",
            "/favicon.ico",
            "/contact/",
        ]
        
        if any(request.path.startswith(prefix) for prefix in public_prefixes):
            return None

        # Redirect unauthenticated users to login page
        return redirect("account_login")

@database_sync_to_async
def get_user_from_token(token):
    try:
        user = JWTTokenStrategy().get_user_from_token(token)
        if user and user.is_active:
            return user
    except Exception:
        pass
    return AnonymousUser()

class CombinedAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Check for token in query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = None
        if 'token' in query_params:
            token = query_params['token'][0]
        if not token:
            for header, value in scope.get('headers', []):
                if header == b'authorization':
                    value_str = value.decode()
                    if value_str.lower().startswith('bearer '):
                        token = value_str[7:]
        if token:
            scope['user'] = await get_user_from_token(token)
            return await super().__call__(scope, receive, send)
        else:
            # Fallback to session-based auth
            inner = AuthMiddlewareStack(self.inner)
            return await inner(scope, receive, send)
