import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestA5EvalSuite(unittest.TestCase):
    """A5 / R0-2 · 评测集：如实标注来源 + 未人工标注时拒绝输出百分比"""

    def test_1_engine_baseline_and_template_structure(self):
        baseline_path = ROOT_DIR / "evals" / "engine_baseline.json"
        self.assertTrue(baseline_path.exists(), "evals/engine_baseline.json must exist")
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        self.assertIn("引擎输出，不是人工标注", baseline.get("source_note", ""))
        self.assertEqual(len(baseline.get("matches") or []), 10)

        tpl_path = ROOT_DIR / "evals" / "annotations_template.json"
        self.assertTrue(tpl_path.exists(), "evals/annotations_template.json must exist")
        tpl = json.loads(tpl_path.read_text(encoding="utf-8"))
        self.assertEqual(len(tpl.get("matches") or []), 10)

    def test_2_run_eval_on_unfilled_template_outputs_unannotated_notice(self):
        script_path = ROOT_DIR / "evals" / "run_eval.py"
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, f"run_eval.py failed: {proc.stderr}")
        self.assertIn("尚未人工标注", proc.stdout)
        self.assertNotIn("%", proc.stdout)


if __name__ == "__main__":
    unittest.main()
