# iRacing API Client Migration Plan

## Overview
We're replacing the third-party `iracingdataapi` library with our own focused implementation that provides better control over rate limiting, error handling, and caching.

## Benefits of Custom Client

1. **Reduced Dependencies**: Eliminates the `iracingdataapi` dependency
2. **Better Control**: Full control over rate limiting, caching, error handling, and retry logic
3. **Django Integration**: Leverages Django's cache framework, logging, and settings
4. **Focused Functionality**: Only implements the endpoints we actually need
5. **Enhanced Error Handling**: Custom error handling with detailed logging
6. **Performance**: Optimized for our specific use cases

## Migration Steps

### 1. Custom Client Features ✓
- [x] Authentication with session caching
- [x] Rate limiting (1 second between requests)
- [x] Comprehensive error handling with detailed logging
- [x] Automatic retries with exponential backoff
- [x] Django cache integration for data and session caching
- [x] Only endpoints we actually use

### 2. Update Dependencies
- [ ] Remove `iracingdataapi` from requirements files
- [ ] Update imports in services.py
- [ ] Update method calls to match our client's API

### 3. Method Mapping
Our custom client vs old library:

| Old Library Method | Our Custom Client Method |
|--------------------|--------------------------|
| `get_series()` | `get_series()` ✓ |
| `get_series_assets()` | `get_series_assets()` ✓ |
| `series_seasons()` | `get_series_seasons()` ✓ |
| `series_past_seasons()` | `get_series_past_seasons()` ✓ |
| `series_season_schedule()` | `get_series_season_schedule()` ✓ |
| `cars` (property) | `get_cars()` |
| `tracks` (property) | `get_tracks()` |
| `get_carclasses()` | `get_car_classes()` ✓ |
| `member_info()` | `get_member_info()` ✓ |
| `stats_member_summary()` | Not needed yet |
| `stats_member_recent_races()` | Not needed yet |
| `stats_member_yearly()` | Not needed yet |
| `result_search_series()` | Not needed yet |
| Various results methods | Add as needed |

### 4. Error Handling Improvements ✓
- [x] Custom `IRacingAPIError` exception with detailed information
- [x] Structured logging with status codes, endpoints, and response data
- [x] Meaningful error messages based on HTTP status codes
- [x] Proper handling of rate limiting, timeouts, and connection errors

### 5. Testing
- [ ] Test authentication and session caching
- [ ] Test rate limiting and retry logic
- [ ] Test error handling with invalid endpoints
- [ ] Test data caching functionality
- [ ] Verify existing sync tasks work with new client

### 6. Cleanup
- [ ] Remove old `iracing_api_client.py` file
- [ ] Update test files to use new client
- [ ] Remove dependency from requirements

## Key Configuration

The custom client uses these settings:
- `IRACING_USERNAME` and `IRACING_PASSWORD` from Django settings
- Session cache timeout: 24 hours
- Data cache timeout: 5 minutes (configurable per request)
- Rate limiting: 1 second between requests
- Max retries: 3 with exponential backoff
- Request timeout: 30 seconds

## Error Handling Features

1. **Detailed Logging**: Every API error logs:
   - HTTP status code
   - Request endpoint
   - Response headers and data
   - Request URL and method

2. **Meaningful Error Messages**: Based on HTTP status codes:
   - 400: Bad Request with parameter info
   - 401: Authentication issues
   - 403: Access denied
   - 404: Endpoint not found
   - 429: Rate limiting
   - 5xx: Server errors

3. **Automatic Retries**: For:
   - Network timeouts
   - Connection errors
   - Rate limiting (with proper backoff)
   - Authentication expiry

## Migration Status
- [x] Custom client implementation complete
- [x] Error handling and logging enhanced
- [x] Django integration (cache, settings, logging)
- [ ] Update service layer to use new client
- [ ] Remove old dependency
- [ ] Test complete functionality 