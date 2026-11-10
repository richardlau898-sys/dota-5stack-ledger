import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestA5EvalSuite(unittest.TestCase):
    """A5 · 评测集：10 场标注比赛 + 一致率评测脚本"""

    def test_1_evals_dataset_has_10_annotated_matches(self):
        """evals/annotations.json 包含 10 场真实比赛的人工基准标注（谁的问题最大 + 3 个关键时刻）"""
        dataset_path = ROOT_DIR / "evals" / "annotations.json"
        self.assertTrue(dataset_path.exists(), "evals/annotations.json must exist")
        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        self.assertIn("matches", data)
        matches = data["matches"]
        self.assertEqual(len(matches), 10, "Must contain exactly 10 annotated matches")

        seen_ids = set()
        for item in matches:
            mid = item.get("match_id")
            self.assertIsInstance(mid, int)
            seen_ids.add(mid)
            self.assertIn(item.get("side"), ("radiant", "dire"))
            # biggest_issue_pos: 1..5 or None (no obvious culprit)
            pos = item.get("biggest_issue_pos")
            self.assertTrue(pos is None or pos in (1, 2, 3, 4, 5), f"Invalid biggest_issue_pos: {pos}")
            self.assertIsInstance(item.get("biggest_issue_reason_zh"), str)
            self.assertTrue(len(item["biggest_issue_reason_zh"]) > 0)

            moments = item.get("key_moments")
            self.assertIsInstance(moments, list)
            self.assertEqual(len(moments), 3, f"Match {mid} must have exactly 3 key_moments")
            for m in moments:
                self.assertIn("time_sec", m)
                self.assertIn("time_str", m)
                self.assertIn("window_sec", m)
                self.assertEqual(len(m["window_sec"]), 2)
                self.assertLessEqual(m["window_sec"][0], m["window_sec"][1])
                self.assertTrue(len(m.get("description_zh", "")) > 0)

        self.assertEqual(len(seen_ids), 10, "All 10 match_ids must be distinct")

    def test_2_run_eval_script_outputs_agreement_table(self):
        """evals/run_eval.py 能离线运行并输出包含一致率指标的对比表"""
        script_path = ROOT_DIR / "evals" / "run_eval.py"
        self.assertTrue(script_path.exists(), "evals/run_eval.py must exist")

        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, f"run_eval.py failed: {proc.stderr}")
        out = proc.stdout
        self.assertIn("谁的问题最大一致率", out)
        self.assertIn("关键时刻命中率", out)
        self.assertIn("事实核查通过率", out)
        self.assertIn("|", out, "Must output a formatted table")


if __name__ == "__main__":
    unittest.main()
