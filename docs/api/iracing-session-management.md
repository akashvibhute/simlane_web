# iRacing API Session Management Strategy

## Problem Statement

The iracingdataapi library uses `requests.Session()` to store cookies in memory, which causes re-authentication on every:
- Django dev server restart (auto-reload on file changes)
- Production process restart
- New worker process spawn
- Container restart

Currently, all API calls use a single shared account (system credentials). In the future, we plan to implement OAuth2 flow where users can connect their own iRacing accounts.

## Current Architecture

```python
# Current implementation
from iracingdataapi.client import irDataClient

client = irDataClient(username=SYSTEM_USERNAME, password=SYSTEM_PASSWORD)
# Session lost on process restart, requires re-authentication
```

## Future Architecture Requirements

1. **Multiple authentication contexts**: System account + per-user OAuth2 tokens
2. **Persistent sessions**: Survive process restarts and dev server reloads
3. **Token refresh**: Automatic OAuth2 token refresh via allauth integration
4. **Graceful fallback**: Use system account when user tokens are invalid
5. **Gradual migration**: Support both auth methods during transition

## Recommended Solution: Multi-User Session Manager

### Architecture Overview

```python
class IRacingSessionManager:
    def get_system_client(self):
        """Returns cached client with system credentials"""
        
    def get_client_for_user(self, user):
        """Returns user-specific client or falls back to system"""
        
    def get_client_for_request(self, request=None):
        """Smart client selection based on request context"""
```

### Session Storage Strategy

**Cache Key Pattern**:
```
iracing_session_system                    # System account session
iracing_session_user_{user_id}           # User OAuth2 session
iracing_session_oauth_{user_id}          # Alternative OAuth2 key format
```

**Storage Content**:
- Session cookies (for API authentication)
- Authentication method metadata
- Token expiry information
- Last successful authentication timestamp

## Implementation Phases

### Phase 1: System Session Caching (Immediate)
**Goal**: Solve current dev server restart issue

**Implementation**:
```python
class IRacingSessionManager:
    def get_system_client(self):
        # Check cache for existing session
        # If found, restore cookies to client
        # If not found or expired, authenticate and cache
        # Return client with persistent session
    
    def clear_system_cache(self):
        # For testing/troubleshooting
```

**Benefits**:
- Eliminates re-authentication on dev server restarts
- Reduces authentication overhead in production
- Maintains current API functionality
- Simple implementation

### Phase 2: Multi-User Architecture (Preparation)
**Goal**: Prepare for OAuth2 without breaking current functionality

**Implementation**:
```python
class IRacingSessionManager:
    def get_client_for_request(self, request=None):
        # For now, always return system client
        # Later: check if user has OAuth2 tokens
        return self.get_system_client()
    
    def get_client_for_user(self, user):
        # Placeholder for future OAuth2 implementation
        # For now, return system client
        return self.get_system_client()
```

**Benefits**:
- API ready for OAuth2 integration
- No breaking changes to existing code
- Easy to test and validate

### Phase 3: OAuth2 Integration (Future)
**Goal**: Support per-user iRacing authentication via allauth

**Implementation**:
```python
class IRacingSessionManager:
    def get_client_for_user(self, user):
        # Check if user has valid OAuth2 tokens in allauth
        if self._user_has_valid_tokens(user):
            return self._get_or_create_oauth_client(user)
        else:
            # Fallback to system account
            return self.get_system_client()
    
    def _refresh_user_tokens(self, user):
        # Integrate with allauth token refresh mechanism
        
    def _get_or_create_oauth_client(self, user):
        # Check cache for user's session
        # Create OAuth2-authenticated client if needed
        # Handle token refresh automatically
```

**OAuth2 Client Implementation**:
```python
class OAuth2IRacingClient(irDataClient):
    def __init__(self, access_token, refresh_token, user):
        # Custom initialization for OAuth2
        # Override authentication methods
        
    def _login(self):
        # Use OAuth2 tokens instead of username/password
        
    def _refresh_tokens_if_needed(self):
        # Automatic token refresh via allauth
```

### Phase 4: Migration and Optimization (Future)
**Goal**: Optimize performance and user experience

**Features**:
- User preference for using personal vs system account
- Analytics on authentication success/failure rates
- Advanced caching strategies (per-endpoint caching)
- Rate limit handling per authentication context

