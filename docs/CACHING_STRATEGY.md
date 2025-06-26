# SimLane Caching Strategy - Product Requirements Document

## Executive Summary

This document outlines the comprehensive caching strategy for the SimLane application, leveraging the existing Redis infrastructure (currently used for Celery) to improve application performance, reduce database load, and enhance user experience.

## Current State Analysis

### Existing Infrastructure
- **Redis**: Already configured for Celery (`redis://redis:6379/0`)
- **Production Cache**: Redis cache enabled in production settings
- **Development Cache**: Currently using `LocMemCache` in development
- **Session Storage**: Using database-backed sessions

### Performance Bottlenecks Identified
1. **Database-heavy views**: Club dashboards, team formations, sim profiles
2. **Complex queries**: Availability overlaps, team allocations, event participation
3. **Search functionality**: User and sim profile searches
4. **Session management**: Database sessions cause unnecessary DB hits
5. **Static content**: Template fragments and computed data

## Goals and Objectives

### Primary Goals
- **Performance**: Reduce database queries by 40-60%
- **User Experience**: Improve page load times by 30-50%
- **Scalability**: Support increased concurrent users
- **Cost Efficiency**: Reduce database server load

### Success Metrics
- Average response time reduction
- Database query count reduction
- Cache hit ratio > 80%
- User session performance improvement

## Caching Architecture

### Cache Layers

#### 1. Session Cache
- **Purpose**: Store user sessions in Redis instead of database
- **TTL**: 2 weeks (configurable)
- **Key Pattern**: `session:<session_key>`

#### 2. View Cache
- **Purpose**: Cache entire view responses for anonymous/public content
- **TTL**: 15 minutes (public), 5 minutes (semi-static)
- **Key Pattern**: `view:<view_name>:<params_hash>`

#### 3. Template Fragment Cache
- **Purpose**: Cache expensive template fragments
- **TTL**: 5-30 minutes depending on content
- **Key Pattern**: `fragment:<template_name>:<identifier>`

#### 4. Database Query Cache
- **Purpose**: Cache expensive database queries and aggregations
- **TTL**: 1-60 minutes depending on data volatility
- **Key Pattern**: `query:<model>:<query_hash>`

#### 5. API Response Cache
- **Purpose**: Cache API endpoint responses
- **TTL**: 5-15 minutes
- **Key Pattern**: `api:<endpoint>:<params_hash>`

### Redis Database Allocation
```
Database 0: Celery (existing)
Database 1: Sessions
Database 2: View & Fragment Cache
Database 3: Query Cache
Database 4: API Cache
```

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. **Session Storage Migration**
   - Configure Redis for session storage
   - Update settings for development and production
   - Test session persistence and cleanup

2. **Cache Configuration**
   - Set up Redis databases for different cache types
   - Configure cache backends in Django settings
   - Implement cache key versioning

### Phase 2: Core Caching (Week 2-3)
1. **View-Level Caching**
   - Public sim profiles (`/profiles/`)
   - Search results pages
   - Static content (about, terms, etc.)

2. **Database Query Caching**
   - Club member lists
   - Team formations and allocations
   - Event participations
   - Sim profile statistics

### Phase 3: Advanced Caching (Week 4-5)
1. **Template Fragment Caching**
   - Dashboard components
   - Navigation menus
   - User profile sections

2. **API Caching**
   - Search endpoints
   - Club and team data
   - Event information

### Phase 4: Optimization (Week 6)
1. **Cache Warming**
   - Implement background tasks for popular data
   - Preload frequently accessed content

2. **Monitoring and Tuning**
   - Add cache metrics
   - Optimize TTL values
   - Performance analysis

## Detailed Implementation

### 1. Session Cache Configuration

#### Settings Updates
```python
# config/settings/base.py
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/2',  # Database 2
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    },
    'sessions': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/1',  # Database 1
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'TIMEOUT': 60 * 60 * 24 * 14,  # 2 weeks
    },
    'query_cache': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/3',  # Database 3
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    },
    'api_cache': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/4',  # Database 4
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    },
}
```

### 2. View-Level Caching

#### Public Content Caching
```python
# simlane/sim/views.py
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

@cache_page(60 * 15)  # 15 minutes
@vary_on_headers('Accept-Language')
def profiles_list(request):
    # Existing code...

@cache_page(60 * 5)  # 5 minutes
def profile_detail(request, simulator_slug, profile_identifier):
    # Existing code...
```

#### Conditional Caching for Authenticated Users
```python
# simlane/core/decorators.py
from django.core.cache import cache
from django.utils.decorators import decorator_from_middleware

def cache_for_anonymous(timeout):
    """Cache view only for anonymous users"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            
            cache_key = f"anon_view:{request.path}:{hash(str(request.GET))}"
            response = cache.get(cache_key)
            
            if response is None:
                response = view_func(request, *args, **kwargs)
                cache.set(cache_key, response, timeout)
            
            return response
        return wrapper
    return decorator
```

### 3. Database Query Caching

