# Public Cars and Tracks Pages - Product Requirements Document

## Overview

This document outlines the requirements for implementing public-facing pages for cars and tracks in the SimLane application. These pages will serve as a central database for racing enthusiasts to explore available cars and tracks across different simulators.

## URL Structure Discussion

### Current State
- The sim module is currently mounted at `/sim/`
- The domain is `simlane.app`

### Recommendation
I agree that the `/sims/iracing` prefix doesn't make sense for a domain called `simlane.app`. Instead, I propose a cleaner structure:

**Option 1 (Recommended): Top-level paths**
- `/cars/` - All cars listing
- `/cars/<car_slug>/` - Car detail page
- `/tracks/` - All tracks listing  
- `/tracks/<track_slug>/` - Track detail page
- `/tracks/<track_slug>/<layout_slug>/` - Layout detail page

**Option 2: Under sim namespace**
- `/sim/cars/` - All cars listing
- `/sim/cars/<car_slug>/` - Car detail page
- `/sim/tracks/` - All tracks listing
- `/sim/tracks/<track_slug>/` - Track detail page
- `/sim/tracks/<track_slug>/<layout_slug>/` - Layout detail page

Given that SimLane is focused on sim racing, Option 1 provides cleaner, more intuitive URLs.

## Cars Pages

### 1. Cars Listing Page (`/cars/`)

**Purpose**: Browse all available cars across simulators

**Features**:
- Grid/list view toggle
- Filtering options:
  - By simulator (checkboxes)
  - By car class
  - By manufacturer
  - By release year range
- Sorting options:
  - Alphabetical (A-Z, Z-A)
  - By release year
  - By number of simulators available in
- Search functionality (car name, manufacturer)
- Pagination or infinite scroll
- Car cards showing:
  - Car image (default_image_url or placeholder)
  - Manufacturer and model name
  - Car class badge
  - Available simulators (icons)
  - Release year (if available)

**Technical Details**:
- Query from `CarModel` model
- Aggregate simulator availability from `SimCar` relationships
- Use Django's ORM aggregation for counts
- Implement caching for performance

### 2. Car Detail Page (`/cars/<car_slug>/`)

**Purpose**: Detailed information about a specific car model

**Features**:
- Hero section with car image
- Car specifications:
  - Full name (manufacturer + model)
  - Car class with description
  - Release year
  - Base specifications (from base_specs JSON field)
- Simulator availability section:
  - List of simulators where this car is available
  - For each simulator:
    - Simulator logo/icon
    - Link to simulator-specific details (if applicable)
    - BOP version information
    - Active/inactive status
- Related cars section (same class or manufacturer)
- Breadcrumb navigation

**Technical Details**:
- Query `CarModel` with prefetch_related on `sim_cars__simulator`
- Handle 404 for non-existent slugs
- SEO-friendly meta tags

## Tracks Pages

### 1. Tracks Listing Page (`/tracks/`)

**Purpose**: Browse all available tracks across simulators

**Features**:
- Grid/list view with map integration (optional)
- Filtering options:
  - By simulator (checkboxes)
  - By country
  - By track type (from layouts)
  - Laser-scanned only option
- Sorting options:
  - Alphabetical (A-Z, Z-A)
  - By country
  - By number of layouts
  - By number of simulators available in
- Search functionality (track name, location)
- Track cards showing:
  - Track image (default_image_url or placeholder)
  - Track name
  - Country flag and location
  - Available simulators (icons)
  - Number of layouts/configurations
  - Laser-scanned badge (if applicable)

**Technical Details**:
- Query from `TrackModel` model
- Aggregate layout counts and simulator availability
- Consider geographic clustering for map view

### 2. Track Detail Page (`/tracks/<track_slug>/`)

**Purpose**: Overview of a track with all its configurations

**Features**:
- Hero section with track image
- Track information:
  - Full name
  - Country and location
  - GPS coordinates (if available)
  - Description
