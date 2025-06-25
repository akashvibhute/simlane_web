"""
Cache utilities for SimLane application.

This module provides advanced caching functionality including:
- Cache key management with versioning
- Cache stampede prevention
- Circuit breaker pattern for cache failures
- Tagged cache system for sophisticated invalidation
- Compression for large objects
"""

import hashlib
import json
import logging
import pickle
import time
import threading
from typing import Any, Optional, List, Dict, Callable
import gzip

from django.core.cache import caches, cache
from django.conf import settings

logger = logging.getLogger(__name__)


class CacheKeyManager:
    """Manages cache keys with versioning and hierarchical structure"""
    
    @staticmethod
    def get_versioned_key(base_key: str, version: int = 1) -> str:
        """Generate versioned cache key"""
        return f"v{version}:{base_key}"
    
    @staticmethod
    def get_user_cache_key(user_id: int, key_type: str, identifier: str = "") -> str:
        """Generate user-specific cache key"""
        key = f"user:{user_id}:{key_type}"
        if identifier:
            key += f":{identifier}"
        return key
    
    @staticmethod
    def get_model_cache_key(model_name: str, pk: int, action: str = "detail") -> str:
        """Generate model-specific cache key"""
        return f"model:{model_name}:{pk}:{action}"
    
    @staticmethod
    def get_query_cache_key(func_name: str, *args, **kwargs) -> str:
        """Generate cache key for database queries"""
        key_data = {
            'func': func_name,
            'args': str(args),
            'kwargs': str(sorted(kwargs.items()))
        }
        key_hash = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
        return f"query:{func_name}:{key_hash}"
    
    @staticmethod
    def get_view_cache_key(view_name: str, *args, **kwargs) -> str:
        """Generate cache key for view results"""
        params_hash = hashlib.md5(str(sorted(kwargs.items())).encode()).hexdigest()
        return f"view:{view_name}:{params_hash}"


