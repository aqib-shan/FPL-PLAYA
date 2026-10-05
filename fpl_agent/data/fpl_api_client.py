import logging
import requests
from typing import Dict, Any, List, Optional
import json

logger = logging.getLogger(__name__)

class FPLAPIClient:
    """Client for authenticated FPL API operations (making transfers, changing lineups)"""
    
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.session = requests.Session()
        
        # Standard headers to mimic browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*'
        })
        
        self.team_id = None
        
    def login(self) -> bool:
        """Authenticate with FPL servers and fetch team ID"""
        if not self.email or not self.password:
            logger.error("FPL email or password not provided.")
            return False
            
        logger.info(f"Attempting to log in to FPL as {self.email}...")
        login_url = "https://users.premierleague.com/accounts/login/"
        
        payload = {
            "login": self.email,
            "password": self.password,
            "app": "plfpl-web",
            "redirect_uri": "https://fantasy.premierleague.com/"
        }
        
        try:
            # Step 1: POST to login endpoint
            response = self.session.post(login_url, data=payload, timeout=30)
            
            # Step 2: Verify login and get team ID (entry ID)
            me_url = "https://fantasy.premierleague.com/api/me/"
            me_response = self.session.get(me_url, timeout=30)
            
            if me_response.status_code == 200:
                me_data = me_response.json()
                self.team_id = me_data.get('player', {}).get('entry')
                
                if self.team_id:
                    logger.info(f"Successfully logged in. Team ID: {self.team_id}")
                    return True
                else:
                    logger.error("Logged in, but could not find an active FPL team (entry ID).")
                    return False
            else:
                logger.error(f"Login failed. Status code: {me_response.status_code}")
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
            # We also need the csrftoken for POST requests in Django apps usually?
            # Wait, FPL api doesn't always strictly require csrf if using the session cookies right, 
            # but we can pull it from cookies if needed.
            csrf_token = self.session.cookies.get('csrftoken', domain='fantasy.premierleague.com')
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
            csrf_token = self.session.cookies.get('csrftoken', domain='fantasy.premierleague.com')
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
