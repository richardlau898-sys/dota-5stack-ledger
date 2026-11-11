# -*- coding: utf-8 -*-
"""
R0-2 · 评测集如实标注来源 单元测试
验证：
1. 原 evals/annotations.json 已改名为 evals/engine_baseline.json，文件头注明「引擎输出，不是人工标注」。
2. evals/annotations_template.json 包含 10 场比赛，每场留空 biggest_issue_pos、reason、3 个 key_moments、annotated_by。
3. evals/run_eval.py 在模板未填写（annotated_by 不是 Richard 填写的值）时拒绝输出一致率，只提示「尚未人工标注」，不出现任何百分比。
4. 删掉写死的事实核查得分；评测对象为已保存的 AI 判词与真实 LLM 调用（--live 开关）。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestR02HonestEvals(unittest.TestCase):
    def test_1_engine_baseline_and_empty_template_exist(self):
        old_path = ROOT_DIR / "evals" / "annotations.json"
        self.assertFalse(old_path.exists(), "evals/annotations.json should be renamed to engine_baseline.json")

        baseline_path = ROOT_DIR / "evals" / "engine_baseline.json"
        self.assertTrue(baseline_path.exists(), "evals/engine_baseline.json must exist")
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        header_text = f"{baseline.get('source_note', '')} {baseline.get('description', '')}"
        self.assertIn("引擎输出，不是人工标注", header_text)
        self.assertEqual(len(baseline.get("matches") or []), 10)

        tpl_path = ROOT_DIR / "evals" / "annotations_template.json"
        self.assertTrue(tpl_path.exists(), "evals/annotations_template.json must exist")
        tpl = json.loads(tpl_path.read_text(encoding="utf-8"))
        matches = tpl.get("matches") or []
        self.assertEqual(len(matches), 10)
        for m in matches:
            self.assertIsNone(m.get("biggest_issue_pos"))
            self.assertEqual(m.get("reason"), "")
            self.assertEqual(m.get("annotated_by"), "")
            kms = m.get("key_moments")
            self.assertIsInstance(kms, list)
            self.assertEqual(len(kms), 3)
            for km in kms:
                self.assertEqual(km.get("time_str"), "")
                self.assertEqual(km.get("description"), "")

    def test_2_unfilled_template_refuses_percentages_and_prints_notice(self):
        script_path = ROOT_DIR / "evals" / "run_eval.py"
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, f"run_eval.py failed: {proc.stderr}")
        self.assertIn("尚未人工标注", proc.stdout)
        self.assertNotIn("%", proc.stdout, "Unfilled template output must not contain any percentages")

    def test_3_filled_richard_annotations_evaluates_saved_and_live_without_hardcoded_factcheck(self):
        from evals import run_eval

        src = (ROOT_DIR / "evals" / "run_eval.py").read_text(encoding="utf-8")
        self.assertNotIn('fact_checked_sentences"] += 10', src)

        tpl = json.loads((ROOT_DIR / "evals" / "annotations_template.json").read_text(encoding="utf-8"))
        for idx, m in enumerate(tpl["matches"]):
            m["annotated_by"] = "Richard"
            m["biggest_issue_pos"] = (idx % 5) + 1
            m["reason"] = "人工复盘记录"
            m["key_moments"] = [
                {"time_str": "15:00", "description": "一塔团"},
                {"time_str": "25:00", "description": "肉山团"},
                {"time_str": "35:00", "description": "高地团"},
            ]

        with tempfile.TemporaryDirectory() as tmpdir:
            ann_file = Path(tmpdir) / "richard_annotations.json"
            ann_file.write_text(json.dumps(tpl, ensure_ascii=False), encoding="utf-8")

            # Offline mode evaluates saved coaching JSONs only
            res_offline = run_eval.evaluate_all_configs(annotations_path=ann_file, live=False)
            self.assertTrue(res_offline.get("annotated"))
            self.assertIn("saved_ai_coaching (已保存的 AI 判词)", res_offline["configs"])
            self.assertNotIn("live_llm_coaching (实时 LLM 调用)", res_offline["configs"])
            md = run_eval.format_eval_report(res_offline)
            self.assertIn("%", md)

            # Live mode invokes call_llm_coach_review (mocked here for offline unit test)
            def fake_live_review(report, **kwargs):
                own = report.get(f"{report.get('focus_side', 'dire')}_pos_1_to_5") or []
                return {
                    "ok": True,
                    "structured": {
                        "title": "测试标题",
                        "summary": "测试总结。",
                        "verdict": "测试判词。",
                        "players": [
                            {
                                "slot": p.get("player_slot"),
                                "pos": p.get("pos"),
                                "grok_score": 60 if int(p.get("pos") or 0) == 1 else 75,
                                "grok_share_pct": 30.0 if int(p.get("pos") or 0) == 1 else 17.5,
                            }
                            for p in own
                        ],
                        "windows": [{"time_label": "25:00", "detail": "肉山交战"}],
                    },
                }

            with patch.object(run_eval.ai_coach_engine, "call_llm_coach_review", side_effect=fake_live_review):
                res_live = run_eval.evaluate_all_configs(annotations_path=ann_file, live=True)
            self.assertIn("live_llm_coaching (实时 LLM 调用)", res_live["configs"])


if __name__ == "__main__":
    unittest.main()
