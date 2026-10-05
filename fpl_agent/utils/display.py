"""
Display utilities for FPL team results and data
"""

from typing import Dict, Any
from datetime import datetime

from .team_utils import extract_team_payload, normalize_chip


def display_data_status(data_status: Dict[str, Any]) -> None:
    """
    Display comprehensive data status information.
    
    Args:
        data_status: Dictionary containing data status information
    """
    print("📊 FPL Data Status")
    print("=" * 50)
    
    # FPL Data Status
    print(f"\n🔄 FPL Data:")
    if data_status['fpl_data']['available']:
        age = data_status['fpl_data']['age_hours']
        status = "✅ Fresh" if data_status['fpl_data']['fresh'] else "⚠️  Stale"
        print(f"   • Status: {status}")
        print(f"   • Age: {age:.1f} hours")
        print(f"   • Last updated: {datetime.now().timestamp() - (age * 3600):.0f} seconds ago")
    else:
        print("   • Status: ❌ Not available")
        print("   • Action: Run 'fetch' command")
    
    # Enriched Data Status
    print(f"\n🧠 Enriched Data:")
    if data_status['enriched_data']['available']:
        age = data_status['enriched_data']['age_hours']
        status = "✅ Fresh" if data_status['enriched_data']['fresh'] else "⚠️  Stale"
        print(f"   • Status: {status}")
        print(f"   • Age: {age:.1f} hours")
        print(f"   • Last updated: {datetime.now().timestamp() - (age * 3600):.0f} seconds ago")
    else:
        print("   • Status: ❌ Not available")
        print("   • Action: Run 'enrich' command")
    
    # Embeddings Status
    print(f"\n🔍 Embeddings:")
    if data_status['embeddings']['available']:
        age = data_status['embeddings']['age_hours']
        status = "✅ Fresh" if data_status['embeddings']['fresh'] else "⚠️  Stale"
        print(f"   • Status: {status}")
        print(f"   • Age: {age:.1f} hours")
    else:
        print("   • Status: ❌ Not available")
    
    # Overall Status
    print(f"\n📋 Overall Status:")
    overall = data_status['overall_status']
    if overall == 'fresh':
        print("   • Status: ✅ All data is fresh and ready")
        print("   • Action: Ready for team building/updates")
    elif overall == 'stale':
        print("   • Status: ⚠️  Data is available but stale")
        print("   • Action: Consider running 'gw-update' or 'build-team' with --force-all")
    elif overall == 'partial':
        print("   • Status: ⚠️  Partial data available")
        print("   • Action: Run 'enrich' to complete data preparation")
    elif overall == 'fpl_only':
        print("   • Status: ⚠️  Only FPL data available")
        print("   • Action: Run 'enrich' to add LLM insights")
    else:
        print("   • Status: ❌ No data available")
        print("   • Action: Run 'fetch' to get started")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    if data_status['overall_status'] == 'fresh':
        print("   • All data is fresh - ready for team operations")
    elif data_status['overall_status'] in ['stale', 'partial']:
        print("   • Run 'gw-update' for complete weekly refresh")
        print("   • Or run 'build-team' with --force-all for fresh team")
    else:
        print("   • Start with 'fetch' to get FPL data")
        print("   • Then 'enrich' to add insights")
        print("   • Finally 'build-team' or 'gw-update'")


def display_fetch_results(result: Dict[str, Any], use_cached: bool = False) -> None:
    """Display fetch operation results to the user"""
    if use_cached:
        print(f"📊 Loaded cached FPL data:")
    else:
        print(f"🔄 Fetched fresh FPL data:")
    
    print(f"   • Players: {result['total_players']}")
    print(f"   • Fixtures: {result['total_fixtures']}")
    print(f"   • Fetched at: {result['fetched_at']}")
    print("✅ Data fetch complete!")


