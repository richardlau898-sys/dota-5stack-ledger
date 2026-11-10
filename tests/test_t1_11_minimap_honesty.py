import os
import unittest

from tests.helpers import build_all_sample_reports

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestT111MinimapHonesty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_reports = build_all_sample_reports()

    def test_1_no_false_claims_in_frontend_or_html(self):
        """文案里不再出现 '逐秒走位'、'逐秒回放十人走位'、'十人走位'、'100% 源自'、'当时装备'、'当时已合成装备'"""
        for rel_path in ("static/index.html", "static/app.js", "tactical_microscope_engine.py"):
            full_path = os.path.join(REPO_ROOT, rel_path)
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            for forbidden in (
                "逐秒走位",
                "逐秒回放十人走位",
                "十人走位",
                "英雄走位",
                "100% 源自",
                "当时装备",
                "当时已合成装备",
            ):
                self.assertNotIn(
                    forbidden,
                    content,
                    f"Forbidden claim '{forbidden}' still present in {rel_path}",
                )

    def test_2_synthetic_positions_labeled_and_semi_transparent_and_real_points_excluded_from_decluster(self):
        """合成的位置用半透明显示并标注 '示意位置，非真实走位'；真实点用实心显示且不参与防重叠位移"""
        app_js_path = os.path.join(REPO_ROOT, "static", "app.js")
        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js = f.read()

        self.assertIn("示意位置，非真实走位", app_js)
        self.assertIn("最近购买", app_js)
        self.assertIn("isReal", app_js)
        self.assertIn("isSynthetic", app_js)

        # declusterMinimapNodes must skip real points (nodes where isReal is true)
        decluster_idx = app_js.find("function declusterMinimapNodes")
        self.assertGreater(decluster_idx, 0)
        decluster_slice = app_js[decluster_idx : decluster_idx + 1200]
        self.assertIn("isReal", decluster_slice, "declusterMinimapNodes must check isReal and not displace real points")

    def test_3_minute_snapshots_expose_recent_purchases(self):
        """minute_snapshots 玩家快照提供 recent_purchases 字段"""
        for mid, report in self.sample_reports.items():
            if not report.get("is_parsed"):
                continue
            snaps = (report.get("deep_forensics") or {}).get("minute_snapshots") or []
            self.assertGreater(len(snaps), 0, f"Parsed match {mid} missing minute_snapshots")
            first_players = snaps[0].get("players") or []
            self.assertGreater(len(first_players), 0)
            for p_snap in first_players:
                self.assertIn("recent_purchases", p_snap)
            break


if __name__ == "__main__":
    unittest.main()