## Technical Implementation Details

### Cache Backend Configuration
```python
# Use Redis for session storage (already configured)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        # ... existing configuration
    }
}

# Session cache settings
IRACING_SESSION_CACHE_TIMEOUT = 86400  # 24 hours (iRacing sessions ~12h)
IRACING_SESSION_CACHE_PREFIX = 'iracing_session'
```

### Error Handling Strategy
```python
class IRacingSessionManager:
    def _handle_auth_failure(self, client_type, user_id=None):
        # Clear relevant cache entries
        # Log authentication failure
        # Attempt fallback authentication if applicable
        # Raise appropriate exception if all methods fail
```

### Integration Points

#### With Existing Service
```python
# Current usage
service = IRacingAPIService()
data = service.get_member_summary()

# Future usage (backward compatible)
service = IRacingAPIService()
data = service.get_member_summary(request=request)  # Auto-detects user context
```

#### With allauth (Future)
```python
# Token storage integration
from allauth.socialaccount.models import SocialToken

def get_user_iracing_tokens(user):
    try:
        social_token = SocialToken.objects.get(
            account__user=user,
            account__provider='iracing'
        )
        return social_token.token, social_token.token_secret
    except SocialToken.DoesNotExist:
        return None, None
```

## Security Considerations

1. **Token Storage**: OAuth2 tokens stored securely via allauth
2. **Cache Security**: Session cookies cached with appropriate TTL
3. **Fallback Security**: System credentials remain protected
4. **User Privacy**: User data accessed only with proper permissions
5. **Rate Limiting**: Respect iRacing's rate limits per authentication context

## Testing Strategy

### Unit Tests
- Session caching functionality
- Authentication fallback logic
- Token refresh mechanisms
- Error handling scenarios

### Integration Tests
- End-to-end API calls with cached sessions
- OAuth2 flow simulation
- Cache invalidation scenarios
- Multi-user session isolation

### Management Commands
```bash
# Check session cache status
python manage.py manage_iracing_sessions --status

# Clear cached sessions
python manage.py manage_iracing_sessions --clear-cache

# Test session persistence
python manage.py manage_iracing_sessions --test-persistence
```

## Monitoring and Observability

### Metrics to Track
- Authentication success/failure rates
- Session cache hit/miss ratios
- Token refresh frequency
- API call distribution (system vs user accounts)

### Logging Strategy
```python
logger.info("iRacing session restored from cache", extra={
    'auth_type': 'system|oauth2',
    'user_id': user_id,
    'cache_hit': True
})

logger.warning("iRacing session expired, re-authenticating", extra={
    'auth_type': 'system|oauth2',
    'user_id': user_id,
    'session_age': session_age_seconds
})
```

## Migration Timeline

### Immediate (Phase 1)
- [ ] Implement system session caching
- [ ] Add cache management commands
- [ ] Test with development environment
- [ ] Deploy to production

### Short-term (Phase 2)
- [ ] Refactor service to use session manager
- [ ] Add multi-user architecture foundation
- [ ] Update existing API calls to use new manager
- [ ] Add comprehensive testing

### Long-term (Phase 3+)
- [ ] Implement OAuth2 flow with iRacing
- [ ] Integrate with allauth
- [ ] Add user preference management
- [ ] Implement advanced caching strategies
- [ ] Add monitoring and analytics

## Alternative Approaches Considered

### Database-Based Session Storage
**Pros**: Most persistent, survives cache clears
**Cons**: Database overhead, more complex
**Decision**: Cache-based approach preferred for performance

### File-Based Session Storage
**Pros**: Simple, no external dependencies
**Cons**: Doesn't work in containerized environments
**Decision**: Not suitable for production deployment

### Singleton Pattern
**Pros**: Minimal overhead, simple
**Cons**: Doesn't solve restart issue, not multi-user ready
**Decision**: Doesn't meet future requirements

## References

- [iracingdataapi source code](https://raw.githubusercontent.com/jasondilworth56/iracingdataapi/refs/heads/main/src/iracingdataapi/client.py)
- [iRacing Data API Documentation](https://forums.iracing.com/discussion/15068/general-availability-of-data-api/)
- [Django Allauth Documentation](https://django-allauth.readthedocs.io/)
- [Django Cache Framework](https://docs.djangoproject.com/en/stable/topics/cache/) 