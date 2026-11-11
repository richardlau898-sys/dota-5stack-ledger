import glob
import json
import os
import unittest
from unittest.mock import patch, MagicMock

import ai_coach_engine
from tests.helpers import build_all_sample_reports

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestA4OutputValidationAndFactCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_report = next(
            r for r in build_all_sample_reports().values() if r.get("is_parsed")
        )

    def test_1_truncated_json_fails_validation(self):
        """喂一份截断的 JSON，断言解析/校验不通过"""
        truncated_1 = '{"title": "半截标题", "summary": "还没写完就被截断了'
        truncated_2 = '{"title": "半截对象", "players": [{"pos": 1, "hero": "主宰", "grok_score": 85}'
        self.assertIsNone(
            ai_coach_engine._parse_llm_json_robust(truncated_1),
            "Truncated JSON string must not be accepted",
        )
        self.assertIsNone(
            ai_coach_engine._parse_llm_json_robust(truncated_2),
            "Unbalanced/truncated JSON object must not be accepted",
        )

        # Also test validate_coaching_schema rejects out-of-range scores or missing required fields
        self.assertTrue(
            hasattr(ai_coach_engine, "validate_coaching_schema"),
            "ai_coach_engine must define validate_coaching_schema",
        )
        bad_score_obj = {
            "title": "标题",
            "summary": "摘要",
            "verdict": "判词",
            "team_practice": "训练",
            "stage_reviews": {
                "early_lanes": "前期",
                "mid_tempo": "中期",
                "late_and_roshan": "后期",
                "overall_verdict": "总评",
            },
            "mvp": {"slot": 0, "reason": "原因"},
            "players": [
                {
                    "slot": i,
                    "pos": i + 1,
                    "hero": f"英雄{i}",
                    "grok_score": 135 if i == 0 else 70,  # Invalid score > 100
                    "grok_share_pct": 20.0,
                    "headline": "摘要",
                    "deep_verdict": "正文",
                }
                for i in range(5)
            ],
        }
        ok, err = ai_coach_engine.validate_coaching_schema(bad_score_obj)
        self.assertFalse(ok, f"Expected schema validation to reject score=135, got ok={ok}, err={err}")

    def test_2_hallucinated_timestamps_and_numbers_stripped_and_counted(self):
        """喂一份故意写错时间点和伤害数的假模型输出，断言错误句子被删掉，核查计数正确"""
        report = json.loads(json.dumps(self.sample_report))
        report["match_id"] = 9999990401
        focus_side = "radiant" if (report.get("focus_side") or "radiant") in ("radiant", "天辉") else "dire"
        own_team = report.get("radiant_pos_1_to_5") if focus_side == "radiant" else report.get("dire_pos_1_to_5")

        p1 = own_team[0]
        real_dmg = int(p1.get("hero_damage") or 12345)
        real_nw = int(p1.get("net_worth") or 15432)
        fake_dmg = 987654
        fake_time = "89:59"

        def fake_urlopen(req, timeout=36):
            body = json.loads(req.data.decode("utf-8"))
            user_msg = body["messages"][1]["content"]
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp

            if "并发分片 Pos " not in user_msg:
                resp_obj = {
                    "title": "本局复盘总结",
                    "summary": f"1号位打出 {real_dmg} 点英雄伤害。但在 {fake_time} 发生了一次不存在的团灭。",
                    "verdict": f"1号位终局净资产达到 {real_nw} 金。另有虚构的 {fake_dmg} 点爆炸伤害。",
                    "team_practice": "保持视野沟通。",
                    "stage_reviews": {
                        "early_lanes": "前期三路正常对线。",
                        "mid_tempo": "中期围绕关键装抱团。",
                        "late_and_roshan": "后期控盾推进。",
                        "overall_verdict": "全队配合良好。",
                    },
                    "mvp": {
                        "slot": p1["player_slot"],
                        "runner_up_slot": own_team[1]["player_slot"],
                        "confidence": "高",
                        "reason": f"全场打出 {real_dmg} 点伤害。",
                        "comparison": "输出领先队友。",
                        "evidence": [f"英雄伤害 {real_dmg}", f"在 {fake_time} 打出 {fake_dmg} 伤害"],
                    },
                    "player_rankings": [
                        {
                            "slot": p["player_slot"],
                            "pos": int(p["pos"]),
                            "hero": p["hero_short_zh"],
                            "lane": "上路",
                            "grok_score": 90 - int(p["pos"]) * 3,
                            "grok_share_pct": 20.0,
                        }
                        for p in own_team
                    ],
                    "players": [],
                    "windows": [],
                }
            else:
                import re as _re
                m = _re.search(r"并发分片 Pos (\d)", user_msg)
                pos_i = int(m.group(1))
                p_orig = next(p for p in own_team if int(p["pos"]) == pos_i)
                p_real_dmg = int(p_orig.get("hero_damage") or 10000)
                resp_obj = {
                    "players": [
                        {
                            "slot": p_orig["player_slot"],
                            "pos": pos_i,
                            "hero": p_orig["hero_short_zh"],
                            "lane": "上路",
                            "grok_score": 90 - pos_i * 3,
                            "grok_share_pct": 20.0,
                            "headline": f"{pos_i}号位表现稳健",
                            "deep_verdict": f"本局累计造成 {p_real_dmg} 点英雄伤害。他在 {fake_time} 单人打出 {fake_dmg} 点虚构伤害。",
                            "early_story": "上路正常对线补刀。",
                            "mid_story": "中期参团推进。",
                            "late_story": "后期高地团战。",
                            "item_and_blink_audit": "出装符合阵容需求。",
                            "good": [f"累计英雄伤害 {p_real_dmg}"],
                            "bad": [f"在 {fake_time} 送出不存在的人头"],
                            "practice": "继续保持站位纪律。",
                        }
                    ]
                }

            mock_resp.read.return_value = json.dumps(
                {"choices": [{"message": {"content": json.dumps(resp_obj, ensure_ascii=False)}}]}
            ).encode("utf-8")
            return mock_resp

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(
                ai_coach_engine,
                "load_env_llm_config",
                return_value={
                    "provider": "xai",
                    "api_key": "test-key",
                    "model_name": "grok-4.20-0309-non-reasoning",
                    "base_url": "https://api.x.ai/v1",
                },
            ), patch.dict(ai_coach_engine.__dict__, {"REPORTS_DIR": tmpdir}), \
                 patch("urllib.request.urlopen", side_effect=fake_urlopen):
                res = ai_coach_engine.call_llm_coach_review(report)

            self.assertTrue(res.get("ok"), f"Expected ok=True, got {res}")
            structured = res["structured"]
            full_dump = json.dumps(structured, ensure_ascii=False)

            # Hallucinated timestamp and number must be removed from the output text fields
            self.assertNotIn(fake_time, structured["summary"])
            self.assertNotIn(str(fake_dmg), structured["verdict"])
            for gp in structured["players"]:
                self.assertNotIn(fake_time, gp["deep_verdict"])
                self.assertNotIn(str(fake_dmg), gp["deep_verdict"])
                self.assertNotIn(fake_time, json.dumps(gp.get("bad") or [], ensure_ascii=False))

            # Real numbers must be preserved
            self.assertIn(str(real_dmg), structured["summary"])
            self.assertIn(str(real_nw), structured["verdict"])

            # Fact check audit counts must be recorded accurately
            fc = structured.get("fact_check_audit")
            self.assertIsInstance(fc, dict, "Expected fact_check_audit dict in structured output")
            self.assertGreaterEqual(fc.get("verified_count", 0), 8)
            self.assertGreaterEqual(fc.get("removed_count", 0), 8)
            self.assertEqual(
                fc.get("checked_sentences"),
                fc.get("verified_count", 0) + fc.get("removed_count", 0),
            )

    def test_3_frontend_factcheck_panel_displays_real_audit_counts(self):
        """界面上的'事实核查'卡片展示这次核查的真实结果（通过了几条、删掉了几条）"""
        with open(os.path.join(REPO_ROOT, "static", "app.js"), encoding="utf-8") as f:
            app_js = f.read()
        self.assertIn("fact_check_audit", app_js)
        self.assertIn("verified_count", app_js)
        self.assertIn("removed_count", app_js)


if __name__ == "__main__":
    unittest.main()
