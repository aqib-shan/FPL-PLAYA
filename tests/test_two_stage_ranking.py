#!/usr/bin/env python3
"""Tests for two-stage embedding ranking (no model download required)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fpl_agent.utils.keyword_extractor import (
    extract_expert_tier,
    extract_expert_bonus,
    scale_scores_0_to_10,
    select_players_two_stage,
    TIER_MUST_HAVE,
    TIER_RECOMMENDED,
    TIER_NEUTRAL,
    TIER_AVOID,
)
from fpl_agent.utils.prompt_formatter import PromptFormatter
from fpl_agent.data.embedding_filter import EmbeddingFilter


class KeywordTierTests(unittest.TestCase):
    def test_extract_tiers(self):
        data = {
            "A": {"expert_insights": "Must-have - elite mid"},
            "B": {"expert_insights": "Recommended - solid"},
            "C": {"expert_insights": "Avoid - minutes risk"},
            "D": {"expert_insights": "No flag here"},
            "E": {"expert_insights": "Rotation risk - cup games"},
        }
        self.assertEqual(extract_expert_tier("A", data), TIER_MUST_HAVE)
        self.assertEqual(extract_expert_tier("B", data), TIER_RECOMMENDED)
        self.assertEqual(extract_expert_tier("C", data), TIER_AVOID)
        self.assertEqual(extract_expert_tier("D", data), TIER_NEUTRAL)
        self.assertEqual(extract_expert_tier("E", data), 3)
        self.assertEqual(extract_expert_bonus("A", data), 0.5)
        self.assertEqual(extract_expert_bonus("C", data), -0.5)

    def test_scale_0_to_10(self):
        scaled = scale_scores_0_to_10([0.602, 0.701, 0.654])
        self.assertAlmostEqual(scaled[0], 0.0, places=5)
        self.assertAlmostEqual(scaled[1], 10.0, places=5)
        self.assertTrue(0.0 < scaled[2] < 10.0)
        # Flat range
        self.assertEqual(scale_scores_0_to_10([0.7, 0.7]), [5.0, 5.0])


class SelectTwoStageTests(unittest.TestCase):
    def test_must_have_outranks_higher_cosine(self):
        players = [
            {"name": "HighCosine", "keyword_tier": TIER_NEUTRAL, "embedding_score": 0.90, "hybrid_score": 1},
            {"name": "MustHave", "keyword_tier": TIER_MUST_HAVE, "embedding_score": 0.61, "hybrid_score": 1},
            {"name": "Avoid", "keyword_tier": TIER_AVOID, "embedding_score": 0.99, "hybrid_score": 1},
            {"name": "Rec", "keyword_tier": TIER_RECOMMENDED, "embedding_score": 0.70, "hybrid_score": 1},
        ]
        selected = select_players_two_stage(players, count=2)
        names = [p["name"] for p in selected]
        self.assertEqual(names[0], "MustHave")
        self.assertEqual(names[1], "Rec")
        self.assertNotIn("Avoid", names)

    def test_force_all_must_haves_over_count(self):
        players = [
            {"name": f"MH{i}", "keyword_tier": TIER_MUST_HAVE, "embedding_score": 0.6 + i * 0.01, "hybrid_score": 1}
            for i in range(5)
        ] + [
            {"name": "Neutral", "keyword_tier": TIER_NEUTRAL, "embedding_score": 0.99, "hybrid_score": 1}
        ]
        selected = select_players_two_stage(players, count=2)
        self.assertEqual(len(selected), 5)
        self.assertTrue(all(p["keyword_tier"] == TIER_MUST_HAVE for p in selected))
        self.assertNotIn("Neutral", [p["name"] for p in selected])

    def test_cosine_orders_within_tier(self):
        players = [
            {"name": "Low", "keyword_tier": TIER_NEUTRAL, "embedding_score": 0.60, "hybrid_score": 1},
            {"name": "High", "keyword_tier": TIER_NEUTRAL, "embedding_score": 0.70, "hybrid_score": 1},
            {"name": "Mid", "keyword_tier": TIER_NEUTRAL, "embedding_score": 0.65, "hybrid_score": 1},
        ]
        selected = select_players_two_stage(players, count=3)
        self.assertEqual([p["name"] for p in selected], ["High", "Mid", "Low"])


class EmbeddingFilterTwoStageTests(unittest.TestCase):
    def test_calculate_hybrid_scores_orders_by_tier_then_cosine(self):
        config = MagicMock()
        config.get_embeddings_config.return_value = {}
        filt = EmbeddingFilter(config)

        similarities = {
            "MID": [
                ("AvoidStar", 0.90),
                ("MustHaveLow", 0.62),
                ("NeutralHigh", 0.80),
                ("MustHaveHigh", 0.70),
                ("Recommended", 0.75),
            ]
        }
        structured = {
            "AvoidStar": {"expert_insights": "Avoid - bad"},
            "MustHaveLow": {"expert_insights": "Must-have - nailed"},
            "NeutralHigh": {"expert_insights": "Solid enough"},
            "MustHaveHigh": {"expert_insights": "Must-have - premium"},
            "Recommended": {"expert_insights": "Recommended - value"},
        }

        ranked = filt._calculate_hybrid_scores(similarities, structured)["MID"]
        names = [row[0] for row in ranked]
        self.assertEqual(
            names,
            ["MustHaveHigh", "MustHaveLow", "Recommended", "NeutralHigh", "AvoidStar"],
        )
        # Scaled cosine present and in 0–10
        for row in ranked:
            self.assertGreaterEqual(row[5], 0.0)
            self.assertLessEqual(row[5], 10.0)
        # Must-haves should outscore neutrals on sort_score even with lower cosine
        must_low_sort = next(r[1] for r in ranked if r[0] == "MustHaveLow")
        neutral_sort = next(r[1] for r in ranked if r[0] == "NeutralHigh")
        self.assertGreater(must_low_sort, neutral_sort)


class PromptShortlistTests(unittest.TestCase):
    def test_format_player_list_forces_must_haves(self):
        players = {}
        # 4 neutrals with high hybrid leftover + 1 must-have with lower cosine
        for i in range(4):
            name = f"Neutral{i}"
            players[name] = {
                "full_name": name,
                "name": name,
                "team_name": "Arsenal",
                "position": "MID",
                "now_cost": 50,
                "form": 1,
                "total_points": 10,
                "minutes": 100,
                "hybrid_score": 100,
                "keyword_tier": TIER_NEUTRAL,
                "keyword_tier_name": "neutral",
                "embedding_score": 0.85 - i * 0.01,
                "embedding_score_scaled": 9.0 - i,
                "keyword_bonus": 0.0,
            }
        players["SleeperMust"] = {
            "full_name": "SleeperMust",
            "name": "SleeperMust",
            "team_name": "Arsenal",
            "position": "MID",
            "now_cost": 55,
            "form": 1,
            "total_points": 10,
            "minutes": 100,
            "hybrid_score": 400,
            "keyword_tier": TIER_MUST_HAVE,
            "keyword_tier_name": "must-have",
            "embedding_score": 0.61,
            "embedding_score_scaled": 1.0,
            "keyword_bonus": 0.5,
            "expert_insights": "Must-have - differential",
            "injury_news": "None",
        }

        text = PromptFormatter.format_player_list(
            players,
            use_enrichments=True,
            use_ranking=True,
            selection_counts={"MID": 2, "GK": 0, "DEF": 0, "FWD": 0},
        )
        self.assertIn("SleeperMust", text)
        self.assertIn("tier=must-have", text)
        # count=2: must-have + highest cosine neutral
        self.assertIn("Neutral0", text)


if __name__ == "__main__":
    unittest.main()