class CacheCircuitBreaker:
    """Circuit breaker for cache operations"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()
    
    def call_with_fallback(self, cache_func: Callable, fallback_func: Callable, *args, **kwargs) -> Any:
        """Execute cache operation with fallback"""
        with self._lock:
            if self.state == 'OPEN':
                if self.last_failure_time and time.time() - self.last_failure_time > self.timeout:
                    self.state = 'HALF_OPEN'
                else:
                    logger.info("Circuit breaker OPEN, using fallback")
                    return fallback_func(*args, **kwargs)
        
        try:
            result = cache_func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                with self._lock:
                    self.state = 'CLOSED'
                    self.failure_count = 0
                    logger.info("Circuit breaker reset to CLOSED")
            return result
        except Exception as e:
            with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = 'OPEN'
                    logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            
            logger.warning(f"Cache operation failed, using fallback: {e}")
            return fallback_func(*args, **kwargs)


class TaggedCacheService:
    """Cache service with tag-based invalidation"""
    
    def __init__(self, cache_alias: str = 'default'):
        self.cache = caches[cache_alias]
        self.tag_index_key = "cache_tags_index"
    
    def set_with_tags(self, key: str, value: Any, timeout: int, tags: List[str]) -> None:
        """Set cache value with associated tags"""
        try:
            self.cache.set(key, value, timeout)
            
            # Update tag index
            for tag in tags:
                tag_key = f"tag:{tag}"
                tagged_keys = self.cache.get(tag_key, set())
                if not isinstance(tagged_keys, set):
                    tagged_keys = set()
                tagged_keys.add(key)
                self.cache.set(tag_key, tagged_keys, timeout * 2)  # Tags live longer
        except Exception as e:
            logger.error(f"Failed to set tagged cache entry {key}: {e}")
    
    def invalidate_tag(self, tag: str) -> None:
        """Invalidate all cache entries with specific tag"""
        try:
            tag_key = f"tag:{tag}"
            tagged_keys = self.cache.get(tag_key, set())
            
            if tagged_keys and isinstance(tagged_keys, set):
                keys_to_delete = list(tagged_keys)
                if keys_to_delete:
                    self.cache.delete_many(keys_to_delete)
                    logger.info(f"Invalidated {len(keys_to_delete)} cache entries for tag: {tag}")
                self.cache.delete(tag_key)
        except Exception as e:
            logger.error(f"Failed to invalidate tag {tag}: {e}")


class CompressedCache:
    """Cache with automatic compression for large objects"""
    
    def __init__(self, cache_alias: str = 'default', compression_threshold: int = 1024):
        self.cache = caches[cache_alias]
        self.threshold = compression_threshold
    
    def set(self, key: str, value: Any, timeout: int) -> None:
        """Set with automatic compression"""
        try:
            serialized = pickle.dumps(value)
            
            if len(serialized) > self.threshold:
                # Compress large objects
                compressed = gzip.compress(serialized)
                compressed_key = f"compressed:{key}"
                self.cache.set(compressed_key, compressed, timeout)
                logger.debug(f"Compressed cache entry {key}: {len(serialized)} -> {len(compressed)} bytes")
            else:
                self.cache.set(key, value, timeout)
        except Exception as e:
            logger.error(f"Failed to set compressed cache entry {key}: {e}")
    
    def get(self, key: str) -> Any:
        """Get with automatic decompression"""
        try:
            # Try compressed first
            compressed_key = f"compressed:{key}"
            compressed_data = self.cache.get(compressed_key)
            if compressed_data:
                decompressed = gzip.decompress(compressed_data)
                return pickle.loads(decompressed)
            
            return self.cache.get(key)
        except Exception as e:
            logger.error(f"Failed to get compressed cache entry {key}: {e}")
            return None


# Cache stampede prevention
_cache_locks = {}
_lock_mutex = threading.Lock()

def cache_with_lock(timeout: int = 300, lock_timeout: int = 30, cache_alias: str = 'default'):
    """Decorator that prevents cache stampede using distributed locks"""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            cache_key = CacheKeyManager.get_query_cache_key(func.__name__, *args, **kwargs)
            cache_backend = caches[cache_alias]
            
            # Try to get from cache first
            try:
                result = cache_backend.get(cache_key)
                if result is not None:
                    return result
            except Exception as e:
                logger.warning(f"Cache get failed for {cache_key}: {e}")
            
            # Try to acquire lock
            lock_key = f"lock:{cache_key}"
            try:
                lock_acquired = cache_backend.add(lock_key, "locked", lock_timeout)
                
                if lock_acquired:
                    try:
                        # We got the lock, compute the value
                        result = func(*args, **kwargs)
                        try:
                            cache_backend.set(cache_key, result, timeout)
                        except Exception as e:
                            logger.warning(f"Cache set failed for {cache_key}: {e}")
                        return result
                    finally:
                        try:
                            cache_backend.delete(lock_key)
                        except Exception:
                            pass  # Lock cleanup is best effort
                else:
                    # Another process is computing, wait briefly and try cache again
                    time.sleep(0.1)
                    try:
                        result = cache_backend.get(cache_key)
                        if result is not None:
                            return result
                    except Exception:
                        pass
                    
                    # If still not available, compute anyway (fallback)
                    return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Lock operation failed for {cache_key}: {e}")
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def cache_query(timeout: int = 300, cache_alias: str = 'query_cache', tags: Optional[List[str]] = None):
    """Decorator for caching expensive database queries with tag support"""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            cache_key = CacheKeyManager.get_query_cache_key(func.__name__, *args, **kwargs)
            
            try:
                if tags:
                    tagged_cache = TaggedCacheService(cache_alias)
                    result = caches[cache_alias].get(cache_key)
                    if result is not None:
                        return result
                    
                    result = func(*args, **kwargs)
                    tagged_cache.set_with_tags(cache_key, result, timeout, tags)
                    return result
                else:
                    cache_backend = caches[cache_alias]
                    result = cache_backend.get(cache_key)
                    if result is not None:
                        return result
                    
                    result = func(*args, **kwargs)
                    cache_backend.set(cache_key, result, timeout)
                    return result
            except Exception as e:
                logger.error(f"Cache operation failed for {func.__name__}: {e}")
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def cache_for_anonymous(timeout: int = 300):
    """Cache view only for anonymous users"""
    def decorator(view_func: Callable) -> Callable:
        def wrapper(request, *args, **kwargs) -> Any:
            if request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            
            cache_key = CacheKeyManager.get_view_cache_key(
                view_func.__name__, 
                path=request.path,
                query=str(request.GET)
            )
            
            try:
                response = cache.get(cache_key)
                if response is not None:
                    return response
                
                response = view_func(request, *args, **kwargs)
                cache.set(cache_key, response, timeout)
                return response
            except Exception as e:
                logger.error(f"View cache failed for {view_func.__name__}: {e}")
                return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def invalidate_cache_pattern(pattern: str, cache_alias: str = 'default') -> None:
    """Invalidate cache keys matching a pattern using Redis pattern matching"""
    try:
        # For django-redis, use direct Redis connection
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection(cache_alias)
        keys = redis_conn.keys(pattern)
        if keys:
            redis_conn.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache keys for pattern: {pattern}")
        else:
            logger.info(f"No keys found for pattern: {pattern}")
    except ImportError:
        logger.warning("django-redis not available for pattern invalidation")
    except Exception as e:
        logger.error(f"Failed to invalidate cache pattern {pattern}: {e}")


# Global circuit breaker instance
cache_circuit_breaker = CacheCircuitBreaker()

# Global tagged cache service
tagged_cache = TaggedCacheService()

# Global compressed cache service
compressed_cache = CompressedCache() 