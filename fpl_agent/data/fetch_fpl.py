"""
FPL Data Fetcher
Fetches data from the FPL API
"""

import logging
import requests
from typing import Dict, Any, Optional, List

from ..core.config import Config

logger = logging.getLogger(__name__)


class FPLDataFetcher:
    """Fetches data from the FPL API"""
    
    def __init__(self, config: Config):
        """
        Initialize the fetcher.
        
        Args:
            config: FPL configuration object
        """
        self.config = config
        self.base_url = "https://fantasy.premierleague.com/api/"
        self.session = requests.Session()
        
        # Set user agent to avoid being blocked
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """
        Make a request to the FPL API.
        
        Args:
            endpoint: API endpoint to request
            
        Returns:
            Response data as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.info(f"Fetching data from {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Successfully fetched data from {endpoint}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch data from {endpoint}: {e}")
            raise
        except ValueError as e:
            logger.error(f"Failed to parse JSON response from {endpoint}: {e}")
            raise
    
    def get_fpl_static_data(self) -> Dict[str, Any]:
        """Get all FPL static data from bootstrap-static endpoint"""
        return self._make_request("bootstrap-static/")
    
    def get_fixtures(self) -> List[Dict[str, Any]]:
        """Get all fixtures"""
        logger.info("Fetching FPL fixtures...")
        return self._make_request("fixtures/")
    
    def get_current_gameweek(self) -> Optional[int]:
        """Get the current gameweek number"""
        try:
            bootstrap_data = self.get_fpl_static_data()
            events = bootstrap_data.get('events', [])
            
            for event in events:
                if event.get('is_current', False):
                    return event['id']
            
            # If no current gameweek found, return the first gameweek
            if events:
                return events[0]['id']
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get current gameweek: {e}")
            return None
    
