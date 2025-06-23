# JavaScript Bundle Optimization Strategy

## Overview

We've implemented a smart code-splitting strategy to minimize JavaScript bundle sizes and improve page load performance. Instead of loading all libraries on every page, we only load what's needed.

## Bundle Architecture

### 1. **Global Bundle (`project.js`)** - ~15KB gzipped
Loaded on **ALL pages**:
- Alpine.js for reactive UI (~15KB)
- Global utilities and helpers
- Base SimLane namespace

### 2. **Event Signup Bundle (`event-signup.js`)** - ~60KB gzipped
Loaded **ONLY** on event signup pages:
- AvailabilityCalendar component (~5KB)
- FullCalendar (dynamically imported when needed) (~50KB)
- Auto-initialization logic

### 3. **Team Formation Bundle (`team-formation.js`)** - ~75KB gzipped  
Loaded **ONLY** on team management pages:
- TeamFormationDashboard component (~5KB)
- D3.js (dynamically imported when needed) (~70KB)
- Heatmap visualization helpers

## Bundle Size Comparison

### Before Optimization
- **Every page**: ~150KB+ gzipped (Alpine + FullCalendar + D3 + Components)

### After Optimization
- **Most pages**: ~15KB gzipped (Alpine only)
- **Event signup pages**: ~75KB gzipped (Alpine + FullCalendar)
- **Team formation pages**: ~90KB gzipped (Alpine + D3)

**Savings**: Up to 135KB (90%) on pages that don't need calendars or visualizations!

## Implementation Details

### Webpack Configuration
```javascript
// webpack/common.config.js
entry: {
  project: './simlane/static/js/project',          // Global
  'event-signup': './simlane/static/js/event-signup',    // Signup pages
  'team-formation': './simlane/static/js/team-formation', // Team pages
}
```

### Template Usage
```django
{% extends "base.html" %}
{% load webpack_loader %}

{# Only load the bundle needed for this page #}
{% block javascript %}
    {{ block.super }}
    {% render_bundle 'event-signup' 'js' %}
{% endblock %}
```

### Dynamic Imports
Libraries are loaded on-demand using dynamic imports:
```javascript
// Only loads FullCalendar when a calendar component exists
if (document.querySelector('[data-component="availability-calendar"]')) {
    await import('@fullcalendar/core');
}
```

## Production Optimizations

### Code Splitting
The production build automatically splits vendor libraries into separate chunks:
- `vendor.js` - Shared libraries (Alpine.js)
- `fullcalendar.js` - FullCalendar modules
- `d3.js` - D3.js visualization library

### Caching Strategy
Each chunk has a unique hash in the filename, enabling aggressive caching:
- `vendor.[hash].js` - Can be cached for months
- `event-signup.[hash].js` - App-specific code
- Library chunks are only re-downloaded when upgraded

## Usage Guidelines

### When to Use Each Bundle

1. **No extra bundle needed** (use base template):
   - Static pages (about, terms, privacy)
   - Simple list/detail views
   - Basic forms without complex UI

2. **Use `event-signup` bundle**:
   - Event signup forms
   - Any page with availability calendar
   - Time selection interfaces

3. **Use `team-formation` bundle**:
   - Team formation dashboard
   - Availability heatmaps
   - Data visualization pages

### Adding New Features

When adding new JavaScript features, consider:
1. Can it go in the global bundle? (< 5KB, used on many pages)
2. Does it belong in an existing bundle?
3. Should it have its own bundle? (Large library, specific use case)

### Performance Monitoring

Monitor bundle sizes with:
```bash
# Development
npm run build
ls -lah simlane/static/webpack_bundles/js/

# Analyze bundle composition
npm run build -- --analyze
```

## Best Practices

1. **Lazy Load Heavy Libraries**: Use dynamic imports for libraries > 20KB
2. **Component-Based Loading**: Check for component existence before loading
3. **Graceful Fallbacks**: Always provide basic functionality without JavaScript
4. **Monitor Bundle Growth**: Set up CI alerts for bundle size increases > 10%

## Future Optimizations

1. **Preload Critical Chunks**: Use `<link rel="preload">` for known next pages
2. **Service Worker**: Cache common bundles for offline support
3. **Module Federation**: Share modules between micro-frontends
4. **Tree Shaking**: Import only needed D3/FullCalendar modules

## Metrics

Expected improvements:
- **Initial Load**: 90% faster on non-calendar pages
- **Cache Hit Rate**: 95%+ for vendor bundles
- **Time to Interactive**: < 2s on 3G networks
- **Lighthouse Score**: 95+ performance score 