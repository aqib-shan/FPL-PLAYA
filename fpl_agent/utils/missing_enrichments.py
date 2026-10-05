#!/usr/bin/env python3
"""Utility functions for checking missing enrichments from in-memory data."""

from typing import Dict, List, Any


def get_missing_enrichments_from_data(players_data: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Check which players are missing enrichments from in-memory data.
    
    Args:
        players_data: Dictionary of player data (e.g., all_gameweek_data['players'])
    
    Returns:
        Dict with keys 'expert_insights' and 'injury_news', each containing list of player names
    """
    missing_expert_insights = []
    missing_injury_news = []
    
    for player_name, player_data in players_data.items():
        # Check expert insights
        if not _has_valid_expert_insights(player_data):
            missing_expert_insights.append(player_name)
        
        # Check injury news  
        if not _has_valid_injury_news(player_data):
            missing_injury_news.append(player_name)
    
    return {
        'expert_insights': missing_expert_insights,
        'injury_news': missing_injury_news
    }


def _has_valid_expert_insights(player_data: Dict[str, Any]) -> bool:
    """Check if player has valid expert insights."""
    insights = player_data.get('expert_insights', '')
    return insights and insights != 'None' and insights != 'No expert insights available'


def _has_valid_injury_news(player_data: Dict[str, Any]) -> bool:
    """Check if player has valid injury news."""
    news = player_data.get('injury_news', '')
    return news and news != 'None' and news != 'No injury news available'
