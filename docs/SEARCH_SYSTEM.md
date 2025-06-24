# SimLane Search System Documentation

## Overview

SimLane's search system provides fast, comprehensive search across all platform content including users, sim profiles, events, teams, clubs, simulators, tracks, and cars. The system is built with a modular architecture that supports easy migration between different search backends.

## Features

- **Universal Search**: Search across all content types in a single query
- **Live Search**: Real-time search results as you type with HTMX
- **Faceted Search**: Filter results by type, simulator, and other criteria
- **Keyboard Shortcuts**: Quick access with Cmd+K / Ctrl+K
- **Mobile Responsive**: Optimized for all screen sizes
- **Backend Agnostic**: Easy migration between PostgreSQL, Meilisearch, and Elasticsearch

## Architecture

### Service Layer Pattern

The search system uses an abstract service layer that allows easy switching between search backends:

```python
# Abstract interface
class SearchService(ABC):
    def search(query, filters, limit, offset) -> SearchResults
    def search_by_type(query, model_type, limit) -> List[SearchResult]
    def get_suggestions(query, limit) -> List[str]

# Current implementation
class PostgresSearchService(SearchService):
    # PostgreSQL full-text search implementation

# Future implementations
class MeilisearchService(SearchService):
    # Meilisearch implementation
```

### Search Document Format

All search results use a standardized format:

```python
@dataclass
class SearchResult:
    id: str                    # Unique identifier (e.g., "user_123")
    type: str                  # Content type (user, event, team, etc.)
    title: str                 # Display title
    description: str           # Brief description
    url: str                   # Direct link to content
    image_url: Optional[str]   # Optional image/avatar
    metadata: Dict[str, Any]   # Type-specific metadata
    relevance_score: float     # Search relevance score
```

## API Endpoints

### Universal Search API

**Endpoint**: `GET /api/search/`

**Parameters**:
- `q` (required): Search query string
- `types` (optional): Comma-separated list of content types to search
- `simulator` (optional): Filter by simulator slug
- `limit` (optional): Number of results (default: 20, max: 100)
- `offset` (optional): Pagination offset (default: 0)

**Example Request**:
```bash
GET /api/search/?q=john&types=user,sim_profile&limit=10
```

**Example Response**:
```json
{
  "results": [
    {
      "id": "user_123",
      "type": "user",
      "title": "John Doe",
      "description": "SimLane member since 2023",
      "url": "/users/johndoe/",
      "image_url": null,
      "metadata": {
        "username": "johndoe",
        "profile_count": 3
      },
      "relevance_score": 0.95
    }
  ],
  "total_count": 1,
  "facets": {
    "types": {"user": 1},
    "simulators": {"iRacing": 1}
  },
  "query_time_ms": 12.5,
  "pagination": {
    "limit": 10,
    "offset": 0,
    "has_more": false
  }
}
```

### Search Suggestions API

**Endpoint**: `GET /api/search/suggestions/`

**Parameters**:
- `q` (required): Partial search query
- `limit` (optional): Number of suggestions (default: 5, max: 10)

**Example Request**:
```bash
GET /api/search/suggestions/?q=joh&limit=5
```

**Example Response**:
```json
{
  "suggestions": ["john", "johnny", "johnson"]
}
```

### Full Search Page

**Endpoint**: `GET /search/`

**Parameters**:
- `q` (optional): Search query
- `types` (optional): Content type filters
- `page` (optional): Page number for pagination

Renders the full search page with filters, pagination, and results.

### HTMX Live Search

**Endpoint**: `GET /search/htmx/`

**Parameters**:
- `q` (required): Search query
- `types` (optional): Content type filters

Returns HTML partial for live search dropdown results.

## Usage Examples

### Frontend JavaScript

```javascript
// Search with fetch API
async function performSearch(query, types = []) {
    const params = new URLSearchParams({
        q: query,
        limit: 20
    });
    
    if (types.length > 0) {
        params.append('types', types.join(','));
    }
    
    const response = await fetch(`/api/search/?${params}`);
    const data = await response.json();
    return data;
}

// Use search results
const results = await performSearch('racing event', ['event', 'team']);
console.log(`Found ${results.total_count} results in ${results.query_time_ms}ms`);
```

### Django Views

```python
from simlane.core.search import get_search_service, SearchFilters

def my_search_view(request):
    query = request.GET.get('q', '')
    
    # Create filters
    filters = SearchFilters()
    filters.types = ['event', 'team']
    filters.simulator = 'iracing'
    
    # Perform search
    search_service = get_search_service()
    results = search_service.search(query, filters, limit=10)
    
    return JsonResponse({
        'results': [result.__dict__ for result in results['results']],
        'total': results['total_count']
    })
```

### Management Commands

```bash
# Test search functionality
just manage test_search "racing" --types=user,event --limit=10

# Test specific content type
just manage test_search "john" --types=user --limit=5
```

## Configuration

### Settings

Add to your Django settings:

