/**
 * Team Allocation Wizard JavaScript
 * Handles drag-and-drop team member allocation, validation, and HTMX integration
 */

class TeamAllocationWizard {
    constructor() {
        this.selectedMembers = new Set();
        this.teamAllocations = new Map();
        this.validationRules = {
            minDriversPerTeam: 1,
            maxDriversPerTeam: 6,
            minTeams: 1,
            maxTeams: 10
        };
        this.init();
    }

    init() {
        this.setupDragAndDrop();
        this.setupEventListeners();
        this.setupValidation();
        this.setupAutoSuggestion();
        this.initializeState();
    }

    setupDragAndDrop() {
        // Enable drag for member cards
        const memberCards = document.querySelectorAll('.member-card');
        memberCards.forEach(card => {
            card.draggable = true;
            card.addEventListener('dragstart', this.handleDragStart.bind(this));
            card.addEventListener('dragend', this.handleDragEnd.bind(this));
        });

        // Enable drop for team containers
        const teamContainers = document.querySelectorAll('.team-container');
        teamContainers.forEach(container => {
            container.addEventListener('dragover', this.handleDragOver.bind(this));
            container.addEventListener('drop', this.handleDrop.bind(this));
            container.addEventListener('dragenter', this.handleDragEnter.bind(this));
            container.addEventListener('dragleave', this.handleDragLeave.bind(this));
        });

        // Enable drop for unassigned members area
        const unassignedArea = document.querySelector('.unassigned-members');
        if (unassignedArea) {
            unassignedArea.addEventListener('dragover', this.handleDragOver.bind(this));
            unassignedArea.addEventListener('drop', this.handleDropUnassigned.bind(this));
        }
    }

    handleDragStart(event) {
        const memberCard = event.target.closest('.member-card');
        event.dataTransfer.setData('text/plain', memberCard.dataset.memberId);
        event.dataTransfer.effectAllowed = 'move';

        memberCard.classList.add('dragging');
        this.showDropZones();
    }

    handleDragEnd(event) {
        const memberCard = event.target.closest('.member-card');
        memberCard.classList.remove('dragging');
        this.hideDropZones();
    }

    handleDragOver(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }

    handleDragEnter(event) {
        event.preventDefault();
        const teamContainer = event.target.closest('.team-container');
        if (teamContainer && this.canDropInTeam(teamContainer)) {
            teamContainer.classList.add('drag-over');
        }
    }

    handleDragLeave(event) {
        const teamContainer = event.target.closest('.team-container');
        if (teamContainer && !teamContainer.contains(event.relatedTarget)) {
            teamContainer.classList.remove('drag-over');
        }
    }

    handleDrop(event) {
        event.preventDefault();
        const memberId = event.dataTransfer.getData('text/plain');
        const teamContainer = event.target.closest('.team-container');
        const teamId = teamContainer.dataset.teamId;

        if (this.canDropInTeam(teamContainer)) {
            this.assignMemberToTeam(memberId, teamId);
            this.updateUI();
            this.validateAllocation();
        }

        teamContainer.classList.remove('drag-over');
    }

    handleDropUnassigned(event) {
        event.preventDefault();
        const memberId = event.dataTransfer.getData('text/plain');
        this.unassignMember(memberId);
        this.updateUI();
        this.validateAllocation();
    }

    canDropInTeam(teamContainer) {
        const teamId = teamContainer.dataset.teamId;
        const currentMembers = this.teamAllocations.get(teamId) || [];
        const maxMembers = parseInt(teamContainer.dataset.maxMembers) || this.validationRules.maxDriversPerTeam;

        return currentMembers.length < maxMembers;
    }

    assignMemberToTeam(memberId, teamId) {
        // Remove member from previous team
        this.unassignMember(memberId);

        // Add to new team
        if (!this.teamAllocations.has(teamId)) {
            this.teamAllocations.set(teamId, []);
        }
        this.teamAllocations.get(teamId).push(memberId);

        // Track change for undo functionality
        this.trackChange('assign', { memberId, teamId });
    }

