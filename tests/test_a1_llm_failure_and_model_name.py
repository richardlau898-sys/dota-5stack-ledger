import json
import os
import re
import unittest
from unittest.mock import patch, MagicMock

import ai_coach_engine
import server
from tests.helpers import build_all_sample_reports

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestA1LlmFailureAndModelName(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_report = next(
            r for r in build_all_sample_reports().values() if r.get("is_parsed")
        )

    def test_1_all_requests_fail_returns_ok_false_no_file_write_no_cloud_store(self):
        """mock 全部请求失败，断言返回 ok: False 且没有写文件、没有调云存储"""
        report = json.loads(json.dumps(self.sample_report))
        report["match_id"] = 9999990001

        with patch.object(
            ai_coach_engine,
            "load_env_llm_config",
            return_value={
                "provider": "xai",
                "api_key": "test-xai-key",
                "model_name": "grok-4.7",
                "base_url": "https://api.x.ai/v1",
            },
        ), patch("urllib.request.urlopen", side_effect=OSError("network timeout")), patch(
            "builtins.open", wraps=open
        ) as spy_open, patch.object(server, "cloud_save_match_report") as mock_cloud:
            res = ai_coach_engine.call_llm_coach_review(report)
            self.assertFalse(res.get("ok"), f"Expected ok=False when all LLM calls fail, got: {res}")
            self.assertIsNone(res.get("structured"))
            # Confirm no coaching-9999990001-*.json was opened for writing
            write_calls = [
                c
                for c in spy_open.call_args_list
                if len(c.args) >= 2 and "w" in str(c.args[1]) and "9999990001" in str(c.args[0])
            ]
            self.assertEqual(len(write_calls), 0, f"Unexpected file writes on failure: {write_calls}")
            mock_cloud.assert_not_called()

    def test_2_single_shard_failure_returns_ok_false_and_does_not_persist(self):
        """任一分片失败就整体返回 ok: False，不落库（严禁用模板文字冒充判词）"""
        report = json.loads(json.dumps(self.sample_report))
        report["match_id"] = 9999990002

        call_count = {"n": 0}

        def fake_urlopen(req, timeout=36):
            call_count["n"] += 1
            body_str = req.data.decode("utf-8") if req.data else ""
            # Fail permanently on the Pos 3 shard (or if single-call, fail)
            if "并发分片 Pos 3" in body_str or call_count["n"] >= 3:
                raise OSError("Shard 3 failed")
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            body_obj = {
                "title": "测试标题",
                "summary": "测试总结",
                "verdict": "测试判词",
                "team_practice": "测试训练",
                "stage_reviews": {
                    "early_lanes": "前期",
                    "mid_tempo": "中期",
                    "late_and_roshan": "后期",
                    "overall_verdict": "总评",
                },
                "mvp": {"slot": 0, "reason": "测试"},
                "players": [
                    {
                        "slot": i,
                        "pos": i + 1,
                        "hero": "测试英雄",
                        "grok_score": 70,
                        "grok_share_pct": 20.0,
                        "headline": "测试",
                        "deep_verdict": "测试深度判词",
                    }
                    for i in range(5)
                ],
                "windows": [],
            }
            mock_resp.read.return_value = json.dumps(
                {"choices": [{"message": {"content": json.dumps(body_obj, ensure_ascii=False)}}]}
            ).encode("utf-8")
            return mock_resp

        with patch.object(
            ai_coach_engine,
            "load_env_llm_config",
            return_value={
                "provider": "xai",
                "api_key": "test-xai-key",
                "model_name": "grok-4.7",
                "base_url": "https://api.x.ai/v1",
            },
        ), patch("urllib.request.urlopen", side_effect=fake_urlopen), patch(
            "builtins.open", wraps=open
        ) as spy_open:
            res = ai_coach_engine.call_llm_coach_review(report)
            self.assertFalse(res.get("ok"), f"Expected ok=False when a shard fails, got: {res}")
            write_calls = [
                c
                for c in spy_open.call_args_list
                if len(c.args) >= 2 and "w" in str(c.args[1]) and "9999990002" in str(c.args[0])
            ]
            self.assertEqual(len(write_calls), 0, f"Unexpected file writes on partial failure: {write_calls}")

    def test_3_records_real_invoked_model_id(self):
        """存档与返回结果记录真实调用的模型 ID（如 grok-4.20-0309-non-reasoning 而非 grok-4.7）"""
        report = json.loads(json.dumps(self.sample_report))
        report["match_id"] = 9999990003

        def fake_urlopen_ok(req, timeout=36):
            req_body = json.loads(req.data.decode("utf-8"))
            invoked_model = req_body.get("model")
            self.assertEqual(invoked_model, "grok-4.20-0309-non-reasoning")
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            body_obj = {
                "title": "测试标题",
                "summary": "测试总结",
                "verdict": "测试判词",
                "team_practice": "测试训练",
                "stage_reviews": {
                    "early_lanes": "前期",
                    "mid_tempo": "中期",
                    "late_and_roshan": "后期",
                    "overall_verdict": "总评",
                },
                "mvp": {"slot": 0, "reason": "测试"},
                "players": [
                    {
                        "slot": i,
                        "pos": i + 1,
                        "hero": "测试英雄",
                        "grok_score": 70,
                        "grok_share_pct": 20.0,
                        "headline": "测试",
                        "deep_verdict": "测试深度判词",
                    }
                    for i in range(5)
                ],
                "windows": [],
            }
            mock_resp.read.return_value = json.dumps(
                {"choices": [{"message": {"content": json.dumps(body_obj, ensure_ascii=False)}}]}
            ).encode("utf-8")
            return mock_resp

        with patch.object(
            ai_coach_engine,
            "load_env_llm_config",
            return_value={
                "provider": "xai",
                "api_key": "test-xai-key",
                "model_name": "grok-4.7",
                "base_url": "https://api.x.ai/v1",
            },
        ), patch("urllib.request.urlopen", side_effect=fake_urlopen_ok), patch("builtins.open", MagicMock()):
            res = ai_coach_engine.call_llm_coach_review(report)
            self.assertTrue(res.get("ok"), f"Expected ok=True when all shards succeed, got: {res}")
            self.assertEqual(res.get("model"), "grok-4.20-0309-non-reasoning")
            self.assertEqual(res["structured"].get("model"), "grok-4.20-0309-non-reasoning")
            self.assertIn("grok-4.20-0309-non-reasoning", res["structured"].get("author", ""))

    def test_4_frontend_reads_model_name_from_response_data(self):
        """前端的模型名从返回数据里读，不再写死 grok-4.7 / Grok 4.7"""
        for rel_path in ("static/app.js", "static/index.html"):
            full_path = os.path.join(REPO_ROOT, rel_path)
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            matches = re.findall(r"grok[- ]4\.7", content, flags=re.I)
            self.assertEqual(
                len(matches),
                0,
                f"Found {len(matches)} hardcoded grok-4.7 strings in {rel_path}",
            )
        with open(os.path.join(REPO_ROOT, "static", "app.js"), "r", encoding="utf-8") as f:
            app_js = f.read()
        self.assertIn("getCoachModelDisplayName", app_js)


if __name__ == "__main__":
    unittest.main()
