import json
import os
import unittest
from unittest.mock import patch, MagicMock

import ai_coach_engine
from tests.helpers import build_all_sample_reports

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestA2PromptRewrite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_report = next(
            r for r in build_all_sample_reports().values() if r.get("is_parsed")
        )

    def _capture_llm_requests(self, provider="xai", model_name="grok-4.20-0309-non-reasoning"):
        report = json.loads(json.dumps(self.sample_report))
        captured_requests = []

        def fake_urlopen(req, timeout=36):
            body = json.loads(req.data.decode("utf-8"))
            captured_requests.append(body)
            raise RuntimeError("Abort after capture")

        with patch.object(
            ai_coach_engine,
            "load_env_llm_config",
            return_value={
                "provider": provider,
                "api_key": "test-key",
                "model_name": model_name,
                "base_url": "https://api.x.ai/v1",
            },
        ), patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ai_coach_engine.call_llm_coach_review(report)

        return captured_requests

    def test_1_no_numeric_examples_or_mandatory_share_ranges_or_prewritten_conclusions(self):
        """删掉带具体数字的示例、删掉'头号大锅必须 27%~40%'强制要求、删掉'必须严厉批判'预先结论"""
        reqs = self._capture_llm_requests()
        self.assertTrue(len(reqs) > 0, "Expected at least one LLM request")
        all_prompt_text = "\n".join(
            m.get("content", "")
            for r in reqs
            for m in (r.get("messages") or [])
        )
        banned_phrases = [
            "27%~40%",
            "26%~35%",
            "10%~15%",
            "8%~14%",
            "25~48",
            "65~85",
            "80~92+",
            "巨浪185次",
            "13699伤",
            "43.5%",
            '"grok_score": 96',
            '"grok_share_pct": 34.0',
            "必须严厉批判",
            "假辅助真毒瘤",
            "毒瘤4号位",
        ]
        for phrase in banned_phrases:
            self.assertNotIn(
                phrase,
                all_prompt_text,
                f"Banned numeric example / prewritten conclusion found in prompt: {phrase}",
            )

    def test_2_no_steam_nicknames_or_image_urls_or_always_empty_fields_sent_to_llm(self):
        """不要把玩家的 Steam 昵称发给模型（用位置和英雄代指），删掉恒为空的字段和图片 URL"""
        reqs = self._capture_llm_requests()
        all_prompt_text = "\n".join(
            m.get("content", "")
            for r in reqs
            for m in (r.get("messages") or [])
        )
        # Collect all player nicknames in the match
        nicknames = set()
        for side_key in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
            for p in self.sample_report.get(side_key) or []:
                name = (p.get("personaname") or "").strip()
                if name and len(name) >= 2:
                    nicknames.add(name)

        for nick in nicknames:
            self.assertNotIn(
                nick,
                all_prompt_text,
                f"Player Steam nickname '{nick}' must not be sent to LLM",
            )

        # No image URLs or always-empty fields
        for bad_token in (
            "steamstatic.com",
            "http://",
            "https://",
            "roshan_and_tower_timeline",
            "phoenix_egg_audit",
            "slark_mechanism_audit",
            "economy_timeline",
        ):
            self.assertNotIn(
                bad_token,
                all_prompt_text,
                f"Redundant/empty field or URL '{bad_token}' should be removed from LLM prompt",
            )

        # Also check call_llm_pregame_coach does not send personaname
        pregame_reqs = []

        def fake_pregame_open(req, timeout=45):
            pregame_reqs.append(json.loads(req.data.decode("utf-8")))
            raise RuntimeError("Abort")

        sample_plan = {
            "own_players": [
                {"pos": i, "hero_short_zh": f"英雄{i}", "personaname": f"SecretNick_{i}"}
                for i in range(1, 6)
            ],
            "enemy_players": [{"pos": i, "hero_short_zh": f"敌英雄{i}"} for i in range(1, 6)],
        }
        with patch.object(
            ai_coach_engine,
            "load_env_llm_config",
            return_value={
                "provider": "xai",
                "api_key": "test-key",
                "model_name": "grok-4.20-0309-non-reasoning",
                "base_url": "https://api.x.ai/v1",
            },
        ), patch("urllib.request.urlopen", side_effect=fake_pregame_open):
            ai_coach_engine.call_llm_pregame_coach(sample_plan)

        pregame_text = json.dumps(pregame_reqs, ensure_ascii=False)
        self.assertNotIn("SecretNick_", pregame_text)

    def test_3_includes_patch_version_temperature_zero_and_facts_plus_rubric_structure(self):
        """加入比赛的补丁号，温度设为 0，结构改成'事实数据 + 评分标准'"""
        reqs = self._capture_llm_requests()
        for r in reqs:
            self.assertEqual(r.get("temperature"), 0, "LLM request must set temperature=0")
        sys_msg = reqs[0]["messages"][0]["content"]
        usr_msg = reqs[0]["messages"][1]["content"]
        self.assertIn("事实数据", sys_msg + usr_msg)
        self.assertIn("评分标准", sys_msg + usr_msg)
        self.assertIn('"patch"', usr_msg)

    def test_4_input_tokens_reduced_by_more_than_half(self):
        """输入 token 数比现在少一半以上（贴出前后对比）"""
        # Pre-A2 baseline on sample parsed match:
        # - Single-call prompt (sys + user): 87,024 chars
        # - 6-shard prompt (1 attempt): 163,894 chars
        reqs = self._capture_llm_requests()
        first_call_chars = sum(len(m.get("content", "")) for m in reqs[0]["messages"])
        self.assertLess(
            first_call_chars,
            87024 // 2,
            f"Expected single-call prompt chars < {87024 // 2}, got {first_call_chars}",
        )


if __name__ == "__main__":
    unittest.main()
