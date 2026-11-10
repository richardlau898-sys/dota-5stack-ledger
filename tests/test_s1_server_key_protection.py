import io
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

import ai_coach_engine


class _FakeHttpResponse(io.BytesIO):
    def __init__(self, payload: dict):
        super().__init__(json.dumps(payload).encode("utf-8"))
        self.code = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class TestS1ServerKeyProtection(unittest.TestCase):
    """S1 · 服务器密钥不得发往客户端指定的地址 & Gemini key 改用请求头"""

    def setUp(self):
        self.mock_env_cfg = {
            "provider": "xai",
            "model_name": "grok-4.7",
            "api_key": "server-secret-xai-key",
            "base_url": "https://api.x.ai/v1",
            "gemini_api_key": "server-secret-gemini-key",
            "xai_api_key": "server-secret-xai-key",
        }

    def test_coach_review_ignores_client_base_url_and_key(self):
        captured_requests = []

        def fake_urlopen(req, timeout=None):
            captured_requests.append(req)
            return _FakeHttpResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "title": "测试标题",
                                        "summary": "测试总结",
                                        "verdict": "测试判词",
                                        "team_practice": "测试练习",
                                        "stage_reviews": {},
                                        "mvp": {},
                                        "windows": [],
                                        "players": [],
                                    }
                                )
                            }
                        }
                    ]
                }
            )

        sample_report = {
            "match_id": None,
            "radiant_win": False,
            "focus_side": "radiant",
            "radiant_pos_1_to_5": [{"pos": 1, "player_slot": 0, "hero_short_zh": "幽鬼"}],
            "dire_pos_1_to_5": [{"pos": 1, "player_slot": 128, "hero_short_zh": "瘟疫法师"}],
        }

        with patch.object(ai_coach_engine, "load_env_llm_config", return_value=dict(self.mock_env_cfg)):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ai_coach_engine.call_llm_coach_review(
                    report=sample_report,
                    api_key=None,
                    provider="openai",
                    base_url="https://evil.example/v1",
                )

        self.assertGreater(len(captured_requests), 0, "Expected at least one outbound LLM request")
        for req in captured_requests:
            parsed = urlparse(req.full_url)
            self.assertEqual(
                parsed.hostname,
                "api.x.ai",
                f"Server secret key was sent to untrusted host: {parsed.hostname} ({req.full_url})",
            )

    def test_pregame_coach_ignores_client_base_url_and_key(self):
        captured_requests = []

        def fake_urlopen(req, timeout=None):
            captured_requests.append(req)
            return _FakeHttpResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "headline": "测试",
                                        "win_condition": "测试",
                                        "lose_condition": "测试",
                                        "combo_calls": [],
                                        "early_game": "测试",
                                        "mid_game": "测试",
                                        "late_game": "测试",
                                        "role_orders": [],
                                    }
                                )
                            }
                        }
                    ]
                }
            )

        sample_plan = {
            "own_players": [{"pos": 1, "hero_short_zh": "主宰", "personaname": "Player1"}],
            "enemy_players": [{"pos": 1, "hero_short_zh": "幻影刺客"}],
        }

        with patch.object(ai_coach_engine, "load_env_llm_config", return_value=dict(self.mock_env_cfg)):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ai_coach_engine.call_llm_pregame_coach(
                    plan=sample_plan,
                    api_key=None,
                    provider="openai",
                    base_url="https://evil.example/v1",
                )

        self.assertEqual(len(captured_requests), 1)
        parsed = urlparse(captured_requests[0].full_url)
        self.assertEqual(
            parsed.hostname,
            "api.x.ai",
            f"Server secret key was sent to untrusted host: {parsed.hostname} ({captured_requests[0].full_url})",
        )

    def test_gemini_requests_use_header_instead_of_url_query_key(self):
        captured_requests = []

        def fake_urlopen(req, timeout=None):
            captured_requests.append(req)
            return _FakeHttpResponse(
                {
                    "output_text": json.dumps({"title": "ok", "players": []}),
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"inlineData": {"mimeType": "image/png", "data": "iVBORw0KGgo="}}
                                ]
                            }
                        }
                    ],
                }
            )

        gemini_cfg = dict(self.mock_env_cfg, provider="gemini", model_name="gemini-3.8-flash", api_key="server-secret-gemini-key")
        sample_report = {"match_id": None, "radiant_win": True, "focus_side": "radiant"}

        with patch.object(ai_coach_engine, "load_env_llm_config", return_value=gemini_cfg):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                ai_coach_engine.call_llm_coach_review(report=sample_report)
                ai_coach_engine._call_gemini_nano_banana_api("test prompt", "server-secret-gemini-key")

        self.assertGreaterEqual(len(captured_requests), 2)
        for req in captured_requests:
            self.assertNotIn("key=", req.full_url, f"Gemini API key leaked in URL query string: {req.full_url}")
            headers_lower = {k.lower(): v for k, v in req.header_items()}
            self.assertEqual(headers_lower.get("x-goog-api-key"), "server-secret-gemini-key")


if __name__ == "__main__":
    unittest.main()
