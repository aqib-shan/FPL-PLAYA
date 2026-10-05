#!/usr/bin/env python3
"""Regression checks for season-start correctness fixes (no LLM / network)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fpl_agent.utils.team_utils import extract_team_payload, normalize_chip
from fpl_agent.utils.display import display_comprehensive_team_result
from fpl_agent.utils.prompt_formatter import PromptFormatter
from fpl_agent.core.team_manager import TeamManager


def _sample_team(**overrides):
    team = {
        "captain": "Player A",
        "vice_captain": "Player B",
        "captain_reason": "form",
        "vice_captain_reason": "fixture",
        "total_cost": 99.5,
        "bank": 0.5,
        "expected_points": 50,
        "chip": None,
        "chip_reason": "none needed",
        "transfers": [],
        "starting": [
            {"name": "Player A", "position": "MID", "price": 8.0, "team": "Arsenal", "reason": "x"},
            {"name": "Player B", "position": "FWD", "price": 7.5, "team": "Chelsea", "reason": "x"},
            {"name": "Player C", "position": "DEF", "price": 5.0, "team": "Everton", "reason": "x"},
            {"name": "Player D", "position": "DEF", "price": 4.5, "team": "Brentford", "reason": "x"},
            {"name": "Player E", "position": "DEF", "price": 4.5, "team": "Fulham", "reason": "x"},
            {"name": "Player F", "position": "MID", "price": 6.0, "team": "Liverpool", "reason": "x"},
            {"name": "Player G", "position": "MID", "price": 6.5, "team": "Spurs", "reason": "x"},
            {"name": "Player H", "position": "MID", "price": 5.5, "team": "West Ham", "reason": "x"},
            {"name": "Player I", "position": "FWD", "price": 7.0, "team": "Newcastle", "reason": "x"},
            {"name": "Player J", "position": "FWD", "price": 5.5, "team": "Brighton", "reason": "x"},
            {"name": "Player K", "position": "GK", "price": 5.0, "team": "Man City", "reason": "x"},
        ],
        "substitutes": [
            {"name": "Player L", "position": "DEF", "price": 4.0, "team": "Wolves", "sub_order": 1, "reason": "x"},
            {"name": "Player M", "position": "MID", "price": 4.5, "team": "Palace", "sub_order": 2, "reason": "x"},
            {"name": "Player N", "position": "FWD", "price": 4.5, "team": "Burnley", "sub_order": 3, "reason": "x"},
            {"name": "Player O", "position": "GK", "price": 4.0, "team": "Ipswich", "sub_order": None, "reason": "x"},
        ],
    }
    team.update(overrides)
    return team


class ExtractAndDisplayTests(unittest.TestCase):
    def test_extract_nested_and_flat(self):
        flat = _sample_team(chip="bench_boost")
        wrapped = {"team": flat}
        self.assertEqual(extract_team_payload(wrapped)["captain"], "Player A")
        self.assertEqual(extract_team_payload(flat)["chip"], "bench_boost")
        self.assertEqual(extract_team_payload({"team": {"team": flat}})["captain"], "Player A")

    def test_normalize_chip(self):
        self.assertIsNone(normalize_chip(None))
        self.assertIsNone(normalize_chip("null"))
        self.assertIsNone(normalize_chip("None"))
        self.assertEqual(normalize_chip("wildcard"), "wildcard")

    def test_display_reads_nested_captain(self):
        # Should not raise and should resolve nested fields (smoke via capturing prints)
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            display_comprehensive_team_result({"team": _sample_team(chip="triple_captain")})
        out = buf.getvalue()
        self.assertIn("Captain: Player A", out)
        self.assertIn("Chip Used: TRIPLE_CAPTAIN", out)
        self.assertIn("Bank: £0.5m", out)


class MetaAndTransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.manager = TeamManager(team_name="TestTeam", data_dir=str(self.tmp), auto_create=True)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_save_new_team_preserves_meta_mid_season(self):
        gw5 = _sample_team(bank=1.2, chip="wildcard")
        # Seed meta as if mid-season with chips already partially used
        self.manager._save_meta({
            "current_gw": 4,
            "last_team_file": "gw04.json",
            "bank": 0.8,
            "free_transfers_carried_over": 1,
            "chips_used": {
                "wildcard": False,
                "bench_boost": True,
                "free_hit": False,
                "triple_captain": False,
            },
        })
        self.manager.save_new_team({"team": gw5}, gameweek=5, reset_meta=False)
        meta = self.manager.get_meta()
        self.assertTrue(meta["chips_used"]["wildcard"])
        self.assertTrue(meta["chips_used"]["bench_boost"])  # preserved
        self.assertEqual(meta["free_transfers_carried_over"], 1)  # WC preserves FTs
        self.assertEqual(meta["bank"], 1.2)

    def test_save_new_team_resets_on_gw1(self):
        self.manager._save_meta({
            "current_gw": 38,
            "last_team_file": "gw38.json",
            "bank": 0.1,
            "free_transfers_carried_over": 1,
            "chips_used": {c: True for c in TeamManager.CHIP_NAMES},
        })
        self.manager.save_new_team({"team": _sample_team(bank=0.3)}, gameweek=1, reset_meta=True)
        meta = self.manager.get_meta()
        self.assertFalse(any(meta["chips_used"].values()))
        self.assertEqual(meta["free_transfers_carried_over"], 0)
        self.assertEqual(meta["bank"], 0.3)

    def test_update_meta_reads_nested_chip_and_transfers(self):
        self.manager._save_meta({
            "current_gw": 9,
            "last_team_file": "gw09.json",
            "bank": 0.5,
            "free_transfers_carried_over": 1,
            "chips_used": {c: False for c in TeamManager.CHIP_NAMES},
        })
        response = {
            "team": _sample_team(
                bank=0.2,
                chip="bench_boost",
                transfers=[
                    {
                        "player_out": "Player L",
                        "player_in": "Player X",
                        "player_out_price": 4.0,
                        "player_in_price": 4.3,
                        "reason": "upgrade",
                    }
                ],
            )
        }
        self.manager.update_meta_from_response(10, response, self.manager.get_meta())
        meta = self.manager.get_meta()
        self.assertTrue(meta["chips_used"]["bench_boost"])
        # available=2, made=1 → carry 1
        self.assertEqual(meta["free_transfers_carried_over"], 1)
        self.assertEqual(meta["bank"], 0.2)

    def test_can_make_transfers_with_zero_carry(self):
        info = self.manager.get_available_transfers_from_meta({
            "current_gw": 2,
            "free_transfers_carried_over": 0,
        })
        self.assertEqual(info["free_transfers_available"], 1)
        self.assertTrue(info["can_make_transfers"])

    def test_free_transfers_bank_up_to_five(self):
        """Unused FTs roll over; available is capped at 5."""
        self.assertEqual(TeamManager.MAX_FREE_TRANSFERS, 5)

        # Carry 3 → available 4; use none → carry min(4, 4) = 4
        self.manager._save_meta({
            "current_gw": 5,
            "last_team_file": "gw05.json",
            "bank": 0.5,
            "free_transfers_carried_over": 3,
            "chips_used": {c: False for c in TeamManager.CHIP_NAMES},
        })
        self.manager.update_meta_from_response(
            6, {"team": _sample_team(transfers=[])}, self.manager.get_meta()
        )
        self.assertEqual(self.manager.get_meta()["free_transfers_carried_over"], 4)

        # Carry 4 → available 5; use none → carry capped at MAX-1 = 4
        self.manager._save_meta({
            **self.manager.get_meta(),
            "free_transfers_carried_over": 4,
        })
        self.manager.update_meta_from_response(
            7, {"team": _sample_team(transfers=[])}, self.manager.get_meta()
        )
        self.assertEqual(self.manager.get_meta()["free_transfers_carried_over"], 4)
        info = self.manager.get_available_transfers_from_meta(self.manager.get_meta())
        self.assertEqual(info["free_transfers_available"], 5)

    def test_free_hit_preserves_banked_transfers(self):
        self.manager._save_meta({
            "current_gw": 8,
            "last_team_file": "gw08.json",
            "bank": 0.5,
            "free_transfers_carried_over": 3,
            "chips_used": {c: False for c in TeamManager.CHIP_NAMES},
        })
        self.manager.update_meta_from_response(
            9,
            {"team": _sample_team(chip="free_hit", transfers=[])},
            self.manager.get_meta(),
        )
        meta = self.manager.get_meta()
        self.assertTrue(meta["chips_used"]["free_hit"])
        self.assertEqual(meta["free_transfers_carried_over"], 3)

    def test_transfers_are_affordable_bank(self):
        ok, expected = self.manager.transfers_are_affordable(
            transfers=[{"player_out": "Player A", "player_in_price": 8.5}],
            bank=1.0,
            current_team_player_data={"Player A": {"sale_price": 8.0}},
        )
        self.assertTrue(ok)
        self.assertEqual(expected, 0.5)


class FormationConstraintTests(unittest.TestCase):
    def test_mid_minimum_is_three(self):
        from fpl_agent.core.config import Config

        constraints = Config().get_formation_constraints()
        self.assertEqual(constraints["MID"], [3, 5])
        self.assertEqual(constraints["DEF"], [3, 5])
        self.assertEqual(constraints["FWD"], [1, 3])


class PromptHelperTests(unittest.TestCase):
    def test_availability_alerts(self):
        team = _sample_team()
        pdata = {
            "Player A": {
                "chance_of_playing": 0,
                "injury_news": "Out with hamstring",
                "expert_insights": "Avoid",
            },
            "Player B": {"chance_of_playing": 100, "injury_news": "None", "expert_insights": "None"},
        }
        # Fill remaining squad keys so formatter can iterate (missing → treated as available)
        text = PromptFormatter.format_owned_availability_alerts(team, pdata)
        self.assertIn("OWNED PLAYER AVAILABILITY ALERTS", text)
        self.assertIn("Player A", text)
        self.assertIn("Out with hamstring", text)
        self.assertNotIn("Player B\n", text)

    def test_fixture_landscape_doubles_and_blanks(self):
        fixtures = [
            {"event": 1, "team_h": "Arsenal", "team_a": "Chelsea"},
            {"event": 1, "team_h": "Arsenal", "team_a": "Spurs"},  # Arsenal DGW
            {"event": 2, "team_h": "Chelsea", "team_a": "Spurs"},
        ]
        text = PromptFormatter.format_fixture_landscape(fixtures, start_gameweek=1, horizon=2)
        self.assertIn("Doubles: Arsenal", text)
        self.assertIn("GW1:", text)
        self.assertIn("GW2:", text)
        self.assertIn("Club fixture counts", text)


if __name__ == "__main__":
    unittest.main()
