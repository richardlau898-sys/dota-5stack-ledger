import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestF4PersonalTrendsAndGoals(unittest.TestCase):
    def test_build_personal_trends_and_goals_four_curves_and_weekly_goal(self):
        """build_personal_trends_and_goals computes the 4 required trend series and weekly goal progress."""
        from squad_growth_metrics import build_personal_trends_and_goals

        fake_reports = []
        for idx, (mid, pickoffs, nw10, opp_nw10, obs, sen, bkb_sec) in enumerate([
            (9001, [{"time_sec": 750}, {"time_sec": 1100}], 4600, 4100, 12, 15, 1140),
            (9002, [{"time_sec": 820}], 4300, 4500, 14, 16, 1200),
            (9003, [], 4900, 4000, 16, 18, 1260),
        ]):
            fake_reports.append({
                "match_id": mid,
                "start_time": 1760000000 + idx * 3600,
                "start_time_str": f"2026-11-0{idx + 1} 20:00",
                "duration_min": 30.0,
                "is_parsed": True,
                "radiant_pos_1_to_5": [
                    {
                        "account_id": 86080912,
                        "pos": 1,
                        "raw_lane": 1,
                        "hero_short_zh": "主宰",
                        "laning_10m": {"gold10": nw10},
                        "phase_telemetry": {"solo_pickoffs": pickoffs},
                        "final_items_rich": [{"key": "black_king_bar", "purchase_time_sec": bkb_sec}],
                    },
                    {
                        "account_id": 125383759,
                        "pos": 5,
                        "raw_lane": 1,
                        "hero_short_zh": "巫医",
                        "obs_placed": obs,
                        "sen_placed": sen,
                        "laning_10m": {"gold10": 2600},
                        "phase_telemetry": {"solo_pickoffs": []},
                        "final_items_rich": [{"key": "glimmer_cape", "purchase_time_sec": 1080}],
                    },
                ],
                "dire_pos_1_to_5": [
                    {
                        "account_id": 999001,
                        "pos": 3,
                        "raw_lane": 1,
                        "hero_short_zh": "斧王",
                        "laning_10m": {"gold10": opp_nw10},
                    }
                ],
            })

        res = build_personal_trends_and_goals(
            fake_reports,
            roster={
                "players": {
                    "86080912": {"name": "Flame"},
                    "125383759": {"name": "Siesta"},
                }
            },
            weekly_goals={
                "86080912": {
                    "metric": "non_teamfight_deaths_after_10m",
                    "label_zh": "10分钟后团战外阵亡 <= 1.5 次/局",
                    "direction": "max",
                    "target": 1.5,
                }
            },
        )
        players = res["players"]
        self.assertIn("86080912", players)
        self.assertIn("125383759", players)

        p_core = players["86080912"]
        self.assertEqual(p_core["games_count"], 3)
        self.assertEqual(p_core["median_key_item_sec"], 1200.0)
        series_core = p_core["series"]
        self.assertEqual([pt["non_teamfight_deaths_after_10m"] for pt in series_core], [2, 1, 0])
        self.assertEqual([pt["lane_nw_diff_10m"] for pt in series_core], [500.0, -200.0, 900.0])
        self.assertEqual([pt["key_item_timing_delta_sec"] for pt in series_core], [-60.0, 0.0, 60.0])
        self.assertTrue(p_core["weekly_goal"]["achieved"])
        self.assertEqual(p_core["weekly_goal"]["current_avg"], 1.0)

        p_sup = players["125383759"]
        series_sup = p_sup["series"]
        self.assertEqual([pt["support_wards_per_min"] for pt in series_sup], [0.9, 1.0, 1.13])
        self.assertIsNone(p_sup["weekly_goal"])

    def test_squad_ledger_and_frontend_expose_personal_trends_and_goals(self):
        """build_squad_history_ledger includes personal_trends_and_goals and static/app.js renders #squad-personal-trends-goals."""
        from draft_and_phase_coach import build_squad_history_ledger

        roster = json.loads((ROOT / "roster.json").read_text(encoding="utf-8"))
        ledger = build_squad_history_ledger(ROOT / "reports", roster, [])
        self.assertIn("personal_trends_and_goals", ledger)
        self.assertIn("players", ledger["personal_trends_and_goals"])

        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("personal_trends_and_goals", js)
        self.assertIn("squad-personal-trends-goals", js)


if __name__ == "__main__":
    unittest.main()
