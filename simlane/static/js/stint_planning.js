/**
 * Stint Planning Interface JavaScript
 * Handles timeline visualization, stint assignments, pit strategy, and collaborative editing
 */

class StintPlanningInterface {
    constructor() {
        this.eventData = null;
        this.teamData = null;
        this.stintAssignments = new Map();
        this.pitStops = [];
        this.timeline = null;
        this.collaborationWs = null;
        
        this.init();
    }

    init() {
        this.loadEventData();
        this.loadTeamData();
        this.setupTimeline();
        this.setupEventListeners();
        this.setupCollaboration();
        this.setupCalculations();
        this.setupMobileOptimization();
        this.loadExistingPlan();
    }

    loadEventData() {
        const eventDataEl = document.getElementById('event-data');
        if (eventDataEl) {
            try {
                this.eventData = JSON.parse(eventDataEl.textContent);
            } catch (e) {
                console.error('Failed to load event data:', e);
            }
        }
    }

    loadTeamData() {
        const teamDataEl = document.getElementById('team-data');
        if (teamDataEl) {
            try {
                this.teamData = JSON.parse(teamDataEl.textContent);
            } catch (e) {
                console.error('Failed to load team data:', e);
            }
        }
    }

    setupTimeline() {
        const timelineContainer = document.getElementById('stint-timeline');
        if (!timelineContainer || !this.eventData) return;

        const raceLength = this.eventData.duration_minutes;
        const pixelsPerMinute = 4; // Adjustable zoom level
        const timelineWidth = raceLength * pixelsPerMinute;

        // Create timeline SVG
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', timelineWidth);
        svg.setAttribute('height', '300');
        svg.setAttribute('class', 'stint-timeline-svg');

        // Add time markers
        this.addTimeMarkers(svg, raceLength, pixelsPerMinute);
        
        // Add driver lanes
        this.addDriverLanes(svg, pixelsPerMinute);
        
        // Add pit window indicators
        this.addPitWindows(svg, pixelsPerMinute);

        timelineContainer.appendChild(svg);
        this.timeline = { svg, pixelsPerMinute, width: timelineWidth };
    }

    addTimeMarkers(svg, raceLength, pixelsPerMinute) {
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', 'time-markers');

        // Major markers every 30 minutes
        for (let minute = 0; minute <= raceLength; minute += 30) {
            const x = minute * pixelsPerMinute;
            
            // Vertical line
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', x);
            line.setAttribute('y1', 0);
            line.setAttribute('x2', x);
            line.setAttribute('y2', 300);
            line.setAttribute('class', 'time-marker-line');
            g.appendChild(line);
            
            // Time label
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', x);
            text.setAttribute('y', 15);
            text.setAttribute('class', 'time-marker-text');
            text.textContent = this.formatTimeForDisplay(minute);
            g.appendChild(text);
        }

        // Minor markers every 10 minutes
        for (let minute = 10; minute < raceLength; minute += 10) {
            if (minute % 30 !== 0) {
                const x = minute * pixelsPerMinute;
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', x);
                line.setAttribute('y1', 0);
                line.setAttribute('x2', x);
                line.setAttribute('y2', 300);
                line.setAttribute('class', 'time-marker-minor');
                g.appendChild(line);
            }
        }

        svg.appendChild(g);
    }

    addDriverLanes(svg, pixelsPerMinute) {
        if (!this.teamData || !this.teamData.members) return;

        const laneHeight = 40;
        const laneSpacing = 50;
        const startY = 40;

        this.teamData.members.forEach((driver, index) => {
            const y = startY + (index * laneSpacing);
            
            // Driver lane background
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', 0);
            rect.setAttribute('y', y);
            rect.setAttribute('width', this.timeline.width);
            rect.setAttribute('height', laneHeight);
            rect.setAttribute('class', 'driver-lane');
            rect.setAttribute('data-driver-id', driver.id);
            svg.appendChild(rect);
            
            // Driver name label
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', 10);
            text.setAttribute('y', y + 25);
            text.setAttribute('class', 'driver-name-label');
            text.textContent = driver.name;
            svg.appendChild(text);

            // Add availability indicators
            this.addAvailabilityIndicators(svg, driver, y, laneHeight, pixelsPerMinute);
        });
    }

    addAvailabilityIndicators(svg, driver, y, height, pixelsPerMinute) {
        if (!driver.availability) return;

        driver.availability.forEach(period => {
            const startX = period.start_minute * pixelsPerMinute;
            const width = (period.end_minute - period.start_minute) * pixelsPerMinute;
            
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', startX);
            rect.setAttribute('y', y + 2);
            rect.setAttribute('width', width);
            rect.setAttribute('height', height - 4);
            rect.setAttribute('class', period.available ? 'availability-available' : 'availability-unavailable');
            svg.appendChild(rect);
        });
    }

