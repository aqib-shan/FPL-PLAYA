import os
import sys
import json
import logging

# Fix Windows console encoding for emoji characters
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from flask import Flask, jsonify, request
from fpl_agent.main import FPLAgent
from fpl_agent.core.team_manager import TeamManager
from fpl_agent.data.fpl_sync import sync_team_to_fpl
from fpl_agent.data.fpl_public_import import import_public_team
from fpl_agent.core.config import Config

app = Flask(__name__, static_folder='static', static_url_path='/')
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def get_agent():
    """Returns FPLAgent configured for the available API key."""
    if os.environ.get('OPENROUTER_API_KEY'):
        return FPLAgent()  # defaults to main_openrouter
    return FPLAgent(model_name="main")  # fallback to Gemini directly

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/team', methods=['GET'])
def get_team():
    team_name = request.args.get('team', 'default')
    try:
        team_manager = TeamManager(team_name=team_name)
        if not team_manager.team_exists():
            return jsonify({"error": "Team does not exist", "team": None}), 404
            
        latest_gw = team_manager.get_latest_gameweek()
        if not latest_gw:
            return jsonify({"error": "No gameweek data found", "team": None}), 404
            
        team_data = team_manager.load_team(latest_gw)
        meta = team_manager.get_meta()
        
        return jsonify({
            "team": team_data,
            "meta": meta,
            "gameweek": latest_gw
        })
    except Exception as e:
        logger.error(f"Error fetching team: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/import_team', methods=['POST'])
def import_fpl_team():
    data = request.json or {}
    team_id = data.get('team_id')
    
    if not team_id:
        return jsonify({"error": "Team ID is required."}), 400
        
    try:
        agent = get_agent()
        all_data = agent.fetch_fpl_data(use_cached=False)
        current_gw = agent.data_service.fetcher.get_current_gameweek() or 1
        
        cookie_string = os.environ.get('FPL_COOKIE')
        access_token = os.environ.get('FPL_ACCESS_TOKEN')
        local_team = None
        
        if cookie_string and access_token:
            from fpl_agent.data.fpl_api_client import FPLAPIClient
            try:
                client = FPLAPIClient(cookie_string, access_token)
                if client.login():
                    my_team = client.get_my_team()
                    if my_team and 'picks' in my_team:
                        logger.info("Successfully fetched private team data for import.")
                        
                        id_to_player = {}
                        for name, p_data in all_data['players'].items():
                            id_to_player[p_data['id']] = {
                                'name': name,
                                'position': p_data['position'],
                                'team': p_data.get('team_short_name', 'UNK'),
                                'now_cost': p_data['now_cost']
                            }
                        
                        starting = []
                        substitutes = []
                        captain = None
                        vice_captain = None
                        total_cost = 0.0
                        
                        picks = my_team.get('picks', [])
                        picks.sort(key=lambda x: x['position'])
                        
                        for pick in picks:
                            p_data = id_to_player.get(pick['element'])
                            if not p_data: continue
                            
                            if pick.get('is_captain'): captain = p_data['name']
                            if pick.get('is_vice_captain'): vice_captain = p_data['name']
                            
                            player_entry = {
                                "name": p_data['name'],
                                "position": p_data['position'],
                                "team": p_data['team'],
                                "price": pick.get('selling_price', p_data['now_cost']) / 10.0 if pick.get('selling_price') else p_data['now_cost'] / 10.0
                            }
                            total_cost += player_entry['price']
                            
                            if pick['position'] <= 11:
                                starting.append(player_entry)
                            else:
                                player_entry['sub_order'] = pick['position'] - 11
                                substitutes.append(player_entry)
                                
                        transfers = my_team.get('transfers', {})
                        bank = transfers.get('bank', 0) / 10.0
                        
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
            except Exception as e:
                logger.error(f"Failed to fetch private team: {e}")
                
        if not local_team:
            logger.info("Falling back to public team import...")
            local_team = import_public_team(team_id, current_gw, all_data['players'])
        
        # Save team locally
        team_manager = TeamManager(team_name='default', auto_create=True)
        team_manager.save_new_team(local_team, current_gw)
        
        return jsonify({"success": True, "team": local_team})
    except Exception as e:
        logger.error(f"Import failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/update', methods=['POST'])
def gw_update():
    data = request.json or {}
    team_name = data.get('team', 'default')
    
    # Only use Gemini 2.5 Flash as requested by the user
    models_to_try = [
        'gemini_25_flash'
    ]
    
    # Check for multiple API keys
    api_keys = []
    for i in ["", "_2", "_3", "_4", "_5"]:
        key_val = os.environ.get(f'GEMINI_API_KEY{i}')
        if key_val:
            api_keys.append((f'GEMINI_API_KEY{i}', key_val))
            
    if not api_keys:
        api_keys = [('GEMINI_API_KEY', None)]
    
    last_error = None
    team_result = None
    
    for key_name, api_key in api_keys:
        if team_result:
            break
            
        if api_key:
            logger.info(f"Using API Key from {key_name}")
            os.environ['GEMINI_API_KEY'] = api_key
            
        for model_name in models_to_try:
            try:
                logger.info(f"Attempting to update team with model: {model_name}")
                agent = FPLAgent(model_name=model_name)
                
                # Generate update
                team_result = agent.gw_update(team_name=team_name, save_team=True)
                
                if team_result:
                    # Successfully generated team
                    logger.info(f"Successfully generated team update using model: {model_name} with {key_name}")
                    break
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {e}")
                last_error = e
                # If it's a 429 quota error, break this inner loop to try the next API key
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    logger.warning(f"Quota exhausted on {key_name}, switching to next key if available.")
                    break
                continue
                
    if team_result is None:
        logger.error(f"All models and keys failed to update team. Last error: {last_error}")
        return jsonify({"error": f"Failed to update team using any model/key. Last error: {str(last_error)}"}), 500

    sync_status = False
    sync_message = "Auto-sync skipped: Ready to apply manually."
    
    if data.get('auto_sync'):
        cookie_string = data.get('cookie') or os.environ.get('FPL_COOKIE')
        access_token = data.get('access_token') or os.environ.get('FPL_ACCESS_TOKEN')
        
        if cookie_string:
            try:
                logger.info("Auto-syncing to FPL...")
                all_data = agent.fetch_fpl_data(use_cached=True)
                current_gw = agent.data_service.fetcher.get_current_gameweek() or 1
                
                success = sync_team_to_fpl(team_result, cookie_string, access_token, all_data['players'], current_gw)
                if success:
                    sync_status = True
                    sync_message = "Successfully auto-synced AI team to your official FPL account!"
                else:
                    sync_message = "Failed to sync team. The cookie might be invalid or expired."
            except Exception as e:
                logger.error(f"Sync error: {e}")
                sync_message = f"Sync error: {str(e)}"
                
    return jsonify({
        "success": True, 
        "team": team_result,
        "sync_status": sync_status,
        "sync_message": sync_message
    })

@app.route('/api/sync_action', methods=['POST'])
def sync_action():
    data = request.json or {}
    sync_type = data.get('sync_type', 'all')
    team_result = data.get('team_result')
    
    cookie_string = os.environ.get('FPL_COOKIE')
    access_token = os.environ.get('FPL_ACCESS_TOKEN')
    
    if not cookie_string:
        return jsonify({"success": False, "error": "No FPL cookie provided in .env"}), 400
        
    try:
        agent = FPLAgent(model_name="main")
        all_data = agent.fetch_fpl_data(use_cached=True)
        current_gw = agent.data_service.fetcher.get_current_gameweek() or 1
        
        success = sync_team_to_fpl(team_result, cookie_string, access_token, all_data['players'], current_gw, sync_type)
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def check_status():
    """Check API keys and overall readiness"""
    config = Config()
    llm_conf = config._config.get('llm', {})
    
    has_gemini = bool(os.environ.get('GEMINI_API_KEY')) or 'gemini' in str(llm_conf)
    has_openrouter = bool(os.environ.get('OPENROUTER_API_KEY'))
    
    return jsonify({
        "status": "online",
        "api_keys_configured": has_gemini or has_openrouter
    })

if __name__ == '__main__':
    app.run(debug=False, port=5001)
