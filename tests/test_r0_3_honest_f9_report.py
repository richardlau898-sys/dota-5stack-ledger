# -*- coding: utf-8 -*-
"""
R0-3 · F9 可行性报告改成如实（方案二：环境无 JVM / Docker，未实测真实录像）
验证：
1. tools/verify_replay_coordinates.py 已删除，改名为 tools/simulate_replay_coordinates.py，且文件头注明输出是合成数据。
2. docs/f9_replay_coordinates_report.md 标题改为“方案设想（未实测）”，删掉耗时表、样本坐标和所有数字。
3. simulate_replay_coordinates 的坐标转换与合成流函数仍可在真实 raw_*.json 样本上正常调用，且不会将合成数据标为实测。
"""
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestR03HonestF9Report(unittest.TestCase):
    def test_tool_renamed_to_simulate_and_marked_synthetic(self):
        old_tool = REPO_ROOT / "tools" / "verify_replay_coordinates.py"
        new_tool = REPO_ROOT / "tools" / "simulate_replay_coordinates.py"
        self.assertFalse(old_tool.exists(), "tools/verify_replay_coordinates.py 必须删除并重命名为 simulate_replay_coordinates.py")
        self.assertTrue(new_tool.exists(), "缺少 tools/simulate_replay_coordinates.py")

        source = new_tool.read_text(encoding="utf-8")
        head = "\n".join(source.splitlines()[:20])
        self.assertIn("合成数据", head, "文件头必须明确注明输出是合成数据")
        self.assertNotIn("耗时实测", source)
        self.assertNotIn("~3.5s", source)

    def test_report_is_unmeasured_proposal_with_zero_digits(self):
        report_path = REPO_ROOT / "docs" / "f9_replay_coordinates_report.md"
        self.assertTrue(report_path.exists(), "缺少 docs/f9_replay_coordinates_report.md")
        content = report_path.read_text(encoding="utf-8")
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        self.assertTrue(lines, "报告内容不能为空")
        self.assertIn("方案设想（未实测）", lines[0])
        self.assertNotIn("耗时实测", content)
        self.assertNotIn("trajectories", content)

        digit_matches = re.findall(r"\d+", content)
        self.assertEqual(
            digit_matches,
            [],
            f"未实测方案设想报告不得包含任何数字，实际发现: {digit_matches}",
        )

    def test_simulate_replay_coordinates_runs_on_real_sample(self):
        from tools import simulate_replay_coordinates

        raw_path = REPO_ROOT / "reports" / "raw_8774383260.json"
        raw_match = json.loads(raw_path.read_text(encoding="utf-8"))
        replay_url = simulate_replay_coordinates.extract_replay_url_from_raw_match(raw_match)
        self.assertIsInstance(replay_url, str)
        self.assertTrue(replay_url.startswith("http"))

        synth_lines = simulate_replay_coordinates.build_synthetic_interval_lines_from_match(
            raw_match, duration_override=60
        )
        self.assertEqual(len(synth_lines), 600)
        summary = simulate_replay_coordinates.simulate_interval_stream_compression(
            match_id=int(raw_match["match_id"]),
            replay_url=replay_url,
            jsonl_lines=synth_lines,
        )
        self.assertTrue(summary["synthetic"])
        self.assertEqual(summary["hero_count"], 10)
        self.assertEqual(summary["total_ticks_per_hero"], 60)
        self.assertLess(summary["gzip_bytes"], summary["raw_json_bytes"])


if __name__ == "__main__":
    unittest.main()