    addPitWindows(svg, pixelsPerMinute) {
        if (!this.eventData.pit_windows) return;

        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', 'pit-windows');

        this.eventData.pit_windows.forEach((window, index) => {
            const startX = window.start_minute * pixelsPerMinute;
            const endX = window.end_minute * pixelsPerMinute;
            const width = endX - startX;
            
            // Pit window background
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', startX);
            rect.setAttribute('y', 0);
            rect.setAttribute('width', width);
            rect.setAttribute('height', 300);
            rect.setAttribute('class', 'pit-window');
            rect.setAttribute('data-window-index', index);
            g.appendChild(rect);
            
            // Pit window label
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', startX + 5);
            text.setAttribute('y', 35);
            text.setAttribute('class', 'pit-window-label');
            text.textContent = `Pit ${index + 1}`;
            g.appendChild(text);
        });

        svg.appendChild(g);
    }

    setupEventListeners() {
        // Timeline interaction
        if (this.timeline) {
            this.timeline.svg.addEventListener('click', this.handleTimelineClick.bind(this));
            this.timeline.svg.addEventListener('mousedown', this.handleTimelineMouseDown.bind(this));
            this.timeline.svg.addEventListener('mousemove', this.handleTimelineMouseMove.bind(this));
            this.timeline.svg.addEventListener('mouseup', this.handleTimelineMouseUp.bind(this));
        }

        // Stint duration inputs
        const stintInputs = document.querySelectorAll('.stint-duration-input');
        stintInputs.forEach(input => {
            input.addEventListener('change', this.handleStintDurationChange.bind(this));
        });

        // Fuel strategy controls
        const fuelControls = document.querySelectorAll('.fuel-strategy-control');
        fuelControls.forEach(control => {
            control.addEventListener('change', this.handleFuelStrategyChange.bind(this));
        });

        // Auto-calculate button
        const autoCalcBtn = document.getElementById('auto-calculate-stints');
        if (autoCalcBtn) {
            autoCalcBtn.addEventListener('click', this.handleAutoCalculate.bind(this));
        }

        // Save plan button
        const savePlanBtn = document.getElementById('save-stint-plan');
        if (savePlanBtn) {
            savePlanBtn.addEventListener('click', this.handleSavePlan.bind(this));
        }

        // Export buttons
        const exportPdfBtn = document.getElementById('export-pdf');
        const exportCalendarBtn = document.getElementById('export-calendar');
        if (exportPdfBtn) exportPdfBtn.addEventListener('click', this.handleExportPdf.bind(this));
        if (exportCalendarBtn) exportCalendarBtn.addEventListener('click', this.handleExportCalendar.bind(this));

        // Real-time calculation updates
        document.addEventListener('input', (e) => {
            if (e.target.matches('.calculation-input')) {
                this.updateCalculations();
            }
        });
    }

    setupCollaboration() {
        // WebSocket connection for real-time updates
        if (this.teamData && this.teamData.collaboration_enabled) {
            this.initializeWebSocket();
        }

        // Version conflict detection
        this.lastSaveTimestamp = Date.now();
        this.conflictResolution = 'merge'; // 'merge', 'overwrite', 'ask'
        
        // Set up collaboration indicators
        this.setupCollaborationIndicators();
        
        // Set up real-time cursor tracking
        this.setupCursorTracking();
        
        // Set up collaborative undo/redo
        this.setupCollaborativeHistory();
        
        // Set up presence indicators
        this.setupPresenceIndicators();
        
        // Set up conflict resolution UI
        this.setupConflictResolution();
    }

    setupCollaborationIndicators() {
        // Create collaboration panel
        const collaborationPanel = document.createElement('div');
        collaborationPanel.id = 'collaboration-panel';
        collaborationPanel.className = 'fixed top-4 right-4 bg-white border border-gray-200 rounded-lg shadow-lg p-4 z-50 max-w-xs';
        collaborationPanel.innerHTML = `
            <div class="flex items-center justify-between mb-3">
                <h4 class="text-sm font-medium text-gray-900">Active Users</h4>
                <div class="flex items-center">
                    <div class="w-2 h-2 bg-green-400 rounded-full animate-pulse mr-2"></div>
                    <span class="text-xs text-gray-500">Live</span>
                </div>
            </div>
            <div id="collaborator-list" class="space-y-2"></div>
            <div class="mt-3 pt-3 border-t border-gray-200">
                <div class="flex items-center text-xs text-gray-500">
                    <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                    </svg>
                    Auto-save enabled
                </div>
            </div>
        `;
        document.body.appendChild(collaborationPanel);
        
        // Initially hide if no collaborators
        collaborationPanel.style.display = 'none';
        this.collaborationPanel = collaborationPanel;
    }

