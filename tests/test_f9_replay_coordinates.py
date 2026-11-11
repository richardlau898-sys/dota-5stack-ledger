# -*- coding: utf-8 -*-
"""
F9 · 走位坐标合成流模拟与方案设想文档单元测试（R0-3 如实化后）
验证：
1. tools/simulate_replay_coordinates.py 支持提取 replay_url、解析 interval JSONL 流并标注 synthetic=True。
2. docs/f9_replay_coordinates_report.md 明确标注为“方案设想（未实测）”且不含任何未实测数字。
"""
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestF9ReplayCoordinates(unittest.TestCase):
    def test_simulate_replay_coordinates_pipeline_and_compression(self):
        from tools import simulate_replay_coordinates

        raw_path = REPO_ROOT / "reports" / "raw_8774383260.json"
        raw_match = json.loads(raw_path.read_text(encoding="utf-8"))
        replay_url = simulate_replay_coordinates.extract_replay_url_from_raw_match(raw_match)
        self.assertTrue(replay_url.startswith("http"))
        self.assertIn("8774383260", replay_url)

        sample_lines = []
        for t in range(0, 120):
            for slot in range(10):
                sample_lines.append(
                    json.dumps({
                        "time": t,
                        "type": "interval",
                        "slot": slot,
                        "unit": f"CDOTA_Unit_Hero_Slot{slot}",
                        "x": 96 + (t + slot) % 64,
                        "y": 96 + (t * 2 + slot) % 64,
                        "life_state": 0,
                    })
                )

        bench = simulate_replay_coordinates.simulate_interval_stream_compression(
            match_id=int(raw_match["match_id"]),
            replay_url=replay_url,
            jsonl_lines=sample_lines,
        )
        self.assertTrue(bench["synthetic"])
        self.assertEqual(bench["match_id"], int(raw_match["match_id"]))
        self.assertEqual(bench["hero_count"], 10)
        self.assertEqual(bench["total_ticks_per_hero"], 120)
        self.assertLess(bench["gzip_bytes"], bench["raw_json_bytes"])
        self.assertGreaterEqual(bench["parse_elapsed_ms"], 0.0)

    def test_proposal_report_exists_and_has_no_unmeasured_numbers(self):
        report_md = REPO_ROOT / "docs" / "f9_replay_coordinates_report.md"
        self.assertTrue(report_md.exists(), "缺少 docs/f9_replay_coordinates_report.md")
        txt = report_md.read_text(encoding="utf-8")
        self.assertIn("方案设想（未实测）", txt)
        self.assertIn("gzip", txt.lower())
        self.assertEqual(re.findall(r"\d+", txt), [])


if __name__ == "__main__":
    unittest.main()
