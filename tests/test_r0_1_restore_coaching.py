# -*- coding: utf-8 -*-
"""
R0-1 · 恢复被改动的 AI 判词 单元测试
验证：
1. reports/coaching-*.json 与 2ee46c9^ 完全一致（不再有任何手工篡改痕迹）。
2. tests/test_a3_single_call_ranking.py 不再读取 reports/coaching-*.json，全部走 call_llm_coach_review 真实代码路径。
"""
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestR01RestoreCoaching(unittest.TestCase):
    def test_1_coaching_files_restored_to_pre_2ee46c9(self):
        has_commit = subprocess.run(
            ["git", "cat-file", "-e", "2ee46c9^"],
            cwd=str(REPO_ROOT),
            capture_output=True,
        )
        if has_commit.returncode == 0:
            diff = subprocess.run(
                ["git", "diff", "2ee46c9^", "--", "reports/coaching-*.json"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(diff.stdout.strip(), "", "reports/coaching-*.json must match 2ee46c9^ with zero diff")

    def test_2_test_a3_does_not_read_saved_coaching_files(self):
        src = (REPO_ROOT / "tests" / "test_a3_single_call_ranking.py").read_text(encoding="utf-8")
        self.assertNotIn("coaching-*.json", src)
        self.assertNotIn('"reports", "coaching-', src)
        self.assertIn("call_llm_coach_review", src)


if __name__ == "__main__":
    unittest.main()