    setupCursorTracking() {
        this.collaboratorCursors = new Map();
        let cursorTimeout;
        
        // Track mouse movement on timeline
        const timeline = document.getElementById('stint-timeline');
        if (timeline) {
            timeline.addEventListener('mousemove', (event) => {
                clearTimeout(cursorTimeout);
                
                const rect = timeline.getBoundingClientRect();
                const x = event.clientX - rect.left;
                const y = event.clientY - rect.top;
                
                // Broadcast cursor position
                if (this.collaborationWs && this.collaborationWs.readyState === WebSocket.OPEN) {
                    this.collaborationWs.send(JSON.stringify({
                        type: 'cursor_move',
                        user_id: this.getCurrentUserId(),
                        x: x,
                        y: y,
                        timestamp: Date.now()
                    }));
                }
                
                // Hide cursor after 2 seconds of inactivity
                cursorTimeout = setTimeout(() => {
                    if (this.collaborationWs && this.collaborationWs.readyState === WebSocket.OPEN) {
                        this.collaborationWs.send(JSON.stringify({
                            type: 'cursor_hide',
                            user_id: this.getCurrentUserId()
                        }));
                    }
                }, 2000);
            });
        }
    }

    setupCollaborativeHistory() {
        this.undoStack = [];
        this.redoStack = [];
        this.maxHistorySize = 50;
        
        // Set up undo/redo buttons
        const undoBtn = document.getElementById('undo-button');
        const redoBtn = document.getElementById('redo-button');
        
        if (undoBtn) {
            undoBtn.addEventListener('click', () => this.performUndo());
        }
        
        if (redoBtn) {
            redoBtn.addEventListener('click', () => this.performRedo());
        }
        
        // Set up keyboard shortcuts
        document.addEventListener('keydown', (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === 'z' && !event.shiftKey) {
                event.preventDefault();
                this.performUndo();
            } else if ((event.ctrlKey || event.metaKey) && (event.key === 'y' || (event.key === 'z' && event.shiftKey))) {
                event.preventDefault();
                this.performRedo();
            }
        });
        
