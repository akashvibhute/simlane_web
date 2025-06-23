/**
 * Event Signup Bundle
 * Only loaded on event signup pages
 * Includes FullCalendar and availability components
 */

// Only import what we need for signup pages
import { AvailabilityCalendar } from './components/availability-calendar.js';

// Dynamic import FullCalendar when needed (code splitting)
async function loadFullCalendar() {
    try {
        const [
            { Calendar },
            interactionPlugin,
            dayGridPlugin,
            timeGridPlugin
        ] = await Promise.all([
            import('@fullcalendar/core'),
            import('@fullcalendar/interaction'),
            import('@fullcalendar/daygrid'),
            import('@fullcalendar/timegrid')
        ]);
        
        // Make FullCalendar available globally for our component
        window.FullCalendar = {
            Calendar,
            plugins: {
                interaction: interactionPlugin,
                dayGrid: dayGridPlugin,
                timeGrid: timeGridPlugin
            }
        };
        
        return true;
    } catch (error) {
        console.warn('FullCalendar not available:', error);
        return false;
    }
}

// Component initialization for signup pages
window.SimLane = window.SimLane || {};

window.SimLane.initializeAvailabilityCalendar = async (containerId, options = {}) => {
    // Load FullCalendar if needed
    if (!window.FullCalendar) {
        await loadFullCalendar();
    }
    
    const instance = new AvailabilityCalendar(containerId, options);
    window.availabilityCalendar = instance;
    return instance;
};

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', async function() {
    const calendars = document.querySelectorAll('[data-component="availability-calendar"]');
    
    if (calendars.length > 0) {
        // Load FullCalendar only if we have calendars
        await loadFullCalendar();
        
        calendars.forEach(element => {
            const options = {
                userTimezone: element.dataset.userTimezone || 'UTC',
                eventStartDate: element.dataset.eventStart,
                eventEndDate: element.dataset.eventEnd,
                existingWindows: JSON.parse(element.dataset.existingWindows || '[]')
            };
            
            SimLane.initializeAvailabilityCalendar(element.id, options);
        });
    }
});

// HTMX integration for signup pages
document.addEventListener('htmx:afterSwap', async function(event) {
    const swappedContent = event.detail.elt;
    const calendars = swappedContent.querySelectorAll('[data-component="availability-calendar"]');
    
    if (calendars.length > 0) {
        await loadFullCalendar();
        
        calendars.forEach(element => {
            const options = {
                userTimezone: element.dataset.userTimezone || 'UTC',
                eventStartDate: element.dataset.eventStart,
                eventEndDate: element.dataset.eventEnd,
                existingWindows: JSON.parse(element.dataset.existingWindows || '[]')
            };
            
            SimLane.initializeAvailabilityCalendar(element.id, options);
        });
    }
}); 