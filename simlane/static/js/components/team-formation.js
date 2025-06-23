/**
 * Team Formation ES6 Module
 * Handles team formation dashboard with availability visualization
 */

export class TeamFormationDashboard {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.options = {
            eventId: null,
            teamSize: 3,
            maxTeams: null,
            timezone: 'UTC',
            ...options
        };
        
        this.participants = [];
        this.teamSuggestions = [];
        this.availabilityData = null;
        
        this.init();
    }

    async init() {
        if (!this.container) {
            console.error('Team formation container not found:', this.containerId);
            return;
        }

        this.createDashboardLayout();
        await this.loadParticipantData();
        this.renderParticipantList();
        this.generateTeamSuggestions();
    }

    createDashboardLayout() {
        this.container.innerHTML = `
            <div class="team-formation-dashboard">
                <!-- Header -->
                <div class="mb-6">
                    <h2 class="text-2xl font-bold text-gray-900 mb-2">Team Formation</h2>
                    <p class="text-gray-600">Review signups and form teams based on availability overlap</p>
                </div>

                <!-- Stats Overview -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                    <div class="bg-white rounded-lg border p-4">
                        <div class="text-2xl font-bold text-blue-600" id="total-signups">0</div>
                        <div class="text-sm text-gray-600">Total Signups</div>
                    </div>
                    <div class="bg-white rounded-lg border p-4">
                        <div class="text-2xl font-bold text-green-600" id="ready-for-teams">0</div>
                        <div class="text-sm text-gray-600">Ready for Teams</div>
                    </div>
                    <div class="bg-white rounded-lg border p-4">
                        <div class="text-2xl font-bold text-yellow-600" id="suggested-teams">0</div>
                        <div class="text-sm text-gray-600">Suggested Teams</div>
                    </div>
                    <div class="bg-white rounded-lg border p-4">
                        <div class="text-2xl font-bold text-purple-600" id="avg-overlap">0h</div>
                        <div class="text-sm text-gray-600">Avg Overlap</div>
                    </div>
                </div>

                <!-- Main Content Grid -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <!-- Left Column: Participants & Availability -->
                    <div class="lg:col-span-2 space-y-6">
                        <!-- Participants List -->
                        <div class="bg-white rounded-lg border">
                            <div class="px-6 py-4 border-b border-gray-200">
                                <h3 class="text-lg font-semibold">Participants</h3>
                                <div class="flex items-center space-x-4 mt-2">
                                    <select id="filter-status" class="text-sm border-gray-300 rounded-md">
                                        <option value="">All Status</option>
                                        <option value="signed_up">Signed Up</option>
                                        <option value="team_assigned">Team Assigned</option>
                                    </select>
                                    <button id="refresh-data" class="text-sm text-blue-600 hover:text-blue-800">
                                        Refresh Data
                                    </button>
                                </div>
                            </div>
                            <div id="participants-list" class="divide-y divide-gray-200">
                                <!-- Participants will be rendered here -->
                            </div>
                        </div>

                        <!-- Availability Heatmap -->
                        <div class="bg-white rounded-lg border">
                            <div class="px-6 py-4 border-b border-gray-200">
                                <h3 class="text-lg font-semibold">Availability Coverage</h3>
                                <div class="flex items-center space-x-4 mt-2">
                                    <select id="timezone-selector" class="text-sm border-gray-300 rounded-md">
                                        <option value="UTC">UTC</option>
                                        <option value="US/Eastern">Eastern</option>
                                        <option value="US/Central">Central</option>
                                        <option value="US/Mountain">Mountain</option>
                                        <option value="US/Pacific">Pacific</option>
                                        <option value="Europe/London">London</option>
                                        <option value="Europe/Paris">Paris</option>
                                    </select>
                                    <button id="toggle-heatmap" class="text-sm text-blue-600 hover:text-blue-800">
                                        Toggle View
                                    </button>
                                </div>
                            </div>
                            <div id="availability-heatmap" class="p-6">
                                <!-- Heatmap will be rendered here -->
                            </div>
                        </div>
                    </div>

                    <!-- Right Column: Team Suggestions -->
                    <div class="space-y-6">
                        <!-- Team Formation Controls -->
                        <div class="bg-white rounded-lg border p-6">
                            <h3 class="text-lg font-semibold mb-4">Formation Settings</h3>
                            <div class="space-y-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Team Size</label>
                                    <input type="number" id="team-size" min="2" max="6" value="${this.options.teamSize}"
                                           class="w-full rounded-md border-gray-300">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Max Teams</label>
                                    <input type="number" id="max-teams" min="1" max="20" 
                                           value="${this.options.maxTeams || ''}" placeholder="No limit"
                                           class="w-full rounded-md border-gray-300">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-1">Algorithm</label>
                                    <select id="formation-algorithm" class="w-full rounded-md border-gray-300">
                                        <option value="availability">Availability Based</option>
                                        <option value="balanced">Balanced Experience</option>
                                        <option value="manual">Manual Selection</option>
                                    </select>
                                </div>
                                <button id="generate-teams" 
                                        class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700">
                                    Generate Teams
                                </button>
                            </div>
                        </div>

                        <!-- Team Suggestions -->
                        <div class="bg-white rounded-lg border">
                            <div class="px-6 py-4 border-b border-gray-200">
                                <h3 class="text-lg font-semibold">Suggested Teams</h3>
                            </div>
                            <div id="team-suggestions" class="p-6">
                                <!-- Team suggestions will be rendered here -->
                            </div>
                        </div>

                        <!-- Actions -->
                        <div class="bg-white rounded-lg border p-6">
                            <h3 class="text-lg font-semibold mb-4">Actions</h3>
                            <div class="space-y-3">
                                <button id="create-teams" 
                                        class="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:opacity-50"
                                        disabled>
                                    Create Teams
                                </button>
                                <button id="export-data" 
                                        class="w-full bg-gray-600 text-white py-2 px-4 rounded-md hover:bg-gray-700">
                                    Export Data
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.attachEventListeners();
    }

    attachEventListeners() {
        // Refresh data
        document.getElementById('refresh-data').addEventListener('click', () => {
            this.loadParticipantData();
        });

        // Generate teams
        document.getElementById('generate-teams').addEventListener('click', () => {
            this.generateTeamSuggestions();
        });

        // Create teams
        document.getElementById('create-teams').addEventListener('click', () => {
            this.createTeamsFromSuggestions();
        });

        // Export data
        document.getElementById('export-data').addEventListener('click', () => {
            this.exportData();
        });

        // Timezone change
        document.getElementById('timezone-selector').addEventListener('change', (e) => {
            this.options.timezone = e.target.value;
            this.renderAvailabilityHeatmap();
        });

        // Team size change
        document.getElementById('team-size').addEventListener('change', (e) => {
            this.options.teamSize = parseInt(e.target.value);
        });

        // Max teams change
        document.getElementById('max-teams').addEventListener('change', (e) => {
            this.options.maxTeams = e.target.value ? parseInt(e.target.value) : null;
        });
    }

    async loadParticipantData() {
        try {
            // In a real implementation, this would be an HTMX request or fetch
            // For now, we'll simulate with local data
            const response = await this.fetchParticipantData();
            this.participants = response.participants || [];
            this.availabilityData = response.availability_data || null;
            
            this.updateStats();
            this.renderParticipantList();
            this.renderAvailabilityHeatmap();
        } catch (error) {
            console.error('Error loading participant data:', error);
            this.showError('Failed to load participant data');
        }
    }

    async fetchParticipantData() {
        // Simulate API call - in real implementation would use HTMX or fetch
        // This would be replaced with actual HTMX request
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve({
                    participants: [
                        {
                            id: 1,
                            user: { username: 'driver1', first_name: 'John', last_name: 'Doe' },
                            status: 'signed_up',
                            preferred_car: 'GT3 BMW',
                            experience_level: 'intermediate',
                            availability_hours: 12.5
                        },
                        {
                            id: 2,
                            user: { username: 'racer2', first_name: 'Jane', last_name: 'Smith' },
                            status: 'signed_up',
                            preferred_car: 'GT3 Mercedes',
                            experience_level: 'advanced',
                            availability_hours: 8.0
                        }
                    ],
                    availability_data: {
                        total_participants: 2,
                        hourly_coverage: {},
                        timezone: this.options.timezone
                    }
                });
            }, 500);
        });
    }

    updateStats() {
        document.getElementById('total-signups').textContent = this.participants.length;
        
        const readyCount = this.participants.filter(p => p.status === 'signed_up').length;
        document.getElementById('ready-for-teams').textContent = readyCount;
        
        document.getElementById('suggested-teams').textContent = this.teamSuggestions.length;
        
        const avgOverlap = this.calculateAverageOverlap();
        document.getElementById('avg-overlap').textContent = `${avgOverlap.toFixed(1)}h`;
    }

    calculateAverageOverlap() {
        if (this.teamSuggestions.length === 0) return 0;
        
        const totalOverlap = this.teamSuggestions.reduce((sum, team) => {
            return sum + (team.total_overlap_hours || 0);
        }, 0);
        
        return totalOverlap / this.teamSuggestions.length;
    }

    renderParticipantList() {
        const listContainer = document.getElementById('participants-list');
        
        if (this.participants.length === 0) {
            listContainer.innerHTML = `
                <div class="p-6 text-center text-gray-500">
                    No participants have signed up yet.
                </div>
            `;
            return;
        }

        listContainer.innerHTML = this.participants.map(participant => {
            const user = participant.user;
            const displayName = user.first_name && user.last_name 
                ? `${user.first_name} ${user.last_name}` 
                : user.username;
            
            return `
                <div class="px-6 py-4 hover:bg-gray-50">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-3">
                            <div class="flex-shrink-0">
                                <div class="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center">
                                    <span class="text-xs font-medium">${displayName.charAt(0)}</span>
                                </div>
                            </div>
                            <div>
                                <div class="font-medium text-gray-900">${displayName}</div>
                                <div class="text-sm text-gray-500">@${user.username}</div>
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="text-sm font-medium">${participant.preferred_car || 'No preference'}</div>
                            <div class="text-xs text-gray-500">${participant.experience_level} • ${participant.availability_hours || 0}h available</div>
                        </div>
                    </div>
                    <div class="mt-2 flex items-center space-x-2">
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                            ${participant.status === 'signed_up' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}">
                            ${participant.status.replace('_', ' ').toUpperCase()}
                        </span>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderAvailabilityHeatmap() {
        const heatmapContainer = document.getElementById('availability-heatmap');
        
        if (!this.availabilityData || this.participants.length === 0) {
            heatmapContainer.innerHTML = `
                <div class="text-center text-gray-500 py-8">
                    No availability data to display
                </div>
            `;
            return;
        }

        // Simple heatmap representation (would be enhanced with D3.js when available)
        heatmapContainer.innerHTML = `
            <div class="space-y-2">
                <div class="text-sm font-medium text-gray-700 mb-3">Coverage by Hour (${this.options.timezone})</div>
                <div class="bg-gray-100 p-4 rounded text-center text-sm text-gray-600">
                    📊 Advanced heatmap visualization will be available when D3.js is loaded
                </div>
                <div class="text-xs text-gray-500 mt-2">
                    Total participants with availability: ${this.availabilityData.total_participants}
                </div>
            </div>
        `;
    }

    async generateTeamSuggestions() {
        const algorithm = document.getElementById('formation-algorithm').value;
        const teamSize = parseInt(document.getElementById('team-size').value);
        const maxTeams = document.getElementById('max-teams').value 
            ? parseInt(document.getElementById('max-teams').value) 
            : null;

        try {
            // Show loading state
            const suggestionsContainer = document.getElementById('team-suggestions');
            suggestionsContainer.innerHTML = `
                <div class="text-center py-8">
                    <div class="text-sm text-gray-600">Generating team suggestions...</div>
                </div>
            `;

            // Simulate team generation (would be HTMX request in real implementation)
            const suggestions = await this.fetchTeamSuggestions(algorithm, teamSize, maxTeams);
            this.teamSuggestions = suggestions;
            
            this.renderTeamSuggestions();
            this.updateStats();
            
            // Enable create teams button
            document.getElementById('create-teams').disabled = suggestions.length === 0;
            
        } catch (error) {
            console.error('Error generating team suggestions:', error);
            this.showError('Failed to generate team suggestions');
        }
    }

    async fetchTeamSuggestions(algorithm, teamSize, maxTeams) {
        // Simulate API call
        return new Promise((resolve) => {
            setTimeout(() => {
                // Mock team suggestions
                const suggestions = [];
                const availableParticipants = this.participants.filter(p => p.status === 'signed_up');
                
                if (availableParticipants.length >= teamSize) {
                    for (let i = 0; i < Math.min(Math.floor(availableParticipants.length / teamSize), maxTeams || 10); i++) {
                        const teamMembers = availableParticipants.slice(i * teamSize, (i + 1) * teamSize);
                        suggestions.push({
                            id: i + 1,
                            members: teamMembers,
                            compatibility_score: Math.random() * 10 + 5, // 5-15 hours
                            total_overlap_hours: Math.random() * 8 + 4, // 4-12 hours
                            balance_score: Math.random(),
                            recommended_car: teamMembers[0]?.preferred_car || 'GT3 BMW'
                        });
                    }
                }
                
                resolve(suggestions);
            }, 1000);
        });
    }

    renderTeamSuggestions() {
        const suggestionsContainer = document.getElementById('team-suggestions');
        
        if (this.teamSuggestions.length === 0) {
            suggestionsContainer.innerHTML = `
                <div class="text-center text-gray-500 py-8">
                    No team suggestions generated.<br>
                    Try adjusting the team size or formation settings.
                </div>
            `;
            return;
        }

        suggestionsContainer.innerHTML = this.teamSuggestions.map((team, index) => `
            <div class="border border-gray-200 rounded-lg p-4 mb-4 hover:border-blue-300 transition-colors">
                <div class="flex items-center justify-between mb-3">
                    <h4 class="font-medium text-gray-900">Team ${String.fromCharCode(65 + index)}</h4>
                    <div class="text-sm text-gray-500">${team.total_overlap_hours.toFixed(1)}h overlap</div>
                </div>
                
                <div class="space-y-2 mb-3">
                    ${team.members.map(member => {
                        const displayName = member.user.first_name && member.user.last_name 
                            ? `${member.user.first_name} ${member.user.last_name}` 
                            : member.user.username;
                        return `
                            <div class="flex items-center space-x-2 text-sm">
                                <div class="w-6 h-6 bg-gray-200 rounded-full flex items-center justify-center">
                                    <span class="text-xs">${displayName.charAt(0)}</span>
                                </div>
                                <span>${displayName}</span>
                                <span class="text-gray-500">(${member.experience_level})</span>
                            </div>
                        `;
                    }).join('')}
                </div>
                
                <div class="flex items-center justify-between text-xs text-gray-500">
                    <span>Car: ${team.recommended_car}</span>
                    <span>Balance: ${(team.balance_score * 100).toFixed(0)}%</span>
                </div>
            </div>
        `).join('');
    }

    async createTeamsFromSuggestions() {
        if (this.teamSuggestions.length === 0) {
            alert('No team suggestions to create');
            return;
        }

        if (!confirm(`Create ${this.teamSuggestions.length} teams from suggestions?`)) {
            return;
        }

        try {
            // Show loading state
            const createButton = document.getElementById('create-teams');
            const originalText = createButton.textContent;
            createButton.textContent = 'Creating...';
            createButton.disabled = true;

            // Simulate team creation (would be HTMX request)
            await this.submitTeamCreation();
            
            // Success feedback
            this.showSuccess('Teams created successfully!');
            
            // Refresh data
            await this.loadParticipantData();

        } catch (error) {
            console.error('Error creating teams:', error);
            this.showError('Failed to create teams');
        } finally {
            const createButton = document.getElementById('create-teams');
            createButton.textContent = 'Create Teams';
            createButton.disabled = false;
        }
    }

    async submitTeamCreation() {
        // This would be an HTMX request in real implementation
        return new Promise((resolve) => {
            setTimeout(() => {
                console.log('Teams created:', this.teamSuggestions);
                resolve();
            }, 2000);
        });
    }

    exportData() {
        const data = {
            participants: this.participants,
            team_suggestions: this.teamSuggestions,
            availability_data: this.availabilityData,
            settings: this.options
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `team-formation-data-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        URL.revokeObjectURL(url);
    }

    showError(message) {
        // Simple error display - could be enhanced with better UI
        const errorDiv = document.createElement('div');
        errorDiv.className = 'fixed top-4 right-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded z-50';
        errorDiv.textContent = message;
        document.body.appendChild(errorDiv);
        
        setTimeout(() => {
            document.body.removeChild(errorDiv);
        }, 5000);
    }

    showSuccess(message) {
        // Simple success display
        const successDiv = document.createElement('div');
        successDiv.className = 'fixed top-4 right-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded z-50';
        successDiv.textContent = message;
        document.body.appendChild(successDiv);
        
        setTimeout(() => {
            document.body.removeChild(successDiv);
        }, 5000);
    }
} 