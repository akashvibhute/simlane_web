from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from simlane.api.auth import JWTTokenStrategy

@database_sync_to_async
def get_user_from_token(token):
    try:
        user = JWTTokenStrategy().get_user_from_token(token)
        if user and user.is_active:
            return user
    except Exception:
        pass
    return AnonymousUser()

class TokenAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
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
        scope['user'] = await get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send) 