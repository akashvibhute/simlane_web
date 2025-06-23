import '../css/tailwind.css';
import '../sass/project.scss';

// Import Alpine.js for reactive state management (useful globally)
import Alpine from 'alpinejs';

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