```python
# Search backend configuration
SEARCH_BACKEND = "postgres"  # Options: postgres, meilisearch, elasticsearch
```

### Environment Variables

```bash
# Optional: Override search backend
SEARCH_BACKEND=postgres
```

## Searchable Content Types

### Users
- **Fields**: username, name, email
- **Filters**: Authenticated users only
- **Metadata**: profile_count, is_staff, date_joined

### Sim Profiles
- **Fields**: profile_name, linked_user username/name
- **Filters**: Public profiles only
- **Metadata**: simulator, verification status, last_active

### Events
- **Fields**: name, description, track name
- **Filters**: Non-draft events only
- **Metadata**: simulator, status, event_date, organizer

### Teams
- **Fields**: name, description
- **Filters**: Public and active teams only
- **Metadata**: club, member_count, source_simulator

### Clubs
- **Fields**: name, description
- **Filters**: Active clubs only
- **Metadata**: member_count, website, visibility

### Simulators
- **Fields**: name, description
- **Filters**: Active simulators only
- **Metadata**: car_count, track_count, profile_count

### Tracks
- **Fields**: name, location, country
- **Filters**: None
- **Metadata**: coordinates, simulator_count

### Cars
- **Fields**: name, manufacturer, car_class
- **Filters**: None
- **Metadata**: release_year, simulator_count

## UI Components

### Navbar Search Component

The global search component is integrated into the navbar:

**Features**:
- Live search with 300ms debounce
- Keyboard shortcut (Cmd+K / Ctrl+K)
- Dropdown results with icons
- Mobile responsive design

**Usage**:
```django
{% include 'components/search_component.html' %}
```

### Search Results Page

Full-featured search page with:
- Advanced filtering options
- Pagination
- Result type indicators
- Performance metrics
- Faceted navigation

**URL**: `/search/?q=your+query`

## Backend Migration Strategy

### Current: PostgreSQL Full-Text Search

**Pros**:
- No additional infrastructure
- Automatic consistency with Django ORM
- Good performance for small to medium datasets
- Built-in relevance scoring

**Cons**:
- Limited advanced features
- Performance degrades with very large datasets
- Basic typo tolerance

### Future: External Search Services

#### Meilisearch Migration

```python
# 1. Add Meilisearch service
class MeilisearchService(SearchService):
    def __init__(self):
        self.client = meilisearch.Client('http://meilisearch:7700')
    
    def search(self, query, filters, limit, offset):
        # Meilisearch implementation
        pass

# 2. Update settings
SEARCH_BACKEND = "meilisearch"

# 3. Initial data sync
just manage reindex_search
```

#### Elasticsearch Migration

```python
# Similar pattern for Elasticsearch
SEARCH_BACKEND = "elasticsearch"
```

## Performance Considerations

### PostgreSQL Optimization

```sql
-- Create GIN indexes for better full-text search performance
CREATE INDEX CONCURRENTLY idx_users_search ON users_user 
USING gin(to_tsvector('english', username || ' ' || name));

CREATE INDEX CONCURRENTLY idx_events_search ON sim_event 
USING gin(to_tsvector('english', name || ' ' || description));
```

### Caching Strategy

```python
# Add Redis caching for frequent searches
from django.core.cache import cache

def cached_search(query, filters, limit=20):
    cache_key = f"search:{hash(query)}:{hash(str(filters))}:{limit}"
    results = cache.get(cache_key)
    
    if results is None:
        search_service = get_search_service()
        results = search_service.search(query, filters, limit)
        cache.set(cache_key, results, timeout=300)  # 5 minutes
    
    return results
```

## Testing

### Unit Tests

```python
# Test search service
from simlane.core.search import get_search_service

def test_search_users():
    search_service = get_search_service()
    results = search_service.search("john", limit=10)
    
    assert results['total_count'] >= 0
    assert 'results' in results
    assert 'facets' in results

def test_search_filters():
    filters = SearchFilters()
    filters.types = ['user']
    
    search_service = get_search_service()
    results = search_service.search("test", filters)
    
    # All results should be users
    for result in results['results']:
        assert result.type == 'user'
```

### API Tests

```python
# Test search endpoints
def test_search_api():
    response = client.get('/api/search/?q=test&limit=5')
    
    assert response.status_code == 200
    data = response.json()
    assert 'results' in data
    assert len(data['results']) <= 5

def test_search_suggestions():
    response = client.get('/api/search/suggestions/?q=te')
    
    assert response.status_code == 200
    data = response.json()
    assert 'suggestions' in data
```

### Management Command Testing

```bash
# Test search with various queries
just manage test_search "test" --types=user --limit=5
just manage test_search "racing" --types=event,team --limit=10
just manage test_search "spa" --types=track --limit=3
```

## Monitoring & Analytics

### Performance Metrics

Monitor these key metrics:

- **Query Response Time**: Target < 100ms for most queries
- **Search Volume**: Track popular queries and trends
- **Result Click-Through Rate**: Measure search effectiveness
- **Empty Result Rate**: Identify search gaps

