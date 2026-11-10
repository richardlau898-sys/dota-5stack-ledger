import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestF3TeamMetrics(unittest.TestCase):
    def test_single_match_all_seven_team_metrics(self):
        """build_team_metrics_by_side computes fight_conversion, first_roshan, throw_comeback_audit, buyback_diebacks, smoke_effectiveness, short_lived_wards_under_2m, and lane_duo_networth_diff."""
        from dota_analyst import analyze_match_data

        raw_path = ROOT / "reports" / "raw_9043191843.json"
        raw_match = json.loads(raw_path.read_text(encoding="utf-8"))
        roster = json.loads((ROOT / "roster.json").read_text(encoding="utf-8"))
        report = analyze_match_data(raw_match, roster)

        self.assertIn("team_metrics", report)
        self.assertIn("team_metrics_by_side", report)

        for side in ("radiant", "dire"):
            tm = report["team_metrics_by_side"][side]
            for key in (
                "fight_conversion",
                "first_roshan",
                "throw_comeback_audit",
                "buyback_diebacks",
                "smoke_effectiveness",
                "short_lived_wards_under_2m",
                "lane_duo_networth_diff",
            ):
                self.assertIn(key, tm, f"Missing {key} in team_metrics_by_side[{side}]")

            fc = tm["fight_conversion"]
            self.assertTrue(fc["available"])
            self.assertEqual(fc["evidence"], "measured")
            self.assertIsInstance(fc["fights"], list)

            tc = tm["throw_comeback_audit"]
            self.assertTrue(tc["available"])
            self.assertEqual(tc["evidence"], "measured")
            self.assertIsInstance(tc["is_10k_throw_loss"], bool)

            se = tm["smoke_effectiveness"]
            self.assertEqual(se["evidence"], "inferred")
            self.assertIn("推断", se["note"])

            ld = tm["lane_duo_networth_diff"]
            self.assertIsInstance(ld, list)
            self.assertGreaterEqual(len(ld), 1)
            for row in ld:
                self.assertEqual(row["evidence"], "measured")
                self.assertEqual(
                    row["net_worth_diff_10m"],
                    row["our_net_worth_10m"] - row["opp_net_worth_10m"],
                )

    def test_buyback_dieback_and_10k_throw_synthetic_verification(self):
        """Verify exact 60s buyback->death threshold and >=10,000 gold lead throw loss + worst 3min window."""
        from squad_growth_metrics import build_team_metrics_by_side

        synthetic_match = {
            "radiant_win": False,
            "radiant_gold_adv": [0, 2000, 6000, 11500, 8000, 1000, -3000],
            "objectives": [
                {"time": 1120, "type": "CHAT_MESSAGE_ROSHAN_KILL", "team": 2},
                {"time": 1240, "type": "CHAT_MESSAGE_TOWER_KILL", "team": 2, "key": "npc_dota_badguys_tower1_mid"},
            ],
            "teamfights": [
                {
                    "start": 1180,
                    "end": 1200,
                    "players": [
                        {"deaths": 0}, {"deaths": 0}, {"deaths": 0}, {"deaths": 0}, {"deaths": 0},
                        {"deaths": 1}, {"deaths": 1}, {"deaths": 1}, {"deaths": 0}, {"deaths": 0},
                    ],
                }
            ],
            "players": [
                {
                    "player_slot": 0,
                    "hero_id": 1,
                    "hero_name": "npc_dota_hero_antimage",
                    "buyback_log": [{"time": 1500}],
                    "kills_log": [],
                },
                {
                    "player_slot": 128,
                    "hero_id": 2,
                    "hero_name": "npc_dota_hero_axe",
                    "kills_log": [{"time": 1545, "key": "npc_dota_hero_antimage"}],
                },
            ],
        }
        synthetic_report = {
            "is_parsed": True,
            "radiant_win": False,
            "radiant_gold_adv": synthetic_match["radiant_gold_adv"],
            "key_teamfights": [
                {"start_sec": 240, "time_range": "04:00–04:30", "net_swing_radiant": -4500}
            ],
            "radiant_pos_1_to_5": [
                {"player_slot": 0, "pos": 1, "hero_short_zh": "敌法师", "personaname": "P1", "lane": 1, "net_worth_10m": 4500}
            ],
            "dire_pos_1_to_5": [
                {"player_slot": 128, "pos": 3, "hero_short_zh": "斧王", "personaname": "P2", "lane": 1, "net_worth_10m": 3800}
            ],
        }

        tm_by_side = build_team_metrics_by_side(synthetic_match, synthetic_report)
        rad_tm = tm_by_side["radiant"]

        # 1. Fight conversion: 0 deaths vs 3 deaths at 1180-1200, tower killed at 1240 (within 90s)
        self.assertEqual(rad_tm["fight_conversion"]["won_fights_count"], 1)
        self.assertEqual(rad_tm["fight_conversion"]["converted_count"], 1)
        self.assertEqual(rad_tm["fight_conversion"]["conversion_rate_pct"], 100.0)

        # 2. First Roshan at 1120s (18:40) by Radiant
        self.assertEqual(rad_tm["first_roshan"]["time_sec"], 1120)
        self.assertEqual(rad_tm["first_roshan"]["side"], "radiant")

        # 3. 10k throw loss & worst 3min window (min 3: +11500 -> min 6: -3000 = -14500)
        self.assertTrue(rad_tm["throw_comeback_audit"]["is_10k_throw_loss"])
        self.assertEqual(rad_tm["throw_comeback_audit"]["max_gold_lead"], 11500)
        self.assertEqual(rad_tm["throw_comeback_audit"]["worst_3min_window"]["gold_delta"], -14500)

        # 4. Buyback at 1500s -> death at 1545s (45s <= 60s)
        self.assertEqual(len(rad_tm["buyback_diebacks"]), 1)
        self.assertEqual(rad_tm["buyback_diebacks"][0]["delta_sec"], 45)

    def test_cross_match_high_risk_ward_spots_in_squad_ledger(self):
        """aggregate_high_risk_ward_spots finds fixed spots with median lifespan < 120s and is exposed in squad_ledger."""
        from draft_and_phase_coach import build_squad_history_ledger
        from squad_growth_metrics import aggregate_high_risk_ward_spots

        fake_matches = [
            {
                "players": [
                    {
                        "obs_log": [{"time": 600, "x": 140, "y": 148, "ehandle": 11}],
                        "obs_left_log": [{"time": 650, "x": 140, "y": 148, "ehandle": 11}],
                    }
                ]
            },
            {
                "players": [
                    {
                        "obs_log": [{"time": 900, "x": 141, "y": 149, "ehandle": 22}],
                        "obs_left_log": [{"time": 980, "x": 141, "y": 149, "ehandle": 22}],
                    }
                ]
            },
        ]
        spots = aggregate_high_risk_ward_spots(fake_matches, max_median_lifespan_sec=120.0, min_samples=2)
        self.assertEqual(len(spots), 1)
        self.assertEqual(spots[0]["sample_count"], 2)
        self.assertEqual(spots[0]["median_lifespan_sec"], 65.0)

        roster = json.loads((ROOT / "roster.json").read_text(encoding="utf-8"))
        ledger = build_squad_history_ledger(ROOT / "reports", roster, [])
        self.assertIn("high_risk_ward_spots", ledger)
        self.assertIsInstance(ledger["high_risk_ward_spots"], list)


if __name__ == "__main__":
    unittest.main()
