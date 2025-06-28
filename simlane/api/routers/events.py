# Legacy event API endpoints removed
#
# The following models and their associated API endpoints have been removed:
# - TeamAllocation and TeamAllocationMember
# - TeamEventStrategy and StintAssignment
#
# These have been replaced by the enhanced participation system:
# - EventParticipation model for unified event participation
# - AvailabilityWindow model for driver availability
# - Team model for team management
#
# New API endpoints should be built using the enhanced models.
# See simlane.teams.models for the new model structure.

from ninja import Router

router = Router()

# TODO: Implement new API endpoints using EventParticipation model
# TODO: Add availability management endpoints
# TODO: Add team formation endpoints
