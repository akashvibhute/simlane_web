/**
 * Team Formation Bundle
 * Only loaded on team formation/management pages
 * Includes D3.js visualizations and dashboard components
 */

// Only import what we need for team formation
import { TeamFormationDashboard } from './components/team-formation.js';

// Dynamic import D3 modules when needed (code splitting)
async function loadD3Visualization() {
    try {
        // Only import the D3 modules we actually use
        const d3 = await import('d3');

        // Make D3 available for our components
        window.d3 = d3;
        return true;
    } catch (error) {
        console.warn('D3.js not available:', error);
        return false;
    }
}

// Component initialization for team formation pages
window.SimLane = window.SimLane || {};

window.SimLane.initializeTeamFormationDashboard = async (containerId, options = {}) => {
    // Load D3 if needed for visualizations
    if (!window.d3) {
        await loadD3Visualization();
    }

    const instance = new TeamFormationDashboard(containerId, options);
    window.teamFormationDashboard = instance;
    return instance;
};

// Auto-initialize on DOM ready
document.addEventListener('DOMContentLoaded', async function() {
    const dashboards = document.querySelectorAll('[data-component="team-formation"]');

    if (dashboards.length > 0) {
        // Load D3 only if we have dashboards
        await loadD3Visualization();

        dashboards.forEach(element => {
            const options = {
                eventId: element.dataset.eventId,
                teamSize: parseInt(element.dataset.teamSize) || 3,
                maxTeams: element.dataset.maxTeams ? parseInt(element.dataset.maxTeams) : null,
                timezone: element.dataset.timezone || 'UTC'
            };

            SimLane.initializeTeamFormationDashboard(element.id, options);
        });
    }
});

// HTMX integration for team formation pages
document.addEventListener('htmx:afterSwap', async function(event) {
    const swappedContent = event.detail.elt;
    const dashboards = swappedContent.querySelectorAll('[data-component="team-formation"]');

    if (dashboards.length > 0) {
        await loadD3Visualization();

        dashboards.forEach(element => {
            const options = {
                eventId: element.dataset.eventId,
                teamSize: parseInt(element.dataset.teamSize) || 3,
                maxTeams: element.dataset.maxTeams ? parseInt(element.dataset.maxTeams) : null,
                timezone: element.dataset.timezone || 'UTC'
            };

            SimLane.initializeTeamFormationDashboard(element.id, options);
        });
    }
});

// Heatmap visualization helper
window.SimLane.createHeatmap = async function(containerId, data, options = {}) {
    if (!window.d3) {
        await loadD3Visualization();
    }

    if (!window.d3) {
        console.error('D3.js required for heatmap visualization');
        return;
    }

    const { select, scaleLinear, scaleOrdinal, axisBottom, axisLeft } = window.d3;

    // D3 heatmap implementation
    const container = document.getElementById(containerId);
    const width = options.width || container.offsetWidth;
    const height = options.height || 400;
    const margin = { top: 50, right: 50, bottom: 100, left: 100 };

    // Clear existing content
    select(container).selectAll('*').remove();

    const svg = select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    // Create heatmap visualization
    // ... D3 implementation details ...

    return svg.node();
};
