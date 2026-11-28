import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestA6AsyncLlmReview(unittest.TestCase):
    """A6 · 判词生成移出请求：超时小于函数上限、异步任务ID返回与Supabase状态存储、前端轮询"""

    def test_1_all_llm_timeouts_strictly_under_60s(self):
        """ai_coach_engine.py 中所有 urlopen 的 timeout 均小于 60 秒（Vercel 函数上限）"""
        src = (ROOT_DIR / "ai_coach_engine.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        timeouts = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                elif isinstance(node.func, ast.Name):
                    func_name = node.func.id
                if func_name == "urlopen":
                    for kw in node.keywords:
                        if kw.arg == "timeout" and isinstance(kw.value, ast.Constant):
                            timeouts.append((node.lineno, kw.value.value))
        self.assertTrue(len(timeouts) > 0, "Expected at least one urlopen timeout in ai_coach_engine.py")
        for lineno, val in timeouts:
            self.assertLess(
                val,
                60,
                f"urlopen at ai_coach_engine.py:{lineno} has timeout={val}s which is >= 60s function limit",
            )

    def test_2_task_lifecycle_and_supabase_persistence(self):
        """POST /api/llm_review 立即返回 task_id，后台执行并把状态存入 Supabase，可通过状态接口轮询"""
        import cloud_store
        import server

        saved_supabase_tasks = {}

        def fake_supabase_upsert_task(task_id, task_obj, cfg=None):
            saved_supabase_tasks[task_id] = dict(task_obj)
            return True

        def fake_supabase_fetch_task(task_id, cfg=None):
            return saved_supabase_tasks.get(task_id)

        fake_report = {
            "match_id": 9046276667,
            "is_parsed": True,
            "focus_side": "dire",
            "radiant_win": True,
            "user_won": False,
        }
        fake_structured = {
            "title": "测试异步判词标题",
            "summary": "测试异步判词摘要",
            "verdict": "测试异步判词结论",
            "model": "grok-4.20-0309-non-reasoning",
            "provider": "xai",
            "players": [],
            "windows": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir, \
             patch.object(server, "REPORTS_DIR", Path(tmpdir)), \
             patch.object(server, "TMP_REPORTS_DIR", Path(tmpdir)), \
             patch.object(cloud_store, "TMP_REPORTS_DIR", Path(tmpdir)), \
             patch.object(cloud_store, "_supabase_upsert_llm_task", side_effect=fake_supabase_upsert_task), \
             patch.object(cloud_store, "_supabase_fetch_llm_task", side_effect=fake_supabase_fetch_task), \
             patch.object(server, "call_llm_coach_review", return_value={"ok": True, "structured": fake_structured}), \
             patch.object(server, "cloud_save_match_report", return_value={"supabase": True}):
            task_info = server.start_async_llm_review_task(
                match_id=9046276667,
                side="dire",
                report=fake_report,
                run_async=False,  # deterministic synchronous execution of worker for unit test after creation check
            )
            self.assertTrue(task_info.get("ok"))
            task_id = task_info.get("task_id")
            self.assertTrue(isinstance(task_id, str) and task_id.startswith("llm-9046276667-dire-"))
            self.assertIn(task_id, saved_supabase_tasks)

            fetched = cloud_store.cloud_load_llm_task(task_id)
            self.assertIsNotNone(fetched)
            self.assertEqual(fetched.get("status"), "completed")
            self.assertEqual(fetched.get("structured", {}).get("title"), "测试异步判词标题")

    def test_3_frontend_polls_llm_review_status(self):
        """static/app.js 中 triggerGrokReview 支持 task_id 与 /api/llm_review_status 轮询"""
        app_js = (ROOT_DIR / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("/api/llm_review_status", app_js)
        self.assertIn("task_id", app_js)


if __name__ == "__main__":
    unittest.main()