### Logging

```python
import logging

logger = logging.getLogger('simlane.search')

# Log slow queries
if query_time_ms > 500:
    logger.warning(f"Slow search query: '{query}' took {query_time_ms}ms")

# Log popular searches
logger.info(f"Search query: '{query}' returned {total_count} results")
```

### Django Admin Integration

```python
# admin.py
from django.contrib import admin
from django.http import JsonResponse

@admin.register(SearchAnalytics)
class SearchAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['query', 'result_count', 'response_time', 'created_at']
    list_filter = ['created_at', 'result_count']
    search_fields = ['query']
```

## Troubleshooting

### Common Issues

#### No Search Results

1. **Check Index Status**:
   ```bash
   # Verify PostgreSQL indexes exist
   just manage dbshell
   \d+ users_user  # Check for GIN indexes
   ```

2. **Verify Model Visibility**:
   ```python
   # Check if content is being filtered out
   from simlane.core.search import get_search_service
   service = get_search_service()
   service.search_by_type("test", "user", limit=100)
   ```

#### Slow Search Performance

1. **Add Database Indexes**:
   ```sql
   CREATE INDEX CONCURRENTLY idx_search_field ON table_name 
   USING gin(to_tsvector('english', search_field));
   ```

2. **Enable Query Caching**:
   ```python
   # Add caching layer for frequent queries
   CACHES = {
       'default': {
           'BACKEND': 'django_redis.cache.RedisCache',
           'LOCATION': 'redis://redis:6379/1',
       }
   }
   ```

#### HTMX Search Not Working

1. **Check HTMX Headers**:
   ```javascript
   // Verify HTMX is loaded
   console.log(typeof htmx);  // Should not be 'undefined'
   ```

2. **Verify URL Configuration**:
   ```python
   # Check URLs are properly configured
   python manage.py show_urls | grep search
   ```

#### Keyboard Shortcuts Not Working

1. **Check Alpine.js**:
   ```javascript
   // Verify Alpine.js is loaded
   console.log(typeof Alpine);
   ```

2. **Verify Event Listeners**:
   ```javascript
   // Check if search input exists
   console.log(document.getElementById('global-search'));
   ```

### Debug Mode

Enable debug logging for search operations:

```python
# settings/local.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'simlane.core.search': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## Future Enhancements

### Planned Features

1. **Advanced Search Operators**
   - Boolean operators (AND, OR, NOT)
   - Quoted phrases
   - Field-specific searches

2. **Search Analytics Dashboard**
   - Popular queries
   - Search performance metrics
   - User search behavior

3. **Machine Learning Integration**
   - Query suggestion improvements
   - Personalized search results
   - Auto-correction

4. **Advanced Filtering**
   - Date range filters
   - Geographic filters for tracks
   - Rating-based filters

### External Service Integration

1. **Meilisearch Setup**:
   ```yaml
   # docker-compose.yml
   meilisearch:
     image: getmeili/meilisearch:latest
     ports:
       - "7700:7700"
     environment:
       - MEILI_ENV=development
   ```

2. **Elasticsearch Setup**:
   ```yaml
   # docker-compose.yml
   elasticsearch:
     image: docker.elastic.co/elasticsearch/elasticsearch:8.0.0
     environment:
       - discovery.type=single-node
       - xpack.security.enabled=false
   ```

## Contributing

### Adding New Searchable Models

1. **Update SearchDocumentBuilder**:
   ```python
   @staticmethod
   def _build_newmodel_document(instance) -> SearchResult:
       return SearchResult(
           id=f"newmodel_{instance.pk}",
           type="newmodel",
           title=instance.name,
           description=instance.description,
           url=f"/newmodel/{instance.slug}/",
           metadata={
               'category': instance.category,
               'created': instance.created_at.isoformat()
           }
       )
   ```

2. **Add to Searchable Models**:
   ```python
   def _get_searchable_models(self):
       return {
           # ... existing models
           'newmodel': apps.get_model('myapp', 'NewModel'),
       }
   ```

3. **Define Search Configuration**:
   ```python
   def _get_search_config(self, model_type: str):
       configs = {
           # ... existing configs
           'newmodel': {
               'fields': ['name', 'description', 'category']
           },
       }
   ```

### Adding New Search Backends

1. **Implement SearchService**:
   ```python
   class NewBackendService(SearchService):
       def search(self, query, filters, limit, offset):
           # Implementation specific to new backend
           pass
   ```

2. **Update Service Factory**:
   ```python
   def get_search_service():
       backend = getattr(settings, 'SEARCH_BACKEND', 'postgres')
       
       if backend == 'new_backend':
           return NewBackendService()
   ```

## Support

For questions or issues with the search system:

1. Check this documentation first
2. Review the troubleshooting section
3. Test with the management command: `just manage test_search "query"`
4. Check the application logs for error details
5. Create an issue with reproduction steps if the problem persists

---

*Last updated: 2024 - SimLane Search System v1.0* 