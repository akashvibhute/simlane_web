/**
 * Availability Calendar Component
 * Uses FullCalendar for intuitive availability input with timezone support
 */

class AvailabilityCalendar {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.options = {
            userTimezone: 'UTC',
            eventStartDate: null,
            eventEndDate: null,
            existingWindows: [],
            ...options
        };

        this.availabilityWindows = [...this.options.existingWindows];
        this.calendar = null;
        this.init();
    }

    init() {
        if (!this.container) {
            console.error('Availability calendar container not found:', this.containerId);
            return;
        }

        // Create calendar container
        const calendarEl = document.createElement('div');
        calendarEl.id = `${this.containerId}-calendar`;
        this.container.appendChild(calendarEl);

        // Initialize FullCalendar
        this.calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'timeGridWeek',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'timeGridWeek,timeGridDay'
            },
            timeZone: this.options.userTimezone,
            selectable: true,
            selectMirror: true,
            selectMinDistance: 5, // Minimum 5 pixels to create selection
            slotMinTime: '00:00:00',
            slotMaxTime: '24:00:00',
            allDaySlot: false,
            height: 600,

            // Event handlers
            select: this.handleTimeSelection.bind(this),
            eventClick: this.handleEventClick.bind(this),
            eventChange: this.handleEventChange.bind(this),

            // Style customization
            eventClassNames: 'availability-window',
            selectConstraint: this.getSelectConstraint(),

            // Load existing availability windows
            events: this.formatWindowsForCalendar()
        });

        this.calendar.render();
        this.createControlPanel();
    }

    getSelectConstraint() {
        if (this.options.eventStartDate && this.options.eventEndDate) {
            return {
                start: this.options.eventStartDate,
                end: this.options.eventEndDate
            };
        }
        return null;
    }

    formatWindowsForCalendar() {
        return this.availabilityWindows.map((window, index) => ({
            id: window.id || `temp-${index}`,
            start: window.start_time,
            end: window.end_time,
            title: this.getWindowTitle(window),
            backgroundColor: this.getWindowColor(window),
            borderColor: this.getWindowBorderColor(window),
            extendedProps: {
                canDrive: window.can_drive,
                canSpot: window.can_spot,
                canStrategize: window.can_strategize,
                preferenceLevel: window.preference_level,
                maxConsecutiveStints: window.max_consecutive_stints,
                preferredStintLength: window.preferred_stint_length,
                notes: window.notes
            }
        }));
    }

    getWindowTitle(window) {
        const roles = [];
        if (window.can_drive) roles.push('Drive');
        if (window.can_spot) roles.push('Spot');
        if (window.can_strategize) roles.push('Strategy');

        const preference = ['', 'Preferred', 'Good', 'OK', 'Last Resort', 'Emergency'][window.preference_level] || 'OK';
        return `${roles.join('/')} (${preference})`;
    }

    getWindowColor(window) {
        // Color based on preference level (1 = best, 5 = worst)
        const colors = {
            1: '#22c55e', // green-500 - Preferred
            2: '#84cc16', // lime-500 - Good
            3: '#eab308', // yellow-500 - OK
            4: '#f97316', // orange-500 - Last resort
            5: '#ef4444'  // red-500 - Emergency
        };
        return colors[window.preference_level] || colors[3];
    }

    getWindowBorderColor(window) {
        return this.getWindowColor(window);
    }

    handleTimeSelection(selectionInfo) {
        this.showAvailabilityModal(selectionInfo);
    }

    handleEventClick(clickInfo) {
        this.showEditModal(clickInfo.event);
    }

    handleEventChange(changeInfo) {
        // Update the window data when dragged/resized
        const event = changeInfo.event;
        const windowIndex = this.availabilityWindows.findIndex(w =>
            (w.id && w.id == event.id) || (!w.id && event.id.startsWith('temp-'))
        );

        if (windowIndex >= 0) {
            this.availabilityWindows[windowIndex].start_time = event.start.toISOString();
            this.availabilityWindows[windowIndex].end_time = event.end.toISOString();
            this.updateHiddenField();
        }
    }

    showAvailabilityModal(selectionInfo) {
        const modal = this.createAvailabilityModal({
            start: selectionInfo.start,
            end: selectionInfo.end,
            isNew: true
        });

        document.body.appendChild(modal);
        modal.style.display = 'block';
    }

    showEditModal(event) {
        const windowData = {
            start: event.start,
            end: event.end,
            ...event.extendedProps,
            isNew: false,
            eventId: event.id
        };

        const modal = this.createAvailabilityModal(windowData);
        document.body.appendChild(modal);
        modal.style.display = 'block';
    }

    createAvailabilityModal(data) {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        modal.innerHTML = `
            <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                <h3 class="text-lg font-semibold mb-4">
                    ${data.isNew ? 'Add' : 'Edit'} Availability Window
                </h3>

                <form id="availability-form">
                    <div class="space-y-4">
                        <!-- Time Display -->
                        <div class="bg-gray-50 p-3 rounded">
                            <div class="text-sm text-gray-600">Time Period</div>
                            <div class="font-medium">
                                ${this.formatTimeRange(data.start, data.end)}
                            </div>
                        </div>

                        <!-- Roles -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                Available Roles
                            </label>
                            <div class="space-y-2">
                                <label class="flex items-center">
                                    <input type="checkbox" name="can_drive"
                                           ${data.canDrive !== false ? 'checked' : ''}
                                           class="rounded border-gray-300">
                                    <span class="ml-2">Driver</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="checkbox" name="can_spot"
                                           ${data.canSpot !== false ? 'checked' : ''}
                                           class="rounded border-gray-300">
                                    <span class="ml-2">Spotter</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="checkbox" name="can_strategize"
                                           ${data.canStrategize === true ? 'checked' : ''}
                                           class="rounded border-gray-300">
                                    <span class="ml-2">Strategist</span>
                                </label>
                            </div>
                        </div>

                        <!-- Preference Level -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                Preference Level
                            </label>
                            <select name="preference_level" class="w-full rounded-md border-gray-300">
                                <option value="1" ${data.preferenceLevel === 1 ? 'selected' : ''}>Strongly Preferred</option>
                                <option value="2" ${data.preferenceLevel === 2 ? 'selected' : ''}>Preferred</option>
                                <option value="3" ${data.preferenceLevel === 3 || !data.preferenceLevel ? 'selected' : ''}>Good</option>
                                <option value="4" ${data.preferenceLevel === 4 ? 'selected' : ''}>Last Resort</option>
                                <option value="5" ${data.preferenceLevel === 5 ? 'selected' : ''}>Emergency Only</option>
                            </select>
                        </div>

                        <!-- Max Consecutive Stints -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                Max Consecutive Stints
                            </label>
                            <input type="number" name="max_consecutive_stints" min="1" max="10"
                                   value="${data.maxConsecutiveStints || 1}"
                                   class="w-full rounded-md border-gray-300">
                        </div>

                        <!-- Preferred Stint Length -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                Preferred Stint Length (minutes)
                            </label>
                            <input type="number" name="preferred_stint_length" min="15" max="180" step="15"
                                   value="${data.preferredStintLength || 60}"
                                   class="w-full rounded-md border-gray-300">
                        </div>

                        <!-- Notes -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                Notes
                            </label>
                            <textarea name="notes" rows="2"
                                      class="w-full rounded-md border-gray-300"
                                      placeholder="Any additional notes...">${data.notes || ''}</textarea>
                        </div>
                    </div>

                    <div class="flex justify-end space-x-3 mt-6">
                        ${!data.isNew ? `
                            <button type="button" class="px-4 py-2 text-red-600 hover:bg-red-50 rounded-md"
                                    onclick="this.closest('.fixed').remove(); window.availabilityCalendar.deleteWindow('${data.eventId}')">
                                Delete
                            </button>
                        ` : ''}
                        <button type="button" class="px-4 py-2 text-gray-600 hover:bg-gray-50 rounded-md"
                                onclick="this.closest('.fixed').remove()">
                            Cancel
                        </button>
                        <button type="submit" class="px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-md">
                            ${data.isNew ? 'Add' : 'Update'}
                        </button>
                    </div>
                </form>
            </div>
        `;

        // Handle form submission
        modal.querySelector('#availability-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveAvailabilityWindow(modal, data);
        });

        return modal;
    }

    formatTimeRange(start, end) {
        const options = {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            timeZoneName: 'short'
        };

        const startStr = start.toLocaleString(undefined, options);
        const endStr = end.toLocaleString(undefined, options);

        return `${startStr} - ${endStr}`;
    }

    saveAvailabilityWindow(modal, originalData) {
        const form = modal.querySelector('#availability-form');
        const formData = new FormData(form);

        const windowData = {
            start_time: originalData.start.toISOString(),
            end_time: originalData.end.toISOString(),
            can_drive: formData.has('can_drive'),
            can_spot: formData.has('can_spot'),
            can_strategize: formData.has('can_strategize'),
            preference_level: parseInt(formData.get('preference_level')),
            max_consecutive_stints: parseInt(formData.get('max_consecutive_stints')),
            preferred_stint_length: parseInt(formData.get('preferred_stint_length')),
            notes: formData.get('notes')
        };

        if (originalData.isNew) {
            // Add new window
            windowData.id = `temp-${Date.now()}`;
            this.availabilityWindows.push(windowData);

            // Add to calendar
            this.calendar.addEvent({
                id: windowData.id,
                start: windowData.start_time,
                end: windowData.end_time,
                title: this.getWindowTitle(windowData),
                backgroundColor: this.getWindowColor(windowData),
                borderColor: this.getWindowBorderColor(windowData),
                extendedProps: {
                    canDrive: windowData.can_drive,
                    canSpot: windowData.can_spot,
                    canStrategize: windowData.can_strategize,
                    preferenceLevel: windowData.preference_level,
                    maxConsecutiveStints: windowData.max_consecutive_stints,
                    preferredStintLength: windowData.preferred_stint_length,
                    notes: windowData.notes
                }
            });
        } else {
            // Update existing window
            const windowIndex = this.availabilityWindows.findIndex(w =>
                (w.id && w.id == originalData.eventId) || (!w.id && originalData.eventId.startsWith('temp-'))
            );

            if (windowIndex >= 0) {
                this.availabilityWindows[windowIndex] = { ...this.availabilityWindows[windowIndex], ...windowData };

                // Update calendar event
                const event = this.calendar.getEventById(originalData.eventId);
                if (event) {
                    event.setProp('title', this.getWindowTitle(windowData));
                    event.setProp('backgroundColor', this.getWindowColor(windowData));
                    event.setProp('borderColor', this.getWindowBorderColor(windowData));
                    event.setExtendedProp('canDrive', windowData.can_drive);
                    event.setExtendedProp('canSpot', windowData.can_spot);
                    event.setExtendedProp('canStrategize', windowData.can_strategize);
                    event.setExtendedProp('preferenceLevel', windowData.preference_level);
                    event.setExtendedProp('maxConsecutiveStints', windowData.max_consecutive_stints);
                    event.setExtendedProp('preferredStintLength', windowData.preferred_stint_length);
                    event.setExtendedProp('notes', windowData.notes);
                }
            }
        }

        this.updateHiddenField();
        modal.remove();

        // Clear calendar selection
        this.calendar.unselect();
    }

    deleteWindow(eventId) {
        // Remove from data
        this.availabilityWindows = this.availabilityWindows.filter(w =>
            !(w.id && w.id == eventId) && !(eventId.startsWith('temp-') && !w.id)
        );

        // Remove from calendar
        const event = this.calendar.getEventById(eventId);
        if (event) {
            event.remove();
        }

        this.updateHiddenField();
    }

    updateHiddenField() {
        const hiddenField = document.getElementById('availability-data');
        if (hiddenField) {
            hiddenField.value = JSON.stringify(this.availabilityWindows);
        }

        // Trigger custom event for other components to listen
        document.dispatchEvent(new CustomEvent('availabilityUpdated', {
            detail: { windows: this.availabilityWindows }
        }));
    }

    createControlPanel() {
        const controlPanel = document.createElement('div');
        controlPanel.className = 'mt-4 flex items-center justify-between bg-gray-50 p-3 rounded-lg';
        controlPanel.innerHTML = `
            <div class="text-sm text-gray-600">
                <span id="window-count">${this.availabilityWindows.length}</span> availability windows defined
            </div>
            <div class="space-x-2">
                <button type="button" id="clear-all" class="text-sm text-red-600 hover:text-red-800">
                    Clear All
                </button>
                <button type="button" id="preview-coverage" class="text-sm text-blue-600 hover:text-blue-800">
                    Preview Coverage
                </button>
            </div>
        `;

        this.container.appendChild(controlPanel);

        // Event listeners for control panel
        controlPanel.querySelector('#clear-all').addEventListener('click', () => {
            if (confirm('Are you sure you want to clear all availability windows?')) {
                this.clearAllWindows();
            }
        });

        controlPanel.querySelector('#preview-coverage').addEventListener('click', () => {
            this.showCoveragePreview();
        });

        // Update counter when windows change
        document.addEventListener('availabilityUpdated', (e) => {
            controlPanel.querySelector('#window-count').textContent = e.detail.windows.length;
        });
    }

    clearAllWindows() {
        this.availabilityWindows = [];
        this.calendar.removeAllEvents();
        this.updateHiddenField();
    }

    showCoveragePreview() {
        // This could show a simple preview of coverage
        // For now, just log the data
        console.log('Availability Coverage:', {
            totalWindows: this.availabilityWindows.length,
            totalHours: this.availabilityWindows.reduce((sum, w) => {
                const start = new Date(w.start_time);
                const end = new Date(w.end_time);
                return sum + (end - start) / (1000 * 60 * 60);
            }, 0)
        });
    }

    // Public API methods
    getAvailabilityData() {
        return this.availabilityWindows;
    }

    setAvailabilityData(windows) {
        this.availabilityWindows = windows;
        this.calendar.removeAllEvents();
        this.calendar.addEventSource(this.formatWindowsForCalendar());
        this.updateHiddenField();
    }
}

// Global reference for the modal callbacks
window.availabilityCalendar = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const calendarContainer = document.getElementById('availability-input');
    if (calendarContainer) {
        const options = {
            userTimezone: calendarContainer.dataset.userTimezone || 'UTC',
            eventStartDate: calendarContainer.dataset.eventStart,
            eventEndDate: calendarContainer.dataset.eventEnd,
            existingWindows: JSON.parse(calendarContainer.dataset.existingWindows || '[]')
        };

        window.availabilityCalendar = new AvailabilityCalendar('availability-input', options);
    }
});
