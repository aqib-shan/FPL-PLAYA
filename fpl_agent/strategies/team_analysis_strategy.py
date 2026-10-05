"""
Team Analysis Strategy

This strategy analyzes FPL teams and provides insights and recommendations.
"""

import logging
from typing import Dict, List, Any

from ..core.config import Config
from ..utils.validator import Validator
from ..utils.prompt_formatter import PromptFormatter
from ..utils.schemas import create_player_schema
from .base_strategy import BaseLLMStrategy

logger = logging.getLogger(__name__)


class TeamAnalysisStrategy(BaseLLMStrategy):
    """Strategy for analyzing FPL teams"""
    
    def __init__(self, config: Config, model_name: str = "lightweight_openrouter"):
        """
        Initialize the strategy.
        
        Args:
            config: FPL configuration object
            model_name: Name of the LLM model to use
        """

        super().__init__(config, model_name)
        self.validator = Validator(config)
    
    def get_strategy_name(self) -> str:
        """Return the name of this strategy."""

        return "TeamAnalysisStrategy"
    
    def get_team_hints_tips(self, team_name: str, team_players: List[Dict[str, Any]], current_gameweek: int, fixture_info: dict) -> Dict[str, str]:
        """
        Get hints, tips, and recommendations for players in a specific team.
        
        Args:
            team_name: Name of the team
            team_players: List of player data for the team
            current_gameweek: Current gameweek number
            fixture_info: Dictionary containing fixture information
            
        Returns:
            Dictionary mapping player names to hints and tips
        """
        logger.info(f"Getting hints and tips for {team_name}")
        
        try:
            # Create the prompt
            prompt = self._create_hints_tips_prompt(team_name, team_players, current_gameweek, fixture_info)
            
            # Debug: Log the prompt being sent
            logger.info(f"Prompt for hints/tips (length: {len(prompt)}): {prompt[:500]}...")

            # Define LLM response schema
            response_schema = create_player_schema(team_players.keys())
            
            # Get LLM response
            response = self.llm_engine.query(prompt, response_schema)
            
            # Debug: Log the response received
            logger.info(f"LLM response received (length: {len(response)}): {repr(response[:200])}")
            
            # Parse the response to extract insights for each player
            return self.validator.parse_llm_json_response(response, raise_on_error=False, expected_type="hints/tips")
            
        except Exception as e:
            logger.error(f"Failed to get hints and tips for {team_name}: {e}")
            # Return empty insights on failure
            return {}
    
    def get_team_injury_news(self, team_name: str, team_players: List[Dict[str, Any]], current_gameweek: int, fixture_info: dict) -> Dict[str, str]:
        """
        Get injury news and playing likelihood for players in a specific team.
        
        Args:
            team_name: Name of the team
            team_players: List of player data for the team
            current_gameweek: Current gameweek number
            fixture_info: Dictionary containing fixture information

        Returns:
            Dictionary mapping player names to injury news
        """
        logger.info(f"Getting injury news for {team_name}")
        
        try:            
            # Create the prompt
            prompt = self._create_injury_news_prompt(team_name, team_players, current_gameweek, fixture_info)
            
            # Debug: Log the prompt being sent
            logger.info(f"Prompt for injury news (length: {len(prompt)}): {prompt[:500]}...")
            
            # Define LLM response schema
            response_schema = create_player_schema(team_players.keys())
            
            # Get LLM response
            response = self.llm_engine.query(prompt, response_schema)
            
            # Debug: Log the response received
            logger.info(f"LLM response received (length: {len(response)}): {repr(response[:200])}")
            
            # Parse the response to extract injury news for each player
            return self.validator.parse_llm_json_response(response, raise_on_error=False, expected_type="injury news")
            
        except Exception as e:
            logger.error(f"Failed to get injury news for {team_name}: {e}")
            # Return empty injury news on failure
            return {}
    
    def get_mixed_team_expert_insights(self, player_data: Dict[str, Dict[str, Any]], current_gameweek: int, fixtures_data: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Get expert insights for a mixed group of players from different teams.
        
        Args:
            player_names: List of player names to analyze
            current_gameweek: Current gameweek number
            fixture_info: Dictionary containing fixture information
            
        Returns:
            Dictionary mapping player names to their expert insights
        """
        logger.info(f"Getting mixed team expert insights for {len(player_data)} players")
        
        try:
            # Create the mixed team prompt for expert insights
            prompt = self._create_mixed_hints_tips_prompt(player_data, current_gameweek, fixtures_data)
            
            # Debug: Log the prompt being sent
            logger.info(f"Prompt for mixed team expert insights (length: {len(prompt)}): {prompt[:500]}...")
            
            # Define LLM response schema for expert insights (same as existing team analysis)
            response_schema = create_player_schema(list(player_data.keys()))
            
            # Get LLM response
            response = self.llm_engine.query(prompt, response_schema)
            
            # Debug: Log the response received
            logger.info(f"LLM response received (length: {len(response)}): {repr(response[:200])}")
            
            # Parse the response to extract expert insights for each player
            parsed_response = self.validator.parse_llm_json_response(response, raise_on_error=False, expected_type="mixed team expert insights")
            
            if not parsed_response:
                logger.warning("Failed to parse mixed team expert insights response")
                return {}
            
            logger.info(f"Successfully processed mixed team expert insights for {len(parsed_response)} players")
            return parsed_response
            
        except Exception as e:
            logger.error(f"Failed to get mixed team expert insights: {e}")
            # Return empty results on failure
            return {}
    
    def get_mixed_team_injury_news(self, player_data: Dict[str, Dict[str, Any]], current_gameweek: int, fixtures_data: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Get injury news for a mixed group of players from different teams.
        
        Args:
            player_names: List of player names to analyze
            current_gameweek: Current gameweek number
            fixture_info: Dictionary containing fixture information
            
        Returns:
            Dictionary mapping player names to their injury news
        """
        logger.info(f"Getting mixed team injury news for {len(player_data)} players")
        
        try:
            # Create the mixed team prompt for injury news
            prompt = self._create_mixed_team_injury_news_prompt(player_data, current_gameweek, fixtures_data)
            
            # Debug: Log the prompt being sent
            logger.info(f"Prompt for mixed team injury news (length: {len(prompt)}): {prompt[:500]}...")
            
            # Define LLM response schema for injury news (same as existing team analysis)
            response_schema = create_player_schema(list(player_data.keys()))
            
            # Get LLM response
            response = self.llm_engine.query(prompt, response_schema)
            
            # Debug: Log the response received
            logger.info(f"LLM response received (length: {len(response)}): {repr(response[:200])}")
            
            # Parse the response to extract injury news for each player
            parsed_response = self.validator.parse_llm_json_response(response, raise_on_error=False, expected_type="mixed team injury news")
            
            if not parsed_response:
                logger.warning("Failed to parse mixed team injury news response")
                return {}
            
            logger.info(f"Successfully processed mixed team injury news for {len(parsed_response)} players")
            return parsed_response
            
        except Exception as e:
            logger.error(f"Failed to get mixed team injury news: {e}")
            # Return empty results on failure
            return {}
    
    def _create_hints_tips_prompt(self, team_name: str, team_players: Dict[str, Any], current_gameweek: int, fixture_info: dict) -> str:
        """Create the hints and tips prompt
        
        Args:
            team_name: Name of the team
            formatted_players: Formatted players for the prompt
            current_gameweek: Current gameweek number
            fixture_info: Dictionary containing fixture information

        Returns:
            The hints and tips prompt as a string
        """

        # Get fixture information
        fixture_str = fixture_info['fixture_str']
        is_double_gameweek = fixture_info['is_double_gameweek']
        fixture_difficulty = fixture_info['fixture_difficulty']
        
        # Create double gameweek text
        double_gameweek_text = "This is a double gameweek." if is_double_gameweek else ""
        
        return f"""Your task is to collate the Fantasy Premier League (FPL) hints, tips, and recommendations for players in the {team_name} squad. Your outputs will be used to assess whether each player is a strong pick for the upcoming gameweek.

        
GAMEWEEK CONTEXT:
- Season: 2026/2027
- Gameweek: {current_gameweek}
- Team: {team_name}
- Fixture: {team_name} are {fixture_str}
- Fixture difficulty: {fixture_difficulty}
{"- Double gameweek: " + double_gameweek_text if is_double_gameweek else ""}
Squad & stats below are for context only. Do NOT copy this section into the output. Focus on returning the JSON exactly as specified later.


{team_name.upper()} SQUAD:

{PromptFormatter.format_player_list(team_players, use_enrichments=False, use_ranking=False, show_header=False)}
YOUR TASK
For each player in the squad list provide one short sentence summarising the hints, tips and recommendations for the player in the format:
INSERT_PLAYER_TIP_STATUS - <short sentence summarising the hints, tips, and recommendations for the player>

- INSERT_PLAYER_TIP_STATUS must be one of: Must-have, Recommended, Avoid, Rotation risk.
- The sentence after the dash is mandatory and should explain why the player received that status, based on your research, recent form, expected minutes, fixture difficulty, and tactical insights.
- Do not return only the status. A sentence is required for every player.
- Example: Must-have - Haaland is starting every match, in excellent form, and has a favorable fixture.


DECISION MAKING CRITERIA:
1. Use the latest news, tips, and recommendations from trusted sources (official FPL, reliable football news outlets, manager press conferences). You may use your web search tool to fetch the most recent information.
2. If it is early in the season (Gameweek < 6), be cautious with stats since the sample size is small.
3. Stats should support decisions, but do not over-prioritize them over expert/insider insights.
4. Factors to weigh include:
    - Recent form and performance
    - Expected role and minutes
    - Set-piece duties
    - Fixture difficulty and schedule
    - Transfer advice (buy/hold/sell)
    - Tactical or rotation news
5. No player should be skipped. If information is limited, make the best possible judgment (for example, mark as "Rotation risk" if uncertain about playtime).


OUTPUT INSTRUCTIONS:
- You must return only valid JSON.
- No commentary, no markdown, no extra text.
- The output must strictly follow the JSON structure below.
- Every player from the squad list must be included exactly as written (copy keys exactly).
- Do not rename, re-order, or omit any player.


JSON STRUCTURE:
(First, produce the JSON with empty strings for each player. Then, fill them in with your recommendation.)

{PromptFormatter.format_team_analysis_output_prompt_structure(team_players)}

Important: You MUST respond with ONLY valid JSON. Do not include any markdown, explanations, or text outside the JSON structure.


FINAL CHECK: 
Before returning your answer, double-check that your output is valid JSON, that it includes every player exactly as listed, and that no names are changed, skipped, or added."""
    
    def _create_injury_news_prompt(self, team_name: str, team_players: Dict[str, Any], current_gameweek: int, fixture_info: dict) -> str:
        """Create the injury news prompt
        
        Args:
            team_name: Name of the team
            team_players: List of player data for the team
            current_gameweek: Current gameweek number
            fixture_info: Dictionary containing fixture information

        Returns:
            The injury news prompt as a string
        """
        # Get fixture information
        fixture_str = fixture_info['fixture_str']
        is_double_gameweek = fixture_info['is_double_gameweek']
        fixture_difficulty = fixture_info['fixture_difficulty']
        
        # Create double gameweek text
        double_gameweek_text = "This is a double gameweek." if is_double_gameweek else ""
        
        return f"""Your task is to collate the latest injury news on players in the {team_name} squad. Your outputs will be used to assess whether each player is fit for the upcoming gameweek.

        
GAMEWEEK CONTEXT:
- Season: 2026/2027
- Gameweek: {current_gameweek}
- Team: {team_name}
- Fixture: {team_name} are {fixture_str}
- Fixture difficulty: {fixture_difficulty}
{"- Double gameweek: " + double_gameweek_text if is_double_gameweek else ""}
Squad & stats below are for context only. Do NOT copy this section into the output. Focus on returning the JSON exactly as specified later.


{team_name.upper()} SQUAD:

{PromptFormatter.format_player_list(team_players, use_enrichments=False, use_ranking=False, show_header=False)}
YOUR TASK
For each player in the squad list provide one short sentence summarising the injury news and playing likelihood for the player in the format:
INSERT_PLAYER_AVAILABILITY_STATUS - <short sentence summarising the injury news and playing likelihood for the player>

- INSERT_PLAYER_AVAILABILITY_STATUS must be one of: Fit, Minor doubt, Major doubt, Out.
- The sentence after the dash is mandatory and should explain why the player received that status, based on your research and injury news.
- Do not return only the status. A sentence is required for every player.
- Example: Fit - Haaland is fit and available for selection.


DECISION MAKING CRITERIA:
1. Use the latest news, tips, and recommendations from trusted sources (official FPL, reliable football news outlets, manager press conferences). You may use your web search tool to fetch the most recent information.
2. If it is early in the season (Gameweek < 6), be cautious with stats since the sample size is small.
3. Factors to weigh include:
    - Current availability of the player as of gameweek {current_gameweek}. E.g., currently injured, currently suspended, currently on international duty, etc.
    - Current injury status of the player. E.g., minor injury, major injury, long term injury, etc.
    - Likelihood of playing in the next gameweek (percentage).
    - Expected return date.
    - Any reasons for whether the player could be rested for the this gameweek.
    - Any reason the player is currently out of the squad and not included, e.g., long term suspension, banned,injury or personal issues.

    
OUTPUT INSTRUCTIONS:
- You must return only valid JSON.
- No commentary, no markdown, no extra text.
- The output must strictly follow the JSON structure below.
- Every player from the squad list must be included exactly as written (copy keys exactly).
- Do not rename, re-order, or omit any player.


JSON STRUCTURE:
(First, produce the JSON with empty strings for each player. Then, fill them in with your injury news.)

{PromptFormatter.format_team_analysis_output_prompt_structure(team_players)}

Important: You MUST respond with ONLY valid JSON. Do not include any markdown, explanations, or text outside the JSON structure.


FINAL CHECK: 
Before returning your answer, double-check that your output is valid JSON, that it includes every player exactly as listed, and that no names are changed, skipped, or added."""

    def _create_mixed_hints_tips_prompt(self, player_data: Dict[str, Dict[str, Any]], current_gameweek: int, fixtures_data: List[Dict[str, Any]]) -> str:
        """Create the mixed team expert insights prompt.
        
        Args:
            player_data: Dictionary of player data to analyze
            current_gameweek: Current gameweek number
            fixtures_data: List of fixture data for the gameweek

        Returns:
            The mixed team expert insights prompt as a string
        """
        
        return f"""Your task is to collate the Fantasy Premier League (FPL) hints, tips, and recommendations for a set of players. Your outputs will be used to assess whether each player is a strong pick for the upcoming gameweek.

        
GAMEWEEK CONTEXT:
- Season: 2026/2027
- Gameweek: {current_gameweek}

{PromptFormatter.format_fixtures(fixtures_data, current_gameweek)}

PLAYERS TO ANALYZE:

{PromptFormatter.format_player_list(player_data, use_enrichments=False, use_ranking=False, show_header=False)}
YOUR TASK
For each player listed provide one short sentence summarising the hints, tips and recommendations for the player in the format:
INSERT_PLAYER_TIP_STATUS - <short sentence summarising the hints, tips, and recommendations for the player>

- INSERT_PLAYER_TIP_STATUS must be one of: Must-have, Recommended, Avoid, Rotation risk.
- The sentence after the dash is mandatory and should explain why the player received that status, based on your research, recent form, expected minutes, fixture difficulty, and tactical insights.
- Do not return only the status. A sentence is required for every player.
- Example: Must-have - Haaland is starting every match, in excellent form, and has a favorable fixture.


DECISION MAKING CRITERIA:
1. Use the latest news, tips, and recommendations from trusted sources (official FPL, reliable football news outlets, manager press conferences). You may use your web search tool to fetch the most recent information.
2. If it is early in the season (Gameweek < 6), be cautious with stats since the sample size is small.
3. Stats should support decisions, but do not over-prioritize them over expert/insider insights.
4. Factors to weigh include:
    - Recent form and performance
    - Expected role and minutes
    - Set-piece duties
    - Fixture difficulty and schedule
    - Transfer advice (buy/hold/sell)
    - Tactical or rotation news
5. No player should be skipped. If information is limited, make the best possible judgment (for example, mark as "Rotation risk" if uncertain about playtime).


OUTPUT INSTRUCTIONS:
- You must return only valid JSON.
- No commentary, no markdown, no extra text.
- The output must strictly follow the JSON structure below.
- Every player from the squad list must be included exactly as written (copy keys exactly).
- Do not rename, re-order, or omit any player.


JSON STRUCTURE:
(First, produce the JSON with empty strings for each player. Then, fill them in with your recommendation.)

{PromptFormatter.format_team_analysis_output_prompt_structure(player_data)}

Important: You MUST respond with ONLY valid JSON. Do not include any markdown, explanations, or text outside the JSON structure.


FINAL CHECK: 
Before returning your answer, double-check that your output is valid JSON, that it includes every player exactly as listed, and that no names are changed, skipped, or added."""
    
    def _create_mixed_team_injury_news_prompt(self, player_data: Dict[str, Dict[str, Any]], current_gameweek: int, fixtures_data: List[Dict[str, Any]]) -> str:
        """Create the mixed team injury news prompt.
        
        Args:
            player_data: Dictionary of player data to analyze
            current_gameweek: Current gameweek number
            fixtures_data: List of fixture data for the gameweek

        Returns:
            The mixed team injury news prompt as a string
        """
        
        return f"""Your task is to collate the latest injury news for a set of players. Your outputs will be used to assess whether each player is fit for the upcoming gameweek.

        
GAMEWEEK CONTEXT:
- Season: 2026/2027
- Gameweek: {current_gameweek}

{PromptFormatter.format_fixtures(fixtures_data, current_gameweek)}

PLAYERS TO ANALYZE:

{PromptFormatter.format_player_list(player_data, use_enrichments=False, use_ranking=False, show_header=False)}

YOUR TASK
For each player listed provide one short sentence summarising the injury news and playing likelihood for the player in the format:
INSERT_PLAYER_AVAILABILITY_STATUS - <short sentence summarising the injury news and playing likelihood for the player>

- INSERT_PLAYER_AVAILABILITY_STATUS must be one of: Fit, Minor doubt, Major doubt, Out
- The sentence after the dash is mandatory and should explain why the player received that status, based on your research and injury news.
- Do not return only the status. A sentence is required for every player.
- Example: Fit - Haaland is fit and available for selection.


DECISION MAKING CRITERIA:
1. Use the latest news, tips, and recommendations from trusted sources (official FPL, reliable football news outlets, manager press conferences). You may use your web search tool to fetch the most recent information.
2. If it is early in the season (Gameweek < 6), be cautious with stats since the sample size is small.
3. Factors to weigh include:
    - Current availability of the player as of gameweek {current_gameweek}. E.g., currently injured, currently suspended, currently on international duty, etc.
    - Current injury status of the player. E.g., minor injury, major injury, long term injury, etc.
    - Likelihood of playing in the next gameweek (percentage).
    - Expected return date.
    - Any reasons for whether the player could be rested for the this gameweek.
    - Any reason the player is currently out of the squad and not included, e.g., long term suspension, banned,injury or personal issues.

    
OUTPUT INSTRUCTIONS:
- You must return only valid JSON.
- No commentary, no markdown, no extra text.
- The output must strictly follow the JSON structure below.
- Every player from the squad list must be included exactly as written (copy keys exactly).
- Do not rename, re-order, or omit any player.


JSON STRUCTURE:
(First, produce the JSON with empty strings for each player. Then, fill them in with your injury news.)

{PromptFormatter.format_team_analysis_output_prompt_structure(player_data)}

Important: You MUST respond with ONLY valid JSON. Do not include any markdown, explanations, or text outside the JSON structure.


FINAL CHECK: 
Before returning your answer, double-check that your output is valid JSON, that it includes every player exactly as listed, and that no names are changed, skipped, or added."""