    unassignMember(memberId) {
        for (const [teamId, members] of this.teamAllocations.entries()) {
            const index = members.indexOf(memberId);
            if (index > -1) {
                members.splice(index, 1);
                this.trackChange('unassign', { memberId, teamId });
                break;
            }
        }
    }

    setupEventListeners() {
        // Auto-suggest button
        const autoSuggestBtn = document.getElementById('auto-suggest-btn');
        if (autoSuggestBtn) {
            autoSuggestBtn.addEventListener('click', this.handleAutoSuggest.bind(this));
        }

        // Apply suggestions button
        const applySuggestionsBtn = document.getElementById('apply-suggestions-btn');
        if (applySuggestionsBtn) {
            applySuggestionsBtn.addEventListener('click', this.handleApplySuggestions.bind(this));
        }

        // Clear all button
        const clearAllBtn = document.getElementById('clear-all-btn');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', this.handleClearAll.bind(this));
        }

        // Undo/Redo buttons
        const undoBtn = document.getElementById('undo-btn');
        const redoBtn = document.getElementById('redo-btn');
        if (undoBtn) undoBtn.addEventListener('click', this.handleUndo.bind(this));
        if (redoBtn) redoBtn.addEventListener('click', this.handleRedo.bind(this));

        // Balance teams button
        const balanceBtn = document.getElementById('balance-teams-btn');
        if (balanceBtn) {
            balanceBtn.addEventListener('click', this.handleBalanceTeams.bind(this));
        }

        // Member search
        const memberSearch = document.getElementById('member-search');
        if (memberSearch) {
            memberSearch.addEventListener('input', this.handleMemberSearch.bind(this));
        }

