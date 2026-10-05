"""
Embedding-based player filtering for FPL Optimizer
"""

import logging
import json
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from datetime import datetime
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from ..core.config import Config
from ..utils.keyword_extractor import (
    extract_expert_bonus,
    extract_expert_tier,
    scale_scores_0_to_10,
    TIER_AVOID,
    TIER_NAMES,
)

logger = logging.getLogger(__name__)


class EmbeddingFilter:
    """
    Embedding-based player filtering using configurable sentence transformer models.
    
    This class handles:
    - Loading and caching player embeddings (configurable model)
    - Position-specific query encoding
    - Cosine similarity scoring
    - Top player selection per position
    - Hybrid scoring with keyword bonuses
    
    Configuration is loaded from config.yaml under the 'embeddings' section.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.model = None
        self.embeddings_cache = {}
        
        # Load configuration from config file
        embeddings_config = self.config.get_embeddings_config()
        
        # Load position queries from config
        self.position_queries = embeddings_config.get('position_queries', {
            'GK': "Must-have OR recommended, fit, high points, clean sheet, saves, consistent starter, good fixtures. NOT out of form, injured, suspended.",
            'DEF': "Must-have OR recommended, fit, high points, clean sheet, attacking potential, consistent starter, good fixtures. NOT out of form, injured, suspended.",  
            'MID': "Must-have OR recommended, fit, high points, goals, assists, consistent starter, set pieces, penalties, good fixtures. NOT out of form, injured, suspended.",
            'FWD': "Must-have OR recommended, fit, high points, goals, assists, consistent starter, set pieces, penalties, good fixtures. NOT out of form, injured, suspended."
        })
        
        # Load selection counts from config
        self.selection_counts = embeddings_config.get('selection_counts', {
            'GK': 15,
            'DEF': 60,
            'MID': 70,
            'FWD': 30
        })
    
    def _get_embeddings_cache_path(self) -> Path:
        """Get the path to the embeddings cache file"""
        cache_dir = Path("team_data/shared")
        cache_dir.mkdir(exist_ok=True)
        return cache_dir / "player_embeddings.json"
    
    def _load_embeddings_model(self):
        """Load the sentence-transformers model from configuration"""
        try:
            # Get model configuration
            embeddings_config = self.config.get_embeddings_config()
            model_name = embeddings_config.get('model', 'BAAI/bge-base-en-v1.5')
            device = embeddings_config.get('device', 'cpu')
            
            # Handle device selection intelligently
            if device == "auto":
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    device = "mps"  # Apple Silicon
                else:
                    device = "cpu"
            
            logger.info(f"Loading {model_name} embedding model on {device}...")
            self.model = SentenceTransformer(model_name, device=device)
            logger.info("Embedding model loaded successfully")
        except ImportError:
            logger.error("sentence-transformers not installed. Please install with: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    def _load_cached_embeddings(self) -> Optional[Dict[str, Any]]:
        """Load cached embeddings from file"""
        # Check if caching is enabled
        embeddings_config = self.config.get_embeddings_config()
        if not embeddings_config.get('cache_enabled', True):
            logger.info("Embedding cache is disabled")
            return None
        
        cache_path = self._get_embeddings_cache_path()
        
        if not cache_path.exists():
            logger.info("No cached embeddings found")
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # Check cache age
            cache_timestamp = cached_data.get('cache_timestamp')
            if cache_timestamp:
                cache_time = datetime.fromisoformat(cache_timestamp)
                age_hours = (datetime.now() - cache_time).total_seconds() / 3600
                
                # Get cache expiry from config
                embeddings_config = self.config.get_embeddings_config()
                cache_expiry_hours = embeddings_config.get('cache_expiry_hours', 24)
                
                if age_hours > cache_expiry_hours:
                    logger.warning(f"Using cached embeddings that are {age_hours:.1f} hours old (expiry: {cache_expiry_hours}h)")
                else:
                    logger.info(f"Using cached embeddings ({age_hours:.1f} hours old)")
            
            return cached_data
            
        except Exception as e:
            logger.error(f"Failed to load cached embeddings: {e}")
            return None
    
    def _save_embeddings_cache(self, embeddings_data: Dict[str, Any]) -> None:
        """Save embeddings to cache file"""
        # Check if caching is enabled
        embeddings_config = self.config.get_embeddings_config()
        if not embeddings_config.get('cache_enabled', True):
            logger.info("Embedding cache is disabled, skipping save")
            return
        
        cache_path = self._get_embeddings_cache_path()
        
        try:
            cache_data = {
                'cache_timestamp': datetime.now().isoformat(),
                'embeddings': embeddings_data,
                'total_players': len(embeddings_data)
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved embeddings cache with {len(embeddings_data)} players to {cache_path}")
            
        except Exception as e:
            logger.error(f"Failed to save embeddings cache: {e}")
    
    def _encode_players(self, players_data: Dict[str, Dict[str, Any]]) -> Dict[str, np.ndarray]:
        """Encode all players' enriched data into embeddings"""
        if self.model is None:
            self._load_embeddings_model()
        
        logger.info(f"Encoding {len(players_data)} players...")
        
        try:
            # Extract text fields from player data for encoding
            player_names = []
            player_texts = []
            
            for player_name, player_data in players_data.items():
                # Combine relevant text fields for embedding
                text_parts = []
                
                # Add basic player info
                if isinstance(player_data.get('full_name'), str):
                    text_parts.append(player_data['full_name'])
                if isinstance(player_data.get('team_name'), str):
                    text_parts.append(player_data['team_name'])
                if isinstance(player_data.get('element_type'), str):
                    text_parts.append(player_data['element_type'])
                
                # Add enriched data if available
                if isinstance(player_data.get('expert_insights'), str):
                    text_parts.append(player_data['expert_insights'])
                if isinstance(player_data.get('injury_news'), str):
                    text_parts.append(player_data['injury_news'])
                
                # Combine all text parts
                if text_parts:
                    combined_text = " | ".join(text_parts)
                    player_names.append(player_name)
                    player_texts.append(combined_text)
            
            if not player_texts:
                logger.warning("No valid text data found for encoding")
                return {}
            
            # Encode all texts at once (more efficient)
            embeddings_config = self.config.get_embeddings_config()
            batch_size = embeddings_config.get('batch_size', 100)
            
            embeddings = self.model.encode(player_texts, show_progress_bar=True, batch_size=batch_size)
            
            # Create dictionary mapping player names to embeddings
            player_embeddings = {}
            for i, player_name in enumerate(player_names):
                player_embeddings[player_name] = embeddings[i]
            
            logger.info(f"Successfully encoded {len(player_embeddings)} players")
            return player_embeddings
            
        except Exception as e:
            logger.error(f"Failed to encode players: {e}")
            raise
    
    def _encode_queries(self) -> Dict[str, np.ndarray]:
        """Encode position-specific queries"""
        if self.model is None:
            self._load_embeddings_model()
        
        logger.info("Encoding position-specific queries...")
        
        try:
            query_texts = list(self.position_queries.values())
            query_embeddings = self.model.encode(query_texts)
            
            # Create dictionary mapping positions to query embeddings
            position_embeddings = {}
            for i, position in enumerate(self.position_queries.keys()):
                position_embeddings[position] = query_embeddings[i]
            
            logger.info("Successfully encoded position queries")
            return position_embeddings
            
        except Exception as e:
            logger.error(f"Failed to encode queries: {e}")
            raise
    
    def _has_enrichments(self, player_data: Dict[str, Any]) -> bool:
        """Check if player has meaningful enrichments"""
        expert_insights = player_data.get('expert_insights', '')
        injury_news = player_data.get('injury_news', '')
        
        return (expert_insights and expert_insights != "No expert insights available" and
                injury_news and injury_news != "No injury news available")
    
    def _get_player_positions(self, player_data: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
        """Extract player positions from enriched data"""
        player_positions = {}
        
        # Extract positions from the player_data passed in
        for player_name in player_data.keys():
            position = player_data[player_name].get('position', 'UNK')
            player_positions[player_name] = position
        
        return player_positions
    
    def _calculate_similarities(self, player_embeddings: Dict[str, np.ndarray], 
                              query_embeddings: Dict[str, np.ndarray],
                              player_positions: Dict[str, str]) -> Dict[str, List[Tuple[str, float]]]:
        """Calculate cosine similarities between queries and players by position"""
        similarities = {position: [] for position in self.position_queries.keys()}
        
        logger.info("Calculating cosine similarities...")
        
        for position, query_embedding in query_embeddings.items():
            position_players = []
            position_player_embeddings = []
            
            # Get all players for this position
            for player_name, player_embedding in player_embeddings.items():
                if player_positions.get(player_name) == position:
                    position_players.append(player_name)
                    position_player_embeddings.append(player_embedding)
            
            if not position_players:
                logger.warning(f"No players found for position {position}")
                continue
            
            # Calculate similarities for this position
            position_embeddings_array = np.array(position_player_embeddings)
            query_embedding_array = query_embedding.reshape(1, -1)
            
            similarities_array = cosine_similarity(query_embedding_array, position_embeddings_array)[0]
            
            # Create list of (player_name, similarity_score) tuples
            position_similarities = list(zip(position_players, similarities_array))
            
            # Sort by similarity score (highest first)
            position_similarities.sort(key=lambda x: x[1], reverse=True)
            
            similarities[position] = position_similarities
            
            logger.info(f"Calculated similarities for {position}: {len(position_similarities)} players")
        
        return similarities
    
    def _calculate_hybrid_scores(self, similarities: Dict[str, List[Tuple[str, float]]], 
                               structured_data: Dict) -> Dict[str, List[Tuple[str, float, float, float, int, float]]]:
        """
        Rank players with two-stage priority: keyword tier, then raw cosine within tier.

        Display scaling (0–10) is computed per position for readability only and does not
        drive the primary sort order (raw cosine does, within tier).

        Returns per position a list of:
          (name, sort_score, raw_cosine, keyword_bonus, keyword_tier, scaled_cosine_0_10)
        where sort_score preserves two-stage order for callers that sort by hybrid_score.
        """
        hybrid_scores = {}
        # Enough headroom between tiers that scaled cosine (0–10) cannot cross tiers
        tier_span = 100.0

        for position, player_scores in similarities.items():
            if not player_scores:
                hybrid_scores[position] = []
                continue

            raw_cosines = [float(score) for _, score in player_scores]
            scaled_cosines = scale_scores_0_to_10(raw_cosines)

            hybrid_position_scores = []
            for (player_name, embedding_score), scaled in zip(player_scores, scaled_cosines):
                keyword_bonus = extract_expert_bonus(player_name, structured_data)
                keyword_tier = extract_expert_tier(player_name, structured_data)
                # Lower tier = higher priority; within tier higher scaled cosine sorts higher
                sort_score = (TIER_AVOID - keyword_tier) * tier_span + scaled

                hybrid_position_scores.append(
                    (
                        player_name,
                        float(sort_score),
                        float(embedding_score),
                        float(keyword_bonus),
                        int(keyword_tier),
                        float(scaled),
                    )
                )

            # Two-stage: tier ascending, then raw cosine descending (scaled used in sort_score)
            hybrid_position_scores.sort(
                key=lambda row: (row[4], -row[2])
            )
            hybrid_scores[position] = hybrid_position_scores

            logger.info(
                f"Two-stage ranked {position}: {len(hybrid_position_scores)} players "
                f"(keyword tier → cosine)"
            )

        return hybrid_scores
    
    def calculate_player_embeddings(self, players_data: Dict[str, Dict[str, Any]], use_cached: bool = False) -> Dict[str, np.ndarray]:
        """
        Calculate embeddings for all players and save embeddings to player_embeddings.json.
        
        This method calculates embeddings and returns them for use in scoring.
        Embeddings are saved to player_embeddings.json.
        
        Args:
            players_data: Dictionary of player data to calculate embeddings for
            use_cached: If True, use cached player embeddings. If False, generate fresh embeddings.
            
        Returns:
            Dictionary mapping player names to their embedding vectors (numpy arrays)
        """

        try:
            logger.info("Starting calculation of embedding scores for all players...")
            
            # Filter to only enriched players BEFORE processing
            enriched_players = {name: data for name, data in players_data.items() 
                               if self._has_enrichments(data)}
            
            if len(enriched_players) != len(players_data):
                logger.warning(f"Filtered {len(players_data) - len(enriched_players)} players without enrichments")
                logger.info(f"Processing {len(enriched_players)} enriched players")
            
            if use_cached:
                # Load cached embeddings - error if not available
                player_embeddings = self._load_cached_embeddings()
                if not player_embeddings or 'embeddings' not in player_embeddings:
                    raise ValueError("Cached embeddings requested but none available. Run with use_cached=False to generate fresh embeddings.")
                logger.info("Using cached embeddings")
                # Return the raw cached embeddings (will be converted below)
                return player_embeddings['embeddings']
            else:
                # Always generate fresh embeddings
                logger.info("Generating fresh embeddings from enriched player data...")
                try:
                    # Generate embeddings for enriched players only
                    player_embeddings = self._encode_players(enriched_players)
                    
                    # Cache the new embeddings
                    cacheable_embeddings = {}
                    for player_name, embedding in player_embeddings.items():
                        cacheable_embeddings[player_name] = json.dumps(embedding.tolist())
                    
                    self._save_embeddings_cache(cacheable_embeddings)
                    logger.info(f"Generated and cached embeddings for {len(player_embeddings)} enriched players")
                    
                    # Return the fresh embeddings directly (no need to reload)
                    return player_embeddings
                    
                except Exception as e:
                    logger.error(f"Failed to generate embeddings: {e}")
                    raise
            
        except Exception as e:
            logger.error(f"Failed to calculate embeddings: {e}")
            raise
    
    def calculate_player_embedding_scores(self, player_embeddings: Dict[str, np.ndarray], 
                                        players_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Calculate embedding scores for players using existing embeddings.
        
        Args:
            player_embeddings: Dictionary of player embeddings (numpy arrays)
            players_data: Dictionary of player data for context
            
        Returns:
            Dictionary mapping player names to their scores and rankings
        """
        try:
            logger.info("Starting calculation of embedding scores for players...")
            
            # Filter to only enriched players for scoring
            enriched_players = {name: data for name, data in players_data.items() 
                               if self._has_enrichments(data)}
            
            if len(enriched_players) != len(players_data):
                logger.info(f"Calculating scores for {len(enriched_players)} enriched players (filtered from {len(players_data)} total)")
            
            # Get position queries for similarity calculation
            query_embeddings = self._encode_queries()
            
            # Get player positions directly from enriched_players
            player_positions = self._get_player_positions(enriched_players)
            
            # Calculate similarities between players and position queries
            similarities = self._calculate_similarities(player_embeddings, query_embeddings, player_positions)
            
            # Two-stage rank: keyword tier → cosine (scaled cosine for display only)
            hybrid_scores = self._calculate_hybrid_scores(similarities, enriched_players)
            
            # Format and return results
            player_scores = {}
            scores_added = 0
            
            for ranked_players in hybrid_scores.values():
                for rank, (
                    player_name,
                    hybrid_score,
                    embedding_score,
                    keyword_bonus,
                    keyword_tier,
                    embedding_score_scaled,
                ) in enumerate(ranked_players, 1):
                    if player_name in players_data:
                        player_scores[player_name] = {
                            'embedding_score': float(embedding_score),
                            'embedding_score_scaled': float(embedding_score_scaled),
                            'keyword_bonus': float(keyword_bonus),
                            'keyword_tier': int(keyword_tier),
                            'keyword_tier_name': TIER_NAMES.get(keyword_tier, 'neutral'),
                            # sort_score: preserves two-stage order for hybrid_score consumers
                            'hybrid_score': float(hybrid_score),
                            'position_rank': rank,
                        }
                        scores_added += 1
            
            logger.info(f"Successfully calculated embedding scores for {scores_added} players")
            return player_scores
            
        except Exception as e:
            logger.error(f"Failed to calculate embedding scores: {e}")
            raise