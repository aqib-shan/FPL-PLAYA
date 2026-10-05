import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

def import_public_team(team_id: int, gameweek: int, all_players: Dict[str, Any]) -> Dict[str, Any]:
    """Fetches a team's data from the public FPL API using only their Team ID."""
    
    url = f"https://fantasy.premierleague.com/api/entry/{team_id}/event/{gameweek}/picks/"
    response = requests.get(url, timeout=30)
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch team data. Check if your Team ID is correct. Status: {response.status_code}")
        
    team_data = response.json()
    
    # Build ID to Player map
    id_to_player = {}
    for name, data in all_players.items():
        id_to_player[data['id']] = {
            'name': name,
            'position': data['position'],
            'team': data.get('team_short_name', 'UNK'),
            'now_cost': data['now_cost']
        }
        
    picks = team_data.get('picks', [])
    
    starting = []
    substitutes = []
    captain = None
    vice_captain = None
    
    total_cost = 0.0
    
    picks.sort(key=lambda x: x['position'])
    
    for pick in picks:
        element_id = pick['element']
        p_data = id_to_player.get(element_id)
        if not p_data:
            continue
            
        if pick.get('is_captain'):
            captain = p_data['name']
        if pick.get('is_vice_captain'):
            vice_captain = p_data['name']
            
        # In the public endpoint, we don't always have selling_price, so we estimate with now_cost
        player_entry = {
            "name": p_data['name'],
            "position": p_data['position'],
            "team": p_data['team'],
            "price": p_data['now_cost']
        }
        
        total_cost += player_entry['price']
        
        if pick['position'] <= 11:
            starting.append(player_entry)
        else:
            player_entry['sub_order'] = pick['position'] - 11
            substitutes.append(player_entry)
            
    # Calculate bank from entry_history
    history = team_data.get('entry_history', {})
    bank = history.get('bank', 0) / 10.0
    
    local_team = {
        "total_cost": round(total_cost, 1),
        "bank": round(bank, 1),
        "expected_points": 0.0,
        "chip": team_data.get('active_chip'),
        "captain": captain,
        "vice_captain": vice_captain,
        "starting": starting,
        "substitutes": substitutes
    }
    
    return local_team
