#!/usr/bin/env python3
"""FPL Agent Main Module"""

import logging
import sys
from typing import Dict, Optional, Any, List
from datetime import datetime
import argparse

from .core.config import Config
from .core.team_manager import TeamManager
from .data import DataService
from .data.data_store import DataStore
from .utils.team_utils import group_players_by_team, get_team_fixture_info, get_all_teams, get_all_model_configs, extract_team_payload, normalize_chip
from .strategies.team_analysis_strategy import TeamAnalysisStrategy
from .strategies import TeamBuildingStrategy
from .utils.display import display_comprehensive_team_result, display_fetch_results, display_data_status, display_detailed_players_status, display_team_status
from .utils.missing_enrichments import get_missing_enrichments_from_data
from .data.embedding_filter import EmbeddingFilter
from .data.fpl_sync import sync_team_to_fpl


# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Default to normal mode (WARNING + ERROR only)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class FPLAgent:
    """Main FPL Agent class that orchestrates all operations."""
    
    def __init__(self, model_name: Optional[str] = None):
        """Initialize the FPL Agent with configuration and services."""
        import os
        if model_name is None:
            model_name = "main_openrouter" if os.environ.get('OPENROUTER_API_KEY') else "main"
        
        self.config = Config()
        self.data_service = DataService(self.config)
        self.llm_strategy = TeamBuildingStrategy(self.config, model_name)
        self.data_store = DataStore()
        
    def fetch_fpl_data(self, use_cached: bool = False, use_enrichments: bool = False, 
                       gameweek: Optional[int] = None, filter_unavailable_players: bool = False) -> Dict[str, Any]:
        """Fetch both FPL player data and fixtures data"""
        try:
            logger.info("Fetching FPL data...")
            
            if use_cached:
                logger.info("Loading cached FPL data...")
            else:
                logger.info("Fetching fresh FPL data...")

            if gameweek is None:
                gameweek = self.data_service.fetcher.get_current_gameweek() or 1

            if filter_unavailable_players:
                if use_enrichments:
                    filter_unavailable_players_mode = "fpl_data_and_enrichments"
                else:
                    filter_unavailable_players_mode = "fpl_data_only"
            else:
                filter_unavailable_players_mode = "no_filter"

            # For fetch command, don't filter players - show all data
            all_gameweek_data = self.data_service.get_all_gameweek_data(
                gameweek=gameweek,
                use_cached=use_cached,
                filter_unavailable_players_mode=filter_unavailable_players_mode
            )

            if not use_cached and use_enrichments:
                # If using enrichments, gets ranking by default too.
                self.enrich(all_gameweek_data, gameweek)
            
            display_fetch_results({
                'total_players': len(all_gameweek_data['players']),
                'total_fixtures': len(all_gameweek_data['fixtures']),
                'fetched_at': datetime.now().isoformat()
            }, use_cached)

            return all_gameweek_data
            
        except Exception as e:
            logger.error(f"FPL data fetch failed: {e}")
            raise
    
    def enrich(self, all_gameweek_data: Optional[Dict[str, Any]] = None, gameweek: Optional[int] = None, rank_players: Optional[bool] = True, prompt_only: bool = False, model_name: Optional[str] = None, club: Optional[str] = None, club_run_insights: bool = True, club_run_injury: bool = True) -> Dict[str, Any]:
        """Enrich player data with LLM insights including expert insights and injury news.
        If club is set (e.g. 'Arsenal'), run expert insights and/or injury news for that club only and print results (no save).
        club_run_insights and club_run_injury control which to run when club is set; both True = run both."""
        try:
            logger.info("Enriching player data with LLM insights...")
            
            import os
            if model_name is None:
                model_name = "lightweight_openrouter" if os.environ.get('OPENROUTER_API_KEY') else "lightweight"

            if gameweek is None:
                gameweek = self.data_service.fetcher.get_current_gameweek() or 1

            if all_gameweek_data is None:
                # Fetch all gameweek data in one call - when enriching used cached data - the flow should be fetch then enrich or use fetch with --use-enrichments for all.
                # For team building, filter players to only show available ones
                all_gameweek_data = self.fetch_fpl_data(
                    use_cached=True, 
                    use_enrichments=False, 
                    gameweek=gameweek, 
                    filter_unavailable_players=False
                )

            # Group players by team
            team_players = group_players_by_team(all_gameweek_data['players'])

            # Single-club enrichments: one or two queries, print results, no save
            if club is not None:
                return self._enrich_one_club(
                    club=club,
                    team_players=team_players,
                    all_gameweek_data=all_gameweek_data,
                    gameweek=gameweek,
                    model_name=model_name,
                    run_insights=club_run_insights,
                    run_injury=club_run_injury,
                )

            # Get enrichments by team
            print(f"📊 Enriching {len(all_gameweek_data['players'])} players from {len(team_players)} teams...")

            team_analysis_strategy = TeamAnalysisStrategy(self.config, model_name)
            
            # Handle prompt-only mode for first team
            if prompt_only:
                # Get the first team for prompt display
                first_team_name = list(team_players.keys())[0]
                first_team_players = team_players[first_team_name]
                first_team_fixtures = get_team_fixture_info(first_team_name, all_gameweek_data['fixtures'], gameweek)
                
                print(f"📝 Showing prompts for first team: {first_team_name}")
                print("\n" + "="*50)
                print("🔍 HINTS & TIPS PROMPT:")
                print("="*50)
                
                # Get and display hints & tips prompt
                hints_prompt = team_analysis_strategy._create_hints_tips_prompt(
                    first_team_name, 
                    first_team_players,
                    gameweek, 
                    first_team_fixtures
                )
                print(hints_prompt)
                
                print("\n" + "="*50)
                print("🏥 INJURY NEWS PROMPT:")
                print("="*50)
                
                # Get and display injury news prompt
                injury_prompt = team_analysis_strategy._create_injury_news_prompt(
                    first_team_name, 
                    first_team_players,
                    gameweek, 
                    first_team_fixtures
                )
                print(injury_prompt)
                
                print("\n" + "="*50)
                print("✅ Prompt display complete!")
                return {"prompt_only": True, "team_name": first_team_name}
            
            logger.info(f"Processing {len(team_players)} Premier League teams for enrichment")
            
            # Process each team sequentially
            for team_name, team_player_list in team_players.items():
                try:
                    team_name = list(team_player_list.values())[0].get('team_name')
                    logger.info(f"Processing team {team_name}")
                    print(f"🔄 Processing {team_name}...")
                    
                    # Get fixture information for this team
                    fixture_info = get_team_fixture_info(team_name, all_gameweek_data['fixtures'], gameweek)
                    
                    # Get expert insights from LLM strategy
                    print(f"   🔍 Getting expert insights for {team_name}...")
                    expert_insights = team_analysis_strategy.get_team_hints_tips(team_name, team_player_list, gameweek, fixture_info)
                    print(f"   📊 Expert insights received: {len(expert_insights)} players")
                    
                    # Get injury news from LLM strategy
                    print(f"   🏥 Getting injury news for {team_name}...")
                    injury_news = team_analysis_strategy.get_team_injury_news(team_name, team_player_list, gameweek, fixture_info)
                    print(f"   📊 Injury news received: {len(injury_news)} players")
                    
                    # Convert team_player_list to list of player dictionaries
                    team_players_list = list(team_player_list.values())
                    print(f"   👥 Team players list: {len(team_players_list)} players")
                    
                    # Apply enriched data to players
                    print(f"   🔄 Applying enrichments to players...")
                    self._add_enrichments_to_players(all_gameweek_data['players'], team_players_list, expert_insights, injury_news)
                    
                    print(f"   ✅ Team data enriched for {team_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to process team: {e}")
                    print(f"   ❌ Team processing failed: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            logger.info("Player enrichment completed")

            # Complete any missing enrichments for players not returned by team-specific enrichment
            print("🔄 Completing missing enrichments for players not returned by team-specific enrichment...")
            try:
                self._process_missing_enrichments_with_retries(all_gameweek_data, gameweek)
            except Exception as e:
                logger.error(f"Failed to complete missing enrichments: {e}")
                print(f"⚠️  Warning: Could not complete missing enrichments: {e}")

            # Calculate embedding scores for all players after all enrichments are complete
            if rank_players:
                print("🔄 Calculating embedding scores for all enriched players...")
                embedding_filter = EmbeddingFilter(self.config)
                player_embeddings = embedding_filter.calculate_player_embeddings(all_gameweek_data['players'], use_cached=False)
                player_embedding_scores = embedding_filter.calculate_player_embedding_scores(player_embeddings, all_gameweek_data['players'])
                
                # Add embedding scores to players
                if player_embedding_scores:
                    self._add_embedding_scores_to_players(all_gameweek_data['players'], player_embedding_scores)
                    print(f"✅ Added embedding scores for {len(player_embedding_scores)} players")
                else:
                    print("⚠️  No embedding scores calculated")

            # Save enriched data
            enriched_data = {
                'players': all_gameweek_data['players'],
                'enrichment_timestamp': datetime.now().isoformat()
            }

            self.data_service.store.save_player_data(enriched_data)
            
            print(f"✅ Successfully enriched player data for {len(all_gameweek_data['players'])} players")
                
        except Exception as e:
            logger.error(f"Failed to enrich player data: {e}")
            print(f"❌ Error enriching player data: {e}")
            raise

    def _process_missing_enrichments_with_retries(self, all_gameweek_data: Dict[str, Any], gameweek: Optional[int]) -> None:
        """Orchestrate multiple passes of missing enrichment processing."""
        # Get configuration for retry logic
        max_passes = self.config.get_embeddings_config().get('missing_enrichment_retries', {}).get('max_passes', 3)
        
        print(f"🔄 Starting missing enrichment processing with max {max_passes} passes...")
        
        previous_total_missing = float('inf')
        
        for pass_num in range(max_passes):
            # Check if there are any missing enrichments
            missing_enrichment_results = get_missing_enrichments_from_data(all_gameweek_data['players'])
            current_total = len(missing_enrichment_results['expert_insights']) + len(missing_enrichment_results['injury_news'])
            
            if current_total == 0:
                print(f"✅ Pass {pass_num + 1}: All players now have complete enrichment data!")
                break
            
            print(f"📊 Pass {pass_num + 1}: Found {len(missing_enrichment_results['expert_insights'])} players missing expert insights, {len(missing_enrichment_results['injury_news'])} players missing injury news")
            
            # Check if we're making progress
            if current_total >= previous_total_missing:
                if pass_num > 0:  # Don't show this message on first pass
                    print(f"⚠️  No progress made (still {current_total} missing), stopping iterations")
                break
            
            # Process this pass
            self._process_missing_enrichments(all_gameweek_data, missing_enrichment_results, gameweek)
            
            # Update progress tracking
            previous_total_missing = current_total
            
            # If we made minimal progress, continue to next pass
            if current_total > 0:
                print(f"   🔄 Pass {pass_num + 1} complete. {current_total} players still missing enrichments.")
                if pass_num < max_passes - 1:  # Don't show this message on the last pass
                    print("   🔄 Continuing to next pass...")
        
        # Final check and summary
        final_missing = get_missing_enrichments_from_data(all_gameweek_data['players'])
        final_total = len(final_missing['expert_insights']) + len(final_missing['injury_news'])
        
        if final_total == 0:
            print("🎉 All players successfully enriched!")
        else:
            print(f"⚠️  Enrichment complete. {final_total} players still missing data after {max_passes} passes.")
        
    def _process_missing_enrichments(self, all_gameweek_data: Dict[str, Any], missing_enrichment_results: Dict[str, List[str]], gameweek: Optional[int]) -> None:
        """Process missing enrichments for one pass only."""
        
        team_analysis_strategy = TeamAnalysisStrategy(self.config, "lightweight_openrouter")  # Use lightweight_openrouter for missing enrichments
        current_gameweek = gameweek or 1
        fixtures_data = all_gameweek_data.get('fixtures', [])

        # Process all missing expert insights in one go
        if missing_enrichment_results['expert_insights']:
            print(f"   🧠 Processing expert insights for {len(missing_enrichment_results['expert_insights'])} players...")
            # Create player data subset for the missing players
            missing_players_data = {name: all_gameweek_data['players'][name] for name in missing_enrichment_results['expert_insights']}
            expert_insights = team_analysis_strategy.get_mixed_team_expert_insights(
                missing_players_data, 
                current_gameweek, 
                fixtures_data
            )
            
            if expert_insights:
                self._add_enrichments_to_players(all_gameweek_data['players'], list(expert_insights.keys()), expert_insights, None)
                print(f"   ✅ Updated {len(expert_insights)} players with expert insights")
            else:
                print("   ⚠️  No expert insights returned from LLM")
        
        # Process all missing injury news in one go
        if missing_enrichment_results['injury_news']:
            print(f"   🏥 Processing injury news for {len(missing_enrichment_results['injury_news'])} players...")
            # Create player data subset for the missing players
            missing_players_data = {name: all_gameweek_data['players'][name] for name in missing_enrichment_results['injury_news']}
            injury_news = team_analysis_strategy.get_mixed_team_injury_news(
                missing_players_data, 
                current_gameweek, 
                fixtures_data
            )
            
            if injury_news:
                self._add_enrichments_to_players(all_gameweek_data['players'], list(injury_news.keys()), None, injury_news)
                print(f"   ✅ Updated {len(injury_news)} players with injury news")
            else:
                print("   ⚠️  No injury news returned from LLM")

    def _enrich_one_club(
        self,
        club: str,
        team_players: Dict[str, Dict[str, Dict[str, Any]]],
        all_gameweek_data: Dict[str, Any],
        gameweek: int,
        model_name: str,
        run_insights: bool = True,
        run_injury: bool = True,
    ) -> Dict[str, Any]:
        """Run expert insights and/or injury news for a single club only; print results and return (no save)."""
        # Resolve club name (case-insensitive) to exact team key
        club_lower = club.strip().lower()
        match = None
        for team_key in team_players:
            if team_key.strip().lower() == club_lower:
                match = team_key
                break
        if not match:
            available = ", ".join(sorted(team_players.keys()))
            print(f"❌ Club '{club}' not found. Available teams: {available}")
            return {"error": f"Club not found: {club}", "expert_insights": {}, "injury_news": {}}

        team_name = match
        team_player_list = team_players[team_name]
        fixture_info = get_team_fixture_info(team_name, all_gameweek_data['fixtures'], gameweek)
        strategy = TeamAnalysisStrategy(self.config, model_name)

        result: Dict[str, Any] = {"team_name": team_name, "gameweek": gameweek, "expert_insights": {}, "injury_news": {}}

        if run_insights:
            print(f"🔍 Expert insights for {team_name} (GW{gameweek})...")
            expert_insights = strategy.get_team_hints_tips(team_name, team_player_list, gameweek, fixture_info)
            if expert_insights:
                print(f"\n✅ {team_name} – expert insights ({len(expert_insights)} players):\n")
                for player_name, insight in sorted(expert_insights.items()):
                    print(f"   • {player_name}: {insight}")
                print()
                result["expert_insights"] = expert_insights
            else:
                print("   ⚠️  No expert insights returned from LLM\n")

        if run_injury:
            print(f"🏥 Injury news for {team_name} (GW{gameweek})...")
            injury_news = strategy.get_team_injury_news(team_name, team_player_list, gameweek, fixture_info)
            if injury_news:
                print(f"\n✅ {team_name} – injury news ({len(injury_news)} players):\n")
                for player_name, news in sorted(injury_news.items()):
                    print(f"   • {player_name}: {news}")
                print()
                result["injury_news"] = injury_news
            else:
                print("   ⚠️  No injury news returned from LLM\n")

        return result

    def _add_enrichments_to_players(self, players_data: Dict[str, Dict[str, Any]], 
                                      players: List, 
                                      expert_insights: Dict[str, str],
                                      injury_news: Dict[str, str]) -> None:
        """Apply enriched data to player records.
        
        Args:
            players_data: Dictionary of player data
            players: List of either player names (str) or player dicts with 'full_name' key
            expert_insights: Dictionary of expert insights for each player
            injury_news: Dictionary of injury news for each player
        """
        for player in players:
            # Handle both player names (str) and player dicts with 'full_name'
            player_name = player if isinstance(player, str) else player.get('full_name')
            if player_name and player_name in players_data:
                # Only update expert_insights if provided
                if expert_insights and player_name in expert_insights:
                    players_data[player_name]['expert_insights'] = expert_insights[player_name]
                
                # Only update injury_news if provided
                if injury_news and player_name in injury_news:
                    players_data[player_name]['injury_news'] = injury_news[player_name]
    
    def _add_embedding_scores_to_players(self, players_data: Dict[str, Dict[str, Any]], 
                                        embedding_scores: Dict[str, Dict[str, Any]]) -> None:
        """Add embedding scores to players."""
        for player_name, scores in embedding_scores.items():
            if player_name in players_data:
                players_data[player_name].update(scores)
    
    def build_team(self, team_name: str, budget: float = 100.0, gameweek: Optional[int] = None,
                   cached_only: bool = False, rag_mode: str = "ranked_enrichments", prompt_only: bool = False,
                   save_team: bool = False) -> None:
        """Build new team using LLM strategy
        
        Args:
            budget: Team budget (£)
            gameweek: Gameweek number (Default: current gameweek)
            cached_only: Use cached data only (Default: False)
            rag_mode: RAG strategy to use for team building (Default: "ranked_enrichments")
                - "none": No enrichments, no ranking
                - "enrichments": Use enrichments, no ranking
                - "ranked_enrichments": Enrichments + ranking
            prompt_only: Show the prompt that would be sent to the LLM (for debugging) (Default: False)
            save_team: Save the created team to a JSON file (Default: False)
        """
        try:
            print("⚽ Building new FPL team...")
            print(f"🔄 Using RAG mode: {rag_mode}")

            if rag_mode == "none":
                use_enrichments = False
                use_ranking = False
            elif rag_mode == "enrichments":
                use_enrichments = True
                use_ranking = False
            elif rag_mode == "ranked_enrichments":
                use_enrichments = True
                use_ranking = True
            else:
                raise ValueError(f"Invalid rag_mode: {rag_mode}")
            
            # Fetch all gameweek data in one call
            # For team building, filter players to only show available ones
            all_gameweek_data = self.fetch_fpl_data(
                use_cached=cached_only, 
                use_enrichments=use_enrichments, 
                gameweek=gameweek, 
                filter_unavailable_players=True
            )

            print(f"✅ Gameweek data loaded")
            
            # Build team using LLM strategy
            print(f"\n⚽ Building team with £{budget}m budget...")
            team_result = self.llm_strategy.create_team(
                budget=budget,
                gameweek=gameweek,
                all_gameweek_data=all_gameweek_data,
                use_enrichments=use_enrichments,
                use_ranking=use_ranking,
                prompt_only=prompt_only
            )
            
            if prompt_only:
                print("✅ Prompt generation complete!")
                print("\n" + "="*50)
                print("📝 GENERATED PROMPT:")
                print("="*50)
                print(team_result['prompt'])
                return team_result
            
            # Save team if requested
            if save_team:
                # Create team manager for this specific team
                team_manager = TeamManager(team_name=team_name, auto_create=True)
                # GW1 (or missing GW) = fresh season start → reset meta; otherwise preserve chips/FTs
                reset_meta = gameweek is None or gameweek == 1
                team_manager.save_new_team(team_result, gameweek or 1, reset_meta=reset_meta)
                print("✅ Team saved successfully!")
            else:
                print("✅ Team building complete (not saved)")
            
            # Display team results
            display_comprehensive_team_result(team_result)
            return team_result
            
        except Exception as e:
            logger.error(f"Failed to build team: {e}")
            print(f"❌ Error building team: {e}")
            raise
    
    def gw_update(self, team_name: str, gameweek: Optional[int] = None, cached_only: bool = False, 
                  rag_mode: str = "ranked_enrichments", prompt_only: bool = False,
                  save_team: bool = False) -> None:
        """Complete weekly gameweek update using LLM strategy
        
        Args:
            gameweek: Gameweek number (Default: current gameweek)
            cached_only: Use cached data only (Default: False)
            rag_mode: RAG strategy to use for team building (Default: "ranked_enrichments")
                - "none": No enrichments, no ranking
                - "enrichments": Use enrichments, no ranking
                - "ranked_enrichments": Enrichments + ranking
            prompt_only: Show the prompt that would be sent to the LLM (for debugging) (Default: False)
            save_team: Save the created team to a JSON file (Default: False)
        """
        
        try:
            print("🔄 Starting weekly FPL update...")
            print(f"🔄 Using RAG mode: {rag_mode}")
            
            if rag_mode == "none":
                use_enrichments = False
                use_ranking = False
            elif rag_mode == "enrichments":
                use_enrichments = True
                use_ranking = False
            elif rag_mode == "ranked_enrichments":
                use_enrichments = True
                use_ranking = True
            else:
                raise ValueError(f"Invalid rag_mode: {rag_mode}")
            
            # Create team manager for this specific team
            team_manager = TeamManager(team_name=team_name)
            
            # Check if team exists before proceeding
            if not team_manager.team_exists():
                print(f"❌ Team '{team_name}' does not exist. Skipping...")
                return
            
            # Get all team context in one call (includes automatic free hit revert)
            team_context = team_manager.get_team_context(gameweek or 1)
            print(f"✅ Team context loaded for gameweek {team_context['gameweek']}")
            
            # Fetch all gameweek data in one call
            # For team building, filter players to only show available ones
            all_gameweek_data = self.fetch_fpl_data(
                use_cached=cached_only, 
                use_enrichments=use_enrichments, 
                gameweek=gameweek, 
                filter_unavailable_players=True
            )

            print(f"✅ Gameweek data loaded")
            
            # Get data for current team players
            current_team_player_data = self.data_service.get_current_team_player_data(
                current_team=team_context['team'],
                use_enrichments=use_enrichments,
                use_cached=cached_only
            )
            print(f"✅ Current team player data loaded")

            # Add current team player data to team context
            team_context['current_team_player_data'] = current_team_player_data
            
            # Update team using LLM strategy (no persistence, no business logic)
            print(f"\n⚽ Updating team for gameweek {gameweek or 'current'}...")
            team_result = self.llm_strategy.update_team_weekly(
                team_context=team_context,
                all_gameweek_data=all_gameweek_data,
                use_enrichments=use_enrichments,
                use_ranking=use_ranking,
                prompt_only=prompt_only
            )
            
            if prompt_only:
                print("✅ Prompt generation complete!")
                print("\n" + "="*50)
                print("📝 GENERATED PROMPT:")
                print("="*50)
                print(team_result['prompt'])
                return team_result
            
            # Process team update and get final team
            final_team_result = self._handle_chip_usage(
                team_result,
                team_context,
                all_gameweek_data=all_gameweek_data,
                use_enrichments=use_enrichments,
                use_ranking=use_ranking,
            )
            
            # Handle persistence if requested
            if save_team:
                team_manager.save_weekly_update(final_team_result, team_context)
                print("✅ Team saved successfully!")
            else:
                print("✅ Team update complete (not saved)")
            
            # Display results
            display_comprehensive_team_result(final_team_result)
            return final_team_result
            
        except Exception as e:
            logger.error(f"Weekly update failed: {e}")
            print(f"❌ Weekly update failed: {e}")
            raise
     
    def _handle_chip_usage(
        self,
        team_result: Dict[str, Any],
        team_context: Dict[str, Any],
        all_gameweek_data: Optional[Dict[str, Any]] = None,
        use_enrichments: bool = True,
        use_ranking: bool = True,
    ) -> Dict[str, Any]:
        """Handle chip usage. Always returns canonical {"team": {...}} shape."""
        payload = extract_team_payload(team_result)
        chip_type = normalize_chip(payload.get('chip'))
        chip_reason = payload.get('chip_reason', '')

        if not chip_type:
            payload['chip'] = None
            return {'team': payload}

        available_chips = team_context['chips']['available']
        if chip_type not in available_chips:
            print(f"❌ {chip_type.title()} chip is not available!")
            print(f"Available chips: {', '.join(available_chips) if available_chips else 'None'}")
            print(f"Used chips: {', '.join(chip['name'] for chip in team_context['chips']['used'])}")
            raise ValueError(f"{chip_type.title()} chip is not available for use")

        if chip_type in ['wildcard', 'free_hit']:
            print(f"✅ {chip_type.title()} chip is available - proceeding with team rebuild...")

            team_for_budget = dict(team_context['team'] or {})
            team_for_budget['bank'] = team_context.get('bank', team_for_budget.get('bank', 0.0))
            current_players = team_context.get('current_team_player_data') or {}
            available_budget = TeamManager().calculate_team_budget(team_for_budget, current_players)
            print(f"🔄 {chip_type.title()} applied - building new team with £{available_budget}m budget...")

            if all_gameweek_data is None:
                raise ValueError("all_gameweek_data is required to rebuild on wildcard/free hit")

            new_team_result = self.llm_strategy.create_team(
                budget=available_budget,
                gameweek=team_context['gameweek'],
                all_gameweek_data=all_gameweek_data,
                use_enrichments=use_enrichments,
                use_ranking=use_ranking,
                prompt_only=False,
            )
            new_payload = extract_team_payload(new_team_result)
            new_payload['chip'] = chip_type
            new_payload['chip_reason'] = chip_reason
            return {'team': new_payload}

        if chip_type == 'bench_boost':
            print(f"✅ {chip_type.title()} chip is available - proceeding...")
            print("🔄 Bench Boost applied - all 15 players will score")
        elif chip_type == 'triple_captain':
            print(f"✅ {chip_type.title()} chip is available - proceeding...")
            print("🔄 Triple Captain applied - captain points tripled")

        payload['chip'] = chip_type
        payload['chip_reason'] = chip_reason
        return {'team': payload}

    def show_data(self):
        """Show current data status"""
        return display_data_status(self.data_service.get_data_status(self.data_store))

    def show_players(self):
        """Show available players breakdown"""
        players_status = self.data_service.get_players_status(self.data_store, self.config)

        if 'error' in players_status:
            print(f"❌ {players_status['error']}")
        else:
            display_detailed_players_status(
                total_players=players_status['total_players'],
                available_players=players_status['available_players'],
                unavailable_players=players_status['unavailable_players'],
                filtered_players=players_status.get('filtered_players'),
                embedding_filtered_out=players_status.get('embedding_filtered_out'),
                use_embeddings=players_status['use_embeddings']
            )
    
    def show_team(self, team_name: str):
        """Show team-specific data (players, substitutes, formation, etc.)"""
        try:
            # Create team manager for the specific team
            team_manager = TeamManager(team_name=team_name)
            
            # Get the latest team data
            latest_gw = team_manager.get_latest_gameweek()
            if not latest_gw:
                print(f"❌ No team data found for team '{team_name}'")
                return
            
            team_data = team_manager.load_team(latest_gw)
            if not team_data:
                print(f"❌ Failed to load team data for team '{team_name}'")
                return
            
            # Use the display function for consistent formatting
            display_team_status(team_name, team_data, latest_gw)
            
        except Exception as e:
            logger.error(f"Failed to show team: {e}")
            print(f"❌ Failed to show team: {e}")

def main():
    """Main entry point with simplified command structure"""
    parser = argparse.ArgumentParser(description='FPL Agent')
    
    # Main command
    parser.add_argument('command', choices=[
        'fetch', 'enrich', 'gw-update', 'build-team', 'show-data', 'show-players',
        'list-teams', 'show-team', 'delete-team'
    ], help='Command to run')
    
    # Smart data flags
    parser.add_argument('--cached-only', action='store_true',
                       help='Use ONLY cached data (no API calls or enrichment). For fetch command: use stored data instead of fresh fetch.')
    parser.add_argument('--use-enrichments', action='store_true',
                       help='Use enrichments with expert insights or injury news, just basic data (default: False)')
    parser.add_argument('--rag-mode', choices=['none', 'enrichments', 'ranked_enrichments'], default='ranked_enrichments',
                       help='RAG mode to use for team building and weekly updates (default: ranked_enrichments)')
    parser.add_argument('--filter-unavailable-players', action='store_true',
                       help='Filter out unavailable players from the data (default: False)')
    
    # Common options
    parser.add_argument('--budget', type=float, default=100.0,
                       help='Team budget in millions (default: 100.0)')
    parser.add_argument('--gameweek', type=int,
                       help='Current gameweek')
    parser.add_argument('--team', type=str, default='default',
                       help='Team name to operate on (default: default)')
    parser.add_argument('--all-teams', action='store_true',
                       help='Run operation on all teams')
    parser.add_argument('--team-file', type=str,
                       help='Path to JSON file containing current team data')
    
    # Save options
    parser.add_argument('--save-team', action='store_true',
                       help='Save the created team to a JSON file')
    parser.add_argument('--show-prompt', action='store_true',
                       help='Show the prompt that would be sent to the LLM (for debugging)')
    parser.add_argument('--club', type=str, metavar='NAME',
                       help="Enrich one club only (e.g. 'Arsenal'); prints expert insights and injury news, no save")
    parser.add_argument('--insights-only', action='store_true',
                       help="With --club: run only expert insights (no injury news)")
    parser.add_argument('--injury-only', action='store_true',
                       help="With --club: run only injury news (no expert insights)")

    # Official FPL Sync options
    parser.add_argument('--auto-sync', action='store_true',
                       help='Automatically push transfers and lineup to official FPL account')
    parser.add_argument('--fpl-email', type=str,
                       help='FPL account email (overrides .env)')
    parser.add_argument('--fpl-password', type=str,
                       help='FPL account password (overrides .env)')

    # Logging level options
    parser.add_argument('--debug', action='store_true',
                       help='Show debug-level logging (most detailed)')
    parser.add_argument('--verbose', action='store_true',
                       help='Show verbose logging (medium detail)')
    
    args = parser.parse_args()
    
    # Set logging level based on flags
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        print("🔍 Debug mode enabled - showing all logs")
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)
        print("📊 Verbose mode enabled - showing detailed progress")
    else:
        # Default: Normal mode (WARNING + ERROR only)
        logging.getLogger().setLevel(logging.WARNING)
    
    try:
        # Handle commands that don't require team context
        if args.command == 'fetch':
            # Fetch fresh FPL data (shared across all teams)
            fpl_agent = FPLAgent()  # Use default model for data operations
            fpl_agent.fetch_fpl_data(
                use_cached=args.cached_only, 
                use_enrichments=args.use_enrichments,
                gameweek=args.gameweek,
                filter_unavailable_players=args.filter_unavailable_players
            )
            
        elif args.command == 'enrich':
            # Enrich data (shared across all teams), or expert insights + injury for one club
            if args.club and (args.insights_only or args.injury_only):
                club_run_insights = args.insights_only or not args.injury_only
                club_run_injury = args.injury_only or not args.insights_only
            else:
                club_run_insights = True
                club_run_injury = True
            fpl_agent = FPLAgent()  # Use default model for data operations
            fpl_agent.enrich(
                gameweek=args.gameweek,
                prompt_only=args.show_prompt,
                club=args.club,
                club_run_insights=club_run_insights,
                club_run_injury=club_run_injury,
            )
        
        elif args.command == 'list-teams':
            # List all available teams
            teams = get_all_teams()
            if teams:
                print(f"📋 Available teams ({len(teams)}):")
                for team in teams:
                    print(f"  • {team}")
            else:
                print("📋 No teams found. Create a team with 'build-team --team <name>'")
        
        elif args.command == 'show-data':
            fpl_agent = FPLAgent()
            fpl_agent.show_data()

        elif args.command == 'show-players':
            fpl_agent = FPLAgent()
            fpl_agent.show_players()

        elif args.command == 'delete-team':
            # Delete team
            team_name = args.team
            team_manager = TeamManager(team_name=team_name)
            if team_manager.team_exists():
                team_manager.delete_team()
                print(f"✅ Team '{team_name}' deleted successfully!")
            else:
                print(f"❌ Team '{team_name}' does not exist")
        
        elif args.command == 'show-team':
            # Determine which teams to process
            teams = []
            if args.all_teams:
                teams = get_all_teams()
                if not teams:
                    print("📋 No teams found. Create a team with 'build-team --team <name>'")
                    return
            elif args.team and args.team != 'default':
                teams = [args.team]
            else:
                print("❌ Error: Must specify either --team <name> or --all-teams")
                return
            
            # Process each team
            print(f"🚀 Running '{args.command}' on {len(teams)} teams: {', '.join(teams)}")
            
            for team_name in teams:
                print(f"\n Processing team: {team_name}")
                print("=" * 50)
                
                # Check team existence
                team_manager = TeamManager(team_name=team_name)
                if not team_manager.team_exists():
                    print(f"❌ Team '{team_name}' does not exist. Skipping...")
                    continue
                
                # Show team data
                fpl_agent = FPLAgent()  # Use default model for data operations
                fpl_agent.show_team(team_name)
        
        # Handle team-specific commands
        elif args.command in ['build-team', 'gw-update']:
            # Determine which teams to process
            teams = []
            if args.all_teams:
                # Get all model configs with team directories
                config = Config()
                model_configs = get_all_model_configs(config)
                teams = [(model_name, team_directory) for model_name, team_directory in model_configs]
                if not teams:
                    print("📋 No model configurations with team directories found.")
                    return
            elif args.team and args.team != 'default':
                # Find the model config that matches this team directory
                config = Config()
                model_configs = get_all_model_configs(config)
                matching_configs = [(model_name, team_directory) for model_name, team_directory in model_configs if team_directory == args.team]
                if not matching_configs:
                    print(f"❌ No model configuration found for team directory '{args.team}'")
                    print(f"Available team directories: {', '.join([td for _, td in model_configs])}")
                    return
                teams = matching_configs
            else:
                print("❌ Error: Must specify either --team <name> or --all-teams")
                return
            
            # Process each team
            print(f"🚀 Running '{args.command}' on {len(teams)} teams: {', '.join([td for _, td in teams])}")
            
            for model_name, team_directory in teams:
                print(f"\n Processing team: {team_directory} (using {model_name})")
                print("=" * 50)
                
                # Create FPLAgent for this team with the specific model
                fpl_agent = FPLAgent(model_name)
                
                if args.command == 'build-team':
                    team_result = fpl_agent.build_team(
                        team_name=team_directory,
                        budget=args.budget,
                        gameweek=args.gameweek,
                        cached_only=args.cached_only,
                        rag_mode=args.rag_mode,
                        prompt_only=args.show_prompt,
                        save_team=args.save_team
                    )
                    
                    if not args.show_prompt:
                        print(f"✅ Team building complete for '{team_directory}'!")
                        
                        if args.auto_sync and team_result:
                            cookie_string = os.environ.get('FPL_COOKIE')
                            access_token = os.environ.get('FPL_ACCESS_TOKEN')
                            if not cookie_string:
                                print("❌ Cannot auto-sync: FPL_COOKIE must be provided via .env")
                            else:
                                print("🔄 Auto-syncing team to official FPL API...")
                                all_data = fpl_agent.fetch_fpl_data(use_cached=True)
                                success = sync_team_to_fpl(team_result, cookie_string, access_token, all_data['players'], args.gameweek or 1)
                                if success:
                                    print("✅ Successfully synced to FPL!")
                                else:
                                    print("❌ Sync to FPL failed. See logs for details.")
                    else:
                        print(f"✅ Prompt generated for '{team_directory}'!")
                        
                elif args.command == 'gw-update':
                    team_result = fpl_agent.gw_update(
                        team_name=team_directory,
                        gameweek=args.gameweek or 1,
                        cached_only=args.cached_only,
                        rag_mode=args.rag_mode,
                        prompt_only=args.show_prompt,
                        save_team=args.save_team
                    )
                    
                    if not args.show_prompt:
                        print(f"✅ Weekly update complete for '{team_directory}'!")
                        
                        if args.auto_sync and team_result:
                            cookie_string = os.environ.get('FPL_COOKIE')
                            access_token = os.environ.get('FPL_ACCESS_TOKEN')
                            if not cookie_string:
                                print("❌ Cannot auto-sync: FPL_COOKIE must be provided via .env")
                            else:
                                print("🔄 Auto-syncing team to official FPL API...")
                                all_data = fpl_agent.fetch_fpl_data(use_cached=True)
                                success = sync_team_to_fpl(team_result, cookie_string, access_token, all_data['players'], args.gameweek or 1)
                                if success:
                                    print("✅ Successfully synced to FPL!")
                                else:
                                    print("❌ Sync to FPL failed. See logs for details.")
        
    except Exception as e:
        logger.error(f"Command failed: {e}")
        print(f"\n❌ Command failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
