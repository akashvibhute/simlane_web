from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from django.db.models import Q
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Standardized search result format"""
    id: str
    type: str
    title: str
    description: str
    url: str
    image_url: Optional[str] = None
    metadata: Dict[str, Any] = None
    relevance_score: float = 0.0
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SearchFilters:
    """Search filtering options"""
    types: Optional[List[str]] = None
    simulator: Optional[str] = None
    event_status: Optional[str] = None
    user_verified: Optional[bool] = None
    date_range: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.types is None:
            self.types = []


class SearchService(ABC):
    """Abstract search service interface for easy backend switching"""
    
    @abstractmethod
    def search(self, query: str, filters: Optional[SearchFilters] = None, 
               limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Perform search across all indexed content
        
        Returns:
            {
                'results': List[SearchResult],
                'total_count': int,
                'facets': Dict[str, Any],
                'query_time_ms': float
            }
        """
        pass
    
    @abstractmethod
    def search_by_type(self, query: str, model_type: str, 
                       limit: int = 20) -> List[SearchResult]:
        """Search within a specific model type"""
        pass
    
    @abstractmethod
    def get_suggestions(self, query: str, limit: int = 5) -> List[str]:
        """Get search suggestions/autocomplete"""
        pass
    
    @abstractmethod
    def index_model(self, instance) -> bool:
        """Index a single model instance"""
        pass
    
    @abstractmethod
    def remove_from_index(self, instance) -> bool:
        """Remove instance from search index"""
        pass
    
    @abstractmethod
    def reindex_all(self) -> bool:
        """Rebuild entire search index"""
        pass


class SearchDocumentBuilder:
    """Builds standardized search documents from Django model instances"""
    
    @staticmethod
    def build_document(instance) -> SearchResult:
        """Build a search document for any model instance"""
        model_name = instance._meta.model_name
        app_label = instance._meta.app_label
        
        # Dispatch to specific builder method
        builder_method = getattr(
            SearchDocumentBuilder, 
            f'_build_{model_name}_document', 
            SearchDocumentBuilder._build_generic_document
        )
        
        return builder_method(instance)
    
    @staticmethod
    def _build_user_document(user) -> SearchResult:
        return SearchResult(
            id=f"user_{user.pk}",
            type="user",
            title=user.get_full_name() or user.username,
            description=f"SimLane member since {user.date_joined.year}",
            url=user.get_absolute_url(),
            metadata={
                'username': user.username,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined.isoformat(),
                'profile_count': user.linked_sim_profiles.count()
            }
        )
    
    @staticmethod
    def _build_simprofile_document(profile) -> SearchResult:
        return SearchResult(
            id=f"simprofile_{profile.pk}",
            type="sim_profile",
            title=f"{profile.profile_name} ({profile.simulator.name})",
            description=f"Sim racing profile on {profile.simulator.name}" + 
                       (f" - Linked to {profile.linked_user.username}" if profile.linked_user else ""),
            url=profile.get_absolute_url(),
            metadata={
                'simulator': profile.simulator.name,
                'simulator_slug': profile.simulator.slug,
                'is_verified': profile.is_verified,
                'is_public': profile.is_public,
                'linked_user': profile.linked_user.username if profile.linked_user else None,
                'last_active': profile.last_active.isoformat() if profile.last_active else None
            }
        )
    
    @staticmethod
    def _build_event_document(event) -> SearchResult:
        return SearchResult(
            id=f"event_{event.pk}",
            type="event",
            title=event.name,
            description=event.description[:200] + "..." if len(event.description) > 200 else event.description,
            url=f"/events/{event.slug}/",  # You'll need to add this URL pattern
            metadata={
                'simulator': event.simulator.name,
                'simulator_slug': event.simulator.slug,
                'status': event.status,
                'event_type': event.type,
                'event_source': event.event_source,
                'visibility': event.visibility,
                'event_date': event.event_date.isoformat() if event.event_date else None,
                'track': event.sim_layout.sim_track.display_name,
                'track_country': event.sim_layout.sim_track.track_model.country,
                'organizer': event.effective_organizer
            }
        )
    
    @staticmethod
    def _build_team_document(team) -> SearchResult:
        return SearchResult(
            id=f"team_{team.pk}",
            type="team",
            title=team.name,
            description=team.description[:200] + "..." if len(team.description) > 200 else team.description,
            url=f"/teams/{team.slug}/",  # You'll need to add this URL pattern
            image_url=team.logo_url or None,
            metadata={
                'is_public': team.is_public,
                'is_active': team.is_active,
                'is_imported': team.is_imported,
                'club': team.club.name if team.club else None,
                'member_count': team.members.count(),
                'source_simulator': team.source_simulator.name if team.source_simulator else None
            }
        )
    
    @staticmethod
    def _build_club_document(club) -> SearchResult:
        return SearchResult(
            id=f"club_{club.pk}",
            type="club",
            title=club.name,
            description=club.description[:200] + "..." if len(club.description) > 200 else club.description,
            url=f"/clubs/{club.slug}/",  # You'll need to add this URL pattern
            image_url=club.logo_url or None,
            metadata={
                'is_public': club.is_public,
                'is_active': club.is_active,
                'member_count': club.members.count(),
                'website': club.website
            }
        )
    
    @staticmethod
    def _build_simulator_document(simulator) -> SearchResult:
        return SearchResult(
            id=f"simulator_{simulator.pk}",
            type="simulator",
            title=simulator.name,
            description=simulator.description[:200] + "..." if len(simulator.description) > 200 else simulator.description,
            url=f"/sim/{simulator.slug}/",
            image_url=simulator.logo_url or None,
            metadata={
                'is_active': simulator.is_active,
                'website': simulator.website,
                'car_count': simulator.sim_cars.count(),
                'track_count': simulator.sim_tracks.count(),
                'profile_count': simulator.sim_profiles.count()
            }
        )
    
    @staticmethod
    def _build_trackmodel_document(track) -> SearchResult:
        return SearchResult(
            id=f"track_{track.pk}",
            type="track",
            title=track.name,
            description=f"Racing track in {track.location}, {track.country}",
            url=f"/tracks/{track.slug}/",
            image_url=track.default_image_url or None,
            metadata={
                'country': track.country,
                'location': track.location,
                'latitude': track.latitude,
                'longitude': track.longitude,
                'simulator_count': track.sim_tracks.count()
            }
        )
    
    @staticmethod
    def _build_carmodel_document(car) -> SearchResult:
        return SearchResult(
            id=f"car_{car.pk}",
            type="car",
            title=f"{car.manufacturer} {car.name}",
            description=f"{car.car_class.name} from {car.release_year or 'Unknown'}",
            url=f"/cars/{car.slug}/",
            image_url=car.default_image_url or None,
            metadata={
                'manufacturer': car.manufacturer,
                'car_class': car.car_class.name,
                'release_year': car.release_year,
                'simulator_count': car.sim_cars.count()
            }
        )
    
    @staticmethod
    def _build_generic_document(instance) -> SearchResult:
        """Fallback for models without specific builders"""
        return SearchResult(
            id=f"{instance._meta.model_name}_{instance.pk}",
            type=instance._meta.model_name,
            title=str(instance),
            description=f"{instance._meta.verbose_name} from {instance._meta.app_label}",
            url=f"/{instance._meta.app_label}/{instance._meta.model_name}/{instance.pk}/",
            metadata={}
        )


