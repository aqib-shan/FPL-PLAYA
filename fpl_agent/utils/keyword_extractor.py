"""
Utility functions for extracting keyword-based status and bonuses from text fields.
Used by both DataProcessor and EmbeddingFilter to avoid code duplication.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Lower tier = higher priority in two-stage ranking
TIER_MUST_HAVE = 0
TIER_RECOMMENDED = 1
TIER_NEUTRAL = 2
TIER_ROTATION_RISK = 3
TIER_AVOID = 4

TIER_NAMES = {
    TIER_MUST_HAVE: "must-have",
    TIER_RECOMMENDED: "recommended",
    TIER_NEUTRAL: "neutral",
    TIER_ROTATION_RISK: "rotation risk",
    TIER_AVOID: "avoid",
}

# Default bonuses (also used when config is unavailable)
DEFAULT_KEYWORD_BONUSES = {
    "must-have": 0.5,
    "recommended": 0.3,
    "rotation risk": -0.2,
    "avoid": -0.5,
}


def extract_keyword_status(player_name: str, structured_data: Dict, 
                          field_name: str, keyword_map: Dict[str, Any]) -> Any:
    """
    Extract keyword status from the first keyword before the dash.
    
    Args:
        player_name: Name of the player to extract data for
        structured_data: Dictionary containing player data
        field_name: Field name to extract from (e.g., 'injury_news', 'expert_insights')
        keyword_map: Mapping of keywords to return values
        
    Returns:
        The mapped value if keyword found, None otherwise
    """
    try:
        if player_name in structured_data:
            field_text = structured_data[player_name].get(field_name, '')
            if field_text and ' - ' in field_text:  # Look for space-dash-space
                # Split on first occurrence of " - " (space-dash-space)
                first_part = field_text.split(' - ', 1)[0].strip().lower()
                
                # Look for exact keyword match in the first part
                for keyword, value in keyword_map.items():
                    if first_part == keyword.lower():
                        return value
        
        return None  # Default if no keyword found
        
    except Exception as e:
        logger.warning(f"Failed to extract keyword status for {player_name}: {e}")
        return None


def extract_injury_status(player_name: str, structured_data: Dict) -> str:
    """
    Extract injury status from injury_news - only care about 'Out'.
    
    Args:
        player_name: Name of the player
        structured_data: Dictionary containing player data
        
    Returns:
        'out' if player is marked as out, None otherwise
    """
    status_map = {
        "out": "out"  # Only filter out "Out" players
    }
    return extract_keyword_status(player_name, structured_data, 'injury_news', status_map)


def extract_expert_bonus(player_name: str, structured_data: Dict) -> float:
    """
    Extract keyword bonus from expert_insights.
    
    Args:
        player_name: Name of the player
        structured_data: Dictionary containing player data
        
    Returns:
        Float bonus value based on expert keywords, 0.0 if no match
    """
    result = extract_keyword_status(
        player_name, structured_data, 'expert_insights', DEFAULT_KEYWORD_BONUSES
    )
    return result if result is not None else 0.0


def extract_expert_tier(player_name: str, structured_data: Dict) -> int:
    """
    Extract keyword priority tier from expert_insights for two-stage ranking.

    Returns:
        Tier int where lower is better priority (must-have=0 ... avoid=4).
        Neutral (2) when no keyword matches.
    """
    tier_map = {
        "must-have": TIER_MUST_HAVE,
        "recommended": TIER_RECOMMENDED,
        "rotation risk": TIER_ROTATION_RISK,
        "avoid": TIER_AVOID,
    }
    result = extract_keyword_status(player_name, structured_data, 'expert_insights', tier_map)
    return result if result is not None else TIER_NEUTRAL


def scale_scores_0_to_10(scores: List[float]) -> List[float]:
    """Min-max scale a list of floats to 0–10 (display / tie-break readability)."""
    if not scores:
        return []
    lo = min(scores)
    hi = max(scores)
    if hi - lo < 1e-12:
        return [5.0 for _ in scores]
    return [((s - lo) / (hi - lo)) * 10.0 for s in scores]


def select_players_two_stage(
    players: List[Dict[str, Any]],
    count: int,
    tier_key: str = "keyword_tier",
    cosine_key: str = "embedding_score",
) -> List[Dict[str, Any]]:
    """
    Select players for a shortlist: keyword tier first, cosine within tier.

    Must-haves (tier 0) are always included even if that exceeds ``count``.
    """
    sorted_players = sorted(
        players,
        key=lambda p: (
            p.get(tier_key, TIER_NEUTRAL),
            -(p.get(cosine_key) if p.get(cosine_key) is not None else float("-inf")),
        ),
    )
    must_haves = [p for p in sorted_players if p.get(tier_key, TIER_NEUTRAL) == TIER_MUST_HAVE]
    rest = [p for p in sorted_players if p.get(tier_key, TIER_NEUTRAL) != TIER_MUST_HAVE]

    if count <= 0:
        return list(must_haves)

    if len(must_haves) >= count:
        return list(must_haves)

    return must_haves + rest[: max(0, count - len(must_haves))]