        this.updateHistoryButtons();
    }

    setupPresenceIndicators() {
        // Send heartbeat every 30 seconds
        this.heartbeatInterval = setInterval(() => {
            if (this.collaborationWs && this.collaborationWs.readyState === WebSocket.OPEN) {
                this.collaborationWs.send(JSON.stringify({
                    type: 'heartbeat',
                    user_id: this.getCurrentUserId(),
                    timestamp: Date.now()
                }));
            }
        }, 30000);
        
        // Send presence updates
        window.addEventListener('focus', () => {
            if (this.collaborationWs && this.collaborationWs.readyState === WebSocket.OPEN) {
                this.collaborationWs.send(JSON.stringify({
                    type: 'user_active',
                    user_id: this.getCurrentUserId()
                }));
            }
        });
        
        window.addEventListener('blur', () => {
            if (this.collaborationWs && this.collaborationWs.readyState === WebSocket.OPEN) {
                this.collaborationWs.send(JSON.stringify({
                    type: 'user_idle',
                    user_id: this.getCurrentUserId()
                }));
            }
        });
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (this.collaborationWs && this.collaborationWs.readyState === WebSocket.OPEN) {
                this.collaborationWs.send(JSON.stringify({
                    type: 'user_disconnect',
                    user_id: this.getCurrentUserId()
                }));
            }
            if (this.heartbeatInterval) {
                clearInterval(this.heartbeatInterval);
            }
        });
    }

    setupConflictResolution() {
        this.conflictQueue = [];
        this.isResolvingConflict = false;
        
        // Create conflict resolution modal
        const conflictModal = document.createElement('div');
        conflictModal.id = 'conflict-resolution-modal';
        conflictModal.className = 'fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 hidden';
        conflictModal.innerHTML = `
            <div class="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
                <div class="mt-3">
                    <div class="flex items-center mb-4">
                        <svg class="w-6 h-6 text-yellow-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16c-.77.833.192 2.5 1.732 2.5z"/>
                        </svg>
                        <h3 class="text-lg font-medium text-gray-900">Conflict Detected</h3>
                    </div>
                    <div id="conflict-description" class="mb-4 text-sm text-gray-600"></div>
                    <div class="flex justify-end space-x-3">
                        <button id="conflict-keep-mine" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                            Keep My Changes
                        </button>
                        <button id="conflict-keep-theirs" class="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700">
                            Accept Their Changes
                        </button>
                        <button id="conflict-merge" class="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700">
                            Try to Merge
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(conflictModal);
        this.conflictModal = conflictModal;
    }

    setupCalculations() {
        this.calculationEngine = {
            fuelConsumption: this.calculateFuelConsumption.bind(this),
            tireWear: this.calculateTireWear.bind(this),
            lapTimes: this.calculateLapTimes.bind(this),
            pitStopTime: this.calculatePitStopTime.bind(this),
            totalRaceTime: this.calculateTotalRaceTime.bind(this)
        };

        // Initial calculations
        this.updateCalculations();
    }

    setupMobileOptimization() {
        if (this.isMobileDevice()) {
            this.enableMobileMode();
        }
    }

    handleTimelineClick(event) {
        const rect = this.timeline.svg.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const minute = Math.round(x / this.timeline.pixelsPerMinute);
        
        // Determine which driver lane was clicked
        const y = event.clientY - rect.top;
        const driverIndex = this.getDriverIndexFromY(y);
        
        if (driverIndex >= 0) {
            this.handleStintAssignment(driverIndex, minute);
        }
    }

    handleStintAssignment(driverIndex, startMinute) {
        const driver = this.teamData.members[driverIndex];
        if (!driver) return;

        // Create new stint assignment
        const stint = {
            id: `stint-${Date.now()}`,
            driverId: driver.id,
            startMinute: startMinute,
            durationMinutes: 60, // Default stint length
            fuelLoad: this.calculateOptimalFuelLoad(startMinute, 60),
            tireCompound: 'medium' // Default tire compound
        };

        this.addStintAssignment(stint);
        this.updateTimelineDisplay();
        this.updateCalculations();
        this.broadcastChange('stint-added', stint);
    }

    addStintAssignment(stint) {
        if (!this.stintAssignments.has(stint.driverId)) {
            this.stintAssignments.set(stint.driverId, []);
        }
        
        this.stintAssignments.get(stint.driverId).push(stint);
        this.sortStintsByTime(stint.driverId);
    }

    updateTimelineDisplay() {
        if (!this.timeline) return;

        // Clear existing stint rectangles
        const existingStints = this.timeline.svg.querySelectorAll('.stint-assignment');
        existingStints.forEach(el => el.remove());

        // Add stint assignments to timeline
        for (const [driverId, stints] of this.stintAssignments.entries()) {
            const driverIndex = this.getDriverIndexById(driverId);
            if (driverIndex < 0) continue;

            const y = 40 + (driverIndex * 50);
            
            stints.forEach(stint => {
                this.addStintToTimeline(stint, y);
            });
        }
    }

    addStintToTimeline(stint, y) {
        const startX = stint.startMinute * this.timeline.pixelsPerMinute;
        const width = stint.durationMinutes * this.timeline.pixelsPerMinute;

        // Stint rectangle
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', startX);
        rect.setAttribute('y', y + 5);
        rect.setAttribute('width', width);
        rect.setAttribute('height', 30);
        rect.setAttribute('class', 'stint-assignment');
        rect.setAttribute('data-stint-id', stint.id);
        rect.setAttribute('data-driver-id', stint.driverId);
        
        // Add drag handles
        rect.setAttribute('cursor', 'move');
        rect.addEventListener('mousedown', this.handleStintDragStart.bind(this));

        this.timeline.svg.appendChild(rect);

        // Stint label
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', startX + 5);
        text.setAttribute('y', y + 25);
        text.setAttribute('class', 'stint-label');
        text.textContent = `${stint.durationMinutes}min`;
        this.timeline.svg.appendChild(text);
    }

    calculateFuelConsumption(stint) {
        if (!this.eventData.track || !this.teamData.car) return 0;

        const baseConsumption = this.eventData.track.fuel_consumption_per_lap || 2.5;
        const carMultiplier = this.teamData.car.fuel_efficiency || 1.0;
        const lapsInStint = stint.durationMinutes / (this.eventData.average_lap_time / 60);
        
        return Math.ceil(lapsInStint * baseConsumption * carMultiplier);
    }

    calculateOptimalFuelLoad(startMinute, durationMinutes) {
        const remainingRaceTime = this.eventData.duration_minutes - startMinute;
        const stintFuel = this.calculateFuelConsumption({ durationMinutes });
        const safetyMargin = 2; // Extra liters for safety
        
        return Math.min(stintFuel + safetyMargin, remainingRaceTime * 0.5); // Max fuel capacity consideration
    }

    calculateTireWear(stint) {
        const baseDegradation = this.eventData.track.tire_degradation || 0.05;
        const compoundMultiplier = this.getTireCompoundMultiplier(stint.tireCompound);
        
        return stint.durationMinutes * baseDegradation * compoundMultiplier;
    }

    updateCalculations() {
        this.updateFuelCalculations();
        this.updateTireCalculations();
        this.updateTotalRaceTime();
        this.updatePitStopSchedule();
    }

    updateFuelCalculations() {
        const fuelSummary = document.getElementById('fuel-summary');
        if (!fuelSummary) return;

        let totalFuel = 0;
        let pitStopFuel = 0;

        for (const stints of this.stintAssignments.values()) {
            for (const stint of stints) {
                totalFuel += this.calculateFuelConsumption(stint);
            }
        }

        // Calculate required pit stop fuel
        const maxTankCapacity = this.teamData.car?.max_fuel || 100;
        if (totalFuel > maxTankCapacity) {
            pitStopFuel = totalFuel - maxTankCapacity;
        }

        fuelSummary.innerHTML = `
            <div class="fuel-stat">
                <span class="label">Total Fuel:</span>
                <span class="value">${totalFuel.toFixed(1)}L</span>
            </div>
            <div class="fuel-stat">
                <span class="label">Pit Stop Fuel:</span>
                <span class="value">${pitStopFuel.toFixed(1)}L</span>
            </div>
        `;
    }

    handleAutoCalculate() {
        this.showLoadingOverlay('Calculating optimal stint plan...');
        
        // Clear existing assignments
        this.stintAssignments.clear();
        
        // Calculate optimal stint distribution
        const optimalPlan = this.generateOptimalStintPlan();
        
        // Apply the calculated plan
        optimalPlan.forEach(stint => {
            this.addStintAssignment(stint);
        });
        
        this.updateTimelineDisplay();
        this.updateCalculations();
        this.hideLoadingOverlay();
        
        this.broadcastChange('auto-calculate', { plan: optimalPlan });
    }

    generateOptimalStintPlan() {
        const raceLength = this.eventData.duration_minutes;
        const drivers = this.teamData.members;
        const optimalStintLength = this.calculateOptimalStintLength();
        
        const plan = [];
        let currentTime = 0;
        let driverIndex = 0;

        while (currentTime < raceLength) {
            const driver = drivers[driverIndex % drivers.length];
            const remainingTime = raceLength - currentTime;
            const stintDuration = Math.min(optimalStintLength, remainingTime);
            
            // Check driver availability
            if (this.isDriverAvailable(driver.id, currentTime, stintDuration)) {
                const stint = {
                    id: `stint-${Date.now()}-${plan.length}`,
                    driverId: driver.id,
                    startMinute: currentTime,
                    durationMinutes: stintDuration,
                    fuelLoad: this.calculateOptimalFuelLoad(currentTime, stintDuration),
                    tireCompound: this.selectOptimalTireCompound(currentTime, stintDuration)
                };
                
                plan.push(stint);
                currentTime += stintDuration;
            }
            
            driverIndex++;
            
            // Prevent infinite loop
            if (driverIndex > drivers.length * 10) break;
        }

        return plan;
    }

    calculateOptimalStintLength() {
        const trackLength = this.eventData.track?.length || 5000; // meters
        const averageLapTime = this.eventData.average_lap_time || 90; // seconds
        const fuelConsumptionRate = this.eventData.track?.fuel_consumption_per_lap || 2.5;
        const maxFuelCapacity = this.teamData.car?.max_fuel || 100;
        
        // Calculate stint length based on fuel capacity and consumption
        const maxLapsOnFuel = maxFuelCapacity / fuelConsumptionRate;
        const maxStintTime = (maxLapsOnFuel * averageLapTime) / 60; // Convert to minutes
        
        // Factor in tire degradation and driver fatigue
        const optimalStintTime = Math.min(maxStintTime * 0.9, 90); // 90 minutes max for driver comfort
        
        return Math.round(optimalStintTime);
    }

    handleSavePlan() {
        const planData = this.exportPlanData();
        
        // Send to server via HTMX
        htmx.ajax('POST', window.location.href, {
            values: {
                'stint_plan': JSON.stringify(planData),
                'csrfmiddlewaretoken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        }).then(() => {
            this.showSuccessMessage('Stint plan saved successfully!');
            this.lastSaveTimestamp = Date.now();
        }).catch((error) => {
            this.showErrorMessage('Failed to save stint plan. Please try again.');
            console.error('Save error:', error);
        });
    }

    exportPlanData() {
        const planData = {
            team_allocation_id: this.teamData.allocation_id,
            stints: [],
            pit_stops: this.pitStops,
            metadata: {
                created_at: new Date().toISOString(),
                total_fuel: this.calculateTotalFuelRequirement(),
                estimated_finish_time: this.calculateEstimatedFinishTime()
            }
        };

        for (const [driverId, stints] of this.stintAssignments.entries()) {
            planData.stints.push(...stints.map(stint => ({
                driver_id: driverId,
                start_minute: stint.startMinute,
                duration_minutes: stint.durationMinutes,
                fuel_load: stint.fuelLoad,
                tire_compound: stint.tireCompound
            })));
        }

        return planData;
    }

    initializeWebSocket() {
        const wsUrl = `wss://${window.location.host}/ws/stint-planning/${this.teamData.allocation_id}/`;
        
        this.collaborationWs = new WebSocket(wsUrl);
        
        this.collaborationWs.onopen = () => {
            console.log('Collaboration WebSocket connected');
        };
        
        this.collaborationWs.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleCollaborationMessage(data);
        };
        
        this.collaborationWs.onclose = () => {
            console.log('Collaboration WebSocket disconnected');
            // Attempt to reconnect after 5 seconds
            setTimeout(() => this.initializeWebSocket(), 5000);
        };
    }

    broadcastChange(type, data) {
        if (this.collaborationWs && this.collaborationWs.readyState === WebSocket.OPEN) {
            this.collaborationWs.send(JSON.stringify({
                type: type,
                data: data,
                timestamp: Date.now(),
                user_id: this.getCurrentUserId()
            }));
        }
    }

    handleCollaborationMessage(message) {
        if (message.user_id === this.getCurrentUserId()) {
            return; // Ignore our own messages
        }

        switch (message.type) {
            case 'stint-added':
                this.addStintAssignment(message.data);
                this.updateTimelineDisplay();
                this.showCollaborationNotification(`${message.user_name} added a stint assignment`);
                break;
            case 'stint-modified':
                this.updateStintAssignment(message.data);
                this.updateTimelineDisplay();
                this.showCollaborationNotification(`${message.user_name} modified a stint`);
                break;
            case 'stint-deleted':
                this.removeStintAssignment(message.data.stint_id);
                this.updateTimelineDisplay();
                this.showCollaborationNotification(`${message.user_name} deleted a stint`);
                break;
            case 'user-joined':
                this.handleUserJoined(message);
                break;
            case 'user-left':
                this.handleUserLeft(message.user_id);
                break;
            case 'cursor_move':
                this.handleCursorMove(message);
                break;
            case 'cursor_hide':
                this.handleCursorHide(message.user_id);
                break;
            case 'user_active':
                this.handleUserActive(message.user_id);
                break;
            case 'user_idle':
                this.handleUserIdle(message.user_id);
                break;
            case 'user_disconnect':
                this.handleUserDisconnect(message.user_id);
                break;
            case 'conflict_detected':
                this.handleConflictDetected(message);
                break;
            case 'undo_operation':
                this.handleRemoteUndo(message);
                break;
            case 'redo_operation':
                this.handleRemoteRedo(message);
                break;
        }
    }

    handleCursorMove(data) {
        if (data.user_id === this.getCurrentUserId()) return;
        
        const timeline = document.getElementById('stint-timeline');
        if (!timeline) return;
        
        // Create or update cursor indicator
        let cursor = this.collaboratorCursors.get(data.user_id);
        if (!cursor) {
            cursor = this.createCollaboratorCursor(data.user_id, data.user_name);
            this.collaboratorCursors.set(data.user_id, cursor);
        }
        
        // Update cursor position
        cursor.style.left = `${data.x}px`;
        cursor.style.top = `${data.y}px`;
        cursor.style.display = 'block';
        
        // Auto-hide after 5 seconds
        clearTimeout(cursor.hideTimeout);
        cursor.hideTimeout = setTimeout(() => {
            cursor.style.display = 'none';
        }, 5000);
    }

    handleCursorHide(userId) {
        const cursor = this.collaboratorCursors.get(userId);
        if (cursor) {
            cursor.style.display = 'none';
        }
    }

    createCollaboratorCursor(userId, userName) {
        const cursor = document.createElement('div');
        cursor.className = 'collaborator-cursor';
        cursor.style.cssText = `
            position: absolute;
            width: 20px;
            height: 20px;
            background: #3b82f6;
            border-radius: 50%;
            pointer-events: none;
            z-index: 1000;
            display: none;
            transition: all 0.1s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        `;
        
        // Add user label
        const label = document.createElement('div');
        label.className = 'collaborator-label';
        label.textContent = userName || `User ${userId}`;
        label.style.cssText = `
            position: absolute;
            top: 25px;
            left: 50%;
            transform: translateX(-50%);
            background: #3b82f6;
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
            white-space: nowrap;
            box-shadow: 0 1px 2px rgba(0,0,0,0.2);
        `;
        
        cursor.appendChild(label);
        document.body.appendChild(cursor);
        
        return cursor;
    }

    handleUserJoined(data) {
        this.addCollaboratorToPanel(data);
        this.showCollaborationNotification(`${data.user_name} joined the planning session`, 'info');
        
        // Show collaboration panel if hidden
        if (this.collaborationPanel) {
            this.collaborationPanel.style.display = 'block';
        }
    }

    handleUserLeft(userId) {
        this.removeCollaboratorFromPanel(userId);
        const userName = this.getUserName(userId);
        this.showCollaborationNotification(`${userName} left the planning session`, 'info');
        
        // Hide cursor
        this.handleCursorHide(userId);
        
        // Hide panel if no collaborators
        const collaboratorList = document.getElementById('collaborator-list');
        if (collaboratorList && collaboratorList.children.length === 0) {
            this.collaborationPanel.style.display = 'none';
        }
    }

    handleUserActive(userId) {
        const collaboratorEl = document.querySelector(`[data-user-id="${userId}"]`);
        if (collaboratorEl) {
            collaboratorEl.classList.remove('user-idle');
            collaboratorEl.classList.add('user-active');
            const statusEl = collaboratorEl.querySelector('.user-status');
            if (statusEl) statusEl.textContent = 'Active';
        }
    }

    handleUserIdle(userId) {
        const collaboratorEl = document.querySelector(`[data-user-id="${userId}"]`);
        if (collaboratorEl) {
            collaboratorEl.classList.remove('user-active');
            collaboratorEl.classList.add('user-idle');
            const statusEl = collaboratorEl.querySelector('.user-status');
            if (statusEl) statusEl.textContent = 'Idle';
        }
    }

    handleUserDisconnect(userId) {
        this.handleUserLeft(userId);
        
        // Remove cursor
        const cursor = this.collaboratorCursors.get(userId);
        if (cursor) {
            cursor.remove();
            this.collaboratorCursors.delete(userId);
        }
    }

    handleConflictDetected(data) {
        if (this.isResolvingConflict) {
            this.conflictQueue.push(data);
            return;
        }
        
        this.isResolvingConflict = true;
        this.showConflictResolutionModal(data);
    }

    addCollaboratorToPanel(user) {
        const collaboratorList = document.getElementById('collaborator-list');
        if (!collaboratorList) return;
        
        const collaboratorEl = document.createElement('div');
        collaboratorEl.className = 'flex items-center space-x-2 p-2 bg-gray-50 rounded-lg user-active';
        collaboratorEl.setAttribute('data-user-id', user.user_id);
        collaboratorEl.innerHTML = `
            <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white text-xs font-medium">
                ${user.user_name.charAt(0).toUpperCase()}
            </div>
            <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-gray-900 truncate">${user.user_name}</div>
                <div class="text-xs text-gray-500 user-status">Active</div>
            </div>
            <div class="w-2 h-2 bg-green-400 rounded-full"></div>
        `;
        
        collaboratorList.appendChild(collaboratorEl);
    }

    removeCollaboratorFromPanel(userId) {
        const collaboratorEl = document.querySelector(`[data-user-id="${userId}"]`);
        if (collaboratorEl) {
            collaboratorEl.remove();
        }
    }

    showConflictResolutionModal(conflictData) {
        const modal = this.conflictModal;
        const description = document.getElementById('conflict-description');
        
        description.textContent = `${conflictData.user_name} modified the same stint you're working on. How would you like to resolve this conflict?`;
        
        modal.classList.remove('hidden');
        
        // Set up event listeners for resolution buttons
        document.getElementById('conflict-keep-mine').onclick = () => {
            this.resolveConflict('keep_mine', conflictData);
        };
        
        document.getElementById('conflict-keep-theirs').onclick = () => {
            this.resolveConflict('keep_theirs', conflictData);
        };
        
        document.getElementById('conflict-merge').onclick = () => {
            this.resolveConflict('merge', conflictData);
        };
    }

    resolveConflict(resolution, conflictData) {
        // Hide modal
        this.conflictModal.classList.add('hidden');
        this.isResolvingConflict = false;
        
        // Apply resolution
        switch (resolution) {
            case 'keep_mine':
                // Keep current state, ignore remote changes
                this.showCollaborationNotification('Kept your changes', 'success');
                break;
            case 'keep_theirs':
                // Apply remote changes
                this.applyRemoteChanges(conflictData.changes);
                this.showCollaborationNotification('Applied their changes', 'success');
                break;
            case 'merge':
                // Attempt to merge changes
                this.attemptMerge(conflictData);
                this.showCollaborationNotification('Attempted to merge changes', 'info');
                break;
        }
        
        // Process next conflict in queue
        if (this.conflictQueue.length > 0) {
            const nextConflict = this.conflictQueue.shift();
            setTimeout(() => {
                this.handleConflictDetected(nextConflict);
            }, 500);
        }
    }

    showCollaborationNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `fixed bottom-4 right-4 p-3 rounded-lg shadow-lg z-50 transition-all transform translate-x-full max-w-sm`;
        
        const bgColor = type === 'info' ? 'bg-blue-500' : type === 'success' ? 'bg-green-500' : 'bg-orange-500';
        notification.classList.add(bgColor, 'text-white');
        
        notification.innerHTML = `
            <div class="flex items-center">
                <div class="w-2 h-2 bg-white rounded-full mr-2 animate-pulse"></div>
                <span class="text-sm">${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-white hover:text-gray-200">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.classList.remove('translate-x-full');
        }, 100);
        
        // Auto remove after 4 seconds
        setTimeout(() => {
            notification.classList.add('translate-x-full');
            setTimeout(() => notification.remove(), 300);
        }, 4000);
    }

    getUserName(userId) {
        const collaboratorEl = document.querySelector(`[data-user-id="${userId}"]`);
        if (collaboratorEl) {
            const nameEl = collaboratorEl.querySelector('.text-sm.font-medium');
            return nameEl ? nameEl.textContent : `User ${userId}`;
        }
        return `User ${userId}`;
    }

    // Mobile optimization methods
    enableMobileMode() {
        document.body.classList.add('mobile-stint-planning');
        
        // Switch to simplified timeline view
        this.setupMobileTimeline();
        
        // Enable touch gestures
        this.setupTouchGestures();
        
        // Simplify interface
        this.hideMobileUnsupportedFeatures();
    }

    setupMobileTimeline() {
        // Create a simplified list-based view for mobile
        const mobileContainer = document.createElement('div');
        mobileContainer.className = 'mobile-timeline-container';
        mobileContainer.innerHTML = `
            <div class="mobile-timeline-header">
                <h3>Stint Assignments</h3>
                <button class="btn-add-stint">Add Stint</button>
            </div>
            <div class="mobile-stint-list"></div>
        `;
        
        const timelineContainer = document.getElementById('stint-timeline');
        if (timelineContainer) {
            timelineContainer.style.display = 'none';
            timelineContainer.parentNode.insertBefore(mobileContainer, timelineContainer);
        }
    }

    // Utility methods
    formatTimeForDisplay(minutes) {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return `${hours}:${mins.toString().padStart(2, '0')}`;
    }

    isMobileDevice() {
        return window.innerWidth < 768 || 'ontouchstart' in window;
    }

    getCurrentUserId() {
        return document.body.dataset.userId || 'anonymous';
    }

    showSuccessMessage(message) {
        this.showMessage(message, 'success');
    }

    showErrorMessage(message) {
        this.showMessage(message, 'error');
    }

    showMessage(message, type) {
        const messageEl = document.createElement('div');
        messageEl.className = `message message-${type}`;
        messageEl.textContent = message;
        
        document.body.appendChild(messageEl);
        
        setTimeout(() => {
            messageEl.remove();
        }, 5000);
    }

    loadExistingPlan() {
        const existingPlanEl = document.getElementById('existing-stint-plan');
        if (existingPlanEl) {
            try {
                const planData = JSON.parse(existingPlanEl.textContent);
                this.importPlanData(planData);
            } catch (e) {
                console.warn('Failed to load existing plan:', e);
            }
        }
    }

    importPlanData(planData) {
        // Clear existing data
        this.stintAssignments.clear();
        this.pitStops = [];
        
        // Import stint assignments
        if (planData.stints) {
            planData.stints.forEach(stint => {
                const stintObj = {
                    id: stint.id || `stint-${Date.now()}-${Math.random()}`,
                    driverId: stint.driver_id,
                    startMinute: stint.start_minute,
                    durationMinutes: stint.duration_minutes,
                    fuelLoad: stint.fuel_load,
                    tireCompound: stint.tire_compound
                };
                this.addStintAssignment(stintObj);
            });
        }
        
        // Import pit stops
        if (planData.pit_stops) {
            this.pitStops = [...planData.pit_stops];
        }
        
        // Update displays
        this.updateTimelineDisplay();
        this.updateCalculations();
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.stint-planning-interface')) {
        window.stintPlanningInterface = new StintPlanningInterface();
    }
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StintPlanningInterface;
} 