        // Team size inputs
        const teamSizeInputs = document.querySelectorAll('.team-size-input');
        teamSizeInputs.forEach(input => {
            input.addEventListener('change', this.handleTeamSizeChange.bind(this));
        });
    }

    setupValidation() {
        this.validationErrors = [];
        this.validationWarnings = [];
    }

    setupAutoSuggestion() {
        this.suggestionAlgorithms = {
            'skill-balanced': this.generateSkillBalancedSuggestion.bind(this),
            'availability-optimized': this.generateAvailabilityOptimizedSuggestion.bind(this),
            'car-preference': this.generateCarPreferenceSuggestion.bind(this),
            'random': this.generateRandomSuggestion.bind(this)
        };
    }

    initializeState() {
        this.changeHistory = [];
        this.changeIndex = -1;
        this.maxHistorySize = 50;

        // Load existing allocations if any
        this.loadExistingAllocations();
        this.updateUI();
        this.validateAllocation();
    }

    loadExistingAllocations() {
        const existingData = document.getElementById('existing-allocations');
        if (existingData) {
            try {
                const allocations = JSON.parse(existingData.textContent);
                for (const allocation of allocations) {
                    this.assignMemberToTeam(allocation.memberId, allocation.teamId);
                }
            } catch (e) {
                console.warn('Failed to load existing allocations:', e);
            }
        }
    }

    handleAutoSuggest() {
        const algorithm = document.getElementById('suggestion-algorithm')?.value || 'skill-balanced';
        const numTeams = parseInt(document.getElementById('num-teams')?.value) || 2;

        this.showLoadingState('Generating suggestions...');

        // Simulate API call for now - replace with actual HTMX call
        setTimeout(() => {
            const suggestions = this.suggestionAlgorithms[algorithm](numTeams);
            this.displaySuggestions(suggestions);
            this.hideLoadingState();
        }, 1000);
    }

    generateSkillBalancedSuggestion(numTeams) {
        const members = this.getAllMembers();
        const sortedMembers = members.sort((a, b) => {
            const skillA = this.getMemberSkillRating(a.id);
            const skillB = this.getMemberSkillRating(b.id);
            return skillB - skillA; // Sort by skill descending
        });

        const teams = Array.from({ length: numTeams }, () => []);
        let teamIndex = 0;

        // Distribute members in snake draft pattern
        for (let i = 0; i < sortedMembers.length; i++) {
            teams[teamIndex].push(sortedMembers[i].id);

            if (i % numTeams === numTeams - 1) {
                // Reverse direction for snake draft
                teamIndex = numTeams - 1 - (i % (numTeams * 2));
            } else {
                teamIndex = (teamIndex + 1) % numTeams;
            }
        }

        return teams;
    }

    generateAvailabilityOptimizedSuggestion(numTeams) {
        const members = this.getAllMembers();
        const availabilityMatrix = this.getAvailabilityMatrix();

        // Use Hungarian algorithm or greedy approach to optimize availability overlap
        const teams = Array.from({ length: numTeams }, () => []);
        let teamIndex = 0;

        for (const member of members) {
            teams[teamIndex].push(member.id);
            teamIndex = (teamIndex + 1) % numTeams;
        }

        return this.optimizeForAvailability(teams, availabilityMatrix);
    }

    generateCarPreferenceSuggestion(numTeams) {
        const members = this.getAllMembers();
        const carPreferences = this.getCarPreferences();

        // Group members by car preference and distribute evenly
        const carGroups = {};
        for (const member of members) {
            const preferredCar = carPreferences[member.id] || 'default';
            if (!carGroups[preferredCar]) carGroups[preferredCar] = [];
            carGroups[preferredCar].push(member.id);
        }

        const teams = Array.from({ length: numTeams }, () => []);
        let teamIndex = 0;

        for (const [car, memberIds] of Object.entries(carGroups)) {
            for (const memberId of memberIds) {
                teams[teamIndex].push(memberId);
                teamIndex = (teamIndex + 1) % numTeams;
            }
        }

        return teams;
    }

    generateRandomSuggestion(numTeams) {
        const members = this.getAllMembers();
        const shuffled = [...members].sort(() => Math.random() - 0.5);

        const teams = Array.from({ length: numTeams }, () => []);
        let teamIndex = 0;

        for (const member of shuffled) {
            teams[teamIndex].push(member.id);
            teamIndex = (teamIndex + 1) % numTeams;
        }

        return teams;
    }

    displaySuggestions(suggestions) {
        const suggestionsContainer = document.getElementById('suggestions-preview');
        if (!suggestionsContainer) return;

        suggestionsContainer.innerHTML = '';

        suggestions.forEach((team, index) => {
            const teamDiv = document.createElement('div');
            teamDiv.className = 'suggestion-team bg-gray-50 rounded-lg p-4 mb-4';
            teamDiv.innerHTML = `
                <h4 class="font-medium text-gray-900 mb-2">Team ${index + 1} (${team.length} members)</h4>
                <div class="space-y-2">
                    ${team.map(memberId => this.renderMemberSuggestionCard(memberId)).join('')}
                </div>
                <div class="mt-3 text-sm text-gray-600">
                    <div class="flex justify-between">
                        <span>Avg Skill: ${this.calculateTeamAverageSkill(team).toFixed(1)}</span>
                        <span>Availability: ${this.calculateTeamAvailability(team)}%</span>
                    </div>
                </div>
            `;
            suggestionsContainer.appendChild(teamDiv);
        });

        // Show suggestions panel
        const suggestionsPanel = document.getElementById('suggestions-panel');
        if (suggestionsPanel) {
            suggestionsPanel.classList.remove('hidden');
        }
    }

    handleApplySuggestions() {
        const suggestions = this.getCurrentSuggestions();
        if (!suggestions) return;

        // Clear current allocations
        this.teamAllocations.clear();

        // Apply suggestions
        suggestions.forEach((team, index) => {
            const teamId = `team-${index + 1}`;
            this.teamAllocations.set(teamId, [...team]);
        });

        this.trackChange('apply-suggestions', { suggestions });
        this.updateUI();
        this.validateAllocation();

        // Hide suggestions panel
        const suggestionsPanel = document.getElementById('suggestions-panel');
        if (suggestionsPanel) {
            suggestionsPanel.classList.add('hidden');
        }
    }

    handleClearAll() {
        if (confirm('Are you sure you want to clear all team allocations?')) {
            this.teamAllocations.clear();
            this.trackChange('clear-all', {});
            this.updateUI();
            this.validateAllocation();
        }
    }

    handleUndo() {
        if (this.changeIndex >= 0) {
            const change = this.changeHistory[this.changeIndex];
            this.revertChange(change);
            this.changeIndex--;
            this.updateUI();
            this.validateAllocation();
            this.updateUndoRedoButtons();
        }
    }

    handleRedo() {
        if (this.changeIndex < this.changeHistory.length - 1) {
            this.changeIndex++;
            const change = this.changeHistory[this.changeIndex];
            this.applyChange(change);
            this.updateUI();
            this.validateAllocation();
            this.updateUndoRedoButtons();
        }
    }

    handleBalanceTeams() {
        const balancedAllocation = this.balanceTeamsBySkill();

        // Clear current allocations
        this.teamAllocations.clear();

        // Apply balanced allocation
        balancedAllocation.forEach((team, index) => {
            const teamId = `team-${index + 1}`;
            this.teamAllocations.set(teamId, [...team]);
        });

        this.trackChange('balance-teams', { allocation: balancedAllocation });
        this.updateUI();
        this.validateAllocation();
    }

    handleMemberSearch(event) {
        const searchTerm = event.target.value.toLowerCase();
        const memberCards = document.querySelectorAll('.member-card');

        memberCards.forEach(card => {
            const memberName = card.dataset.memberName?.toLowerCase() || '';
            const memberUsername = card.dataset.memberUsername?.toLowerCase() || '';

            if (memberName.includes(searchTerm) || memberUsername.includes(searchTerm)) {
                card.style.display = 'block';
                card.classList.add('search-highlight');
            } else {
                card.style.display = searchTerm ? 'none' : 'block';
                card.classList.remove('search-highlight');
            }
        });
    }

    handleTeamSizeChange(event) {
        const teamId = event.target.dataset.teamId;
        const newSize = parseInt(event.target.value);

        // Validate team size doesn't exceed current members
        const currentMembers = this.teamAllocations.get(teamId) || [];
        if (newSize < currentMembers.length) {
            if (confirm(`This will remove ${currentMembers.length - newSize} members from the team. Continue?`)) {
                // Remove excess members
                const removedMembers = currentMembers.splice(newSize);
                this.trackChange('resize-team', { teamId, removedMembers, newSize });
            } else {
                // Reset input value
                event.target.value = currentMembers.length;
                return;
            }
        }

        this.updateUI();
        this.validateAllocation();
    }

    trackChange(type, data) {
        // Remove any changes after current index (for branching history)
        this.changeHistory = this.changeHistory.slice(0, this.changeIndex + 1);

        // Add new change
        this.changeHistory.push({ type, data, timestamp: Date.now() });
        this.changeIndex++;

        // Limit history size
        if (this.changeHistory.length > this.maxHistorySize) {
            this.changeHistory.shift();
            this.changeIndex--;
        }

        this.updateUndoRedoButtons();
    }

    updateUI() {
        this.updateTeamContainers();
        this.updateUnassignedMembers();
        this.updateStatistics();
        this.updateProgressBar();
    }

    updateTeamContainers() {
        const teamContainers = document.querySelectorAll('.team-container');

        teamContainers.forEach(container => {
            const teamId = container.dataset.teamId;
            const members = this.teamAllocations.get(teamId) || [];
            const memberArea = container.querySelector('.team-members');

            if (memberArea) {
                memberArea.innerHTML = members.map(memberId =>
                    this.renderMemberCard(memberId, true)
                ).join('');
            }

            // Update team stats
            this.updateTeamStats(container, members);
        });
    }

    updateUnassignedMembers() {
        const unassignedArea = document.querySelector('.unassigned-members');
        if (!unassignedArea) return;

        const allMembers = this.getAllMembers();
        const assignedMembers = new Set();

        for (const members of this.teamAllocations.values()) {
            members.forEach(id => assignedMembers.add(id));
        }

        const unassignedMembers = allMembers.filter(member => !assignedMembers.has(member.id));

        unassignedArea.innerHTML = unassignedMembers.map(member =>
            this.renderMemberCard(member.id, false)
        ).join('');
    }

    validateAllocation() {
        this.validationErrors = [];
        this.validationWarnings = [];

        // Check minimum teams
        const activeTeams = Array.from(this.teamAllocations.values()).filter(team => team.length > 0);
        if (activeTeams.length < this.validationRules.minTeams) {
            this.validationErrors.push(`At least ${this.validationRules.minTeams} team(s) required`);
        }

        // Check team sizes
        for (const [teamId, members] of this.teamAllocations.entries()) {
            if (members.length > 0 && members.length < this.validationRules.minDriversPerTeam) {
                this.validationWarnings.push(`Team ${teamId} has only ${members.length} member(s)`);
            }
            if (members.length > this.validationRules.maxDriversPerTeam) {
                this.validationErrors.push(`Team ${teamId} exceeds maximum of ${this.validationRules.maxDriversPerTeam} members`);
            }
        }

        // Check unassigned members
        const unassignedCount = this.getUnassignedMembersCount();
        if (unassignedCount > 0) {
            this.validationWarnings.push(`${unassignedCount} member(s) not assigned to any team`);
        }

        this.displayValidation();
    }

    displayValidation() {
        const validationContainer = document.getElementById('validation-messages');
        if (!validationContainer) return;

        validationContainer.innerHTML = '';

        // Display errors
        this.validationErrors.forEach(error => {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'flex items-center p-3 bg-red-50 border border-red-200 rounded-md text-red-700';
            errorDiv.innerHTML = `
                <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                </svg>
                ${error}
            `;
            validationContainer.appendChild(errorDiv);
        });

        // Display warnings
        this.validationWarnings.forEach(warning => {
            const warningDiv = document.createElement('div');
            warningDiv.className = 'flex items-center p-3 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-700';
            warningDiv.innerHTML = `
                <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
                </svg>
                ${warning}
            `;
            validationContainer.appendChild(warningDiv);
        });

        // Update finalize button state
        const finalizeBtn = document.getElementById('finalize-allocation-btn');
        if (finalizeBtn) {
            finalizeBtn.disabled = this.validationErrors.length > 0;
            finalizeBtn.classList.toggle('opacity-50', this.validationErrors.length > 0);
        }
    }

    showDropZones() {
        document.querySelectorAll('.team-container').forEach(container => {
            container.classList.add('drop-zone-active');
        });
    }

    hideDropZones() {
        document.querySelectorAll('.team-container').forEach(container => {
            container.classList.remove('drop-zone-active', 'drag-over');
        });
    }

    showLoadingState(message = 'Loading...') {
        const loadingEl = document.getElementById('loading-overlay');
        if (loadingEl) {
            loadingEl.querySelector('.loading-message').textContent = message;
            loadingEl.classList.remove('hidden');
        }
    }

    hideLoadingState() {
        const loadingEl = document.getElementById('loading-overlay');
        if (loadingEl) {
            loadingEl.classList.add('hidden');
        }
    }

    // Utility methods
    getAllMembers() {
        const memberCards = document.querySelectorAll('.member-card');
        return Array.from(memberCards).map(card => ({
            id: card.dataset.memberId,
            name: card.dataset.memberName,
            username: card.dataset.memberUsername,
            skillRating: parseFloat(card.dataset.skillRating) || 1000
        }));
    }

    getMemberSkillRating(memberId) {
        const memberCard = document.querySelector(`[data-member-id="${memberId}"]`);
        return parseFloat(memberCard?.dataset.skillRating) || 1000;
    }

    getUnassignedMembersCount() {
        const allMembers = this.getAllMembers();
        const assignedMembers = new Set();

        for (const members of this.teamAllocations.values()) {
            members.forEach(id => assignedMembers.add(id));
        }

        return allMembers.length - assignedMembers.size;
    }

    updateUndoRedoButtons() {
        const undoBtn = document.getElementById('undo-btn');
        const redoBtn = document.getElementById('redo-btn');

        if (undoBtn) {
            undoBtn.disabled = this.changeIndex < 0;
            undoBtn.classList.toggle('opacity-50', this.changeIndex < 0);
        }

        if (redoBtn) {
            redoBtn.disabled = this.changeIndex >= this.changeHistory.length - 1;
            redoBtn.classList.toggle('opacity-50', this.changeIndex >= this.changeHistory.length - 1);
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.team-allocation-wizard')) {
        window.teamAllocationWizard = new TeamAllocationWizard();
    }
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TeamAllocationWizard;
}
