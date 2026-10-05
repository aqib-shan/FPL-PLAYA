"""
FPL Team Validator
Validates FPL teams against official rules and checks bank calculations
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional
from ..core.config import Config

logger = logging.getLogger(__name__)

class Validator:
    """
    Validates FPL teams against official rules and checks bank calculations

    Args:
        config: Configuration
    """
    
    def __init__(self, config: Config):
        self.config = config
    
    def validate_team_data(
        self,
        team_data: Dict[str, Any],
        budget: float,
        *,
        skip_full_squad_budget_check: bool = False,
    ) -> List[str]:
        """
        Validate team data against FPL rules

        Args:
            team_data: Team data to validate
            budget: Current budget, team sale value + bank value
            skip_full_squad_budget_check: If True, do not require total_cost <= budget
                (used for normal weekly updates where only transfers are validated for affordability).

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Basic structure validation
        errors.extend(self._validate_basic_structure(team_data))

        # FPL rules validation
        errors.extend(self._validate_fpl_rules(team_data, budget, skip_full_squad_budget_check))
        
        # Formation validation
        errors.extend(self._validate_formation(team_data))
        
        # Captain validation
        errors.extend(self._validate_captain(team_data))
        
        # Substitute order validation
        errors.extend(self._validate_substitutes(team_data))
        
        return errors
    
    def _validate_basic_structure(self, team_data: Dict[str, Any]) -> List[str]:
        """Validate basic team structure
        
        Args:
            team_data: Team data to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check if team data is wrapped in a 'team' key
        if 'team' not in team_data:
            errors.append("Missing required key: 'team'")
            return errors
        
        team = team_data['team']
        
        # Required keys within the team object
        required_keys = ['captain', 'vice_captain', 'total_cost', 'bank', 'starting', 'substitutes']
        for key in required_keys:
            if key not in team:
                errors.append(f"Missing required key in team: {key}")
        
        if 'starting' in team and 'substitutes' in team:
            if len(team['starting']) != 11:
                errors.append(f"Must have exactly 11 starting players, got {len(team['starting'])}")
            if len(team['substitutes']) != 4:
                errors.append(f"Must have exactly 4 substitutes, got {len(team['substitutes'])}")
        
        return errors
    
    def _validate_fpl_rules(
        self,
        team_data: Dict[str, Any],
        budget: float,
        skip_full_squad_budget_check: bool = False,
    ) -> List[str]:
        """Validate FPL rules

        Args:
            team_data: Team data to validate
            budget: Current budget (full squad sale value + bank)
            skip_full_squad_budget_check: If True, do not add total_cost vs budget error

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if 'team' not in team_data:
            return errors

        team = team_data['team']
        all_players = team.get('starting', []) + team.get('substitutes', [])

        # Get constraints from config
        position_limits = self.config.get_position_limits()
        squad_size = self.config.get_team_config().get('squad_size', 15)
        max_players_per_team = self.config.get_team_config().get('max_players_per_team', 3)

        # Check squad size
        if len(all_players) != squad_size:
            errors.append(f"Must have exactly {squad_size} players, got {len(all_players)}")
            return errors

        # Check position distribution
        position_counts = {'GK': 0, 'DEF': 0, 'MID': 0, 'FWD': 0}
        team_counts = {}

        for player in all_players:
            # Count positions
            position = player.get('position')
            if position in position_counts:
                position_counts[position] += 1

            # Count teams
            team_name = player.get('team')
            if team_name:
                team_counts[team_name] = team_counts.get(team_name, 0) + 1

        # Validate position counts
        for pos, limit in position_limits.items():
            if position_counts.get(pos, 0) != limit:
                errors.append(f"Must have exactly {limit} {pos.lower()}s, got {position_counts.get(pos, 0)}")

        # Validate team limits
        for team_name, count in team_counts.items():
            if count > max_players_per_team:
                errors.append(f"Maximum {max_players_per_team} players allowed from {team_name}, got {count}")

        # Check total cost vs budget (skip for normal weekly updates; only for wildcard/free hit)
        if not skip_full_squad_budget_check:
            total_cost = team.get('total_cost', 0)
            if total_cost > budget:
                errors.append(f"Total cost £{total_cost}m exceeds budget of £{budget}m")

        # Check bank
        bank = team.get('bank', 0)
        if bank < 0:
            errors.append(f"Bank must be greater than or equal to 0, got £{bank}m")
        
        return errors
    
    def _validate_formation(self, team_data: Dict[str, Any]) -> List[str]:
        """Validate formation is legal
        
        Args:
            team_data: Team data to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if 'team' not in team_data:
            return errors
        
        starting = team_data['team'].get('starting', [])
        if len(starting) != 11:
            return errors
        
        # Count positions in starting 11
        position_counts = {'GK': 0, 'DEF': 0, 'MID': 0, 'FWD': 0}
        for player in starting:
            position = player.get('position')
            if position in position_counts:
                position_counts[position] += 1
        
        # Get formation constraints from config
        formation_constraints = self.config.get_formation_constraints()
        
        # Validate formation
        if position_counts['GK'] != 1:
            errors.append(f"Must have exactly 1 goalkeeper in starting 11, got {position_counts['GK']}")
        
        for pos, (min_count, max_count) in formation_constraints.items():
            count = position_counts.get(pos, 0)
            if not (min_count <= count <= max_count):
                errors.append(f"Must have {min_count}-{max_count} {pos.lower()}s in starting 11, got {count}")
        
        return errors
    
    def _validate_captain(self, team_data: Dict[str, Any]) -> List[str]:
        """Validate captain and vice-captain
        
        Args:
            team_data: Team data to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if 'team' not in team_data:
            return errors
        
        team = team_data['team']
        captain = team.get('captain')
        vice_captain = team.get('vice_captain')
        
        if not captain:
            errors.append("Captain is required")
        if not vice_captain:
            errors.append("Vice-captain is required")
        
        if captain and vice_captain and captain == vice_captain:
            errors.append("Captain and vice-captain must be different players")
        
        # Check captain and vice-captain are in the team
        all_players = team.get('starting', []) + team.get('substitutes', [])
        player_names = [p.get('name') for p in all_players]
        
        if captain and captain not in player_names:
            errors.append(f"Captain '{captain}' is not in the team")
        if vice_captain and vice_captain not in player_names:
            errors.append(f"Vice-captain '{vice_captain}' is not in the team")
        
        return errors
    
    def _validate_substitutes(self, team_data: Dict[str, Any]) -> List[str]:
        """Validate substitute order
        
        Args:
            team_data: Team data to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if 'team' not in team_data:
            return errors
        
        substitutes = team_data['team'].get('substitutes', [])
        
        # Check for exactly one goalkeeper
        gk_count = sum(1 for p in substitutes if p.get('position') == 'GK')
        if gk_count != 1:
            errors.append(f"Must have exactly 1 goalkeeper on bench, got {gk_count}")
        
        # Check sub order for non-GK players
        sub_orders = []
        for player in substitutes:
            if player.get('position') != 'GK':
                sub_order = player.get('sub_order')
                if sub_order is None:
                    errors.append(f"Player '{player.get('name')}' missing sub_order")
                elif sub_order in sub_orders:
                    errors.append(f"Duplicate sub_order {sub_order}")
                else:
                    sub_orders.append(sub_order)
        
        # Check sub orders are 1, 2, 3
        expected_orders = [1, 2, 3]
        if sorted(sub_orders) != expected_orders:
            errors.append(f"Sub orders should be 1, 2, 3, got {sorted(sub_orders)}")
        
        return errors
    
    def parse_llm_json_response(self, response: str, raise_on_error: bool = True, 
                               expected_type: str = "any") -> Dict[str, Any]:
        """
        Parse LLM JSON response with robust error handling and fallback parsing.
        
        Note: This function is still needed even when using Google GenAI ResponseSchema,
        as it provides fallback parsing for edge cases and malformed responses.
        
        Args:
            response: Raw LLM response string
            expected_type: Type of response being parsed (for logging)
            raise_on_error: Whether to raise exceptions on parsing errors
            
        Returns:
            Parsed JSON as dictionary, or empty dict on error
        """
        try:
            # Debug: Log the raw response
            logger.info(f"Raw LLM response for {expected_type} (length: {len(response)}): {repr(response[:500])}")
            
            # Check if response is an error message
            if response.startswith('Error:'):
                error_msg = f"LLM returned error: {response}"
                logger.error(error_msg)
                if raise_on_error:
                    raise ValueError(error_msg)
                return {}
            
            # Try to extract JSON from the response
            response_text = response.strip()
            
            # Handle markdown code blocks (models often wrap JSON despite "JSON only" instructions)
            response_text = re.sub(
                r"^\s*```(?:json)?\s*",
                "",
                response_text,
                count=1,
                flags=re.IGNORECASE,
            )
            response_text = re.sub(r"\s*```\s*$", "", response_text)
            
            # Extract JSON content between braces (fallback method)
            if not response_text or response_text.find('{') == -1:
                # Try to find JSON content in the response
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start == -1 or json_end == 0:
                    error_msg = f"No JSON found in response for {expected_type}"
                    logger.error(f"{error_msg}")
                    logger.error(f"Response content: {repr(response)}")
                    logger.error(f"Response length: {len(response)}")
                    logger.error(f"Response starts with: {repr(response[:100])}")
                    if raise_on_error:
                        raise ValueError(error_msg)
                    return {}
                
                response_text = response[json_start:json_end]
            
            # Debug: Log the cleaned response
            logger.info(f"Cleaned response text for {expected_type} (length: {len(response_text)}): {repr(response_text[:500])}")
            
            # Check if response is empty
            if not response_text:
                error_msg = f"Response is empty after cleaning for {expected_type}"
                logger.error(error_msg)
                logger.error(f"Original response: {repr(response)}")
                logger.error(f"Cleaned response: {repr(response_text)}")
                if raise_on_error:
                    raise ValueError(error_msg)
                return {}
            
            parsed = json.loads(response_text)
            logger.debug(f"Successfully parsed {expected_type} response: {parsed}")
            
            return parsed
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON response for {expected_type}: {e}"
            logger.error(error_msg)
            logger.error(f"JSON string that failed to parse: {response_text if 'response_text' in locals() else 'Not available'}")
            logger.error(f"Full response: {repr(response)}")
            if raise_on_error:
                raise ValueError(error_msg)
            return {}
        except Exception as e:
            error_msg = f"Failed to parse {expected_type} response: {e}"
            logger.error(error_msg)
            logger.error(f"Response that failed to parse: {repr(response)}")
            logger.error(f"Exception type: {type(e).__name__}")
            if raise_on_error:
                raise
            return {} 