# -*- coding: utf-8 -*-
"""
F7 · 每场 3 个复盘时刻 单元测试
验证：
1. 每场选出经济波动绝对值最大的 3 次团战 (abs_gold_swing 降序)。
2. 每条包含时间点 (timestamp_str / time_window_str / client_replay_time_str)、实测证据标签 (evidence == "measured") 与一句中性客观描述 (neutral_summary)。
3. 前端首屏与回放中心渲染 #ws-top3-replay-moments。
"""
import json
import unittest
from pathlib import Path

import dota_analyst

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestF7ReplayMoments(unittest.TestCase):
    def test_top3_replay_moments_sorted_by_abs_gold_swing_and_neutral(self):
        raw_path = REPO_ROOT / "reports" / "raw_8774383260.json"
        raw_match = json.loads(raw_path.read_text(encoding="utf-8"))
        roster = dota_analyst.load_roster()
        report = dota_analyst.analyze_match_data(raw_match, roster)

        self.assertIn("top3_replay_moments", report)
        moments = report["top3_replay_moments"]
        self.assertEqual(len(moments), 3)

        # 验证按 abs_gold_swing 降序排列
        swings = [m["abs_gold_swing"] for m in moments]
        self.assertEqual(swings, sorted(swings, reverse=True))
        self.assertGreater(swings[0], 0)

        forbidden_words = ("罪犯", "战犯", "毒瘤", "冥币", "暴毙", "直接导致", "害死")
        for idx, m in enumerate(moments, start=1):
            self.assertEqual(m["rank"], idx)
            self.assertEqual(m["evidence"], "measured")
            self.assertTrue(m.get("timestamp_str"))
            self.assertTrue(m.get("time_window_str"))
            self.assertTrue(m.get("client_replay_time_str"))
            summary = m.get("neutral_summary") or ""
            self.assertTrue(summary)
            for fw in forbidden_words:
                self.assertNotIn(fw, summary)

    def test_frontend_renders_top3_replay_moments(self):
        html_src = (REPO_ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js_src = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("ws-top3-replay-moments", html_src)
        self.assertIn("ws-top3-replay-moments", js_src)
        self.assertIn("top3_replay_moments", js_src)


if __name__ == "__main__":
    unittest.main()
