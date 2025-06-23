/**
 * Availability Calendar ES6 Module
 * Integrates with FullCalendar for availability input
 */

export class AvailabilityCalendar {
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
        this.isFullCalendarLoaded = false;
        
        this.init();
    }

    async init() {
        if (!this.container) {
            console.error('Availability calendar container not found:', this.containerId);
            return;
        }

        // Load FullCalendar dynamically when needed
        await this.loadFullCalendar();
        this.initializeCalendar();
        this.createControlPanel();
    }

    async loadFullCalendar() {
        try {
            // Dynamic import for FullCalendar (will be loaded when npm install works)
            // For now, we'll use a placeholder that can be replaced
            if (typeof window.FullCalendar !== 'undefined') {
                this.isFullCalendarLoaded = true;
            } else {
                // Fallback to basic HTML interface
                console.warn('FullCalendar not loaded, using basic interface');
                this.createBasicInterface();
            }
        } catch (error) {
            console.warn('FullCalendar not available, using basic interface:', error);
            this.createBasicInterface();
        }
    }

    initializeCalendar() {
        if (!this.isFullCalendarLoaded) return;

        const calendarEl = document.createElement('div');
        calendarEl.id = `${this.containerId}-calendar`;
        calendarEl.className = 'availability-calendar-container';
        this.container.appendChild(calendarEl);

        // FullCalendar configuration
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
            selectMinDistance: 5,
            slotMinTime: '00:00:00',
            slotMaxTime: '24:00:00',
            allDaySlot: false,
            height: 600,
            
            select: this.handleTimeSelection.bind(this),
            eventClick: this.handleEventClick.bind(this),
            eventChange: this.handleEventChange.bind(this),
            
            eventClassNames: 'availability-window',
            selectConstraint: this.getSelectConstraint(),
            events: this.formatWindowsForCalendar()
        });

        this.calendar.render();
    }

    createBasicInterface() {
        // Fallback interface when FullCalendar isn't available
        const basicInterface = document.createElement('div');
        basicInterface.className = 'availability-basic-interface bg-white border rounded-lg p-6';
        basicInterface.innerHTML = `
            <div class="mb-4">
                <h3 class="text-lg font-semibold mb-2">Availability Input</h3>
                <p class="text-sm text-gray-600 mb-4">
                    Add your availability windows for this event. Click "Add Window" to create time periods when you're available.
                </p>
            </div>
            
            <div id="availability-list" class="space-y-3 mb-4">
                <!-- Existing windows will be listed here -->
            </div>
            
            <button type="button" id="add-window-btn" 
                    class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
                Add Availability Window
            </button>
        `;
        
        this.container.appendChild(basicInterface);
        this.renderBasicWindowList();
        
        // Event listeners
        basicInterface.querySelector('#add-window-btn').addEventListener('click', () => {
            this.showBasicAvailabilityModal();
        });
    }

    renderBasicWindowList() {
        const listContainer = document.getElementById('availability-list');
        if (!listContainer) return;

        listContainer.innerHTML = '';
        
        this.availabilityWindows.forEach((window, index) => {
            const windowEl = document.createElement('div');
            windowEl.className = 'border rounded-lg p-3 bg-gray-50';
            windowEl.innerHTML = `
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="font-medium text-sm">
                            ${this.formatTimeRange(new Date(window.start_time), new Date(window.end_time))}
                        </div>
                        <div class="text-xs text-gray-600 mt-1">
                            ${this.getWindowTitle(window)}
                        </div>
                        ${window.notes ? `<div class="text-xs text-gray-500 mt-1">${window.notes}</div>` : ''}
                    </div>
                    <div class="flex space-x-2">
                        <button type="button" onclick="window.availabilityCalendar.editWindow(${index})"
                                class="text-blue-600 hover:text-blue-800 text-xs px-2 py-1">
                            Edit
                        </button>
                        <button type="button" onclick="window.availabilityCalendar.deleteWindow(${index})"
                                class="text-red-600 hover:text-red-800 text-xs px-2 py-1">
                            Delete
                        </button>
                    </div>
                </div>
            `;
            listContainer.appendChild(windowEl);
        });

        if (this.availabilityWindows.length === 0) {
            listContainer.innerHTML = `
                <div class="text-center text-gray-500 py-8">
                    No availability windows defined yet.<br>
                    Click "Add Availability Window" to get started.
                </div>
            `;
        }
    }

    showBasicAvailabilityModal(existingIndex = null) {
        const isEdit = existingIndex !== null;
        const windowData = isEdit ? this.availabilityWindows[existingIndex] : {};
        
        const modal = this.createAvailabilityModal({
            start: windowData.start_time ? new Date(windowData.start_time) : new Date(),
            end: windowData.end_time ? new Date(windowData.end_time) : new Date(Date.now() + 60 * 60 * 1000),
            canDrive: windowData.can_drive !== false,
            canSpot: windowData.can_spot !== false,
            canStrategize: windowData.can_strategize === true,
            preferenceLevel: windowData.preference_level || 3,
            maxConsecutiveStints: windowData.max_consecutive_stints || 1,
            preferredStintLength: windowData.preferred_stint_length || 60,
            notes: windowData.notes || '',
            isNew: !isEdit,
            existingIndex
        });
        
        document.body.appendChild(modal);
    }

    createAvailabilityModal(data) {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        modal.innerHTML = `
            <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4 max-h-screen overflow-y-auto">
                <h3 class="text-lg font-semibold mb-4">
                    ${data.isNew ? 'Add' : 'Edit'} Availability Window
                </h3>
                
                <form id="availability-form">
                    <div class="space-y-4">
                        <!-- Date & Time -->
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">
                                    Start Date
                                </label>
                                <input type="date" name="start_date" required
                                       value="${data.start.toISOString().split('T')[0]}"
                                       class="w-full rounded-md border-gray-300">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">
                                    Start Time
                                </label>
                                <input type="time" name="start_time" required
                                       value="${data.start.toTimeString().slice(0, 5)}"
                                       class="w-full rounded-md border-gray-300">
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">
                                    End Date
                                </label>
                                <input type="date" name="end_date" required
                                       value="${data.end.toISOString().split('T')[0]}"
                                       class="w-full rounded-md border-gray-300">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">
                                    End Time
                                </label>
                                <input type="time" name="end_time" required
                                       value="${data.end.toTimeString().slice(0, 5)}"
                                       class="w-full rounded-md border-gray-300">
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
                                           ${data.canDrive ? 'checked' : ''} 
                                           class="rounded border-gray-300">
                                    <span class="ml-2">Driver</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="checkbox" name="can_spot" 
                                           ${data.canSpot ? 'checked' : ''} 
                                           class="rounded border-gray-300">
                                    <span class="ml-2">Spotter</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="checkbox" name="can_strategize" 
                                           ${data.canStrategize ? 'checked' : ''} 
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
                                <option value="3" ${data.preferenceLevel === 3 ? 'selected' : ''}>Good</option>
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
                                   value="${data.maxConsecutiveStints}"
                                   class="w-full rounded-md border-gray-300">
                        </div>
                        
                        <!-- Preferred Stint Length -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                Preferred Stint Length (minutes)
                            </label>
                            <input type="number" name="preferred_stint_length" min="15" max="180" step="15"
                                   value="${data.preferredStintLength}"
                                   class="w-full rounded-md border-gray-300">
                        </div>
                        
                        <!-- Notes -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                Notes
                            </label>
                            <textarea name="notes" rows="2" 
                                      class="w-full rounded-md border-gray-300"
                                      placeholder="Any additional notes...">${data.notes}</textarea>
                        </div>
                    </div>
                    
                    <div class="flex justify-end space-x-3 mt-6">
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

    saveAvailabilityWindow(modal, originalData) {
        const form = modal.querySelector('#availability-form');
        const formData = new FormData(form);
        
        // Combine date and time fields
        const startDate = formData.get('start_date');
        const startTime = formData.get('start_time');
        const endDate = formData.get('end_date');
        const endTime = formData.get('end_time');
        
        const startDateTime = new Date(`${startDate}T${startTime}`);
        const endDateTime = new Date(`${endDate}T${endTime}`);
        
        if (startDateTime >= endDateTime) {
            alert('End time must be after start time');
            return;
        }
        
        const windowData = {
            start_time: startDateTime.toISOString(),
            end_time: endDateTime.toISOString(),
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
            this.availabilityWindows.push(windowData);
        } else {
            // Update existing window
            this.availabilityWindows[originalData.existingIndex] = windowData;
        }
        
        this.updateHiddenField();
        this.renderBasicWindowList();
        modal.remove();
    }

    editWindow(index) {
        this.showBasicAvailabilityModal(index);
    }

    deleteWindow(index) {
        if (confirm('Are you sure you want to delete this availability window?')) {
            this.availabilityWindows.splice(index, 1);
            this.updateHiddenField();
            this.renderBasicWindowList();
        }
    }

    // Utility methods
    formatTimeRange(start, end) {
        const options = { 
            weekday: 'short', 
            month: 'short', 
            day: 'numeric', 
            hour: '2-digit', 
            minute: '2-digit'
        };
        
        const startStr = start.toLocaleDateString(undefined, options);
        const endStr = end.toLocaleDateString(undefined, options);
        
        return `${startStr} - ${endStr}`;
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
        const colors = {
            1: '#22c55e', // green-500
            2: '#84cc16', // lime-500
            3: '#eab308', // yellow-500
            4: '#f97316', // orange-500
            5: '#ef4444'  // red-500
        };
        return colors[window.preference_level] || colors[3];
    }

    formatWindowsForCalendar() {
        return this.availabilityWindows.map((window, index) => ({
            id: window.id || `temp-${index}`,
            start: window.start_time,
            end: window.end_time,
            title: this.getWindowTitle(window),
            backgroundColor: this.getWindowColor(window),
            borderColor: this.getWindowColor(window)
        }));
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

    updateHiddenField() {
        const hiddenField = document.getElementById('availability-data');
        if (hiddenField) {
            hiddenField.value = JSON.stringify(this.availabilityWindows);
        }
        
        // Trigger custom event
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
            </div>
        `;
        
        this.container.appendChild(controlPanel);
        
        // Event listeners
        controlPanel.querySelector('#clear-all').addEventListener('click', () => {
            if (confirm('Are you sure you want to clear all availability windows?')) {
                this.clearAllWindows();
            }
        });
        
        // Update counter when windows change
        document.addEventListener('availabilityUpdated', (e) => {
            controlPanel.querySelector('#window-count').textContent = e.detail.windows.length;
        });
    }

    clearAllWindows() {
        this.availabilityWindows = [];
        this.updateHiddenField();
        this.renderBasicWindowList();
    }

    // Public API
    getAvailabilityData() {
        return this.availabilityWindows;
    }

    setAvailabilityData(windows) {
        this.availabilityWindows = windows;
        this.updateHiddenField();
        this.renderBasicWindowList();
    }

    // Handle FullCalendar events (when available)
    handleTimeSelection(selectionInfo) {
        this.showAvailabilityModal(selectionInfo);
    }

    handleEventClick(clickInfo) {
        // Handle calendar event clicks
    }

    handleEventChange(changeInfo) {
        // Handle calendar event changes
    }

    showAvailabilityModal(selectionInfo) {
        // Handle FullCalendar selection
    }
} 