class PostgresSearchService(SearchService):
    """PostgreSQL full-text search implementation"""
    
    def __init__(self):
        self.searchable_models = self._get_searchable_models()
    
    def _get_searchable_models(self):
        """Define which models are searchable"""
        return {
            'user': apps.get_model('users', 'User'),
            'sim_profile': apps.get_model('sim', 'SimProfile'),
            'event': apps.get_model('sim', 'Event'),
            'team': apps.get_model('teams', 'Team'),
            'club': apps.get_model('teams', 'Club'),
            'simulator': apps.get_model('sim', 'Simulator'),
            'track': apps.get_model('sim', 'TrackModel'),
            'car': apps.get_model('sim', 'CarModel'),
        }
    
    def search(self, query: str, filters: Optional[SearchFilters] = None, 
               limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Perform comprehensive search across all models"""
        import time
        start_time = time.time()
        
        if not query.strip():
            return {
                'results': [],
                'total_count': 0,
                'facets': {},
                'query_time_ms': 0
            }
        
        filters = filters or SearchFilters()
        all_results = []
        
        # Search each model type
        search_models = filters.types if filters.types else list(self.searchable_models.keys())
        
        for model_type in search_models:
            try:
                results = self.search_by_type(query, model_type, limit=limit)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Error searching {model_type}: {e}")
                continue
        
        # Sort by relevance score
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Apply offset and limit
        paginated_results = all_results[offset:offset + limit]
        
        # Build facets
        facets = self._build_facets(all_results)
        
        query_time_ms = (time.time() - start_time) * 1000
        
        return {
            'results': paginated_results,
            'total_count': len(all_results),
            'facets': facets,
            'query_time_ms': query_time_ms
        }
    
    def search_by_type(self, query: str, model_type: str, limit: int = 20) -> List[SearchResult]:
        """Search within a specific model type using PostgreSQL full-text search"""
        if model_type not in self.searchable_models:
            return []
        
        model_class = self.searchable_models[model_type]
        search_query = SearchQuery(query)
        
        # Define search fields for each model
        search_config = self._get_search_config(model_type)
        search_vector = SearchVector(*search_config['fields'], config='english')
        
        try:
            queryset = model_class.objects.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(search=search_query)
            
            # Apply model-specific filters
            queryset = self._apply_model_filters(queryset, model_type)
            
            # Order by relevance
            queryset = queryset.order_by('-rank')[:limit]
            
            # Convert to search results
            results = []
            for instance in queryset:
                try:
                    doc = SearchDocumentBuilder.build_document(instance)
                    doc.relevance_score = float(instance.rank) if hasattr(instance, 'rank') else 0.0
                    results.append(doc)
                except Exception as e:
                    logger.error(f"Error building document for {instance}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching {model_type}: {e}")
            return []
    
    def _get_search_config(self, model_type: str) -> Dict[str, List[str]]:
        """Define searchable fields for each model type"""
        configs = {
            'user': {
                'fields': ['username', 'name', 'email']
            },
            'sim_profile': {
                'fields': ['profile_name', 'linked_user__username', 'linked_user__name']
            },
            'event': {
                'fields': ['name', 'description', 'sim_layout__sim_track__display_name']
            },
            'team': {
                'fields': ['name', 'description']
            },
            'club': {
                'fields': ['name', 'description']
            },
            'simulator': {
                'fields': ['name', 'description']
            },
            'track': {
                'fields': ['name', 'location', 'country']
            },
            'car': {
                'fields': ['name', 'manufacturer', 'car_class__name']
            },
        }
        return configs.get(model_type, {'fields': ['name']})
    
    def _apply_model_filters(self, queryset, model_type: str):
        """Apply model-specific visibility and status filters"""
        if model_type == 'sim_profile':
            queryset = queryset.filter(is_public=True)
        elif model_type == 'event':
            queryset = queryset.exclude(status='DRAFT')
        elif model_type == 'team':
            queryset = queryset.filter(is_public=True, is_active=True)
        elif model_type == 'club':
            queryset = queryset.filter(is_active=True)
        elif model_type == 'simulator':
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    def _build_facets(self, results: List[SearchResult]) -> Dict[str, Any]:
        """Build facet counts from search results"""
        facets = {}
        
        # Count by type
        type_counts = {}
        for result in results:
            type_counts[result.type] = type_counts.get(result.type, 0) + 1
        
        facets['types'] = type_counts
        
        # Count by simulator (for relevant types)
        simulator_counts = {}
        for result in results:
            if result.type in ['sim_profile', 'event'] and 'simulator' in result.metadata:
                sim = result.metadata['simulator']
                simulator_counts[sim] = simulator_counts.get(sim, 0) + 1
        
        if simulator_counts:
            facets['simulators'] = simulator_counts
        
        return facets
    
    def get_suggestions(self, query: str, limit: int = 5) -> List[str]:
        """Get search suggestions - simplified implementation"""
        suggestions = []
        
        if len(query) < 2:
            return suggestions
        
        # Get suggestions from different models
        try:
            # User suggestions
            User = self.searchable_models['user']
            users = User.objects.filter(
                Q(username__istartswith=query) | Q(name__istartswith=query)
            )[:limit//2]
            suggestions.extend([u.username for u in users])
            
            # Event suggestions  
            Event = self.searchable_models['event']
            events = Event.objects.filter(name__istartswith=query)[:limit//2]
            suggestions.extend([e.name for e in events])
            
        except Exception as e:
            logger.error(f"Error getting suggestions: {e}")
        
        return suggestions[:limit]
    
    def index_model(self, instance) -> bool:
        """For PostgreSQL, no separate indexing needed - handled by Django ORM"""
        return True
    
    def remove_from_index(self, instance) -> bool:
        """For PostgreSQL, no separate removal needed - handled by Django ORM"""
        return True
    
    def reindex_all(self) -> bool:
        """For PostgreSQL, no reindexing needed - indexes are maintained automatically"""
        return True


# Service factory
def get_search_service() -> SearchService:
    """Factory function to get the configured search service"""
    from django.conf import settings
    
    backend = getattr(settings, 'SEARCH_BACKEND', 'postgres')
    
    if backend == 'postgres':
        return PostgresSearchService()
    elif backend == 'meilisearch':
        # Future implementation
        raise NotImplementedError("Meilisearch backend not yet implemented")
    elif backend == 'elasticsearch':
        # Future implementation  
        raise NotImplementedError("Elasticsearch backend not yet implemented")
    else:
        raise ValueError(f"Unknown search backend: {backend}") 