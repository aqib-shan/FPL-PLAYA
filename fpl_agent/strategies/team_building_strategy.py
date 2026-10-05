"""
FPL team manager using LLM for comprehensive team management
"""

import logging
from typing import Dict, Any, List, Optional

from ..core.config import Config
from ..core.team_manager import TeamManager
from .base_strategy import BaseLLMStrategy
from ..utils.validator import Validator
from ..utils.prompt_formatter import PromptFormatter
from ..utils.schemas import create_team_creation_schema, create_weekly_update_schema
from ..utils.team_utils import extract_team_payload, normalize_chip

logger = logging.getLogger(__name__)


class TeamBuildingStrategy(BaseLLMStrategy):
    """
    LLM-based strategy for FPL team creation and weekly management.
    
    This class handles:
    - Team creation for Gameweek 1 using LLM analysis
    - Weekly team updates and transfers using LLM insights
    - Chip and wildcard management with LLM recommendations
    """
    
    def __init__(self, config: Config, model_name: str = "main_openrouter"):
        super().__init__(config, model_name)
        self.team_manager = TeamManager()
        self.validator = Validator(config)
    
    def get_strategy_name(self) -> str:
        """Return the name of this strategy."""
        return "Team Building Strategy"
    
    def create_team(self, budget: float, gameweek: int, 
                    all_gameweek_data: Dict[str, Any], 
                    use_enrichments: bool = False,
                    use_ranking: bool = False,
                    prompt_only: bool = False) -> Dict[str, Any]:
        """
        Create new team using LLM and provided input information.

        Args:
            budget: The budget for the team
            gameweek: The gameweek to create the team for
            all_gameweek_data: All gameweek data for that week
            use_enrichments: Whether to use enrichments in the prompt
            use_ranking: Whether to use ranking in the prompt
            prompt_only: Whether to return the prompt only

        Returns:
            The team data
        """
        try:
            # Create the team creation prompt
            prompt = self._create_team_creation_prompt(
                budget,
                gameweek,
                all_gameweek_data['players'],
                all_gameweek_data['fixtures'],
                use_enrichments,
                use_ranking,
                all_fixtures=all_gameweek_data.get('all_fixtures') or [],
            )
            
            if prompt_only:
                return {'prompt': prompt}
            
            # Define LLM response schema for team creation
            response_schema = create_team_creation_schema()
            
            # Send to LLM
            response = self.llm_engine.query(prompt, response_schema)
            
            # Parse and validate LLM response
            team_data = self.validator.parse_llm_json_response(response)
            team = extract_team_payload(team_data)
            
            # Validate team structure
            logger.info("Validating team structure...")
            validation_errors = self.validator.validate_team_data(team_data, budget)
            
            if validation_errors:
                error_msg = "Team validation failed:\n" + "\n".join(f"- {error}" for error in validation_errors)
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Deterministic bank: budget remaining after squad cost
            total_cost = float(team.get('total_cost', 0.0))
            team['bank'] = round(max(0.0, float(budget) - total_cost), 1)
            team['chip'] = normalize_chip(team.get('chip'))
            
            # Return canonical wrapped shape
            return {'team': team}
            
        except Exception as e:
            logger.error(f"Failed to create team: {e}")
            raise
    
    def update_team_weekly(self, team_context: Dict[str, Any], 
                           all_gameweek_data: Dict[str, Any], 
                           use_enrichments: bool = False,
                           use_ranking: bool = False,
                           prompt_only: bool = False) -> Dict[str, Any]:
        """
        Update team using LLM and provided input information.

        Args:
            team_context: All data on the current team, including the team, chips, transfers, and current team player data
            all_gameweek_data: All gameweek data for that week
            use_enrichments: Whether to use enrichments in the prompt
            use_ranking: Whether to use ranking in the prompt
            prompt_only: Whether to return the prompt only
        
        Returns team data (does NOT save or handle business logic)
        """
        try:
            # Extract data from consolidated parameters
            gameweek = team_context['gameweek']
            current_team = team_context['team']
            chips_data = team_context['chips']
            free_transfers = team_context['free_transfers']
            current_team_player_data = team_context['current_team_player_data']
            bank = team_context['bank']
            
            # Calculate team budget - used to validate generated team meets budget constraints
            team_budget = self.team_manager.calculate_team_budget(current_team, current_team_player_data)
            
            # Create the weekly update prompt
            prompt = self._create_weekly_update_prompt(
                current_team, current_team_player_data, gameweek, chips_data, 
                all_gameweek_data['players'], free_transfers, all_gameweek_data['fixtures'], 
                team_budget, bank, use_enrichments, use_ranking,
                all_fixtures=all_gameweek_data.get('all_fixtures') or [],
            )
            
            if prompt_only:
                return {'prompt': prompt}
            
            # Send to LLM with response schema
            response_schema = create_weekly_update_schema()

            # Send to LLM
            response = self.llm_engine.query(prompt, response_schema)
            
            # Parse and validate LLM response
            team_data = self.validator.parse_llm_json_response(response)
            team = extract_team_payload(team_data)
            chip = normalize_chip(team.get('chip'))
            team['chip'] = chip
            use_full_squad_budget_check = chip in ('wildcard', 'free_hit')

            if use_full_squad_budget_check:
                logger.info("Validating team structure (full-squad budget check)...")
                validation_errors = self.validator.validate_team_data(team_data, team_budget)
                # Deterministic bank after full rebuild
                total_cost = float(team.get('total_cost', 0.0))
                team['bank'] = round(max(0.0, float(team_budget) - total_cost), 1)
            else:
                # Normal weekly update: validate transfer affordability, then skip full-squad cost check
                transfers = team.get('transfers') or []
                affordable, expected_bank = self.team_manager.transfers_are_affordable(
                    transfers, bank, current_team_player_data
                )
                if not affordable:
                    raise ValueError(
                        "Transfers not affordable: bank + sale(outs) < cost(ins). "
                        "Check sale prices and player_in_price for the proposed transfers."
                    )
                reported_bank = team.get('bank', 0)
                if abs(float(reported_bank) - expected_bank) > 0.1:
                    logger.warning(
                        f"Reported bank £{reported_bank}m differs from expected £{expected_bank}m after transfers; "
                        f"overwriting with calculated bank"
                    )
                # Bank is truth from sale prices + transfer costs, not the LLM
                team['bank'] = expected_bank
                logger.info("Validating team structure (transfer-affordability only)...")
                validation_errors = self.validator.validate_team_data(
                    team_data, team_budget, skip_full_squad_budget_check=True
                )

            if validation_errors:
                error_msg = "Team validation failed:\n" + "\n".join(f"- {error}" for error in validation_errors)
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Return canonical wrapped shape (NO SAVING, NO BUSINESS LOGIC)
            return {'team': team}
            
        except Exception as e:
            logger.error(f"Failed to update team: {e}")
            raise
    
    def _create_team_creation_prompt(self, budget: float, gameweek: int, 
                                    players_data: Dict[str, Dict[str, Any]], 
                                    fixtures_data: List[Dict[str, Any]],
                                    use_enrichments: bool = True,
                                    use_ranking: bool = True,
                                    all_fixtures: Optional[List[Dict[str, Any]]] = None) -> str:
        """Create the team creation prompt
        
        Args:
            budget: The budget for the team
            gameweek: The gameweek to create the team for
            players_data: All player data for that week
            fixtures_data: Fixture data for that week
            use_enrichments: Whether to use enrichments in the prompt
            use_ranking: Whether to use ranking in the prompt
            all_fixtures: Full-season fixtures for landscape summary

        Returns:
            The team creation prompt
        """
        
        # Get selection counts from config if using ranking
        selection_counts = None
        if use_ranking:
            embeddings_config = self.config.get_embeddings_config()
            selection_counts = embeddings_config.get('selection_counts')

        landscape_source = all_fixtures if all_fixtures else fixtures_data
        fixture_landscape = PromptFormatter.format_fixture_landscape(
            landscape_source, gameweek, horizon=5
        )
        
        return f"""You are a Fantasy Premier League (FPL) team building expert. Your task is to create the optimal FPL team for Gameweek {gameweek}.

CRITICAL INSTRUCTION: You MUST respond with ONLY valid JSON. Do not include any markdown, explanations, or text outside the JSON structure. Your entire response must be a single, valid JSON object.

You must research and analyse the top Fantasy Premier League (FPL) strategies, tips, and recommendations for the upcoming gameweeks. Use a wide range of sources, including expert predictions, blogs, community forums, news articles, fixture difficulty analysis, and pre-season form. Identify underpriced players, strong upcoming fixtures, expected starters, set-piece takers, and hidden value. Your goal is to build the best possible squad for Gameweek {gameweek} and beyond.

GAMEWEEK CONTEXT:
Season: 2026/2027
Gameweek: {gameweek}

You must strictly follow all official FPL rules and constraints when building the team:
* The total budget must not exceed £{budget}m.
{PromptFormatter.format_team_constraints(self.config)}
* A maximum of 3 players are allowed from any single Premier League club.
* Favour players with strong upcoming fixtures and minimal rotation risk.
* Consider injury risks, suspension, rotation, and likely minutes played.

SEASON ENGINE NOTES (2026/27):
* BPS: centre-back clearances/blocks/interceptions now score 1 BPS per 3 actions (was per 2). Direct attackers are no longer penalised for lost tackles — weigh attacking returns accordingly.
* Price rises/falls finalize daily. Gameweek rankings and player points do not lock until 09:00 UK time the morning after the final fixture of the gameweek.

The fixtures this gameweek are:

{PromptFormatter.format_fixtures(fixtures_data, gameweek)}

{fixture_landscape}

{self._get_prompt_intro(use_enrichments=use_enrichments)}

{PromptFormatter.format_player_list(players_data, use_enrichments=use_enrichments, use_ranking=use_ranking, selection_counts=selection_counts)}

If a player is injured, suspended or has a low likelihood of playing, you must be careful to check the reasoning behind this and if they are not going to play not select them, since this will result in a loss of points.

Once the squad is selected:
1. Choose a starting 11 based on expected Gameweek {gameweek} performance and the upcoming gameweeks.
2. Rank the 4 substitutes in expected points order: Sub 1 (highest priority), Sub 2, Sub 3, and the backup goalkeeper.
3. Select a captain with the highest expected points and a strong fixture.
4. Select a vice-captain who is a reliable starter with good expected value.

IMPORTANT: For each player selection, provide a clear, detailed reason explaining:
- Why this player was selected (form, fixtures, value, etc.)
- For starting players: Why they are in the starting 11
- For substitutes: Why they are on the bench and their sub order priority
- For captain: Why they are the best captain choice (fixtures, form, reliability)
- For vice-captain: Why they are the best vice-captain choice

Base your reasoning on the latest expert tips, community insights, and statistical analysis you've researched.

FINAL INSTRUCTION: You MUST respond with ONLY the following JSON format. No other text, no markdown, no explanations outside the JSON:

{{
  "team": {{
    "captain": "CAPTAIN NAME",
    "vice_captain": "VICE CAPTAIN NAME",
    "captain_reason": "Detailed explanation of why this player is the best captain choice for this gameweek",
    "vice_captain_reason": "Detailed explanation of why this player is the best vice-captain choice for this gameweek",
    "total_cost": {budget}.0,
    "bank": 0.0,
    "expected_points": 65.0,
    "starting": [
      {{ 
        "name": "Player 1", 
        "position": "MID", 
        "price": 8.5, 
        "team": "Arsenal",
        "reason": "Detailed explanation of why this player was selected for the starting 11, including form, fixtures, value, and expert recommendations"
      }},
      ...
    ],
    "substitutes": [
      {{ 
        "name": "Sub 1", 
        "position": "DEF", 
        "price": 4.5, 
        "team": "Brentford", 
        "sub_order": 1,
        "reason": "Detailed explanation of why this player is on the bench, their sub order priority, and when they would be most useful"
      }},
      {{ 
        "name": "Sub 2", 
        "position": "MID", 
        "price": 5.0, 
        "team": "Burnley", 
        "sub_order": 2,
        "reason": "Detailed explanation of why this player is on the bench, their sub order priority, and when they would be most useful"
      }},
      {{ 
        "name": "Sub 3", 
        "position": "FWD", 
        "price": 5.5, 
        "team": "Wolves", 
        "sub_order": 3,
        "reason": "Detailed explanation of why this player is on the bench, their sub order priority, and when they would be most useful"
      }},
      {{ 
        "name": "Backup Goalkeeper", 
        "position": "GK", 
        "price": 4.0, 
        "team": "Sheffield Utd", 
        "sub_order": null,
        "reason": "Detailed explanation of why this goalkeeper was selected as backup"
      }}
    ]
  }}
}}

Ensure the final team meets all FPL constraints before submitting:
* Total cost ≤ £{budget}.0 million
* {self.config.get_team_config().get('squad_size', 15)} total players: {self.config.get_position_limits()['GK']} goalkeepers, {self.config.get_position_limits()['DEF']} defenders, {self.config.get_position_limits()['MID']} midfielders, {self.config.get_position_limits()['FWD']} forwards
* Max {self.config.get_position_limits().get('max_players_per_team', 3)} players from any single club
* Valid formation for starting 11 (1GK, {self.config.get_formation_constraints()['DEF'][0]}–{self.config.get_formation_constraints()['DEF'][1]} DEF, {self.config.get_formation_constraints()['MID'][0]}–{self.config.get_formation_constraints()['MID'][1]} MID, {self.config.get_formation_constraints()['FWD'][0]}–{self.config.get_formation_constraints()['FWD'][1]} FWD)

Each player must have a detailed, informative reason for their selection.

REMEMBER: Your response must be ONLY valid JSON. No markdown, no explanations, no text outside the JSON structure."""
    
    def _create_weekly_update_prompt(self, current_team: Dict, current_team_player_data: Dict[str, Dict[str, Any]], 
                                     gameweek: int, chips_data: Dict, players_data: Dict[str, Dict[str, Any]], 
                                     free_transfers: float, fixtures_data: List[Dict[str, Any]], team_budget: float,
                                     bank: float, use_enrichments: bool = True,
                                     use_ranking: bool = True,
                                     all_fixtures: Optional[List[Dict[str, Any]]] = None
                                   ) -> str:
        """Create the weekly update prompt
        
        Args:
            current_team: The current team, including the starting 11 and substitutes
            current_team_player_data: All player data for the current team
            gameweek: The gameweek to update the team for
            chips_data: All chip data for that week
            players_data: All player data for that week
            free_transfers: Number of free transfers available this week
            fixtures_data: Fixture data for that week
            bank: The bank for the team
            use_enrichments: Whether to use enrichments in the prompt
            use_ranking: Whether to use ranking in the prompt
            all_fixtures: Full-season fixtures for landscape summary

        Returns:
            The weekly update prompt
        """
        # Get selection counts from config if using ranking
        selection_counts = None
        if use_ranking:
            embeddings_config = self.config.get_embeddings_config()
            selection_counts = embeddings_config.get('selection_counts')

        landscape_source = all_fixtures if all_fixtures else fixtures_data
        fixture_landscape = PromptFormatter.format_fixture_landscape(
            landscape_source, gameweek, horizon=5
        )
        availability_alerts = PromptFormatter.format_owned_availability_alerts(
            current_team, current_team_player_data
        )
        
        return f"""You are managing a Fantasy Premier League (FPL) team with the goal of maximizing points across the season.

        
GAMEWEEK CONTEXT:
Season: 2026/2027
Gameweek: {gameweek}

{PromptFormatter.format_fixtures(fixtures_data, gameweek)}

{fixture_landscape}

If a team appears multiple times in the fixtures, it is because they are playing in a double gameweek. This could be advantageous for points, as some players will play twice, thus having a greater chance of scoring more points.


YOUR CURRENT TEAM:

{PromptFormatter.format_team(current_team, current_team_player_data)}

{availability_alerts}

Current team budget (squad sale value + bank) is £{team_budget}m.
Bank is £{bank}m. Treat bank as the cash available for transfers; player Sale Prices are what you receive when selling.


PLAYER LIST:

{self._get_prompt_intro(use_enrichments, is_weekly_update=True)}

{PromptFormatter.format_player_list(players_data, use_enrichments=use_enrichments, use_ranking=use_ranking, selection_counts=selection_counts)}

YOUR TASK:
Suggest transfers, substitutions, or chip usage for this gameweek with the goal of maximising points for your FPL team.
You must clearly state your reasoning for each decision, and why you have made the decisions you have, in accordance with the output instructions below.
Remember your team must be built from your current team with only transfers on top, unless you are using a wildcard or chip.


DECISION MAKING CRITERIA:

1. Evaluate your team using the latest information available. Consider:
- Recent player performance and form
- Upcoming fixture difficulty
- Likelihood of starting and playing 90 minutes
- Rotation risk
- Injury or suspension status (see OWNED PLAYER AVAILABILITY ALERTS above)
- Transfer rumours, international absences, or tactical shifts
- Insights from expert sources, fantasy blogs, forums, news sites, and tipsters

2. Identify potential transfers
- You must research and analyse the top Fantasy Premier League (FPL) strategies, tips, and recommendations for the upcoming gameweeks. Use a wide range of sources, including expert predictions, blogs, community forums, news articles, fixture difficulty analysis, and pre-season form. Identify underpriced players, strong upcoming fixtures, expected starters, set-piece takers, and hidden value. Your goal is to build the best possible squad for Gameweek {gameweek} and beyond.
- Use this information to identify the most effective transfers, substitutions, or chip usage for the current and upcoming gameweeks.
- You can use the player list to help you identify potential transfer targets.

3. Identify potential substitutions to make to the team
- You must pick the starting 11 that is likely to score the most points, considering bringing in subs and subbing out players who may score lower points.
- You must justify with reasons and provide a sub order for each player on the bench, and why they are in that order.

4. Identify potential chip usage
- You must identify if it's worthwhile to use a chip this week, and why you have chosen it. This should be in accordance with the rules.

5. Identify the best captain and vice-captain to use this week, and why you have chosen them.


RULES:

The price of the players in your current team may be different to the price of the players in the list of available players. This is because they could have increased or decreased in price since they were picked. When selling a player use the Sale Price of the player in the squad list provided - this is their sale price.

If a player is injured, suspended or has a low likelihood of playing, you must be careful to check the reasoning behind this and if they are not going to play not select them, since this will result in a loss of points.

Transfer rules:
* You have {free_transfers} free transfers available.
* You get one free transfer each week.
* You can save up to 5 free transfers to carry over to subsequent gameweeks.
* Playing a Wildcard or Free Hit chip does not reset your saved free transfers.
* Additional transfers beyond your free transfers cost -4 points each, and should only be used if they are likely to generate greater points by using them.
* To make a transfer you must select a player in the starting 11 or substitutes and replace them with a player from the list of available players (excluding players that are already in your starting 11 or substitutes).

You don't have to use a transfer or all your free transfers for a gameweek. Banking transfers toward 4 or 5 could have high strategic value: multi-transfer moves enable structural team pivots without taking hit penalties. Weigh that against immediate points from a one-off upgrade.
If you consider this to be important you should consider the fixtures for players in the upcoming weeks too.

At the moment you have access to the following chips and wildcards: {PromptFormatter.format_chips(chips_data)}

Chip and wildcard rules:
* You can use one chip or wildcard per gameweek.
* First half of season (GW1–19): 1 wildcard + 1 of each chip (Triple Captain, Bench Boost, Free Hit)
* Second half (GW20+): another wildcard + reset of each chip
* Playing a Wildcard or Free Hit does not wipe or reset your accumulated saved free transfers — you retain them going into the following gameweek.
* Chips:
    * Wildcard: unlimited free transfers for the current week (permanent team change); saved free transfers are preserved
    * Free Hit: unlimited free transfers this gameweek only (team reverts next week); saved free transfers are preserved
    * Bench Boost: all 15 players score points
    * Triple Captain: captain's points are tripled instead of doubled

A wildcard or chip is a great way to shake up a team that's struggling or could be better with many transfers or to build extra points if a player is likely to score highly (e.g., double gameweek) or the bench players will score many points too (e.g., on a double gameweek).
If you plan to use a chip or wildcard this week, clearly state which one. If using Wildcard or Free Hit, you may omit transfers (since they are handled via chip activation). There's no point in not using a chip if you have one available, letting one expire is a waste of a free points, but these should be used sparingly and where appropriate.

SEASON ENGINE NOTES (2026/27):
* BPS: centre-back clearances/blocks/interceptions now score 1 BPS per 3 actions (was per 2). Direct attackers are no longer penalised for lost tackles — favour attackers with high involvement over pure defensive BPS magnets where relevant.
* Price rises/falls finalize daily. Gameweek rankings and player points do not lock until 09:00 UK time the morning after the final fixture of the gameweek.

After completing your analysis:
1. Decide whether to use a wildcard or chip
2. List transfers (if any)
3. Return the final team:
    * Valid formation
    * Bench ordered by expected points
    * Captain and vice-captain optimised for expected value


OUTPUT INSTRUCTIONS:
- You must return only valid JSON.
- No commentary, no markdown, no extra text.
- The output must strictly follow the JSON structure below.
- Players must be included exactly as written in the your current team and player list.
- Do not rename any player.

Important: For each decision, provide extremely concise reasoning (maximum 1-2 short sentences) explaining:
- **Transfers**: Why each transfer is being made (form, fixtures, injuries, value, etc.). If performing more transfers than you have free transfers, briefly explain why the hit is worth it.
- **Chip usage**: Why a chip should be used (or not used) this gameweek
- **Captain/Vice-captain**: Briefly why they are the best choices for this gameweek
- **Starting 11**: Briefly why each player is starting
- **Substitutes**: Briefly why each player is benched
- **Formation**: Briefly why this formation is optimal

You MUST respond with ONLY the following JSON format. No other text, no markdown, no explanations outside the JSON:


JSON STRUCTURE:

{{
  "team": {{
    "chip": null,  // or "wildcard", "bench_boost", "free_hit", "triple_captain"
    "chip_reason": "Detailed explanation of why this chip is being used (or why no chip is needed)",
    "transfers": [
      {{
        "player_in": "Player In Name",
        "player_in_price": 8.0,
        "player_out": "Player Out Name",
        "player_out_price": 7.0,
        "reason": "Detailed explanation of why this transfer is being made, including form, fixtures, injuries, value, and expert recommendations"
      }}
      // Multiple allowed if using wildcard or taking points hit
    ],
    "captain": "CAPTAIN NAME",
    "vice_captain": "VICE CAPTAIN NAME",
    "captain_reason": "Detailed explanation of why this player is the best captain choice for this gameweek",
    "vice_captain_reason": "Detailed explanation of why this player is the best vice-captain choice for this gameweek",
    "total_cost": 99.9,
    "bank": 0.1,
    "expected_points": 66.7,
    "starting": [
      {{ 
        "name": "Player 1", 
        "position": "DEF", 
        "price": 5.5, 
        "team": "Chelsea",
        "reason": "Detailed explanation of why this player is in the starting 11 for this gameweek, including form, fixtures, and tactical considerations"
      }},
      ...
    ],
    "substitutes": [
      {{ 
        "name": "Sub 1", 
        "position": "MID", 
        "price": 5.0, 
        "team": "Burnley", 
        "sub_order": 1,
        "reason": "Detailed explanation of why this player is on the bench, their sub order priority, and when they would be most useful"
      }},
      {{ 
        "name": "Sub 2", 
        "position": "DEF", 
        "price": 4.0, 
        "team": "Luton", 
        "sub_order": 2,
        "reason": "Detailed explanation of why this player is on the bench, their sub order priority, and when they would be most useful"
      }},
      {{ 
        "name": "Sub 3", 
        "position": "FWD", 
        "price": 5.5, 
        "team": "Crystal Palace", 
        "sub_order": 3,
        "reason": "Detailed explanation of why this player is on the bench, their sub order priority, and when they would be most useful"
      }},
      {{ 
        "name": "Backup Goalkeeper", 
        "position": "GK", 
        "price": 4.0, 
        "team": "Burnley", 
        "sub_order": null,
        "reason": "Detailed explanation of why this goalkeeper is the backup choice"
      }}
    ]
  }}
}}


FINAL CHECK:
Before returning your answer, double-check that your output is valid JSON and ensure the final team meets all FPL constraints before submitting:
- Bank >= 0.0
- {self.config.get_team_config().get('squad_size', 15)} total players: {self.config.get_position_limits()['GK']} goalkeepers, {self.config.get_position_limits()['DEF']} defenders, {self.config.get_position_limits()['MID']} midfielders, {self.config.get_position_limits()['FWD']} forwards
- Max {self.config.get_team_config().get('max_players_per_team', 3)} players from any single club
- Valid formation for starting 11 (1 GK, {self.config.get_formation_constraints()['DEF'][0]}–{self.config.get_formation_constraints()['DEF'][1]} DEF, {self.config.get_formation_constraints()['MID'][0]}–{self.config.get_formation_constraints()['MID'][1]} MID, {self.config.get_formation_constraints()['FWD'][0]}–{self.config.get_formation_constraints()['FWD'][1]} FWD)

Each player must have a detailed, informative reason for their selection.

REMEMBER: Your response must be ONLY valid JSON. No markdown, no explanations, no text outside the JSON structure."""
    
    def _get_prompt_intro(self, use_enrichments: bool, is_weekly_update: bool = False) -> str:
        """Get the appropriate prompt introduction based on available data
        
        Args:
            use_enrichments: Whether to use enrichments in the prompt
            is_weekly_update: Whether this is a weekly update prompt

        Returns:
            The prompt introduction
        """

        if use_enrichments:
            base_text = """The list of available players by each position, their costs, basic stats, preliminary score, expert insights and injury news are below. You should use this information to make your decisions, but use this as a starting point for wider research and don't only use this. The players are ranked based on a loose scoring system, which takes their expert insights into account using embeddings, you may use this as a starting point if you find it helpful, but don't only use this."""
        else:
            base_text = """The list of available players by each position, their costs and basic stats are below. You should use this information to make your decisions, but use this as a starting point for wider research and don't only use this."""
        
        if is_weekly_update:
            return f"{base_text} You must select the players to transfer in from this list and replace the players in your current team with these players. You cannot transfer in players that are already in your starting 11 or substitutes."
        else:
            return f"{base_text} You must select the players from this list:"