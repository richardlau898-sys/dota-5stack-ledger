# -*- coding: utf-8 -*-
"""
F9 · 真实走位数据（第一步可行性验证）单元测试
验证：
1. tools/verify_replay_coordinates.py 实现从 raw_*.json 提取 replay_url、解析 odota/parser interval JSONL 流提取逐秒十人坐标、gzip 压缩体积测算与耗时统计。
2. docs/f9_replay_coordinates_report.md 包含输出格式、耗时和文件大小实测汇报。
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestF9ReplayCoordinates(unittest.TestCase):
    def test_verify_replay_coordinates_pipeline_and_compression(self):
        from tools import verify_replay_coordinates

        raw_path = REPO_ROOT / "reports" / "raw_8774383260.json"
        raw_match = json.loads(raw_path.read_text(encoding="utf-8"))
        replay_url = verify_replay_coordinates.extract_replay_url_from_raw_match(raw_match)
        self.assertTrue(replay_url.startswith("http"))
        self.assertIn("8774383260", replay_url)

        # 模拟 odota/parser 输出的 interval JSONL 行（40 分钟 = 2400 秒 × 10 名玩家 = 24,000 条记录）
        sample_lines = []
        for t in range(0, 2400):
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

        bench = verify_replay_coordinates.benchmark_interval_stream(
            match_id=int(raw_match["match_id"]),
            replay_url=replay_url,
            jsonl_lines=sample_lines,
        )
        self.assertEqual(bench["match_id"], int(raw_match["match_id"]))
        self.assertEqual(bench["hero_count"], 10)
        self.assertEqual(bench["total_ticks_per_hero"], 2400)
        self.assertGreater(bench["raw_json_bytes"], 100_000)
        self.assertLess(bench["gzip_bytes"], bench["raw_json_bytes"])
        self.assertGreaterEqual(bench["parse_elapsed_ms"], 0.0)

    def test_feasibility_report_exists_with_format_time_and_size(self):
        report_md = REPO_ROOT / "docs" / "f9_replay_coordinates_report.md"
        self.assertTrue(report_md.exists(), "缺少 docs/f9_replay_coordinates_report.md")
        txt = report_md.read_text(encoding="utf-8")
        self.assertIn("输出格式", txt)
        self.assertIn("耗时", txt)
        self.assertIn("文件大小", txt)
        self.assertIn("gzip", txt.lower())


if __name__ == "__main__":
    unittest.main()
