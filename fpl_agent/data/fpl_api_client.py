import logging
import requests
from typing import Dict, Any, List, Optional
import json
import re

logger = logging.getLogger(__name__)

class FPLAPIClient:
    """Client for authenticated FPL API operations (making transfers, changing lineups)"""
    
    def __init__(self, cookie_string: str, access_token: str = None):
        self.cookie_string = cookie_string
        self.access_token = access_token
        self.session = requests.Session()
        
        # Standard headers to mimic browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Cookie': self.cookie_string
        })
        
        if self.access_token:
            self.session.headers['X-API-Authorization'] = f'Bearer {self.access_token}' if not self.access_token.startswith('Bearer') else self.access_token
        
        self.team_id = None
        
    def login(self) -> bool:
        """Authenticate using the Cookie and fetch team ID"""
        if not self.cookie_string:
            logger.error("FPL cookie not provided.")
            return False
            
        logger.info("Attempting to authenticate with FPL using cookie...")
        
        try:
            # Step 1: Verify token and get team ID (entry ID)
            me_url = "https://fantasy.premierleague.com/api/me/"
            me_response = self.session.get(me_url, timeout=30)
            
            if me_response.status_code == 200:
                me_data = me_response.json()
                
                player_data = me_data.get('player')
                if player_data:
                    self.team_id = player_data.get('entry')
                else:
                    logger.error(f"/api/me/ returned 200 but no 'player' object. Response: {me_data}")
                    self.team_id = None
                
                if self.team_id:
                    logger.info(f"Successfully authenticated. Team ID: {self.team_id}")
                    return True
                else:
                    logger.error("Authenticated, but could not find an active FPL team (entry ID).")
                    return False
            else:
                logger.error(f"Authentication failed. Status code: {me_response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error during FPL authentication: {e}")
            return False

    def get_my_team(self) -> Optional[Dict[str, Any]]:
        """Get the current authenticated user's team state"""
        if not self.team_id:
            logger.error("Not logged in or missing team ID.")
            return None
            
        url = f"https://fantasy.premierleague.com/api/my-team/{self.team_id}/"
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch my-team: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching my-team: {e}")
            return None

    def make_transfers(self, transfers_payload: List[Dict[str, int]], gameweek: int) -> bool:
        """
        Make actual transfers.
        transfers_payload should be a list of dicts: 
        [{"element_in": <id>, "element_out": <id>, "purchase_price": <price>, "selling_price": <price>}]
        """
        if not self.team_id:
            logger.error("Not logged in or missing team ID.")
            return False
            
        url = "https://fantasy.premierleague.com/api/transfers/"
        
        payload = {
            "chip": None,
            "entry": self.team_id,
            "event": gameweek,
            "transfers": transfers_payload
        }
        
        try:
            # Extract CSRF token from raw cookie string
            csrf_token_match = re.search(r'csrftoken=([^;]+)', self.cookie_string)
            csrf_token = csrf_token_match.group(1) if csrf_token_match else None
            
            headers = {'Content-Type': 'application/json'}
            if csrf_token:
                headers['X-CSRFToken'] = csrf_token
                
            response = self.session.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                logger.info("Transfers successfully executed!")
                return True
            else:
                logger.error(f"Transfer failed. Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error making transfers: {e}")
            return False

    def set_lineup(self, picks_payload: List[Dict[str, Any]]) -> bool:
        """
        Update captain, vice-captain, and bench order.
        picks_payload: [{"element": <id>, "position": <1-15>, "is_captain": bool, "is_vice_captain": bool}]
        """
        if not self.team_id:
            logger.error("Not logged in or missing team ID.")
            return False
            
        url = f"https://fantasy.premierleague.com/api/my-team/{self.team_id}/"
        
        payload = {
            "chip": None,
            "picks": picks_payload
        }
        
        try:
            # Extract CSRF token from raw cookie string
            csrf_token_match = re.search(r'csrftoken=([^;]+)', self.cookie_string)
            csrf_token = csrf_token_match.group(1) if csrf_token_match else None
            
            headers = {'Content-Type': 'application/json'}
            if csrf_token:
                headers['X-CSRFToken'] = csrf_token
                
            response = self.session.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                logger.info("Lineup successfully updated!")
                return True
            else:
                logger.error(f"Lineup update failed. Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error updating lineup: {e}")
            return False