def display_comprehensive_team_result(result: Dict[str, Any]) -> None:
    """Display comprehensive team creation/update results"""
    print("✅ Team building complete!")
    print("\n" + "=" * 80)
    print("FPL COMPREHENSIVE TEAM RESULT")
    print("=" * 80)
    
    # Handle different data structures
    if 'team_data' in result:
        team_data_wrapper = result['team_data']
    else:
        team_data_wrapper = result
    
    # Always unwrap nested LLM/file shapes so captain/bank/chip read correctly
    team_data = extract_team_payload(team_data_wrapper)
    captain = team_data.get('captain', 'Unknown')
    vice_captain = team_data.get('vice_captain', 'Unknown')
    total_cost = team_data.get('total_cost', 0.0)
    bank = team_data.get('bank', 0.0)
    expected_points = team_data.get('expected_points', 0.0)
    chip = normalize_chip(team_data.get('chip'))
    chip_reason = team_data.get('chip_reason', '')
    transfers = team_data.get('transfers', []) or []
    captain_reason = team_data.get('captain_reason', '')
    vice_captain_reason = team_data.get('vice_captain_reason', '')
    
    # Display basic info
    print("\n" + "=" * 80)
    print("LLM RESPONSE")
    print("=" * 80)
    print(f"\nCaptain: {captain}")
    if captain_reason:
        print(f"Captain Reason: {captain_reason}")
    print(f"Vice Captain: {vice_captain}")
    if vice_captain_reason:
        print(f"Vice Captain Reason: {vice_captain_reason}")
    print(f"Total Cost: £{total_cost}m")
    print(f"Bank: £{bank}m")
    print(f"Expected Points: {expected_points}")
    
    # Display chip usage if any
    if chip:
        print(f"\nChip Used: {chip.upper()}")
        if chip_reason:
            print(f"Chip Reason: {chip_reason}")
    else:
        print(f"\nChip Used: None")
        if chip_reason:
            print(f"Chip Reason: {chip_reason}")
    
    # Display transfers if any
    if transfers:
        print("\n" + "=" * 80)
        print("TRANSFERS")
        print("=" * 80)
        print(f"{'Player Out':<25} {'Player In':<25} {'Out Price':<10} {'In Price':<10}")
        print("-" * 80)
        
        for transfer in transfers:
            player_out = transfer.get('player_out', 'Unknown')
            player_in = transfer.get('player_in', 'Unknown')
            player_out_price = transfer.get('player_out_price', 0.0)
            player_in_price = transfer.get('player_in_price', 0.0)
            reason = transfer.get('reason', '')
            
            print(f"{player_out:<25} {player_in:<25} £{player_out_price:<9} £{player_in_price:<9}")
            if reason:
                print(f"  └─ Reason: {reason}")
            print()
    
    # Display team selection reasoning
    print("\n" + "=" * 80)
    print("TEAM SELECTION REASONING")
    print("=" * 80)
    
    # Display raw LLM response
    raw_response = team_data_wrapper.get('raw_llm_response', '') or team_data.get('raw_llm_response', '')
    if raw_response:
        print("\n" + "=" * 80)
        print("RAW LLM RESPONSE")
        print("=" * 80)
        print(raw_response)
    
    # Display starting 11
    starting = team_data.get('starting', [])
    if starting:
        print("\n" + "=" * 80)
        print("STARTING 11")
        print("=" * 80)
        print(f"{'Name':<25} {'Team':<15} {'Pos':<4} {'Price':<6}")
        print("-" * 80)
        
        for player in starting:
            name = player.get('name', 'Unknown')
            team = player.get('team', 'Unknown')
            position = player.get('position', 'UNK')
            price = player.get('price', 0.0)
            reason = player.get('reason', '')
            
            # Add captain/vice-captain indicators
            if name == captain:
                name += " (C)"
            elif name == vice_captain:
                name += " (VC)"
            
            print(f"{name:<25} {team:<15} {position:<4} £{price:<5}")
            if reason:
                print(f"  └─ {reason}")
            print()
    
    # Display substitutes
    substitutes = team_data.get('substitutes', [])
    if substitutes:
        print("=" * 80)
        print("SUBSTITUTES")
        print("=" * 80)
        print(f"{'Name':<25} {'Team':<15} {'Pos':<4} {'Price':<6} {'Sub Order':<10}")
        print("-" * 80)
        
        for player in substitutes:
            name = player.get('name', 'Unknown')
            team = player.get('team', 'Unknown')
            position = player.get('position', 'UNK')
            price = player.get('price', 0.0)
            sub_order = player.get('sub_order', '')
            reason = player.get('reason', '')
            
            # Format sub order
            if sub_order is None:
                sub_order = 'GK'
            elif sub_order == '':
                sub_order = '-'
            
            print(f"{name:<25} {team:<15} {position:<4} £{price:<5} {sub_order:<10}")
            if reason:
                print(f"  └─ {reason}")
            print()
    
    print("=" * 80)
    print(f"Comprehensive team operation completed at: {datetime.now()}")
    print("=" * 80)


