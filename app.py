import os
import json
import logging
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
        
        # Import team publicly
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
    
    agent = get_agent()
    try:
        # Generate update
        team_result = agent.gw_update(team_name=team_name, save_team=True)
                
        return jsonify({
            "success": True, 
            "team": team_result,
            "sync_status": False,
            "sync_message": "Auto-sync disabled in public mode."
        })
    except Exception as e:
        logger.error(f"Error updating team: {e}")
        return jsonify({"error": str(e)}), 500

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