#### Query Caching Service
```python
# simlane/core/cache_utils.py
from django.core.cache import caches
import hashlib
import json

query_cache = caches['query_cache']

def cache_query(timeout=300):
    """Decorator for caching expensive database queries"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key_data = {
                'func': func.__name__,
                'args': str(args),
                'kwargs': str(sorted(kwargs.items()))
            }
            cache_key = f"query:{hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()}"
            
            result = query_cache.get(cache_key)
            if result is None:
                result = func(*args, **kwargs)
                query_cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator

def invalidate_cache_pattern(pattern):
    """Invalidate cache keys matching a pattern"""
    # Implementation for cache invalidation
    pass
```

#### Model-Level Caching
```python
# simlane/teams/models.py
from simlane.core.cache_utils import cache_query

class ClubMember(models.Model):
    # ... existing fields ...
    
    @classmethod
    @cache_query(timeout=600)  # 10 minutes
    def get_user_clubs(cls, user):
        return cls.objects.filter(user=user).select_related('club')
    
    @classmethod
    @cache_query(timeout=300)  # 5 minutes
    def get_club_members(cls, club):
        return cls.objects.filter(club=club).select_related('user')
```

### 4. Template Fragment Caching

#### Dashboard Components
```html
<!-- simlane/templates/teams/club_dashboard_content_partial.html -->
{% load cache %}

{% cache 300 club_stats club.id %}
<div class="stats-section">
    <!-- Expensive stats calculations -->
</div>
{% endcache %}

{% cache 600 club_members club.id user.id %}
<div class="members-section">
    <!-- Member list with role-based content -->
</div>
{% endcache %}
```

#### Navigation Caching
```html
<!-- simlane/templates/components/navbar.html -->
{% load cache %}

{% if user.is_authenticated %}
    {% cache 300 user_nav user.id %}
    <div class="user-navigation">
        <!-- User-specific navigation -->
    </div>
    {% endcache %}
{% else %}
    {% cache 3600 anon_nav %}
    <div class="anonymous-navigation">
        <!-- Anonymous navigation -->
    </div>
    {% endcache %}
{% endif %}
```

### 5. API Response Caching

#### API Cache Middleware
```python
# simlane/api/middleware.py
from django.core.cache import caches
from django.http import JsonResponse
import json

api_cache = caches['api_cache']

class APICacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.path.startswith('/api/') and request.method == 'GET':
            cache_key = f"api:{request.path}:{hash(str(request.GET))}"
            
            if not request.user.is_authenticated:
                # Cache for anonymous users
                cached_response = api_cache.get(cache_key)
                if cached_response:
                    return JsonResponse(cached_response)
        
        response = self.get_response(request)
        
        # Cache successful GET responses for anonymous users
        if (request.path.startswith('/api/') and 
            request.method == 'GET' and 
            response.status_code == 200 and
            not request.user.is_authenticated):
            
            try:
                response_data = json.loads(response.content)
                api_cache.set(cache_key, response_data, 300)  # 5 minutes
            except json.JSONDecodeError:
                pass
        
        return response
```

## Cache Invalidation Strategy

### 1. Time-Based Expiration
- **Sessions**: 2 weeks
- **Public content**: 15-30 minutes
- **User-specific content**: 5-10 minutes
- **Search results**: 5 minutes
- **Statistics**: 1 hour

### 2. Event-Based Invalidation
```python
# simlane/core/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

@receiver(post_save, sender='teams.ClubMember')
def invalidate_club_cache(sender, instance, **kwargs):
    # Invalidate club-related cache entries
    cache.delete_many([
        f"club_members:{instance.club.id}",
        f"user_clubs:{instance.user.id}",
    ])

@receiver(post_save, sender='sim.SimProfile')
def invalidate_profile_cache(sender, instance, **kwargs):
    # Invalidate profile-related cache entries
    cache.delete_many([
        f"profile_detail:{instance.simulator.slug}:{instance.sim_api_id}",
        "profiles_list",
    ])
```

### 3. Manual Cache Management
```python
# simlane/core/management/commands/cache_management.py
from django.core.management.base import BaseCommand
from django.core.cache import caches

class Command(BaseCommand):
    help = 'Manage application cache'
    
    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear all caches')
        parser.add_argument('--warm', action='store_true', help='Warm popular caches')
        parser.add_argument('--stats', action='store_true', help='Show cache statistics')
    
    def handle(self, *args, **options):
        if options['clear']:
            self.clear_caches()
        elif options['warm']:
            self.warm_caches()
        elif options['stats']:
            self.show_stats()
    
    def clear_caches(self):
        for cache_name in ['default', 'sessions', 'query_cache', 'api_cache']:
            cache = caches[cache_name]
            cache.clear()
            self.stdout.write(f"Cleared {cache_name} cache")
    
    def warm_caches(self):
        # Implement cache warming logic
        pass
```

## Monitoring and Metrics

