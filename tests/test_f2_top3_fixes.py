import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestF2Top3Fixes(unittest.TestCase):
    def test_report_contains_next_game_top3_fixes_measured_only_team_first(self):
        """next_game_top3_fixes must only include measured conclusions, prioritize team scope over player scope, and include evidence & timestamps."""
        from dota_analyst import analyze_match_data

        raw_path = ROOT / "reports" / "raw_9043191843.json"
        raw_match = json.loads(raw_path.read_text(encoding="utf-8"))
        roster = json.loads((ROOT / "roster.json").read_text(encoding="utf-8"))
        report = analyze_match_data(raw_match, roster)

        self.assertIn("next_game_top3_fixes", report)
        self.assertIn("next_game_top3_fixes_by_side", report)

        for side in ("radiant", "dire"):
            fixes = report["next_game_top3_fixes_by_side"].get(side)
            self.assertIsInstance(fixes, list)
            self.assertGreaterEqual(len(fixes), 1)
            self.assertLessEqual(len(fixes), 3)

            scopes = [f["scope"] for f in fixes]
            for f in fixes:
                self.assertEqual(f.get("evidence"), "measured")
                self.assertIn(f.get("scope"), ("team", "player"))
                self.assertTrue(f.get("timestamp_str"), f"Missing timestamp_str in {f}")
                self.assertRegex(f["timestamp_str"], r"^\d{1,3}:\d{2}")
                self.assertTrue(f.get("fact_evidence"), f"Missing fact_evidence in {f}")
                self.assertTrue(f.get("action_item"), f"Missing action_item in {f}")

            # Verify team scope items always precede player scope items
            seen_player = False
            for sc in scopes:
                if sc == "player":
                    seen_player = True
                elif sc == "team" and seen_player:
                    self.fail(f"Team-level fix appeared after player-level fix in {scopes}")

    def test_candidate_filter_rejects_inferred_and_template_items(self):
        """select_top3_measured_fixes must strip inferred/template candidates and sort team first then by impact_score."""
        from squad_growth_metrics import select_top3_measured_fixes

        candidates = [
            {
                "scope": "team",
                "evidence": "inferred",
                "timestamp_str": "12:00",
                "impact_score": 9999.0,
                "title": "推断结论不应入选",
                "fact_evidence": "推断数据",
                "action_item": "不应出现",
            },
            {
                "scope": "player",
                "evidence": "measured",
                "timestamp_str": "21:15",
                "impact_score": 5000.0,
                "title": "个人保命装未按",
                "fact_evidence": "21:15 阵亡时 BKB 0 次使用",
                "action_item": "接团前先开 BKB",
            },
            {
                "scope": "team",
                "evidence": "measured",
                "timestamp_str": "18:30",
                "impact_score": 1200.0,
                "title": "赢团后 90 秒 0 推塔转化",
                "fact_evidence": "18:30 团战 0 换 3 后 90 秒内 0 建筑 0 肉山",
                "action_item": "赢团后立即就近逼塔或控盾",
            },
            {
                "scope": "team",
                "evidence": "measured",
                "timestamp_str": "27:40",
                "impact_score": 3400.0,
                "title": "视野断档期团灭",
                "fact_evidence": "27:40 地图 0 假眼期间阵亡 4 人，经济波动 -3,400",
                "action_item": "过河道前先补高台假眼",
            },
        ]
        top3 = select_top3_measured_fixes(candidates)
        self.assertEqual(len(top3), 3)
        self.assertTrue(all(x["evidence"] == "measured" for x in top3))
        self.assertEqual([x["title"] for x in top3], [
            "视野断档期团灭",
            "赢团后 90 秒 0 推塔转化",
            "个人保命装未按",
        ])
        self.assertEqual([x["rank"] for x in top3], [1, 2, 3])

    def test_frontend_renders_top3_fixes_on_summary_tab(self):
        """static/index.html and static/app.js must render #ws-top3-fixes-container."""
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="ws-top3-fixes-container"', html)
        self.assertIn("ws-top3-fixes-container", js)
        self.assertIn("next_game_top3_fixes", js)


if __name__ == "__main__":
    unittest.main()
