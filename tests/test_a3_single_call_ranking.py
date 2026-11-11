import inspect
import json
import os
import re
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import ai_coach_engine
from tests.helpers import build_all_sample_reports

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def extract_hero_lane_mentions(coaching: dict) -> dict:
    """
    Extract lane assignments ('上路', '中路', '下路') associated with each own-team hero
    across global early_lanes/summary and the player's own early_story.
    Returns {hero_name: set_of_lanes}.
    """
    players = coaching.get("players") or []
    heroes = [p.get("hero") for p in players if isinstance(p, dict) and p.get("hero")]
    hero_lanes = {h: set() for h in heroes}

    # 1. Check each player's own early_story opening laning assignment
    for p in players:
        if not isinstance(p, dict):
            continue
        hero = p.get("hero")
        if not hero:
            continue
        if p.get("lane") in ("上路", "中路", "下路"):
            hero_lanes[hero].add(p["lane"])
        es = str(p.get("early_story") or "")
        m = re.search(r"(上路|中路|下路)", es[:65])
        if m:
            hero_lanes[hero].add(m.group(1))

    # 2. Check global stage_reviews.early_lanes and summary sub-clauses mentioning the hero's lane
    sr = coaching.get("stage_reviews") or {}
    for global_txt in (sr.get("early_lanes") or "", coaching.get("summary") or ""):
        for clause in re.split(r"[。！？!?；;]", str(global_txt)):
            for sub in re.split(r"[，,]", clause):
                lanes_in_sub = re.findall(r"(上路|中路|下路)", sub)
                if len(set(lanes_in_sub)) == 1:
                    if re.search(r"(击杀|游走|游到|支援|抓死)(?:[^，。]*?)(上路|中路|下路)", sub):
                        continue
                    lane_val = lanes_in_sub[0]
                    for h in heroes:
                        if h in sub:
                            hero_lanes[h].add(lane_val)

    return hero_lanes


def _run_mocked_coach_review(report: dict, preset_scores: dict, preset_shares: dict, mvp_pos: int = 1):
    focus_side = "radiant" if (report.get("focus_side") or "radiant") in ("radiant", "天辉") else "dire"
    own_team = report.get("radiant_pos_1_to_5") if focus_side == "radiant" else report.get("dire_pos_1_to_5")
    mvp_player = next(p for p in own_team if int(p["pos"]) == mvp_pos)
    runner_up_player = next(p for p in own_team if int(p["pos"]) != mvp_pos)
    captured_prompts = []

    def fake_urlopen(req, timeout=36):
        body = json.loads(req.data.decode("utf-8"))
        user_msg = body["messages"][1]["content"]
        captured_prompts.append(user_msg)

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp

        if "并发分片 Pos " not in user_msg:
            p1_lane = (own_team[0].get("laning_10m") or {}).get("lane_zh") or "上路"
            resp_obj = {
                "title": "全局标题",
                "summary": f"{p1_lane}{own_team[0]['hero_short_zh']}对线发育。",
                "verdict": "全局判词",
                "team_practice": "全局练习",
                "stage_reviews": {
                    "early_lanes": f"{p1_lane}{own_team[0]['hero_short_zh']}补刀顺畅。",
                    "mid_tempo": "中期推进。",
                    "late_and_roshan": "后期控盾。",
                    "overall_verdict": "整体总结。",
                },
                "mvp": {
                    "slot": mvp_player["player_slot"],
                    "runner_up_slot": runner_up_player["player_slot"],
                    "confidence": "高",
                    "reason": f"{mvp_pos}号位{mvp_player['hero_short_zh']}发挥最好",
                    "comparison": "综合贡献第一",
                    "evidence": ["参战与输出领先"],
                },
                "player_rankings": [
                    {
                        "slot": p["player_slot"],
                        "pos": int(p["pos"]),
                        "hero": p["hero_short_zh"],
                        "lane": (p.get("laning_10m") or {}).get("lane_zh") or "上路",
                        "grok_score": preset_scores[int(p["pos"])],
                        "grok_share_pct": preset_shares[int(p["pos"])],
                    }
                    for p in own_team
                ],
                "players": [],
                "windows": [],
            }
        else:
            m = re.search(r"并发分片 Pos (\d)", user_msg)
            pos_i = int(m.group(1))
            p_orig = next(p for p in own_team if int(p["pos"]) == pos_i)
            # Read authoritative_lane injected by call_llm_coach_review into the shard prompt
            auth_m = re.search(r'"authoritative_lane"\s*:\s*"([^"]+)"', user_msg)
            lane_zh = auth_m.group(1) if auth_m else ((p_orig.get("laning_10m") or {}).get("lane_zh") or "上路")
            wrong_shard_lane = "下路" if lane_zh == "上路" else "上路"
            resp_obj = {
                "players": [
                    {
                        "slot": p_orig["player_slot"],
                        "pos": pos_i,
                        "hero": p_orig["hero_short_zh"],
                        "lane": wrong_shard_lane,
                        "grok_score": 50,
                        "grok_share_pct": 20.0,
                        "headline": f"{pos_i}号位摘要",
                        "deep_verdict": f"技能伤害贡献 33.3%，本局评分 {preset_scores[pos_i]} 分。",
                        "early_story": f"{lane_zh}{p_orig['hero_short_zh']}对线补刀。",
                        "mid_story": "中期参战。",
                        "late_story": "后期团战。",
                        "item_and_blink_audit": "出装合理。",
                        "good": ["亮点1"],
                        "bad": ["不足1"],
                        "practice": "改进建议",
                    }
                ]
            }

        mock_resp.read.return_value = json.dumps(
            {"choices": [{"message": {"content": json.dumps(resp_obj, ensure_ascii=False)}}]}
        ).encode("utf-8")
        return mock_resp

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
    return res, captured_prompts


