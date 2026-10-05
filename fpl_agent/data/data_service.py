"""
Data service providing a single interface for all FPL data operations.

This class orchestrates the entire data pipeline:
fetch → process → store → retrieve
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from ..core.config import Config
from .fetch_fpl import FPLDataFetcher
from .data_store import DataStore
from .data_processor import DataProcessor
from ..utils.fpl_calculations import calculate_fpl_sale_price
from ..utils.keyword_extractor import extract_injury_status

logger = logging.getLogger(__name__)


class DataService:
    """Single interface for all FPL data operations"""
    
    def __init__(self, config: Config):
        """
        Initialize data service.
        
        Args:
            config: FPL configuration object
        """
        self.config = config
        self.fetcher = FPLDataFetcher(config)
        self.store = DataStore()
        self.processor = DataProcessor(config)

    def get_all_gameweek_data(self, gameweek: int, use_cached: bool = False, 
                             filter_unavailable_players_mode: str = "no_filter") -> Dict[str, Any]:
        """
        Get all fpl and fixture data needed for a gameweek in one call.
        
        Args:
            gameweek: Gameweek number
            use_cached: If True, return cached data. If False, fetch fresh data.
            filter_unavailable_players_mode: If "fpl_data_and_enrichments", apply availability filters using both FPL data and enrichments. If "fpl_data_only", apply availability filters using FPL data only. If "no_filter", return all players.
            
        Returns:
            Dictionary containing players and fixtures data
        """
        players = self.get_players(
            use_cached=use_cached,      # Use cache when use_cached is True
            filter_unavailable_players_mode=filter_unavailable_players_mode  # Pass through filtering preference
        )
        
        # Get raw fixtures data for the gameweek
        fixtures = self.get_fixtures(use_cached=use_cached)
        if fixtures and 'fixtures' in fixtures:
            gameweek_fixtures = self.processor.get_gameweek_fixtures(gameweek, fixtures['fixtures'])
        else:
            gameweek_fixtures = []
        
        return {
            'players': players,
            'fixtures': gameweek_fixtures,  # Current gameweek fixtures
            'all_fixtures': fixtures.get('fixtures', []) if fixtures else [],
        }
    
    def get_players(self, use_cached: bool = False, filter_unavailable_players_mode: str = "no_filter") -> Dict[str, Dict[str, Any]]:
        """
        Get players data with smart caching.
        
        Args:
            use_cached: If True, use only cached data. If False, fetch fresh data.
            filter_unavailable_players_mode: If "fpl_data_and_enrichments", apply availability filters using both FPL data and enrichments. If "fpl_data_only", apply availability filters using FPL data only. If "no_filter", return all players.
            
        Returns:
            Dictionary of processed player data keyed by player name
        """
        
        # Step 1: Fetch FPL data if needed
        if not use_cached:
            try:
                logger.info("Fetching fresh FPL data...")
                # Fetch fresh data from API
                bootstrap_data = self.fetcher.get_fpl_static_data()
                # Process the raw data
                fresh_player_data = self.processor.process_fpl_data(bootstrap_data)
                # Save the fresh data to the store
                self.store.save_player_data(fresh_player_data)
                logger.info("Fresh FPL data fetched and saved to store")
            except Exception as e:
                logger.error(f"Failed to fetch fresh FPL data: {e}")
                raise
        else:
            logger.warning("Returning cached FPL data due to use_cached flag")
        
        # Step 2: Load player data for processing
        players_data = self.store.load_player_data()
        if not players_data:
            raise ValueError("No player data available. Run 'fetch' command first.")
        
        players_data = players_data['players']

        # Step 3: Filter players if requested
        filtered_players = self._filter_out_unavailable_players(players_data, filter_unavailable_players_mode)
        
        return filtered_players
    
    def get_fixtures(self, use_cached: bool = False) -> Dict[str, Any]:
        """
        Get fixtures data, either from cache or fresh from API.
        
        Args:
            use_cached: If True, use cached data. If False, fetch fresh data.
            
        Returns:
            Dictionary containing fixtures data and metadata
        """
        
        # Step 1: Fetch fresh fixtures data
        if not use_cached:
            try:
                logger.info("Fetching fresh fixtures data...")
                # Fetch raw fixtures from FPL API
                fixtures_data = self.fetcher.get_fixtures()
                # Get teams data for team name resolution
                bootstrap_data = self.fetcher.get_fpl_static_data()
                teams_data = bootstrap_data.get('teams', [])
                # Process the raw fixtures data
                processed_fixtures = self.processor.process_fixtures_data(fixtures_data, teams_data)
                # Save to cache
                self.store.save_fixtures_data(processed_fixtures)    
                logger.info(f"Successfully fetched and processed {len(processed_fixtures)} fixtures")
            except Exception as e:
                logger.error(f"Failed to fetch fresh fixtures data: {e}")
                raise
        else:
            logger.warning("Returning cached fixtures data due to use_cached flag")

        # Step 2: Load cached fixtures data
        fixtures_data = self.store.load_fixtures_data()
        if not fixtures_data:
            raise ValueError("No fixtures data available. Run 'fetch' command first.")
        
        return fixtures_data
    
    def _filter_out_unavailable_players(self, players_data: Dict[str, Dict[str, Any]], filter_unavailable_players_mode: str = "no_filter") -> Dict[str, Dict[str, Any]]:
        """
        Filter players based on the filter_unavailable_players_mode.

        Args:
            players_data: Dictionary of processed player data
            filter_unavailable_players_mode: If "fpl_data_and_enrichments", apply availability filters using both FPL data and enrichments. If "fpl_data_only", apply availability filters using FPL data only. If "no_filter", return all players.

        Returns:
            Dictionary of filtered player data
        """

        if filter_unavailable_players_mode == "no_filter":
            return players_data
        
        if filter_unavailable_players_mode != "fpl_data_only" and filter_unavailable_players_mode != "fpl_data_and_enrichments":
            raise ValueError(f"Invalid filter_unavailable_players_mode: {filter_unavailable_players_mode}")
        
        # Basic filtering - remove players who can't play according to FPL data
        available_players = self._filter_available_players_by_chance_of_playing(players_data)

        if filter_unavailable_players_mode == "fpl_data_only":
            logger.info(f"Basic filtering: {len(available_players)} players available from {len(players_data)} total")
            return available_players
        
        # Enrichments filtering - remove players who can't play according to enrichments
        available_players = self._filter_by_injury_news(available_players)
        logger.info(f"Enrichments filtering: {len(available_players)} players available from {len(players_data)} total")

        return available_players
    
    def _filter_available_players_by_chance_of_playing(self, players_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Filter out players who can't play (e.g., injured, suspended, etc.) according to FPL data
        Args:
            players_data: Dictionary of processed player data

        Returns:
            Dictionary of filtered player data
        """
        available_players = {}
        
        for player_name, player_data in players_data.items():
            # Check chance of playing (25% threshold)
            chance_of_playing = player_data.get('chance_of_playing', 100)
            if chance_of_playing is not None and chance_of_playing < 25:
                continue
            
            available_players[player_name] = player_data
        
        return available_players
    
    def _filter_by_injury_news(self, players_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Filter out players marked as 'Out' in injury news

        Args:
            players_data: Dictionary of processed player data

        Returns:
            Dictionary of filtered player data
        """
        available_players = {}
        
        for player_name, player_data in players_data.items():
            # Use the shared keyword extraction utility
            injury_status = extract_injury_status(player_name, {player_name: player_data})
            
            # Filter out players marked as "out"
            if not injury_status or injury_status != "out":
                available_players[player_name] = player_data
        
        return available_players
        
    def get_data_status(self, data_store: DataStore) -> Dict[str, Any]:
        """
        Get current data status information.
        
        Args:
            data_store: DataStore instance for loading player data
            
        Returns:
            Dictionary containing data status information
        """
        try:            
            # Check data freshness using DataStore
            fpl_data = data_store.load_player_data()
            fpl_age_hours = None
            if fpl_data and 'cache_timestamp' in fpl_data:
                fpl_age_hours = data_store._calculate_data_age_hours(fpl_data)
            
            # Check embeddings freshness
            embeddings_file = Path("team_data/shared/player_embeddings.json")
            embeddings_age_hours = None
            if embeddings_file.exists():
                file_stat = embeddings_file.stat()
                embeddings_age_hours = (datetime.now().timestamp() - file_stat.st_mtime) / 3600
            
            # Check enriched data freshness
            enriched_age_hours = None
            if fpl_data and 'enrichment_timestamp' in fpl_data:
                enriched_age_hours = data_store._calculate_data_age_hours(fpl_data, 'enrichment_timestamp')
            
            data_status = {
                'fpl_data': {
                    'fresh': fpl_age_hours is not None and fpl_age_hours < 1.0,
                    'age_hours': fpl_age_hours,
                    'available': fpl_data is not None
                },
                'enriched_data': {
                    'fresh': enriched_age_hours is not None and enriched_age_hours < 1.0,
                    'age_hours': enriched_age_hours,
                    'available': enriched_age_hours is not None
                },
                'embeddings': {
                    'fresh': embeddings_age_hours is not None and embeddings_age_hours < 1.0,
                    'age_hours': embeddings_age_hours,
                    'available': embeddings_age_hours is not None
                },
                'overall_status': 'unknown'
            }
            
            # Determine overall status
            if data_status['fpl_data']['available'] and data_status['enriched_data']['available']:
                if data_status['fpl_data']['fresh'] and data_status['enriched_data']['fresh']:
                    data_status['overall_status'] = 'fresh'
                elif data_status['fpl_data']['available'] and data_status['enriched_data']['available']:
                    data_status['overall_status'] = 'partial'
                else:
                    data_status['overall_status'] = 'stale'
            elif data_status['fpl_data']['available']:
                data_status['overall_status'] = 'fpl_only'
            else:
                data_status['overall_status'] = 'none'

            return data_status
                        
        except Exception as e:
            logger.error(f"Failed to get data status: {e}")
            raise

    def get_players_status(self, data_store: DataStore, config: Config) -> Dict[str, Any]:
        """
        Get available players breakdown showing filtering process.
        
        Args:
            data_store: DataStore instance for loading player data
            config: Config instance for embeddings configuration
            
        Returns:
            Dictionary containing player status information
        """
        try:
            # Load player data
            players_data = data_store.load_player_data()
            if not players_data:
                return {
                    'error': 'No player data available. Run \'fetch\' command first.',
                    'total_players': 0,
                    'available_players': 0,
                    'unavailable_players': 0,
                    'use_embeddings': False,
                    'completed_at': datetime.now().isoformat()
                }
            
            # Extract player data
            if 'players' in players_data:
                all_players = players_data['players']
            elif 'player_data' in players_data:
                all_players = players_data['player_data']
            else:
                all_players = players_data
            
            total_players = len(all_players)
            
            # Apply basic filtering to separate available vs unavailable
            available_players = self._filter_available_players_by_chance_of_playing(all_players)
            unavailable_players = {
                name: data for name, data in all_players.items() 
                if name not in available_players
            }
            
            # Check if embedding filtering is available and configured
            embeddings_config = config.get_embeddings_config()
            use_embeddings = embeddings_config.get('use_embeddings', False)
            
            # Initialize result data
            result = {
                'total_players': total_players,
                'available_players': available_players,
                'unavailable_players': unavailable_players,
                'use_embeddings': use_embeddings,
                'completed_at': datetime.now().isoformat()
            }
            
            if use_embeddings:
                # Check if embeddings cache exists
                embeddings_file = Path("team_data/shared/player_embeddings.json")
                if embeddings_file.exists():
                    try:
                        # Apply embedding filtering
                        filtered_players = self._filter_out_unavailable_players(all_players, "fpl_data_and_enrichments")
                        
                        # Calculate players filtered out by embeddings
                        embedding_filtered_out = {
                            name: data for name, data in available_players.items() 
                            if name not in filtered_players
                        }
                        
                        result.update({
                            'filtered_players': filtered_players,
                            'embedding_filtered_out': embedding_filtered_out
                        })
                        
                    except Exception as e:
                        logger.warning(f"Embedding filtering failed: {e}")
                        # Continue without embedding data
                        pass
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get players status: {e}")
            raise

    def get_current_team_player_data(self, current_team: Dict[str, Any], 
                                    use_enrichments: bool = False,
                                    use_cached: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Get comprehensive data for all players in the current team.
        
        Args:
            current_team: Current team data from gwNN.json
            use_enrichments: Whether to include expert insights and injury news
            use_cached: Whether to use cached data only
            
        Returns:
            Dictionary of player data indexed by full name, including:
            - Current market price (from player_data.json)
            - Purchase price (from gwNN.json)
            - Expert insights (if enrichments available)
            - Injury news (if enrichments available)
            - All other player attributes
            
        Raises:
            ValueError: If any player in current team is not found in market data
        """
        try:
            # 1. Get all player names from current team
            team_players = current_team['starting'] + current_team['substitutes']
            player_names = [player['name'] for player in team_players]
            
            # 2. Get current market data for these specific players
            all_players_data = self.get_players(use_cached=use_cached)
            current_market_data = {
                name: all_players_data[name] 
                for name in player_names 
                if name in all_players_data
            }
            
            # 3. Validate all players found
            missing_players = [name for name in player_names if name not in current_market_data]
            if missing_players:
                raise ValueError(
                    f"Players not found in current market data: {', '.join(missing_players)}. "
                    f"This indicates a data inconsistency that must be resolved."
                )
            
            # 4. Get enriched data if requested
            enriched_data = {}
            if use_enrichments:
                enriched_data = self._get_team_enrichments(player_names, use_cached)
            
            # 5. Merge all data sources
            final_player_data = {}
            for player_name in player_names:
                # Get team data (purchase price, position, etc.)
                team_player = next(p for p in team_players if p['name'] == player_name)
                
                # Get market data (current price, etc.)
                market_player = current_market_data[player_name]
                
                # Get enriched data if available
                player_enrichments = enriched_data.get(player_name, {})
                
                # Calculate sale price using FPL formula
                current_price = market_player.get('now_cost', 0) / 10.0
                purchase_price = team_player['price']
                sale_price = calculate_fpl_sale_price(current_price, purchase_price)
                
                # Merge all data
                final_player_data[player_name] = {
                    # From team data
                    'name': team_player['name'],
                    'position': team_player['position'],
                    'team': team_player['team'],
                    'purchase_price': purchase_price,
                    
                    # From market data
                    'current_price': current_price,
                    'form': market_player.get('form', ''),
                    'total_points': market_player.get('total_points', 0),
                    'minutes': market_player.get('minutes', 0),
                    'chance_of_playing': market_player.get('chance_of_playing', 100),
                    'goals_scored': market_player.get('goals_scored', 0),
                    'assists': market_player.get('assists', 0),
                    'clean_sheets': market_player.get('clean_sheets', 0),
                    'goals_conceded': market_player.get('goals_conceded', 0),
                    'saves': market_player.get('saves', 0),
                    'bonus': market_player.get('bonus', 0),
                    'bps': market_player.get('bps', 0),
                    'ict_index': market_player.get('ict_index', 0.0),
                    
                    # Calculated sale price
                    'sale_price': sale_price,
                    
                    # From enrichments (if available)
                    'expert_insights': player_enrichments.get('expert_insights', 'None'),
                    'injury_news': player_enrichments.get('injury_news', 'None'),
                    
                    # Additional market data
                    'selected_by_percent': market_player.get('selected_by_percent', 0),
                    'transfers_in': market_player.get('transfers_in', 0),
                    'transfers_out': market_player.get('transfers_out', 0),
                }
            
            logger.info(f"Successfully loaded data for {len(final_player_data)} team players")
            return final_player_data
            
        except Exception as e:
            logger.error(f"Failed to get current team player data: {e}")
            raise
    
    def _get_team_enrichments(self, player_names: List[str], use_cached: bool) -> Dict[str, Dict[str, Any]]:
        """
        Get enriched data (expert insights and injury news) for specific players.
        
        Args:
            player_names: List of player names to enrich
            use_cached: Whether to use cached data only
            
        Returns:
            Dictionary of enriched data indexed by player name
        """
        try:
            # Load existing enriched data from cache
            cached_data = self.store.load_player_data()
            if not cached_data:
                logger.info("No player data available for team enrichments")
                return {}
            
            # Extract enrichments for the specific players (works with --cached-only too)
            enriched_data = {}
            for player_name in player_names:
                player_enrichments = {}
                
                # Get expert insights if available
                if 'expert_insights' in cached_data and player_name in cached_data['expert_insights']:
                    player_enrichments['expert_insights'] = cached_data['expert_insights'][player_name]
                
                # Get injury news if available
                if 'injury_news' in cached_data and player_name in cached_data['injury_news']:
                    player_enrichments['injury_news'] = cached_data['injury_news'][player_name]
                
                if player_enrichments:
                    enriched_data[player_name] = player_enrichments
            
            logger.info(f"Loaded enrichments for {len(enriched_data)} out of {len(player_names)} players")
            return enriched_data
            
        except Exception as e:
            logger.warning(f"Failed to load team enrichments: {e}")
            return {}
