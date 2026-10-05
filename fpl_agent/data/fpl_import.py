import logging
from typing import Dict, Any, List
from .fpl_api_client import FPLAPIClient

logger = logging.getLogger(__name__)

def import_official_team(email: str, password: str, all_players: Dict[str, Any]) -> Dict[str, Any]:
    """Logs into official FPL and converts the current team into the local JSON format."""
    client = FPLAPIClient(email, password)
    if not client.login():
        raise Exception("Login failed. Check your email and password.")
        
    my_team = client.get_my_team()
    if not my_team:
        raise Exception("Failed to fetch official team data.")
        
    # Build ID to Player map
    id_to_player = {}
    for name, data in all_players.items():
        # Handle duplicates/aliases by taking the first one or relying on raw data
        id_to_player[data['id']] = {
            'name': name,
            'position': data['position'],
            'team': data.get('team_short_name', 'UNK'),
            'now_cost': data['now_cost']
        }
        
    # Note: my_team['picks'] contains the current players.
    # We need to map them to starting / bench.
    picks = my_team.get('picks', [])
    
    starting = []
    substitutes = []
    captain = None
    vice_captain = None
    
    total_cost = 0.0
    
    # Sort picks by position index (1-11 are starters, 12 is sub GK, 13-15 are sub outfield)
    picks.sort(key=lambda x: x['position'])
    
    for pick in picks:
        element_id = pick['element']
        p_data = id_to_player.get(element_id)
        if not p_data:
            logger.warning(f"Player ID {element_id} not found in local data!")
            continue
            
        is_cap = pick.get('is_captain', False)
        is_vice = pick.get('is_vice_captain', False)
        
        if is_cap:
            captain = p_data['name']
        if is_vice:
            vice_captain = p_data['name']
            
        player_entry = {
            "name": p_data['name'],
            "position": p_data['position'],
            "team": p_data['team'],
            "price": pick['selling_price'] / 10.0  # FPL uses 50 for 5.0m
        }
        
        total_cost += player_entry['price']
        
        # Position 1-11 are starters
        if pick['position'] <= 11:
            starting.append(player_entry)
        else:
            # Substitutes
            player_entry['sub_order'] = pick['position'] - 11
            substitutes.append(player_entry)
            
    # Calculate bank
    bank = my_team.get('transfers', {}).get('bank', 0) / 10.0
    
    local_team = {
        "total_cost": round(total_cost, 1),
        "bank": round(bank, 1),
        "expected_points": 0.0,
        "chip": my_team.get('active_chip'),
        "captain": captain,
        "vice_captain": vice_captain,
        "starting": starting,
        "substitutes": substitutes
    }
    
    return local_team
