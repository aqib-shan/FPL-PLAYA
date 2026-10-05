import logging
from typing import Dict, Any, List
from .fpl_api_client import FPLAPIClient

logger = logging.getLogger(__name__)

def sync_team_to_fpl(team_result: Dict[str, Any], email: str, password: str, all_players: Dict[str, Any], gameweek: int) -> bool:
    """Sync the local AI team result to the official FPL API."""
    
    # Extract payload
    team = team_result.get('team', team_result)
    if 'team' in team:
        team = team['team']
        
    client = FPLAPIClient(email, password)
    if not client.login():
        return False
        
    # Get current team from FPL to know selling prices
    my_team_data = client.get_my_team()
    if not my_team_data:
        return False
        
    # Map player names to element IDs
    name_to_id = {}
    for player_name, pdata in all_players.items():
        name_to_id[player_name] = pdata['id']
        name_to_id[pdata.get('full_name', player_name)] = pdata['id']

    # 1. Process Transfers
    transfers = team.get('transfers', [])
    if transfers:
        logger.info(f"Processing {len(transfers)} transfers for sync...")
        transfer_payload = []
        
        # Create a map of current elements to their selling price
        current_picks = my_team_data.get('picks', [])
        element_to_selling_price = {pick['element']: pick['selling_price'] for pick in current_picks}
        
        for t in transfers:
            p_out_name = t['player_out']
            p_in_name = t['player_in']
            
            p_out_id = name_to_id.get(p_out_name)
            p_in_id = name_to_id.get(p_in_name)
            
            if not p_out_id or not p_in_id:
                logger.error(f"Could not map transfer players to IDs: {p_out_name} -> {p_in_name}")
                return False
                
            selling_price = element_to_selling_price.get(p_out_id)
            if selling_price is None:
                logger.error(f"Could not find selling price for {p_out_name} (ID: {p_out_id}) in current team.")
                return False
                
            purchase_price = all_players[p_in_name]['now_cost']
            
            transfer_payload.append({
                "element_in": p_in_id,
                "element_out": p_out_id,
                "purchase_price": purchase_price,
                "selling_price": selling_price
            })
            
        if transfer_payload:
            if not client.make_transfers(transfer_payload, gameweek):
                logger.error("Failed to execute transfers.")
                return False

    # 2. Process Lineup (Picks)
    logger.info("Processing lineup sync...")
    starting = team.get('starting', [])
    subs = team.get('substitutes', [])
    captain = team.get('captain')
    vice_captain = team.get('vice_captain')
    
    if not starting or not subs:
        logger.warning("No starting or substitute players found to sync lineup.")
        return True
        
    picks_payload = []
    position_idx = 1
    
    # Add starters
    for p in starting:
        p_name = p['name']
        p_id = name_to_id.get(p_name)
        if not p_id:
            logger.error(f"Could not map starting player {p_name} to ID.")
            return False
            
        picks_payload.append({
            "element": p_id,
            "position": position_idx,
            "is_captain": (p_name == captain),
            "is_vice_captain": (p_name == vice_captain)
        })
        position_idx += 1
        
    # Sort subs: GK first (position 12), then outfielders (13, 14, 15) by sub_order
    sub_gk = next((p for p in subs if p.get('position') == 'GK'), None)
    outfield_subs = sorted([p for p in subs if p.get('position') != 'GK'], key=lambda x: x.get('sub_order', 99))
    
    if sub_gk:
        p_name = sub_gk['name']
        p_id = name_to_id.get(p_name)
        if p_id:
            picks_payload.append({
                "element": p_id,
                "position": position_idx,
                "is_captain": (p_name == captain),
                "is_vice_captain": (p_name == vice_captain)
            })
            position_idx += 1
            
    for p in outfield_subs:
        p_name = p['name']
        p_id = name_to_id.get(p_name)
        if p_id:
            picks_payload.append({
                "element": p_id,
                "position": position_idx,
                "is_captain": (p_name == captain),
                "is_vice_captain": (p_name == vice_captain)
            })
            position_idx += 1
            
    if picks_payload:
        if not client.set_lineup(picks_payload):
            logger.error("Failed to set lineup.")
            return False
            
    logger.info("Successfully synced team to official FPL API!")
    return True