def display_players_status(players_status: Dict[str, Any]) -> None:
    """
    Display comprehensive players status information.
    
    Args:
        players_status: Dictionary containing players status information
    """
    print("👥 FPL Players Status")
    print("=" * 50)
    
    # Basic counts
    total_players = players_status.get('total_players', 0)
    available_players = players_status.get('available_players', 0)
    unavailable_players = players_status.get('unavailable_players', 0)
    
    print(f"📊 Total players in data: {total_players}")
    print(f"✅ Available Players: {available_players}")
    print(f"🚫 Not Available Players: {unavailable_players}")
    
    # Embedding status
    use_embeddings = players_status.get('use_embeddings', False)
    if use_embeddings:
        print(f"🔍 Embedding filtering: ENABLED")
    else:
        print(f"🔍 Embedding filtering: DISABLED")
    
    # Completion info
    completed_at = players_status.get('completed_at')
    if completed_at:
        print(f"⏰ Status checked at: {completed_at}")


def display_detailed_players_status(
    total_players: int,
    available_players: Dict[str, Dict[str, Any]],
    unavailable_players: Dict[str, Dict[str, Any]],
    filtered_players: Dict[str, Dict[str, Any]] = None,
    embedding_filtered_out: Dict[str, Dict[str, Any]] = None,
    use_embeddings: bool = False
) -> None:
    """
    Display detailed players status with breakdowns.
    
    Args:
        total_players: Total number of players
        available_players: Dictionary of available players
        unavailable_players: Dictionary of unavailable players
        filtered_players: Dictionary of top players selected by embeddings
        embedding_filtered_out: Dictionary of players filtered out by embeddings
        use_embeddings: Whether embedding filtering is enabled
    """
    print("👥 FPL Players Status")
    print("=" * 50)
    
    print(f"📊 Total players in data: {total_players}")
    
    # Show unavailable players
    print(f"\n🚫 Not Available Players: {len(unavailable_players)}")
    print("-" * 30)
    print("   (Filtered out by: chance_of_playing < 25% OR marked as 'Out' in injury news)")
    print()
    
    if len(unavailable_players) == 0:
        print("   No unavailable players found")
    else:
        print(f"   Found {len(unavailable_players)} unavailable players")
        # Show first few names as debug
        first_names = list(unavailable_players.keys())[:5]
        print(f"   First few: {first_names}")
    
    # Group unavailable players by position and show details
    position_groups = {}
    for name, data in unavailable_players.items():
        position = data.get('position', 'Unknown')
        if position not in position_groups:
            position_groups[position] = []
        position_groups[position].append((name, data))
    
    print(f"   Position groups: {list(position_groups.keys())}")
    
    # Show detailed breakdown of unavailable players by position
    for position in ['GK', 'DEF', 'MID', 'FWD']:
        if position in position_groups:
            players = position_groups[position]
            print(f"\n   {position} ({len(players)} players):")
            print("   " + "-" * 40)
            
            # Sort by name for readability
            sorted_players = sorted(players, key=lambda x: x[0])
            for name, data in sorted_players[:10]:  # Show first 10
                team = data.get('team_name', 'Unknown')
                chance = data.get('chance_of_playing', 'Unknown')
                news = data.get('news', '')
                print(f"   • {name:<25} | {team:<15} | Chance: {chance}%")
                if news:
                    print(f"     └─ {news}")
            
            if len(sorted_players) > 10:
                print(f"   ... and {len(sorted_players) - 10} more {position} players")
    
    # Show available players
    print(f"\n✅ Available Players: {len(available_players)}")
    print("-" * 30)
    
    if use_embeddings:
        print(f"🔍 Embedding filtering: ENABLED")
        
        if filtered_players:
            print(f"\n🎯 Top Players (Embedding Selected): {len(filtered_players)}")
            print("-" * 40)
            print("   (Selected by embedding similarity + keyword bonuses)")
            print()
            
            # Show breakdown of top players by position
            top_position_groups = {}
            for name, data in filtered_players.items():
                position = data.get('position', 'Unknown')
                if position not in top_position_groups:
                    top_position_groups[position] = []
                top_position_groups[position].append((name, data))
            
            for position in ['GK', 'DEF', 'MID', 'FWD']:
                if position in top_position_groups:
                    players = top_position_groups[position]
                    print(f"   {position} ({len(players)} players):")
                    print("   " + "-" * 40)
                    
                    # Sort by hybrid_score (highest first) and show ranking
                    sorted_players = sorted(players, key=lambda x: x[1].get('hybrid_score', 0), reverse=True)
                    for rank, (name, data) in enumerate(sorted_players[:10], 1):  # Show top 10
                        team = data.get('team_name', 'Unknown')
                        hybrid_score = data.get('hybrid_score', 0)
                        position_rank = data.get('position_rank', 'N/A')
                        points = data.get('total_points', 0)
                        form = data.get('form', 0)
                        price = data.get('now_cost', 0)
                        
                        # Format price (convert from pence to pounds)
                        price_pounds = f"£{price/10:.1f}m" if price else "N/A"
                        
                        print(f"   {rank:2d}. {name:<25} | {team:<15} | Score: {hybrid_score:.3f} | Rank: {position_rank}")
                        print(f"       Stats: {points} pts | Form: {form} | Price: {price_pounds}")
                        
                        # Show injury news if available
                        injury_news = data.get('injury_news', '')
                        if injury_news and injury_news != 'None':
                            print(f"       🚑 Injury: {injury_news}")
                        
                        # Show expert insights if available
                        expert_insights = data.get('expert_insights', '')
                        if expert_insights and expert_insights != 'None':
                            print(f"       💡 Tips: {expert_insights}")
                        
                        # Show chance of playing if available
                        chance = data.get('chance_of_playing', None)
                        if chance is not None and chance != 100:
                            print(f"       ⚠️  Chance: {chance}%")
                        
                        print()  # Empty line between players
                    
                    if len(sorted_players) > 10:
                        print(f"   ... and {len(sorted_players) - 10} more {position} players")
        
        if embedding_filtered_out:
            print(f"\n🚫 Filtered Out by Embedding: {len(embedding_filtered_out)}")
            print("-" * 40)
            print("   (Available but didn't make top N per position)")
            print()
            
            # Show breakdown of filtered out players by position
            filtered_position_groups = {}
            for name, data in embedding_filtered_out.items():
                position = data.get('position', 'Unknown')
                if position not in filtered_position_groups:
                    filtered_position_groups[position] = []
                filtered_position_groups[position].append((name, data))
            
            for position in ['GK', 'DEF', 'MID', 'FWD']:
                if position in filtered_position_groups:
                    players = filtered_position_groups[position]
                    print(f"   {position} ({len(players)} players):")
                    print("   " + "-" * 40)
                    
                    # Sort by hybrid_score (highest first) to show why they were filtered out
                    sorted_players = sorted(players, key=lambda x: x[1].get('hybrid_score', 0), reverse=True)
                    for rank, (name, data) in enumerate(sorted_players[:10], 1):  # Show top 10
                        team = data.get('team_name', 'Unknown')
                        hybrid_score = data.get('hybrid_score', 0)
                        position_rank = data.get('position_rank', 'N/A')
                        points = data.get('total_points', 0)
                        form = data.get('form', 0)
                        price = data.get('now_cost', 0)
                        
                        # Format price (convert from pence to pounds)
                        price_pounds = f"£{price/10:.1f}m" if price else "N/A"
                        
                        print(f"   {rank:2d}. {name:<25} | {team:<15} | Score: {hybrid_score:.3f} | Rank: {position_rank}")
                        print(f"       Stats: {points} pts | Form: {form} | Price: {price_pounds}")
                        
                        # Show injury news if available
                        injury_news = data.get('injury_news', '')
                        if injury_news and injury_news != 'None':
                            print(f"       🚑 Injury: {injury_news}")
                        
                        # Show expert insights if available
                        expert_insights = data.get('expert_insights', '')
                        if expert_insights and expert_insights != 'None':
                            print(f"       💡 Tips: {expert_insights}")
                        
                        # Show chance of playing if available
                        chance = data.get('chance_of_playing', None)
                        if chance is not None and chance != 100:
                            print(f"       ⚠️  Chance: {chance}%")
                        
                        print()  # Empty line between players
                    
                    if len(sorted_players) > 10:
                        print(f"   ... and {len(sorted_players) - 10} more {position} players")
    else:
        print(f"🔍 Embedding filtering: DISABLED")
        print(f"\n📋 Basic Players Summary:")
        print("-" * 30)
        
        # Show breakdown of available players by position
        available_position_groups = {}
        for name, data in available_players.items():
            position = data.get('position', 'Unknown')
            if position not in available_position_groups:
                available_position_groups[position] = []
            available_position_groups[position].append((name, data))
        
        for position in ['GK', 'DEF', 'MID', 'FWD']:
            if position in available_position_groups:
                players = available_position_groups[position]
                print(f"   {position} ({len(players)} players):")
                print("   " + "-" * 40)
                
                # Sort by total points (highest first) when no embedding scores available
                sorted_players = sorted(players, key=lambda x: x[1].get('total_points', 0), reverse=True)
                for rank, (name, data) in enumerate(sorted_players[:10], 1):  # Show top 10
                    team = data.get('team_name', 'Unknown')
                    points = data.get('total_points', 0)
                    form = data.get('form', 0)
                    price = data.get('now_cost', 0)
                    
                    # Format price (convert from pence to pounds)
                    price_pounds = f"£{price/10:.1f}m" if price else "N/A"
                    
                    print(f"   {rank:2d}. {name:<25} | {team:<15} | Points: {points}")
                    print(f"       Stats: {points} pts | Form: {form} | Price: {price_pounds}")
                    
                    # Show injury news if available
                    injury_news = data.get('injury_news', '')
                    if injury_news and injury_news != 'None':
                        print(f"       🚑 Injury: {injury_news}")
                    
                    # Show expert insights if available
                    expert_insights = data.get('expert_insights', '')
                    if expert_insights and expert_insights != 'None':
                        print(f"       💡 Tips: {expert_insights}")
                    
                    # Show chance of playing if available
                    chance = data.get('chance_of_playing', None)
                    if chance is not None and chance != 100:
                        print(f"       ⚠️  Chance: {chance}%")
                    
                    print()  # Empty line between players
                
                if len(sorted_players) > 10:
                    print(f"   ... and {len(sorted_players) - 10} more {position} players")
        
        print(f"\n📝 Note: These players would go into LLM prompts with basic stats only (no expert insights or injury news)")


