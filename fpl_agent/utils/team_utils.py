"""
Utility functions for team management and analysis.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional


def extract_team_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return the dict containing team fields (`starting`/`substitutes`/chip/bank/...)
    from mixed LLM / file shapes.

    Accepted shapes:
    - Raw team: {"captain": ..., "starting": ..., "substitutes": ...}
    - Wrapped: {"team": { ... raw team ... }}
    - Double-wrapped: {"team": {"team": { ... }}}
    """
    if not isinstance(data, dict):
        return {}

    if 'starting' in data and 'substitutes' in data:
        return data

    team_candidate = data.get('team')
    if isinstance(team_candidate, dict):
        if 'starting' in team_candidate and 'substitutes' in team_candidate:
            return team_candidate

        nested_team = team_candidate.get('team')
        if isinstance(nested_team, dict) and 'starting' in nested_team and 'substitutes' in nested_team:
            return nested_team

    return data


def normalize_chip(chip: Any) -> Optional[str]:
    """Normalize LLM chip values; treat null-like strings as unused."""
    if chip is None:
        return None
    if isinstance(chip, str) and chip.strip().lower() in ('', 'null', 'none'):
        return None
    return chip


def get_all_teams() -> List[str]:
    """
    Get list of all team names from team_data directory.
    
    Returns:
        List of team names (directory names)
    """
    team_data_dir = Path("team_data")
    if not team_data_dir.exists():
        return []
    
    teams = []
    for item in team_data_dir.iterdir():
        if item.is_dir() and item.name != "shared":
            teams.append(item.name)
    
    return sorted(teams)


def get_all_model_configs(config) -> List[Tuple[str, str]]:
    """
    Get list of all model configurations that have team directories.
    
    Args:
        config: FPL configuration object
        
    Returns:
        List of tuples (model_name, team_directory)
    """
    llm_config = config._config.get('llm', {})
    model_configs = []
    
    for model_name, model_config in llm_config.items():
        if isinstance(model_config, dict) and 'team_directory' in model_config:
            team_directory = model_config['team_directory']
            model_configs.append((model_name, team_directory))
    
    return model_configs


def group_players_by_team(players: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group players by their team.
    
    Args:
        players: List of player dictionaries
        
    Returns:
        Dictionary mapping team names to lists of players
    """
    grouped = {}
    for player, player_data in players.items():
        team = player_data.get('team_name', 'Unknown')
        if team not in grouped:
            grouped[team] = {}
        grouped[team][player] = player_data
    
    return grouped


def get_team_fixture_info(team_name: str, fixtures_data: List[Dict[str, Any]], 
                          current_gameweek: int) -> Dict[str, Any]:
    """
    Get fixture information for a specific team in a gameweek.
    
    Args:
        team_name: Name of the team
        fixtures_data: List of all fixtures (with team names as strings)
        current_gameweek: Current gameweek number
        
    Returns:
        Dictionary containing fixture string, double gameweek status, and fixture difficulty
    """
    # Find opponents for this gameweek
    opponents = []
    fixture_difficulties = []
    
    for fixture_data in fixtures_data:
        if fixture_data.get('event') == current_gameweek:
            home_team = fixture_data.get('team_h')
            away_team = fixture_data.get('team_a')
            
            # Get fixture date and time
            kickoff_time = fixture_data.get('kickoff_time')
            if kickoff_time:
                try:
                    # Parse the ISO format date from FPL API
                    fixture_date = datetime.fromisoformat(kickoff_time.replace('Z', '+00:00'))
                    # Convert UTC to BST (British Summer Time)
                    utc_tz = ZoneInfo('UTC')
                    bst_tz = ZoneInfo('Europe/London')
                    fixture_date = fixture_date.replace(tzinfo=utc_tz).astimezone(bst_tz)
                    # Format as "Sunday 22nd May 2025 at 14:00"
                    day = fixture_date.day
                    suffix = 'th' if 11 <= day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
                    formatted_date = f"{fixture_date.strftime('%A')} {day}{suffix} {fixture_date.strftime('%B %Y')} at {fixture_date.strftime('%H:%M')}"
                except Exception:
                    formatted_date = "TBD"
            else:
                formatted_date = "TBD"
            
            if home_team == team_name:
                # Team is playing home
                opponents.append(f"home to {away_team} on {formatted_date}")
                # Get home difficulty (for the home team)
                fixture_difficulties.append(fixture_data.get('team_h_difficulty', 3))
            elif away_team == team_name:
                # Team is playing away
                opponents.append(f"away to {home_team} on {formatted_date}")
                # Get away difficulty (for the away team)
                fixture_difficulties.append(fixture_data.get('team_a_difficulty', 3))
    
    # Calculate average fixture difficulty
    if fixture_difficulties:
        avg_difficulty = sum(fixture_difficulties) / len(fixture_difficulties)
    else:
        avg_difficulty = 3.0
    
    # Format opponent string
    is_double_gameweek = len(opponents) > 1
    
    if opponents:
        if len(opponents) == 1:
            fixture_str = opponents[0]
        else:
            # Double gameweek
            fixture_str = f"double gameweek: {' and '.join(opponents)}"
    else:
        fixture_str = "no fixture scheduled"
    
    return {
        'fixture_str': fixture_str,
        'is_double_gameweek': is_double_gameweek,
        'fixture_difficulty': avg_difficulty
    }