### 1. Cache Performance Metrics
```python
# simlane/core/middleware.py
import time
from django.core.cache import cache

class CacheMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time
        
        # Log cache performance metrics
        cache_hits = getattr(request, '_cache_hits', 0)
        cache_misses = getattr(request, '_cache_misses', 0)
        
        if cache_hits + cache_misses > 0:
            hit_ratio = cache_hits / (cache_hits + cache_misses)
            # Log metrics to monitoring system
        
        return response
```

### 2. Django Admin Integration
```python
# simlane/core/admin.py
from django.contrib import admin
from django.core.cache import caches
from django.http import HttpResponse

@admin.register
class CacheAdmin:
    def cache_stats(self, request):
        stats = {}
        for cache_name in ['default', 'sessions', 'query_cache', 'api_cache']:
            cache = caches[cache_name]
            # Get cache statistics
            stats[cache_name] = {
                'keys': len(cache._cache.keys()) if hasattr(cache, '_cache') else 'N/A',
                'memory_usage': 'N/A',  # Implementation specific
            }
        
        return HttpResponse(f"Cache Stats: {stats}")
```

## Testing Strategy

### 1. Cache Functionality Tests
```python
# tests/test_caching.py
from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model

User = get_user_model()

class CacheTestCase(TestCase):
    def test_session_cache(self):
        """Test session storage in Redis"""
        # Test session creation and retrieval
        pass
    
    def test_view_cache(self):
        """Test view-level caching"""
        # Test cache hit/miss for views
        pass
    
    def test_query_cache(self):
        """Test database query caching"""
        # Test query cache decorator
        pass
    
    def test_cache_invalidation(self):
        """Test cache invalidation on model changes"""
        # Test signal-based cache invalidation
        pass
```

### 2. Performance Tests
```python
# tests/test_performance.py
from django.test import TestCase
from django.test.utils import override_settings
import time

class PerformanceTestCase(TestCase):
    def test_view_performance_with_cache(self):
        """Compare view performance with and without cache"""
        # Disable cache
        start_time = time.time()
        response1 = self.client.get('/profiles/')
        no_cache_time = time.time() - start_time
        
        # Enable cache and test again
        start_time = time.time()
        response2 = self.client.get('/profiles/')
        with_cache_time = time.time() - start_time
        
        # Assert performance improvement
        self.assertLess(with_cache_time, no_cache_time * 0.5)  # 50% improvement
```

## Security Considerations

### 1. Cache Key Security
- Use hashed keys to prevent cache key enumeration
- Include user ID in cache keys for user-specific content
- Avoid storing sensitive data in cache

### 2. Cache Isolation
- Separate cache databases for different data types
- Use proper cache key prefixes
- Implement cache access controls

### 3. Data Privacy
- Ensure cached data respects user privacy settings
- Implement cache encryption for sensitive data
- Regular cache cleanup for user data

## Rollout Plan

### Development Environment
1. Update local settings to use Redis for caching
2. Test all cache implementations
3. Verify cache invalidation works correctly

### Staging Environment
1. Deploy cache configuration
2. Run performance tests
3. Monitor cache hit ratios
4. Load test with cache enabled

### Production Deployment
1. **Blue-Green Deployment**: Deploy to one server first
2. **Monitor metrics**: Watch for performance improvements
3. **Gradual rollout**: Enable for all servers
4. **Fallback plan**: Ability to disable caching quickly

## Maintenance and Operations

### Daily Operations
- Monitor cache hit ratios
- Check Redis memory usage
- Review slow query logs

### Weekly Maintenance
- Analyze cache performance metrics
- Optimize TTL values based on usage patterns
- Review and update cache keys

### Monthly Reviews
- Performance impact assessment
- Cache strategy optimization
- Capacity planning for Redis

## Risk Mitigation

### Cache Failures
- **Graceful degradation**: Application continues without cache
- **Circuit breaker**: Disable cache if Redis is unavailable
- **Monitoring**: Alert on cache failures

### Memory Management
- **Redis memory limits**: Configure max memory and eviction policies
- **Cache size monitoring**: Alert on high memory usage
- **Key expiration**: Ensure proper TTL on all cached data

### Data Consistency
- **Cache invalidation**: Proper invalidation on data changes
- **Version control**: Cache key versioning for schema changes
- **Backup strategy**: Redis persistence configuration

## Success Criteria

### Performance Metrics
- **Response time**: 30-50% improvement in page load times
- **Database load**: 40-60% reduction in database queries
- **Cache efficiency**: >80% cache hit ratio
- **Concurrent users**: Support 2x more concurrent users

### Operational Metrics
- **Error rate**: No increase in application errors
- **Availability**: 99.9% cache availability
- **Memory usage**: Efficient Redis memory utilization
- **Monitoring**: Complete cache metrics visibility

## Conclusion

This comprehensive caching strategy will significantly improve SimLane's performance while maintaining data consistency and security. The phased implementation approach ensures minimal risk while delivering measurable performance improvements.

The strategy leverages existing Redis infrastructure and follows Django best practices, making it maintainable and scalable for future growth. 