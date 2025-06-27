import '../css/tailwind.css';
import '../sass/project.scss';

// Import Alpine.js for reactive state management (useful globally)
import Alpine from 'alpinejs';
import wsClient from './ws';

/* Project specific Javascript goes here. */

// Initialize Alpine.js globally - it's lightweight and enhances all pages
window.Alpine = Alpine;
Alpine.start();

// Global SimLane namespace for shared utilities
window.SimLane = {
    // Utility functions
    utils: {
        formatDuration: (hours) => {
            if (hours < 1) {
                const minutes = Math.round(hours * 60);
                return `${minutes}m`;
            } else if (hours < 24) {
                return `${hours.toFixed(1)}h`;
            } else {
                const days = Math.floor(hours / 24);
                const remainingHours = hours % 24;
                return `${days}d ${remainingHours.toFixed(1)}h`;
            }
        },
        
        formatTimezone: (timezoneStr) => {
            try {
                const now = new Date();
                const offset = now.toLocaleString('en', {timeZone: timezoneStr, timeZoneName: 'short'}).split(' ').pop();
                return `${timezoneStr} (${offset})`;
            } catch {
                return timezoneStr;
            }
        },
        
        debounce: (func, wait) => {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }
    }
};

window.wsClient = wsClient;

if (wsClient) {
  wsClient.on('sync_status', (data) => {
    if (data.status === 'done' && data.profile_id) {
      const statusEl = document.getElementById('refresh-status');
      if (statusEl) {
        statusEl.innerHTML = '<span class="inline-flex items-center text-sm text-green-600">' +
          '<svg class="h-4 w-4 mr-2 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
          '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />' +
          '</svg>Refreshed!</span>';
      }
    }
  });
}

// Global HTMX skeleton delay functionality
document.addEventListener('DOMContentLoaded', function() {
    // Strip empty parameters before HTMX sends the request
    document.body.addEventListener('htmx:configRequest', function(evt) {
        const params = evt.detail.parameters;
        if (params) {
            Object.keys(params).forEach((key) => {
                if (params[key] === '' || params[key] == null) {
                    delete params[key];
                }
            });
        }
    });

    // Add 150ms delay to skeleton loaders to prevent flicker on fast responses
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        const indicator = evt.detail.elt.querySelector('[data-loading-states]');
        if (indicator) {
            // Store original display style
            indicator._originalDisplay = indicator.style.display;
            
            // Hide initially
            indicator.style.display = 'none';
            
            // Show after delay
            indicator._showTimeout = setTimeout(() => {
                indicator.style.display = indicator._originalDisplay || '';
            }, 150);
        }
    });
    
    document.body.addEventListener('htmx:afterRequest', function(evt) {
        const indicator = evt.detail.elt.querySelector('[data-loading-states]');
        if (indicator && indicator._showTimeout) {
            // Clear timeout if request completes before delay
            clearTimeout(indicator._showTimeout);
            // Hide the indicator
            indicator.style.display = 'none';
        }
    });
});
