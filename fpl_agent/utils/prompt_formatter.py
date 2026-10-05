"""
Prompt formatting utilities for FPL strategies
"""

from datetime import datetime
import logging
from typing import Dict, List, Any, Optional
import json

from ..core.config import Config
from .keyword_extractor import select_players_two_stage, TIER_NAMES

logger = logging.getLogger(__name__)


class PromptFormatter:
    """Utility class for formatting data into LLM prompts"""
    
    @staticmethod
    def format_player_list(players_data: Dict[str, List[Dict[str, Any]]], use_enrichments: bool = True, use_ranking: bool = True, show_header: bool = True, selection_counts: Optional[Dict[str, int]] = None) -> str:
        """
        Format player data for LLM prompts.
        Lists all the players data in paragraphs, grouped by team or position.
        If not use_ranking, players are sorted by position and total points.
        If use_ranking, players are sorted by position rank and filtered to top players.
        
        Args:
            players_data: Dictionary of player data grouped by team or position
            use_enrichments: Whether to include expert insights and injury news
            use_ranking: Whether to include ranking numbers and filter to top players
            show_header: Whether to include a header for the team or position
            selection_counts: Dictionary of position -> count for filtering (e.g., {'GK': 15, 'DEF': 60}). If None, uses defaults.
        Returns:
            Formatted string for LLM prompts
        """

        try:
            if not use_ranking:
                group_by = "grouped_by_team"
            else:
                group_by = "grouped_by_position"
            
            # Group players by team or position
            players_data_grouped = {}
            if group_by == "grouped_by_team":
                # Group players by team
                for player in players_data.values():
                    team_name = player.get('team_name', 'Unknown')
                    if team_name not in players_data_grouped:
                        players_data_grouped[team_name] = []
                    players_data_grouped[team_name].append(player)
            elif group_by == "grouped_by_position":
                # Group players by position
                for player in players_data.values():
                    position = player.get('position', 'Unknown')
                    if position not in players_data_grouped:
                        players_data_grouped[position] = []
                    players_data_grouped[position].append(player)
            else:
                raise ValueError(f"Invalid group_by: {group_by}")
            
            # Format the data
            formatted_data = []
            
            if group_by == "grouped_by_position":
                # Define the correct position order: GK, DEF, MID, FWD
                position_order = {'GK': 0, 'DEF': 1, 'MID': 2, 'FWD': 3}
                
                # Sort positions by the defined order
                sorted_positions = sorted(players_data_grouped.keys(), key=lambda pos: position_order.get(pos, 4))
                
                for position in sorted_positions:
                    players = players_data_grouped[position]
                    
                    if show_header:
                        formatted_data.append(position.upper())
                        formatted_data.append("")  # Empty line between position heading
                    
                    # Filter out players without ranking scores
                    valid_players = [p for p in players if p.get('hybrid_score', -1) > -1]
                    
                    # Two-stage shortlist: keyword tier → cosine; always keep must-haves
                    if use_ranking and selection_counts:
                        count = selection_counts.get(position, 0)
                        sorted_players = select_players_two_stage(valid_players, count)
                    else:
                        sorted_players = sorted(
                            valid_players,
                            key=lambda p: (
                                p.get('keyword_tier', 2),
                                -(p.get('embedding_score') or 0),
                            ),
                        )
                    
                    for i, player in enumerate(sorted_players):
                        # Add ranking number if requested
                        if use_ranking:
                            player['_display_rank'] = i + 1
                        
                        formatted_data.append(PromptFormatter.format_player(player, player_type=group_by, include_enrichments=use_enrichments, include_rankings=use_ranking))
                        formatted_data.append("")  # Empty line between players
                    
                    formatted_data.append("")  # Empty line between positions
            else:
                # Logic for grouped_by_team
                for player_group, players in sorted(players_data_grouped.items()):
                    if show_header:
                        formatted_data.append(player_group.upper())
                        formatted_data.append("")  # Empty line between team heading
                    
                    # Sort players by position (GK, DEF, MID, FWD) then by total points
                    position_order = {'GK': 0, 'DEF': 1, 'MID': 2, 'FWD': 3}
                    sorted_players = sorted(
                        players, 
                        key=lambda p: (position_order.get(p.get('position', 'UNK'), 4), -p.get('total_points', 0))
                    )
                    
                    for player in sorted_players:
                        formatted_data.append(PromptFormatter.format_player(player, player_type=group_by, include_enrichments=use_enrichments, include_rankings=use_ranking))
                        formatted_data.append("")  # Empty line between players
                    
                    formatted_data.append("")  # Empty line between teams
            
            return "\n".join(formatted_data)
            
        except Exception as e:
            logger.error(f"Failed to format players for LLM: {e}")
            return "Error: Could not format player data"
        
    @staticmethod
    def format_team_analysis_output_prompt_structure(player_data: Dict[str, Any]) -> str:
        """Format player data for the output prompt structure in TeamAnalysisStrategy.
        
        Args:
            player_data: Dictionary of player data
            
        Returns:
            Formatted output prompt structure as a JSON string with all players and empty strings
        """
        
        # Create a dictionary with all players and empty strings as values
        output_structure = {}
        for player_name in player_data.keys():
            output_structure[player_name] = ""
        
        # Return as a formatted JSON string with ensure_ascii=False to preserve Unicode characters
        return json.dumps(output_structure, indent=2, ensure_ascii=False)

    @staticmethod
    def format_team(team: Dict, team_player_data: Dict) -> str:
        """Format current team data, with starting 11 and substitutes, for the prompt with enhanced player information
        
        Args:
            team: Dictionary containing the current team data, all players, substitutes and captains/vice captains.
            team_player_data: Dictionary containing the detailed player data for all players in the team.
            
        Returns:
            Formatted string of the current team for the prompt
        """
        if not team:
            return "No current team data available"
        
        formatted = []
        
        captain = team.get('captain', 'Unknown')
        vice_captain = team.get('vice_captain', 'Unknown')
        
        # Add starting players section
        formatted.append("STARTING 11")
        formatted.append("")  # Empty line for spacing
        if 'starting' in team:
            for player in team['starting']:
                player_name = player.get('name', 'Unknown')
                
                # Format player with enhanced data (include sale prices)
                if player_name in team_player_data:
                    player_info = PromptFormatter.format_player(
                        team_player_data[player_name], 
                        player_type="current_team",
                        include_enrichments=True,
                        include_sale_prices=True
                    )
                else:
                    raise ValueError(f"Player {player_name} not found in team_player_data")
                
                # Add captain/vice captain indicators to the first line
                lines = player_info.split('\n')
                if player_name == captain:
                    lines[0] += " (Captain)"
                elif player_name == vice_captain:
                    lines[0] += " (Vice Captain)"
                player_info = '\n'.join(lines)
                
                formatted.append(player_info)
                formatted.append("")  # Add spacing between players
        else:
            raise ValueError("No starting players found in team")
        
        # Add substitutes section
        formatted.append("SUBSTITUTES")
        formatted.append("")  # Empty line for spacing
        if 'substitutes' in team:
            sub_count = 1
            for player in team['substitutes']:
                player_name = player.get('name', 'Unknown')
                position = player.get('position', 'Unknown')
                
                # Format player with enhanced data (include sale prices)
                if player_name in team_player_data:
                    player_info = PromptFormatter.format_player(
                        team_player_data[player_name], 
                        player_type="current_team",
                        include_enrichments=True,
                        include_sale_prices=True
                    )
                else:
                    player_info = f"{player_name} (Data not available)"
                
                # Add sub order to first line
                lines = player_info.split('\n')
                if position == 'GK':
                    lines[0] = f"GK. {lines[0]}"
                else:
                    lines[0] = f"{sub_count}. {lines[0]}"
                player_info = '\n'.join(lines)
                
                formatted.append(player_info)
                formatted.append("")  # Add spacing between players
                
                if position != 'GK':
                    sub_count += 1

        else:
            raise ValueError("No substitutes found in team")

        return "\n".join(formatted)

    @staticmethod
    def format_owned_availability_alerts(
        team: Dict[str, Any],
        team_player_data: Dict[str, Dict[str, Any]],
        chance_threshold: float = 75.0,
    ) -> str:
        """
        Highlight owned players with low availability / injury flags.

        These players are often filtered out of the transfer candidate list, so the
        model must still see loud squad-level context here.
        """
        if not team:
            return ""

        alerts = []
        for player in (team.get('starting') or []) + (team.get('substitutes') or []):
            name = player.get('name', 'Unknown')
            data = team_player_data.get(name, {})
            chance = data.get('chance_of_playing')
            if chance is None:
                chance = 100
            injury = data.get('injury_news') or ''
            insights = data.get('expert_insights') or ''

            injury_flag = bool(injury and injury != 'None')
            low_chance = chance is not None and float(chance) < chance_threshold
            if not (low_chance or injury_flag):
                continue

            lines = [
                f"⚠ {name} ({player.get('position', '?')}, {player.get('team', '?')})",
                f"  Availability: {chance}%",
            ]
            if injury_flag:
                lines.append(f"  Injury news: {injury}")
            if insights and insights != 'None':
                lines.append(f"  Expert insights: {insights}")
            alerts.append("\n".join(lines))

        if not alerts:
            return (
                "OWNED PLAYER AVAILABILITY ALERTS:\n"
                "None — all owned players look available "
                f"(chance_of_playing ≥ {chance_threshold:.0f}% and no injury news)."
            )

        header = [
            "OWNED PLAYER AVAILABILITY ALERTS:",
            "Players below may be filtered out of the transfer list — treat these as high priority:",
            "",
        ]
        return "\n".join(header + alerts)
    
    @staticmethod
    def format_player(player_data: Dict[str, Any], 
                     player_type: str = "grouped_by_team",
                     include_enrichments: bool = True,
                     include_rankings: bool = False,
                     include_sale_prices: bool = False) -> str:
        """
        Unified player formatter for all scenarios.
        
        Args:
            player_data: Dictionary containing the player's data
            player_type: How the players are being grouped, e.g., into teams or positions, either "current_team", "grouped_by_team" or "grouped_by_team".
            include_rankings: Whether to include ranking numbers
            include_sale_prices: Whether to include sale/purchase prices (for team display)
            
        Returns:
            Formatted player string with all information
        """
        if not player_data:
            return "Player data not available"
        
        # Build the player information
        player_name = player_data.get('name', player_data.get('full_name', 'Unknown'))
        team_name = player_data.get('team', player_data.get('team_name', 'Unknown'))
        position = player_data.get('position', 'Unknown')
        
        # Build complete player string
        formatted_parts = []
        
        # First line: Player name, team, and price info
        if player_type == "grouped_by_team":
            # For team display, include position - as team is already present in the heading
            first_line = f"{player_name} ({position}"
        elif player_type == "grouped_by_position" or player_type == "current_team":
            # For position or current team display, include team name
            first_line = f"{player_name} ({team_name}"
        else:
            raise ValueError(f"Invalid player_group: {player_type}")

        if include_sale_prices:
            first_line += f", Sale Price: £{player_data.get('sale_price', 0.0)}m, Purchased For: £{player_data.get('purchase_price', 0.0)}m)"
        else:
            first_line += f", £{player_data.get('now_cost', 0.0) / 10.0}m)"
        
        # Include ranking prefix if requested, e.g., "1. Player Name (Team)"
        # Note: Ranking is now handled at the list level, not individual player level
        if include_rankings:
            # Use the temporary display rank added by the calling method
            display_rank = player_data.get('_display_rank', 0)
            if display_rank > 0:
                first_line = f" {display_rank:2d}. {first_line}"
        elif player_type == "current_team":
            first_line = f"{position.upper()} {first_line}"
        
        formatted_parts.append(first_line)
        
        # Second line: Stats section
        ppg = player_data.get('form', 0.0)
        form = player_data.get('form', 0.0)
        total_points = player_data.get('total_points', 0)
        minutes = player_data.get('minutes', 0)
        ownership = player_data.get('selected_by_percent', 0.0)
        chance = player_data.get('chance_of_playing', 100)
        
        stats_line = f"[STATS] PPG: {ppg}, Form: {form}, Total Points: {total_points}, Minutes: {minutes}"

        # Add position-specific stats
        if position in ['MID', 'FWD']:
            goals = player_data.get('goals_scored', 0)
            assists = player_data.get('assists', 0)
            stats_line += f", Goals: {goals}, Assists: {assists}"
            
        if position in ['GK', 'DEF']:
            clean_sheets = player_data.get('clean_sheets', 0)
            goals_conceded = player_data.get('goals_conceded', 0)
            stats_line += f", Clean Sheets: {clean_sheets}, Goals Conceded: {goals_conceded}"
            
        if position == 'GK':
            saves = player_data.get('saves', 0)
            stats_line += f", Saves: {saves}"
            
        # Add key performance stats
        bonus = player_data.get('bonus', 0)
        bps = player_data.get('bps', 0)
        ict_index = float(player_data.get('ict_index', 0.0))
        stats_line += f", Bonus: {bonus}, BPS: {bps}, ICT: {ict_index:.1f}"

        # Add ownership and availability
        stats_line += f", Ownership: {ownership}%, Availability: {chance}%"

        formatted_parts.append(stats_line)
        
        # Add score line if including rankings
        if include_rankings:
            embedding_score = player_data.get('embedding_score', 0.0)
            embedding_scaled = player_data.get('embedding_score_scaled')
            keyword_bonus = player_data.get('keyword_bonus', 0.0)
            keyword_tier = player_data.get('keyword_tier')
            tier_name = player_data.get('keyword_tier_name') or TIER_NAMES.get(keyword_tier, 'neutral')
            hybrid_score = player_data.get('hybrid_score', 0.0)

            if embedding_scaled is not None:
                emb_part = (
                    f"Cosine: {embedding_score:.3f} → scaled {embedding_scaled:.2f}/10"
                )
            else:
                emb_part = f"Cosine: {embedding_score:.3f}"

            score_line = (
                f"[RANK] tier={tier_name} | {emb_part} | "
                f"Keyword Bonus: {keyword_bonus:+.3f} | sort={hybrid_score:.3f}"
            )
            formatted_parts.append(score_line)
        
        if include_enrichments:
            # Add expert insights (if available)
            if player_data.get('expert_insights') and player_data['expert_insights'] != 'None':
                formatted_parts.append(f"[EXPERT INSIGHTS] {player_data['expert_insights']}")
        
            # Add injury news (if available)
            if player_data.get('injury_news') and player_data['injury_news'] != 'None':
                formatted_parts.append(f"[INJURY NEWS] {player_data['injury_news']}")
        
        return "\n".join(formatted_parts)
    
    @staticmethod
    def format_fixtures(fixtures_data: List[Dict[str, Any]], gameweek: int) -> str:
        """Format fixtures data for LLM prompts.
        
        Args:
            fixtures_data: List of fixture data for the gameweek
            gameweek: Gameweek number
            
        Returns:
            Formatted string of fixtures for prompts
        """
        if not fixtures_data:
            return f"No fixtures found for Gameweek {gameweek}"
        
        formatted_lines = [f"GAMEWEEK {gameweek} FIXTURES:", "=" * 30, ""]
        
        # Group fixtures by date
        fixtures_by_date = {}
        for fixture in fixtures_data:
            kickoff_time = fixture.get('kickoff_time')
            if kickoff_time:
                try:
                    # Parse the ISO format date from FPL API
                    fixture_date = datetime.fromisoformat(kickoff_time.replace('Z', '+00:00'))
                    date_key = fixture_date.strftime('%A %dth %B %Y')
                    if date_key not in fixtures_by_date:
                        fixtures_by_date[date_key] = []
                    fixtures_by_date[date_key].append(fixture)
                except Exception:
                    # Fallback if date parsing fails
                    if 'Unknown Date' not in fixtures_by_date:
                        fixtures_by_date['Unknown Date'] = []
                    fixtures_by_date['Unknown Date'].append(fixture)
            else:
                if 'Unknown Date' not in fixtures_by_date:
                    fixtures_by_date['Unknown Date'] = []
                fixtures_by_date['Unknown Date'].append(fixture)
        
        # Format fixtures by date
        for date_str, date_fixtures in fixtures_by_date.items():
            formatted_lines.append(f"{date_str}:")
            for fixture in date_fixtures:
                home_team = fixture.get('team_h', 'Unknown')
                away_team = fixture.get('team_a', 'Unknown')
                formatted_lines.append(f"• {home_team} vs {away_team}")
            formatted_lines.append("")
        
        return "\n".join(formatted_lines)

    @staticmethod
    def format_fixture_landscape(
        fixtures_data: List[Dict[str, Any]],
        start_gameweek: int,
        horizon: int = 5,
    ) -> str:
        """
        Summarise blanks/doubles and per-club fixture counts for upcoming gameweeks.

        Args:
            fixtures_data: Full season fixtures (not just the current GW)
            start_gameweek: First gameweek to include
            horizon: Number of gameweeks to include (inclusive of start)
        """
        if not fixtures_data:
            return "FIXTURE LANDSCAPE:\nNo fixture data available."

        end_gameweek = start_gameweek + horizon - 1
        relevant = [
            f for f in fixtures_data
            if f.get('event') is not None and start_gameweek <= int(f['event']) <= end_gameweek
        ]

        # Count fixtures per club per GW
        from collections import defaultdict
        counts: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        clubs = set()
        for fixture in relevant:
            gw = int(fixture['event'])
            home = fixture.get('team_h', 'Unknown')
            away = fixture.get('team_a', 'Unknown')
            counts[gw][home] += 1
            counts[gw][away] += 1
            clubs.add(home)
            clubs.add(away)

        lines = [
            f"FIXTURE LANDSCAPE (GW{start_gameweek}–GW{end_gameweek}):",
            "Use this for timing transfers, hits, and chips (blank/double weeks).",
            "",
        ]

        for gw in range(start_gameweek, end_gameweek + 1):
            gw_counts = counts.get(gw, {})
            doubles = sorted([c for c, n in gw_counts.items() if n >= 2])
            blanks = sorted([c for c in clubs if gw_counts.get(c, 0) == 0]) if clubs else []
            lines.append(f"GW{gw}:")
            if doubles:
                lines.append(f"  Doubles: {', '.join(doubles)}")
            else:
                lines.append("  Doubles: none")
            if blanks:
                # Cap blank list length for prompt size
                shown = blanks[:12]
                suffix = f" (+{len(blanks) - 12} more)" if len(blanks) > 12 else ""
                lines.append(f"  Blanks: {', '.join(shown)}{suffix}")
            else:
                lines.append("  Blanks: none")
            lines.append("")

        # Compact per-club run for next horizon (fixture count only)
        lines.append("Club fixture counts over this window (higher = more games):")
        club_totals = {
            club: sum(counts[gw].get(club, 0) for gw in range(start_gameweek, end_gameweek + 1))
            for club in clubs
        }
        for club, total in sorted(club_totals.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"  {club}: {total}")

        return "\n".join(lines)
        
    @staticmethod
    def format_chips(chips_data: Dict) -> str:
        """Format available chips for the prompt
        
        Args:
            chips_data: Dictionary containing the chips data

        Returns:
            Formatted string of available chips for the prompt
        """
        available_chips = []
        used_chips = chips_data.get('used', [])
        
        all_chips = ['wildcard', 'bench_boost', 'free_hit', 'triple_captain']
        for chip in all_chips:
            if chip not in [c.get('name') for c in used_chips]:
                available_chips.append(chip)
        
        return ", ".join(available_chips) if available_chips else "none"
    
    @staticmethod
    def format_team_constraints(config: Config) -> str:
        """Generate team constraints prompt from config
        
        Args:
            config: Configuration
            
        Returns:
            Formatted string of team constraints for the prompt
        """
        position_limits = config.get_position_limits()
        formation_constraints = config.get_formation_constraints()
        
        return f"""* The squad must include exactly 15 players:
    * {position_limits['GK']} goalkeepers
    * {position_limits['DEF']} defenders
    * {position_limits['MID']} midfielders
    * {position_limits['FWD']} forwards
* The starting 11 must follow valid FPL formations:
    * 1 goalkeeper
    * {formation_constraints['DEF'][0]} to {formation_constraints['DEF'][1]} defenders
    * {formation_constraints['MID'][0]} to {formation_constraints['MID'][1]} midfielders
    * {formation_constraints['FWD'][0]} to {formation_constraints['FWD'][1]} forwards"""
