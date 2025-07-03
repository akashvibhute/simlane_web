"""
S3 storage utility for iRacing API responses.

This module provides a clean interface for storing and retrieving compressed
JSON API responses in S3 using parameter-based keys (series_id, season_id, etc).
"""

import gzip
import json
import logging
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from storages.backends.s3 import S3Storage

logger = logging.getLogger(__name__)


class APIResponseS3Storage:
    """
    S3 storage for API responses with compression and parameter-based keys.
    
    This class handles:
    - Automatic gzip compression of JSON data
    - Parameter-based S3 key generation (series_id, season_id, etc)
    - Metadata storage (timestamp, data type, parameters)
    - Efficient retrieval and caching
    """
    
    def __init__(self):
        # Initialize S3 storage with API response configuration
        api_storage_config = settings.API_RESPONSE_STORAGE["OPTIONS"]
        
        self.storage = S3Storage(**{
            'access_key': api_storage_config['access_key'],
            'secret_key': api_storage_config['secret_key'],
            'bucket_name': api_storage_config['bucket_name'],
            'region_name': api_storage_config['region_name'],
            'location': api_storage_config.get('location', 'api_responses'),
            'file_overwrite': api_storage_config.get('file_overwrite', False),
            'default_acl': api_storage_config.get('default_acl', 'private'),
            'object_parameters': api_storage_config.get('object_parameters', {}),
        })
    
    def _generate_key(self, data_type: str, **params) -> str:
        """
        Generate S3 key based on data type and parameters.
        
        Args:
            data_type: Type of data ('series', 'seasons', 'schedules', etc.)
            **params: Additional parameters (series_id, season_id, etc.)
            
        Returns:
            S3 key for the data
            
        Examples:
            _generate_key('series') -> 'series/2024/01/series_20240115_143022.json.gz'
            _generate_key('seasons', series_ids=[123,456]) -> 'seasons/2024/01/seasons_123_456_20240115_143022.json.gz'
            _generate_key('schedule', season_id=789) -> 'schedules/2024/01/schedule_789_20240115_143022.json.gz'
        """
        now = timezone.now()
        date_path = now.strftime('%Y/%m')
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        
        # Build filename based on data type and parameters
        filename_parts = [data_type]
        
        # Add parameters to filename for uniqueness
        if 'series_id' in params:
            filename_parts.append(str(params['series_id']))
        if 'season_id' in params:
            filename_parts.append(str(params['season_id']))
        if 'series_ids' in params and params['series_ids']:
            # For multiple series, use first few IDs
            ids = params['series_ids'][:3]  # Limit to avoid long filenames
            filename_parts.extend([str(id) for id in ids])
        
        filename_parts.append(timestamp)
        
        filename = '_'.join(filename_parts) + '.json.gz'
        
        return f"{data_type}/{date_path}/{filename}"
    
    def store_response(self, data_type: str, data: Any, **params) -> Optional[str]:
        """
        Store API response data in S3 with compression.
        
        Args:
            data_type: Type of data ('series', 'seasons', 'schedules', etc.)
            data: JSON-serializable data to store
            **params: Additional parameters for key generation
            
        Returns:
            S3 key if successful, None if failed
        """
        try:
            # Generate S3 key
            s3_key = self._generate_key(data_type, **params)
            
            # Prepare metadata
            metadata = {
                'data_type': data_type,
                'timestamp': timezone.now().isoformat(),
                'params': json.dumps(params, sort_keys=True),
                'compressed': 'true',
            }
            
            # Compress and store data
            json_data = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
            compressed_data = gzip.compress(json_data.encode('utf-8'))
            
            # Create file-like object for S3 storage
            content_file = ContentFile(compressed_data)
            
            # Store in S3
            saved_path = self.storage.save(s3_key, content_file)
            
            logger.info(
                f"Stored {data_type} data to S3: {saved_path} "
                f"(original: {len(json_data)} bytes, compressed: {len(compressed_data)} bytes)"
            )
            
            return saved_path
            
        except Exception as e:
            logger.error(f"Failed to store {data_type} data to S3: {e}")
            return None
    
    def retrieve_response(self, data_type: str, **params) -> Optional[Any]:
        """
        Retrieve the most recent API response data from S3.
        
        Args:
            data_type: Type of data to retrieve
            **params: Parameters used to filter/find the data
            
        Returns:
            Decompressed JSON data if found, None otherwise
        """
        try:
            # Find the most recent file for this data type and parameters
            s3_key = self._find_latest_key(data_type, **params)
            
            if not s3_key:
                logger.debug(f"No cached {data_type} data found in S3")
                return None
            
            # Retrieve and decompress data
            with self.storage.open(s3_key, 'rb') as f:
                compressed_data = f.read()
            
            json_data = gzip.decompress(compressed_data).decode('utf-8')
            data = json.loads(json_data)
            
            logger.info(f"Retrieved {data_type} data from S3: {s3_key}")
            return data
            
        except Exception as e:
            logger.warning(f"Failed to retrieve {data_type} data from S3: {e}")
            return None
    
    def _find_latest_key(self, data_type: str, **params) -> Optional[str]:
        """
        Find the most recent S3 key for the given data type and parameters.
        
        This is a simplified implementation - in production you might want to
        use S3 list operations with proper filtering and sorting.
        """
        try:
            # List files in the data type directory
            prefix = f"{data_type}/"
            
            # Use storage's listdir if available, otherwise try direct S3 listing
            if hasattr(self.storage, 'listdir'):
                dirs, files = self.storage.listdir(prefix)
                
                # Find files that match our parameters
                matching_files = []
                for file in files:
                    if file.endswith('.json.gz'):
                        # Simple matching - check if params are in filename
                        matches = True
                        if 'series_id' in params:
                            if str(params['series_id']) not in file:
                                matches = False
                        if 'season_id' in params:
                            if str(params['season_id']) not in file:
                                matches = False
                        
                        if matches:
                            matching_files.append(f"{prefix}{file}")
                
                # Return the most recent (alphabetically last due to timestamp format)
                if matching_files:
                    return sorted(matching_files)[-1]
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to find latest key for {data_type}: {e}")
            return None
    
    def get_response_age(self, data_type: str, **params) -> Optional[float]:
        """
        Get the age of the most recent cached response in seconds.
        
        Returns:
            Age in seconds if found, None if no cached data exists
        """
        try:
            s3_key = self._find_latest_key(data_type, **params)
            if not s3_key:
                return None
            
            # Extract timestamp from filename
            # Format: data_type_[params]_YYYYMMDD_HHMMSS.json.gz
            filename = s3_key.split('/')[-1]
            timestamp_part = filename.split('_')[-1].replace('.json.gz', '')
            
            if len(timestamp_part) == 15:  # YYYYMMDD_HHMMSS format
                stored_time = datetime.strptime(timestamp_part, '%Y%m%d_%H%M%S')
                stored_time = timezone.make_aware(stored_time)
                
                age_seconds = (timezone.now() - stored_time).total_seconds()
                return age_seconds
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get response age for {data_type}: {e}")
            return None
    
    def clear_cache(self, data_type: Optional[str] = None, **params):
        """
        Clear cached responses from S3.
        
        Args:
            data_type: Specific data type to clear, or None for all
            **params: Additional parameters to filter which files to clear
        """
        try:
            if data_type:
                # Clear specific data type
                prefix = f"{data_type}/"
                logger.info(f"Clearing {data_type} cache from S3")
            else:
                # Clear all API responses
                prefix = ""
                logger.info("Clearing all API response cache from S3")
            
            # This is a simplified implementation
            # In production, you'd want to implement proper S3 bulk deletion
            logger.warning("Cache clearing not fully implemented - manual S3 cleanup required")
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")


# Global instance for use throughout the application
api_response_storage = APIResponseS3Storage() 