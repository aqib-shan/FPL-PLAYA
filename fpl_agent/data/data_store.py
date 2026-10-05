"""
Data store for managing player_data.json file persistence.

This class handles file I/O operations and provides age-based warnings
without forcing data refresh.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class DataStore:
    """
    Manages persistence of shared FPL data (players, fixtures, embeddings) that all teams can access.
    
    This class handles data that is common across all FPL teams, such as:
    - Player statistics and information
    - Fixture schedules
    - Player embeddings for analysis
    
    Individual team data (squads, transfers, etc.) is managed by TeamManager.
    """
    
    def __init__(self, data_dir: str = "team_data"):
        """
        Initialize data store for shared FPL data.
        
        Args:
            data_dir: Base directory (default: "team_data"). Shared data will be stored in 
                     "{data_dir}/shared/" subdirectory.
        """
        # Set up directory structure for shared FPL data
        self.data_dir = Path(data_dir)
        self.shared_dir = self.data_dir / "shared"
        
        # Create directories if they don't exist
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        
        # Define file paths for shared data
        self.player_data_file = self.shared_dir / "player_data.json"
        self.fixtures_data_file = self.shared_dir / "fixtures.json"
    
    def load_player_data(self) -> Optional[Dict[str, Any]]:
        """
        Load player data from JSON file.
        
        Returns:
            Full data dictionary (including metadata) or None if file doesn't exist
        """
        if not self.player_data_file.exists():
            logger.info("No player data file found")
            return None
        
        try:
            with open(self.player_data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check data age and provide warnings
            self._check_data_age(data)
            return data
            
        except Exception as e:
            logger.error(f"Failed to load player data: {e}")
            return None
    
    def save_player_data(self, player_data: Dict[str, Any]) -> None:
        """
        Save player data to JSON file.
        
        Args:
            player_data: Player data to save (can be either raw player data or enriched data structure)
        """
        try:
            # Check if this is already an enriched data structure
            if 'players' in player_data:
                # This is already the right format, just add/update cache timestamp
                data_to_save = player_data.copy()
                data_to_save['cache_timestamp'] = datetime.now().isoformat()
                # Calculate total players from the players dictionary
                total_players = len(data_to_save['players'])
                data_to_save['total_players'] = total_players
            else:
                # This is raw player data, wrap it in the enriched structure
                data_to_save = {
                    'cache_timestamp': datetime.now().isoformat(),
                    'players': player_data,
                    'total_players': len(player_data)
                }
                total_players = len(player_data)
            
            with open(self.player_data_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved player data with {total_players} players to {self.player_data_file}")
            
        except Exception as e:
            logger.error(f"Failed to save player data: {e}")
            raise
    
    def load_fixtures_data(self) -> Optional[Dict[str, Any]]:
        """
        Load fixtures data from JSON file.
        
        Returns:
            Full fixtures data dictionary (including metadata) or None if file doesn't exist
        """
        if not self.fixtures_data_file.exists():
            logger.info("No fixtures data file found")
            return None
        
        try:
            with open(self.fixtures_data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check data age and provide warnings
            self._check_data_age(data)
            return data
            
        except Exception as e:
            logger.error(f"Failed to load fixtures data: {e}")
            return None
    
    def save_fixtures_data(self, fixtures_data: List[Dict[str, Any]]) -> None:
        """
        Save fixtures data to JSON file.
        
        Args:
            fixtures_data: List of fixtures data to save
        """
        try:
            data_to_save = {
                'cache_timestamp': datetime.now().isoformat(),
                'fixtures': fixtures_data,
                'total_fixtures': len(fixtures_data)
            }
            
            with open(self.fixtures_data_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved fixtures data with {len(fixtures_data)} fixtures to {self.fixtures_data_file}")
            
        except Exception as e:
            logger.error(f"Failed to save fixtures data: {e}")
            raise
    
    def _check_data_age(self, data: Dict[str, Any]) -> None:
        """
        Check data age and provide appropriate warnings.
        
        Args:
            data: Loaded data dictionary
        """
        age_hours = self._calculate_data_age_hours(data)
        if age_hours is None:
            warning_msg = "⚠️  Using player data with unknown age. Consider refreshing for fresh data."
            logger.warning(warning_msg)
            return
        
        # Age thresholds
        CRITICAL_AGE_HOURS = 168  # 7 days
        WARNING_AGE_HOURS = 24    # 1 day
        
        if age_hours > CRITICAL_AGE_HOURS:
            warning_msg = f"⚠️  CRITICAL: Using player data that is {age_hours:.1f} hours old ({age_hours/24:.1f} days). Data is very outdated!"
            logger.warning(warning_msg)
        elif age_hours > WARNING_AGE_HOURS:
            warning_msg = f"⚠️  Using player data that is {age_hours:.1f} hours old. Consider refreshing for fresh data."
            logger.warning(warning_msg)
        else:
            logger.info(f"Using player data ({age_hours:.1f} hours old)")
    
    def _calculate_data_age_hours(self, data: Dict[str, Any], timestamp_field: str = 'cache_timestamp') -> Optional[float]:
        """
        Calculate the age of stored data in hours.
        
        Args:
            data: Loaded data dictionary
            timestamp_field: Field name containing the timestamp (default: 'cache_timestamp')
            
        Returns:
            Age in hours or None if no data or timestamp
        """
        timestamp = data.get(timestamp_field)
        if not timestamp:
            return None
        
        try:
            cache_time = datetime.fromisoformat(timestamp)
            return (datetime.now() - cache_time).total_seconds() / 3600
        except Exception:
            return None