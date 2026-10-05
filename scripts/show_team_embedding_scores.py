#!/usr/bin/env python3
"""
Print embedding scores (cosine similarity to position query) and hybrid scores for one club.

Requires: enriched player data with embeddings already computed (run fetch --use-enrichments first).
Usage:
  python scripts/show_team_embedding_scores.py Arsenal
  python scripts/show_team_embedding_scores.py "Arsenal"
"""
import json
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/show_team_embedding_scores.py <CLUB_NAME>")
        print("Example: python scripts/show_team_embedding_scores.py Arsenal")
        sys.exit(1)

    club = sys.argv[1].strip()
    data_path = Path("team_data/shared/player_data.json")
    if not data_path.exists():
        print("No player data found. Run: python -m fpl_agent.main fetch --use-enrichments")
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    players = data.get("players", data.get("player_data", data))
    if isinstance(players, list):
        players = {p.get("full_name", str(i)): p for i, p in enumerate(players)}

    # Filter by team (case-insensitive match on team_name)
    club_lower = club.lower()
    team_players = [(name, p) for name, p in players.items() if (p.get("team_name") or "").strip().lower() == club_lower]

    if not team_players:
        teams = sorted({(p.get("team_name") or "?") for p in players.values()})
        print(f"No players found for club '{club}'.")
        print(f"Available teams: {', '.join(teams)}")
        sys.exit(1)

    # Sort by keyword tier then cosine (two-stage), fallback hybrid_score
    pos_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
    team_players.sort(
        key=lambda x: (
            pos_order.get(x[1].get("position", ""), 99),
            x[1].get("keyword_tier", 2),
            -(x[1].get("embedding_score") or 0),
        )
    )

    print(f"Embedding scores for {club} (two-stage: keyword tier → cosine)")
    print("=" * 78)
    for name, p in team_players:
        pos = p.get("position", "?")
        emb = p.get("embedding_score")
        scaled = p.get("embedding_score_scaled")
        kw = p.get("keyword_bonus")
        tier = p.get("keyword_tier_name") or p.get("keyword_tier")
        hyb = p.get("hybrid_score")
        if emb is None and hyb is None:
            print(f"  {name} ({pos})  – no embedding scores (missing enrichments?)")
            continue
        emb_s = f"{emb:.3f}" if emb is not None else "N/A"
        scaled_s = f"{scaled:.2f}" if scaled is not None else "N/A"
        kw_s = f"{kw:+.3f}" if kw is not None else "N/A"
        hyb_s = f"{hyb:.3f}" if hyb is not None else "N/A"
        print(
            f"  {name:<28} {pos}  tier={tier!s:<14} cosine={emb_s}  "
            f"scaled={scaled_s}/10  keyword={kw_s}  sort={hyb_s}"
        )
    print("=" * 78)
    print(f"Total: {len(team_players)} players")

if __name__ == "__main__":
    main()