def display_team_status(team_name: str, team_data: Dict[str, Any], gameweek: str) -> None:
    """
    Display comprehensive team status information.
    
    Args:
        team_name: Name of the team
        team_data: Dictionary containing team data. This may either be:
          - The raw team dict (with 'starting'/'substitutes' directly), or
          - A meta wrapper with a 'team' key that itself contains the team dict,
            which may in turn be nested under its own 'team' key.
        gameweek: Current gameweek
    """
    # Unwrap possible meta/team nesting so we always point at the dict
    # that actually contains 'starting' and 'substitutes'.
    team_wrapper = team_data.get('team', team_data)
    if isinstance(team_wrapper, dict) and 'team' in team_wrapper and isinstance(team_wrapper['team'], dict) and team_wrapper['team'].get('starting') is not None:
        team_info = team_wrapper['team']
    else:
        team_info = team_wrapper
    
    print(f"🏆 Team: {team_name}")
    print(f"📅 Gameweek: {gameweek}")
    
    # Display team financial info
    total_cost = team_info.get('total_cost', 0)
    if total_cost is not None:
        print(f"💰 Budget: £{total_cost:.1f}m")
    
    bank = team_info.get('bank', 0)
    if bank is not None:
        print(f"🏦 Bank: £{bank:.1f}m")
    
    expected_points = team_info.get('expected_points', 0)
    if expected_points is not None:
        print(f"📊 Expected Points: {expected_points:.1f}")
    
    # Display captain and vice captain
    print(f"👑 Captain: {team_info.get('captain', 'N/A')}")
    print(f"🔄 Vice Captain: {team_info.get('vice_captain', 'N/A')}")
    
    if team_info.get('chip'):
        print(f"🎯 Chip Used: {team_info['chip']}")
    
    # Display starting XI
    print("\n" + "="*50)
    print("🟢 STARTING XI:")
    print("="*50)
    
    for i, player in enumerate(team_info.get('starting', []), 1):
        price = player.get('price', 0)
        if price is not None:
            print(f"{i:2d}. {player['name']} ({player['position']}) - {player['team']} - £{price:.1f}m")
        else:
            print(f"{i:2d}. {player['name']} ({player['position']}) - {player['team']} - £N/A")
        if 'reason' in player:
            print(f"     💡 {player['reason']}")
    
    # Display substitutes
    print("\n" + "="*50)
    print("🟡 SUBSTITUTES:")
    print("="*50)
    
    for i, player in enumerate(team_info.get('substitutes', []), 1):
        sub_order = player.get('sub_order', i)
        if sub_order is None:
            sub_order = i
        price = player.get('price', 0)
        if price is not None:
            print(f"{sub_order:2d}. {player['name']} ({player['position']}) - {player['team']} - £{price:.1f}m")
        else:
            print(f"{sub_order:2d}. {player['name']} ({player['position']}) - {player['team']} - £N/A")
        if 'reason' in player:
            print(f"     💡 {player['reason']}")
    
    # Display transfers if any
    transfers = team_info.get('transfers', [])
    if transfers:
        print("\n" + "="*50)
        print("🔄 TRANSFERS:")
        print("="*50)
        for transfer in transfers:
            out_price = transfer.get('player_out_price', 0)
            in_price = transfer.get('player_in_price', 0)
            
            if out_price is not None:
                print(f"📤 OUT: {transfer['player_out']} (£{out_price:.1f}m)")
            else:
                print(f"📤 OUT: {transfer['player_out']} (£N/A)")
                
            if in_price is not None:
                print(f"📥 IN:  {transfer['player_in']} (£{in_price:.1f}m)")
            else:
                print(f"📥 IN:  {transfer['player_in']} (£N/A)")
                
            if 'reason' in transfer:
                print(f"     💡 {transfer['reason']}")
            print()