class TestA3SingleCallRanking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        all_reports = build_all_sample_reports()
        cls.parsed_reports = [r for r in all_reports.values() if r.get("is_parsed")][:3]
        cls.sample_report = cls.parsed_reports[0]

    def test_1_scores_shares_mvp_in_single_call_and_no_post_hoc_score_or_regex_mutation(self):
        """
        打分、分锅比例、MVP 在同一次调用里产出（调用时看到全部 5 人数据）；
        个人分片先拿到全局结论与分路；事后不改分数、不用正则改正文。
        """
        report = json.loads(json.dumps(self.sample_report))
        report["match_id"] = 9999990301
        preset_scores = {1: 88, 2: 76, 3: 76, 4: 64, 5: 72}
        preset_shares = {1: 30.0, 2: 20.0, 3: 20.0, 4: 15.0, 5: 15.0}

        res, captured_prompts = _run_mocked_coach_review(report, preset_scores, preset_shares, mvp_pos=1)
        self.assertTrue(res.get("ok"), f"Expected ok=True, got {res}")
        structured = res["structured"]

        pos_prompts = [p for p in captured_prompts if "并发分片 Pos " in p]
        self.assertEqual(len(pos_prompts), 5)
        for pp in pos_prompts:
            self.assertIn("global_conclusion", pp)
            self.assertIn("authoritative_lane", pp)

        by_pos = {int(gp["pos"]): gp for gp in structured["players"]}
        for pos_i in range(1, 6):
            self.assertEqual(by_pos[pos_i]["grok_score"], preset_scores[pos_i])
            self.assertAlmostEqual(by_pos[pos_i]["grok_share_pct"], preset_shares[pos_i], places=1)
            self.assertIn("33.3%", by_pos[pos_i]["deep_verdict"])

    def test_2_post_hoc_reranking_deleted_from_code(self):
        """删掉 ai_coach_engine.py 和 static/app.js 的事后改分/正则改正文/错位重排逻辑"""
        src = inspect.getsource(ai_coach_engine.call_llm_coach_review)
        self.assertNotIn("pls_by_rank", src)
        self.assertNotIn("norm_shares[idx_ns] - 0.3", src)

        with open(os.path.join(REPO_ROOT, "static", "app.js"), encoding="utf-8") as f:
            app_js = f.read()
        self.assertNotIn("contribSharesPool", app_js)
        self.assertNotIn("blameSharesPool", app_js)

    def test_3_mvp_slot_is_highest_grok_score_player(self):
        """走 call_llm_coach_review 真实代码路径：产出的 JSON 里 mvp.slot 对应的人就是 grok_score 最高的人"""
        preset_scores_cases = [
            ({1: 91, 2: 78, 3: 70, 4: 66, 5: 74}, 1),
            ({1: 68, 2: 89, 3: 75, 4: 72, 5: 70}, 2),
            ({1: 65, 2: 71, 3: 74, 4: 86, 5: 79}, 4),
        ]
        preset_shares = {1: 24.0, 2: 22.0, 3: 19.0, 4: 18.0, 5: 17.0}
        for idx, (scores_map, top_pos) in enumerate(preset_scores_cases):
            rep = json.loads(json.dumps(self.parsed_reports[idx % len(self.parsed_reports)]))
            rep["match_id"] = 9999990310 + idx
            res, _ = _run_mocked_coach_review(rep, scores_map, preset_shares, mvp_pos=top_pos)
            self.assertTrue(res.get("ok"), f"Expected ok=True, got {res}")
            data = res["structured"]
            players = [p for p in (data.get("players") or []) if isinstance(p, dict) and p.get("grok_score") is not None]
            self.assertEqual(len(players), 5)
            max_score = max(float(p["grok_score"]) for p in players)
            top_slots = {p.get("slot") for p in players if float(p["grok_score"]) == max_score}
            mvp_slot = (data.get("mvp") or {}).get("slot")
            self.assertIn(mvp_slot, top_slots)

    def test_4_single_lane_description_per_hero_across_report(self):
        """走 call_llm_coach_review 真实代码路径：权威分路注入并覆盖分片错误分路，每个英雄只有唯一分路描述"""
        preset_scores = {1: 85, 2: 78, 3: 74, 4: 70, 5: 72}
        preset_shares = {1: 25.0, 2: 20.0, 3: 20.0, 4: 18.0, 5: 17.0}
        for idx, base_rep in enumerate(self.parsed_reports):
            rep = json.loads(json.dumps(base_rep))
            rep["match_id"] = 9999990320 + idx
            res, _ = _run_mocked_coach_review(rep, preset_scores, preset_shares, mvp_pos=1)
            self.assertTrue(res.get("ok"), f"Expected ok=True, got {res}")
            data = res["structured"]
            hero_lanes = extract_hero_lane_mentions(data)
            self.assertEqual(len(hero_lanes), 5)
            for hero, lanes in hero_lanes.items():
                self.assertLessEqual(
                    len(lanes),
                    1,
                    f"Hero '{hero}' has conflicting lane descriptions across coaching report: {lanes}",
                )


if __name__ == "__main__":
    unittest.main()
