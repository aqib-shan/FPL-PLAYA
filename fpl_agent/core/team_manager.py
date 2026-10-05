"""
Local team management system for FPL
Stores team data for each gameweek in JSON files
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging
from fpl_agent.utils.fpl_calculations import calculate_fpl_sale_price
from fpl_agent.utils.team_utils import extract_team_payload, normalize_chip

logger = logging.getLogger(__name__)


class TeamManager:
    """Manages local FPL team data for each gameweek"""
    
    # FPL Game Rules
    DEFAULT_FREE_TRANSFERS = 0  # 0 transfers carried over at the start, gets 1 free transfer at the start of the next gameweek
    MAX_FREE_TRANSFERS = 5  # Can bank up to 5 free transfers
    CHIP_RESET_GAMEWEEK = 20
    DEFAULT_BUDGET = 100.0
    
    # File Naming
    TEAM_FILE_PREFIX = "gw"
    TEAM_FILE_SUFFIX = ".json"
    META_FILE_NAME = "meta.json"
    
    # Chip Names
    CHIP_NAMES = ['wildcard', 'bench_boost', 'free_hit', 'triple_captain']
    
    def __init__(self, team_name: str = "default", data_dir: str = "team_data", auto_create: bool = False):
        self.team_name = team_name
        self.data_dir = Path(data_dir)
        self.team_dir = self.data_dir / team_name
        self.shared_dir = self.data_dir / "shared"
        self.meta_file = self.team_dir / self.META_FILE_NAME
        
        # Create shared directory if it doesn't exist
        self.shared_dir.mkdir(exist_ok=True)
        
        # Only auto-create team directory if explicitly requested
        if auto_create and not self.team_dir.exists():
            self.create_team()
    
    def create_team(self, budget: float = 100.0) -> None:
        """Create team directory and initial meta.json"""
        self.team_dir.mkdir(exist_ok=True)
        
        # Initialize meta.json with default values
        meta_data = {
            "current_gw": 1,
            "last_team_file": "",
            "bank": budget,
            "free_transfers_carried_over": self.DEFAULT_FREE_TRANSFERS,
            "chips_used": {
                chip: False for chip in self.CHIP_NAMES
            }
        }
        
        self._save_meta(meta_data)
        logger.info(f"Team '{self.team_name}' created successfully")
    
    def team_exists(self) -> bool:
        """Check if team directory exists"""
        return self.team_dir.exists()
    
    def delete_team(self) -> None:
        """Delete this team's directory and data"""
        if self.team_dir.exists():
            import shutil
            shutil.rmtree(self.team_dir)
            logger.info(f"Team '{self.team_name}' deleted successfully")
        else:
            logger.warning(f"Team '{self.team_name}' does not exist")
    
    def _get_team_file(self, gameweek: int) -> Path:
        """Get the file path for a specific gameweek's team data"""
        return self.team_dir / f"{self.TEAM_FILE_PREFIX}{gameweek:02d}{self.TEAM_FILE_SUFFIX}"
    
    def _scan_team_files(self) -> List[Path]:
        """Scan for team files and return them sorted by gameweek"""
        if not self.team_dir.exists():
            return []
            
        team_files = list(self.team_dir.glob(f"{self.TEAM_FILE_PREFIX}*{self.TEAM_FILE_SUFFIX}"))
        # Filter out copy/backup files and any files that don't have a valid numeric gameweek suffix
        valid_team_files: List[Path] = []
        for f in team_files:
            stem = f.stem
            # Skip obvious copy/backup files
            if stem.endswith(' copy'):
                continue
            # Require the expected prefix
            if not stem.startswith(self.TEAM_FILE_PREFIX):
                continue
            # Extract the part after the prefix and ensure it's a valid integer
            suffix = stem[len(self.TEAM_FILE_PREFIX):]
            try:
                int(suffix)
            except ValueError:
                logger.warning(f"Skipping invalid team file with non-numeric gameweek suffix: {f.name}")
                continue
            valid_team_files.append(f)

        # Sort by gameweek number (remove 'gw' prefix and convert to int)
        valid_team_files.sort(key=lambda x: int(x.stem[len(self.TEAM_FILE_PREFIX):]))
        return valid_team_files
    
    def _load_meta(self) -> Dict[str, Any]:
        """Load the meta.json file"""
        if not self.meta_file.exists():
            return {}
        
        try:
            with open(self.meta_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load meta.json: {e}")
            return {}
    
    def _save_meta(self, meta_data: Dict[str, Any]) -> None:
        """Save the meta.json file"""
        try:
            with open(self.meta_file, 'w') as f:
                json.dump(meta_data, f, indent=2)
            logger.info("Meta data saved successfully")
        except IOError as e:
            logger.error(f"Failed to save meta.json: {e}")
    
    def initialize_meta(self, gameweek: int, team_data: Dict[str, Any]) -> None:
        """Initialize the meta.json file with default values for a new team"""
        payload = extract_team_payload(team_data)
        meta_data = {
            "current_gw": gameweek,
            "last_team_file": f"{self.TEAM_FILE_PREFIX}{gameweek:02d}{self.TEAM_FILE_SUFFIX}",
            "bank": payload.get('bank', 0.0),
            "free_transfers_carried_over": self.DEFAULT_FREE_TRANSFERS,
            "chips_used": {
                chip: False for chip in self.CHIP_NAMES
            }
        }
        
        self._save_meta(meta_data)
        logger.info(f"Meta data initialized for Gameweek {gameweek}")
    
    def _update_meta(self, gameweek: int, team_data: Dict[str, Any], 
                   chips_used: Optional[Dict[str, bool]] = None,
                   free_transfers_carried_over: Optional[int] = None) -> None:
        """Update the meta.json file with new team status"""
        meta_data = self._load_meta()
        payload = extract_team_payload(team_data)
        
        # Update basic info
        meta_data["current_gw"] = gameweek
        meta_data["last_team_file"] = f"{self.TEAM_FILE_PREFIX}{gameweek:02d}{self.TEAM_FILE_SUFFIX}"
        meta_data["bank"] = payload.get('bank', meta_data.get('bank', 0.0))
        
        # Update free transfers if provided
        if free_transfers_carried_over is not None:
            meta_data["free_transfers_carried_over"] = free_transfers_carried_over
        
        # Update chips used if provided
        if chips_used is not None:
            if "chips_used" not in meta_data:
                meta_data["chips_used"] = {}
            meta_data["chips_used"].update(chips_used)
        
        self._save_meta(meta_data)
        logger.info(f"Meta data updated for Gameweek {gameweek}")
    
    def get_meta(self) -> Dict[str, Any]:
        """Get the current meta data"""
        return self._load_meta()
    
    def save_team(self, gameweek: int, team_data: Dict[str, Any]) -> None:
        """Save team data for a specific gameweek"""
        team_file = self._get_team_file(gameweek)

        # Persist a single canonical wrapper shape: {"team": {...actual team...}}
        # This avoids double-wrapping and keeps compatibility with older files.
        team_data_with_meta = {
            "team": extract_team_payload(team_data)
        }

        with open(team_file, 'w') as f:
            json.dump(team_data_with_meta, f, indent=2)
        
        logger.info(f"Team data saved for Gameweek {gameweek}")
    
    def load_team(self, gameweek: int) -> Optional[Dict[str, Any]]:
        """Load team data for a specific gameweek"""
        team_file = self._get_team_file(gameweek)
        
        if not team_file.exists():
            return None
        
        try:
            with open(team_file, 'r') as f:
                data = json.load(f)
            normalized_data = {"team": extract_team_payload(data)}
            logger.info(f"Team data loaded for Gameweek {gameweek}")
            return normalized_data
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load team data for Gameweek {gameweek}: {e}")
            return None

    def extract_team_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Return the dict containing team fields from mixed file/LLM shapes."""
        return extract_team_payload(data)
    
    def get_latest_gameweek(self) -> Optional[int]:
        """Get the latest gameweek number"""
        team_files = self._scan_team_files()
        
        if not team_files:
            return None
        
        # Get the latest gameweek number
        latest_file = team_files[-1]
        return int(latest_file.stem[2:])
    
    def get_previous_team(self, gameweek: int) -> Optional[Dict[str, Any]]:
        """Get the team from the previous gameweek"""
        if gameweek <= 1:
            return None
        
        return self.load_team(gameweek - 1)
    
    def is_free_hit_revert_scenario(self, gameweek: int, current_meta: Dict[str, Any]) -> bool:
        """
        Check if this is a free hit revert scenario (next gameweek after free hit was used)
        
        Args:
            gameweek: Current gameweek
            current_meta: Current meta data
            
        Returns:
            True if this is a free hit revert scenario
        """
        # Check if free hit was used in the PREVIOUS gameweek by loading that team file
        # We can't rely on meta.json because it only tracks if a chip was ever used,
        # not which specific gameweek it was used in
        previous_gw = gameweek - 1
        if previous_gw >= 1:
            previous_team_data = self.load_team(previous_gw)
            if previous_team_data and previous_team_data.get('team'):
                # Check if the previous gameweek's team used a free hit chip
                chip_used = previous_team_data['team'].get('chip')
                if chip_used == 'free_hit':
                    # Check if we have a team from before the free hit (2 gameweeks ago)
                    pre_free_hit_gw = gameweek - 2
                    if pre_free_hit_gw >= 1:
                        pre_free_hit_team = self.load_team(pre_free_hit_gw)
                        if pre_free_hit_team:
                            return True
        return False
    
    def calculate_team_budget(self, team_data: Dict[str, Any], current_players: Dict[str, Dict[str, Any]]) -> float:
        """Calculate available budget for wildcard/free hit using correct FPL sale price formula
        
        Args:
            team_data: Team data
            current_players: Current players data
            
        Returns:
            Available budget
        """
        total_value = 0.0
        payload = extract_team_payload(team_data)

        for player in payload.get('starting', []) + payload.get('substitutes', []):
            player_name = player['name']
            current_player = current_players.get(player_name)

            if current_player:
                if 'current_price' in current_player:
                    current_price = float(current_player['current_price'])
                elif 'now_cost' in current_player:
                    now_cost = float(current_player['now_cost'])
                    # FPL API stores tenths of millions (e.g. 55 = £5.5m)
                    current_price = now_cost / 10.0 if now_cost > 20 else now_cost
                else:
                    current_price = float(player.get('price', 0.0))
                purchase_price = float(current_player.get('purchase_price', player.get('price', 0.0)))
                total_value += calculate_fpl_sale_price(current_price, purchase_price)
            else:
                total_value += float(player.get('price', 0.0))

        return total_value + float(payload.get('bank', 0.0))

    def transfers_are_affordable(
        self,
        transfers: List[Dict[str, Any]],
        bank: float,
        current_team_player_data: Dict[str, Dict[str, Any]],
    ) -> Tuple[bool, float]:
        """Check if proposed transfers are affordable (for normal weekly updates).

        Uses FPL sale price for players out; cost is player_in_price for players in.
        Only relevant when not using wildcard/free hit.

        Args:
            transfers: List of {player_out, player_in_price, ...} dicts.
            bank: Current bank balance.
            current_team_player_data: Current squad player data (must include sale_price per player).

        Returns:
            (True, expected_new_bank) if affordable, (False, 0.0) otherwise.
            expected_new_bank = bank + sum(sale_price of outs) - sum(player_in_price of ins).
        """
        if not transfers:
            return (True, bank)
        cash_in = 0.0
        for t in transfers:
            player_out = t.get('player_out')
            if player_out is None:
                raise ValueError("Transfer missing 'player_out'")
            player_data = current_team_player_data.get(player_out)
            if player_data is None:
                raise ValueError(
                    f"Player out '{player_out}' not in current squad; "
                    "transfers must only sell current squad players."
                )
            cash_in += player_data.get('sale_price', 0.0)
        cost_out = sum(t.get('player_in_price', 0.0) for t in transfers)
        expected_bank = round(bank + cash_in - cost_out, 1)
        affordable = bank + cash_in >= cost_out
        return (affordable, expected_bank if affordable else 0.0)

    def update_meta_from_response(self, gameweek: int, team_data: Dict[str, Any], current_meta: Dict[str, Any]) -> None:
        """Update meta.json based on the LLM response"""
        payload = extract_team_payload(team_data)
        
        # Check if a chip was used
        chip_used = normalize_chip(payload.get('chip'))
        
        # Check for consecutive free hit usage (not allowed in FPL)
        if chip_used == 'free_hit':
            chips_used = current_meta.get('chips_used', {})
            if chips_used.get('free_hit', False):
                logger.warning("Free hit cannot be used in consecutive gameweeks")
                # Don't mark free hit as used again
                chip_used = None
        
        # Calculate new free transfers
        current_transfers = current_meta.get('free_transfers_carried_over', self.DEFAULT_FREE_TRANSFERS)
        available_this_week = min(current_transfers + 1, self.MAX_FREE_TRANSFERS)
        transfers_made = len(payload.get('transfers') or [])
        
        if chip_used in ('wildcard', 'free_hit'):
            # WC/FH do not consume or reset banked free transfers
            new_transfers = current_transfers
        else:
            # Remaining FTs after this week's usage (hits do not create negative carry).
            # Cap at MAX-1 so next week's +1 grant cannot exceed MAX_FREE_TRANSFERS.
            new_transfers = max(0, available_this_week - transfers_made)
            new_transfers = min(new_transfers, self.MAX_FREE_TRANSFERS - 1)
        
        # Handle chip usage and reset on Gameweek 20
        chips_used = None
        if chip_used:
            chips_used = {chip_used: True}
        
        # Reset all chips on Gameweek 20 (second half of season)
        if gameweek == self.CHIP_RESET_GAMEWEEK:
            chips_used = {
                chip: False for chip in self.CHIP_NAMES
            }
            logger.info("Gameweek 20: All chips reset for second half of season")
        
        # Update meta.json (payload has bank/chip/transfers at the correct level)
        self._update_meta(
            gameweek=gameweek,
            team_data=payload,
            chips_used=chips_used,
            free_transfers_carried_over=new_transfers
        )
        
        logger.info(f"Meta updated: transfers={new_transfers}, chip_used={chips_used}")
    
    def get_available_chips_from_meta(self, meta_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get available chips information from meta data"""
        chips_used = meta_data.get('chips_used', {})
        available_chips = []
        used_chips = []
        
        all_chips = self.CHIP_NAMES
        for chip in all_chips:
            if chips_used.get(chip, False):
                used_chips.append({'name': chip})
            else:
                available_chips.append(chip)
        
        return {
            'used': used_chips,
            'available': available_chips
        }
    
    def get_available_transfers_from_meta(self, meta_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get available transfer information from meta data"""
        current_gw = meta_data.get('current_gw', 1)
        free_transfers_carried_over = meta_data.get(
            'free_transfers_carried_over', self.DEFAULT_FREE_TRANSFERS
        )
        available_this_week = min(free_transfers_carried_over + 1, self.MAX_FREE_TRANSFERS)
        
        return {
            'current_gw': current_gw,
            'free_transfers_carried_over': free_transfers_carried_over,
            'free_transfers_available': available_this_week,
            # Always true once a season week has started (0 carried still means 1 this week)
            'can_make_transfers': available_this_week > 0
        }
    
    def get_team_context(self, gameweek: int) -> Dict[str, Any]:
        """
        Get all team context needed for weekly update in one call.
        Returns: team, chips, transfers, bank, formation, etc.
        """
        meta_data = self.get_meta()
        
        # Handle free hit revert scenario
        if self.is_free_hit_revert_scenario(gameweek, meta_data):
            # Get the team from 2 gameweeks ago (before free hit)
            team_data = self.load_team(gameweek - 2)
            logger.info(f"Free Hit revert: Using team from gameweek {gameweek - 2}")
        else:
            # Normal case: get team from previous gameweek
            team_data = self.get_previous_team(gameweek)
        
        if not team_data:
            # Fallback to latest available team
            latest_gw = self.get_latest_gameweek()
            if latest_gw:
                team_data = self.load_team(latest_gw)
        
        # Calculate current week's available transfers (carried + 1 weekly grant, capped at 5)
        stored_transfers = meta_data.get('free_transfers_carried_over', 0)
        current_week_transfers = min(stored_transfers + 1, self.MAX_FREE_TRANSFERS)
        
        return {
            'team': team_data['team'] if team_data else None,  # Return team data, not file wrapper
            'chips': self.get_available_chips_from_meta(meta_data),
            'transfers': self.get_available_transfers_from_meta(meta_data),
            'bank': meta_data.get('bank', 0.0),
            'free_transfers': current_week_transfers,  # What LLM sees in prompt (1–5)
            'gameweek': gameweek
        }

    def save_weekly_update(self, team_result: Dict[str, Any], team_context: Dict[str, Any]) -> None:
        """
        Save weekly update team and update meta.
        Moved from main.py to consolidate team save operations.
        
        Args:
            team_result: Team result from LLM strategy
            team_context: Current team context
        """
        payload = extract_team_payload(team_result)
        # Save team using existing method
        self.save_team(team_context['gameweek'], payload)
        
        # Update meta using existing method
        self.update_meta_from_response(team_context['gameweek'], payload, self.get_meta())

    def save_new_team(self, team_result: Dict[str, Any], gameweek: int, reset_meta: bool = False) -> None:
        """
        Save new team and initialize or preserve meta.

        Args:
            team_result: Team result from LLM strategy
            gameweek: Gameweek number
            reset_meta: If True, wipe chips/FTs (fresh season start). If False, preserve
                existing meta when present (e.g. wildcard/free-hit rebuild via build-team).
        """
        payload = extract_team_payload(team_result)
        self.save_team(gameweek, payload)

        existing_meta = self._load_meta()
        has_existing = bool(existing_meta and existing_meta.get('last_team_file'))

        if reset_meta or not has_existing:
            self.initialize_meta(gameweek, payload)
            # If this fresh build includes a chip (unusual for GW1), mark it
            chip = normalize_chip(payload.get('chip'))
            if chip:
                self._update_meta(gameweek, payload, chips_used={chip: True})
        else:
            # Preserve chips_used and free_transfers_carried_over; apply response side-effects
            self.update_meta_from_response(gameweek, payload, existing_meta)
            logger.info(
                "Preserved existing meta for '%s' while saving gameweek %s team",
                self.team_name,
                gameweek,
            )