- Layouts dropdown (similar to sim profiles):
  - Default to showing all layouts
  - Dropdown to filter by specific layout
  - Each layout shows:
    - Layout name
    - Track type (Road, Oval, etc.)
    - Length in km
    - Available simulators
- Simulator availability matrix:
  - Shows which simulators have this track
  - For each simulator:
    - Simulator logo/icon
    - Laser-scanned indicator
    - Number of layouts available
    - Link to view layouts in that simulator
- Track map/layout diagrams (if available)
- Weather statistics (if we have data)
- Lap records section (from LapTime model)

**Technical Details**:
- Complex query with multiple prefetch_related
- Layout dropdown using HTMX for dynamic filtering
- Consider caching strategy for performance

### 3. Layout Detail Page (`/tracks/<track_slug>/<layout_slug>/`)

**Purpose**: Detailed information about a specific track configuration

**Features**:
- Layout-specific information:
  - Full layout name
  - Track type
  - Length
  - Layout diagram/image
- Simulator availability for this specific layout:
  - List of simulators offering this layout
  - Pit stop data (if available):
    - Pit lane delta
    - Fuel flow rates
    - Tire change times
- Lap times leaderboard:
  - Best lap times from `LapTime` model
  - Filter by simulator
  - Show driver, time, date, conditions
- Related layouts (other configurations of the same track)
- Back navigation to track detail page

**Technical Details**:
- Query `SimLayout` with track and simulator relationships
- Aggregate lap time data with proper indexing
- Handle cases where layout doesn't exist

## Shared Components

### 1. Simulator Badges
- Reusable component showing simulator icon/logo
- Tooltip with simulator name
- Clickable to filter by that simulator

### 2. Search Component
- Unified search that works across cars and tracks
- Autocomplete suggestions
- Recent searches

### 3. Filter Sidebar
- Responsive design (collapsible on mobile)
- Clear all filters option
- Show active filter count

## Technical Considerations

### Performance
1. Implement database query optimization:
   - Use `select_related` for foreign keys
   - Use `prefetch_related` for reverse relationships
   - Create appropriate database indexes
2. Caching strategy:
   - Cache car/track listings for 1 hour
   - Cache individual detail pages for 24 hours
   - Invalidate on model updates
3. Image optimization:
   - Lazy loading for images
   - Multiple image sizes for responsive design
   - CDN integration for production

### SEO
1. Structured data (JSON-LD) for:
   - Cars (Product schema)
   - Tracks (Place schema)
2. Meta tags:
   - Dynamic title and description
   - Open Graph tags for social sharing
3. Sitemap generation for all pages

### Mobile Responsiveness
1. Touch-friendly filter controls
2. Optimized card layouts for mobile
3. Bottom sheet pattern for filters on mobile

### Accessibility
1. Proper heading hierarchy
2. Alt text for all images
3. Keyboard navigation support
4. ARIA labels for interactive elements

## Implementation Phases

### Phase 1: Basic Pages
1. Create URL patterns
2. Implement basic views and templates
3. Cars listing and detail pages
4. Tracks listing and detail pages

### Phase 2: Enhanced Features
1. Layout detail pages
2. Filtering and sorting
3. Search functionality
4. Performance optimizations

### Phase 3: Polish
1. Mobile optimizations
2. SEO implementation
3. Caching layer
4. Analytics integration

## Future Enhancements
1. User-generated content:
   - Car/track reviews
   - Setup sharing
   - Lap time submissions
2. Comparison tools:
   - Compare cars side-by-side
   - Compare track layouts
3. API endpoints for third-party integration
4. Track weather history integration
5. Virtual track walks (360° images/videos)

## Success Metrics
1. Page load time < 2 seconds
2. Search response time < 500ms
3. Mobile usability score > 90
4. SEO score > 90
5. User engagement metrics:
   - Average time on page
   - Pages per session
   - Bounce rate < 40% 