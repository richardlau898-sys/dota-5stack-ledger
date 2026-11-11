import json
import os
import random
import re
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import ai_coach_engine
from tests.helpers import build_all_sample_reports

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _extract_true_event_seconds(report: dict) -> set:
    """Independent extraction of actual timeline event seconds from a parsed report."""
    ev_secs = set()

    def _add_sec(val):
        if isinstance(val, (int, float)) and not isinstance(val, bool) and 0 <= int(val) <= 10800:
            ev_secs.add(int(val))

    def _add_ts_str(s):
        for m in re.finditer(r"(?<!\d)(\d{1,3}):(\d{2})(?!\d)", str(s or "")):
            mm, ss = int(m.group(1)), int(m.group(2))
            if 0 <= mm <= 180 and 0 <= ss < 60:
                ev_secs.add(mm * 60 + ss)

    for pd in (report.get("phases_data") or []):
        if not isinstance(pd, dict):
            continue
        for ev in (pd.get("events") or []):
            if isinstance(ev, dict):
                _add_sec(ev.get("time_sec") if ev.get("time_sec") is not None else ev.get("time"))
                _add_ts_str(ev.get("time_str"))
            else:
                _add_ts_str(ev)
        for pl in (pd.get("players") or []):
            if not isinstance(pl, dict):
                continue
            for ke in (pl.get("kills_events") or []):
                _add_sec(ke.get("time_sec") if ke.get("time_sec") is not None else ke.get("time"))
                _add_ts_str(ke.get("time_str"))
            for de in (pl.get("deaths_events") or []):
                _add_sec(de.get("time_sec") if de.get("time_sec") is not None else de.get("time"))
                _add_ts_str(de.get("time_str"))
            for it in (pl.get("items_bought") or []):
                _add_sec(it.get("time_sec") if it.get("time_sec") is not None else it.get("time"))
                _add_ts_str(it.get("time_str"))

    for side_k in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
        for p in (report.get(side_k) or []):
            if not isinstance(p, dict):
                continue
            for kt in (p.get("key_item_timings") or []):
                _add_ts_str(kt)
            for ktr in (p.get("key_item_timings_rich") or []):
                if isinstance(ktr, dict):
                    _add_sec(ktr.get("time_sec") if ktr.get("time_sec") is not None else ktr.get("time"))
                    _add_ts_str(ktr.get("time_str"))

    for tf in (report.get("key_teamfights") or []):
        if isinstance(tf, dict):
            _add_sec(tf.get("start_sec"))
            _add_sec(tf.get("end_sec"))
            _add_ts_str(tf.get("start_str"))
            _add_ts_str(tf.get("end_str"))
            _add_ts_str(tf.get("time_range"))

    df = report.get("deep_forensics") or {}
    for tf in (df.get("teamfight_forensics") or []):
        if isinstance(tf, dict):
            _add_sec(tf.get("start_sec"))
            _add_sec(tf.get("end_sec"))
            _add_ts_str(tf.get("time_range"))

    for side_ms in (df.get("map_space_by_side") or {}).values():
        if isinstance(side_ms, dict):
            for sev in (side_ms.get("solo_pickoff_events") or []):
                if isinstance(sev, dict):
                    _add_sec(sev.get("time_sec") if sev.get("time_sec") is not None else sev.get("time"))
                    _add_ts_str(sev.get("time_str"))

    for side_mo in (df.get("macro_objectives_by_side") or {}).values():
        if isinstance(side_mo, dict):
            for rev in (side_mo.get("roshan_events") or []):
                if isinstance(rev, dict):
                    _add_sec(rev.get("time_sec") if rev.get("time_sec") is not None else rev.get("time"))
                    _add_ts_str(rev.get("time_str"))
                else:
                    _add_ts_str(rev)

    for om in (report.get("objective_markers") or []):
        if isinstance(om, dict):
            _add_sec(om.get("time_sec") if om.get("time_sec") is not None else om.get("time"))
            _add_ts_str(om.get("time_str"))

    for rt in (report.get("roshan_and_tower_timeline") or []):
        if isinstance(rt, dict):
            _add_sec(rt.get("time_sec") if rt.get("time_sec") is not None else rt.get("time"))
            _add_ts_str(rt.get("time_str"))

    for tm in (report.get("top3_replay_moments") or []):
        if isinstance(tm, dict):
            _add_sec(tm.get("time_sec") if tm.get("time_sec") is not None else tm.get("time"))
            _add_ts_str(tm.get("time_str"))

    return ev_secs


class TestR27CoachingRankAndFactcheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        all_reps = build_all_sample_reports()
        cls.parsed_reports = [r for r in all_reps.values() if r.get("is_parsed")]
        cls.sample_report = cls.parsed_reports[1]

    def test_1_200_random_fabricated_timestamps_within_duration_at_least_95pct_deleted(self):
        """
        测试用 200 个比赛时长范围内随机编造的时间点，断言至少 95% 被删除；
        同时断言真实事件时间点（含 ±5 秒内误差）被保留。
        """
        report = json.loads(json.dumps(self.sample_report))
        dur_m, dur_s = map(int, report["duration_str"].split(":"))
        dur_sec = dur_m * 60 + dur_s

        true_ev_secs = _extract_true_event_seconds(report)
        self.assertGreater(len(true_ev_secs), 20)
        allowed_band = {t + d for t in true_ev_secs for d in range(-5, 6) if 0 <= t + d <= dur_sec}
        fabricated_pool = [t for t in range(0, dur_sec + 1) if t not in allowed_band]
        self.assertGreaterEqual(len(fabricated_pool), 200)

        rng = random.Random(20261111)
        fab_200 = rng.sample(fabricated_pool, 200)
        fab_strs = [f"{t // 60:02d}:{t % 60:02d}" for t in fab_200]

        real_ev = sorted(t for t in true_ev_secs if 60 <= t <= dur_sec - 10)[0]
        real_plus_4 = real_ev + 4
        real_str = f"{real_ev // 60:02d}:{real_ev % 60:02d}"
        real_tol_str = f"{real_plus_4 // 60:02d}:{real_plus_4 % 60:02d}"

        structured = {
            "title": "本局复盘总结",
            "summary": f"本方在 {real_str} 发生真实节奏节点。又在 {real_tol_str} 完成联动。",
            "verdict": "整体职责复盘。",
            "team_practice": "保持沟通。",
            "stage_reviews": {
                "early_lanes": "前期正常对线。",
                "mid_tempo": "中期抱团推进。",
                "late_and_roshan": "后期控盾。",
                "overall_verdict": "全局总结。",
            },
            "mvp": {"slot": 0, "reason": "发挥稳定"},
            "players": [
                {
                    "slot": i,
                    "pos": i + 1,
                    "hero": f"英雄{i + 1}",
                    "grok_score": 80 - i,
                    "grok_share_pct": 20.0,
                    "headline": f"{i + 1}号位摘要",
                    "deep_verdict": "个人复盘稳定。",
                    "bad": [f"虚构在 {ts} 出现失误" for ts in fab_strs[i * 40 : (i + 1) * 40]],
                }
                for i in range(5)
            ],
        }

        audit = ai_coach_engine.fact_check_coaching_output(structured, report)
        remaining_bad = []
        for gp in structured["players"]:
            remaining_bad.extend(gp.get("bad") or [])

        deleted_count = 200 - len(remaining_bad)
        self.assertGreaterEqual(
            deleted_count,
            190,
            f"Expected >= 95% (190/200) of fabricated in-match timestamps to be deleted, but only {deleted_count}/200 were deleted!",
        )
        self.assertIn(real_str, structured["summary"])
        self.assertIn(real_tol_str, structured["summary"], "Expected ±5s tolerance on real event timestamp")
        self.assertGreaterEqual(audit.get("removed_count", 0), 190)

    def test_2_mvp_slot_and_reason_mismatch_rejected_and_retried(self):
        """
        MVP 编号和理由不一致（或与最高分不一致）时整条判词判为无效并重试，绝不强行改 mvp.slot 留着错误理由。
        """
        report = json.loads(json.dumps(self.sample_report))
        report["match_id"] = 9999992701
        focus_side = "radiant" if (report.get("focus_side") or "radiant") in ("radiant", "天辉") else "dire"
        own_team = report.get("radiant_pos_1_to_5") if focus_side == "radiant" else report.get("dire_pos_1_to_5")
        p1 = next(p for p in own_team if int(p["pos"]) == 1)
        p2 = next(p for p in own_team if int(p["pos"]) == 2)

        global_calls = {"count": 0}

        def fake_urlopen_retry_succeeds(req, timeout=36):
            body = json.loads(req.data.decode("utf-8"))
            user_msg = body["messages"][1]["content"]
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp

            if "并发分片 Pos " not in user_msg:
                global_calls["count"] += 1
                if global_calls["count"] == 1:
                    # Attempt 1: mvp.slot points to p1 (score 92), while mvp.reason praises p2's hero!
                    mvp_payload = {
                        "slot": p1["player_slot"],
                        "runner_up_slot": p2["player_slot"],
                        "confidence": "高",
                        "reason": f"2号位{p2['hero_short_zh']}全场带节奏表现最佳",
                        "comparison": "输出领先",
                        "evidence": ["参战第一"],
                    }
                else:
                    # Attempt 2: consistent mvp.slot and mvp.reason
                    mvp_payload = {
                        "slot": p1["player_slot"],
                        "runner_up_slot": p2["player_slot"],
                        "confidence": "高",
                        "reason": f"1号位{p1['hero_short_zh']}全场经济转化与输出最高",
                        "comparison": "输出领先",
                        "evidence": ["参战第一"],
                    }
                resp_obj = {
                    "title": "全局标题",
                    "summary": "全局摘要。",
                    "verdict": "全局判词。",
                    "team_practice": "全局建议。",
                    "stage_reviews": {
                        "early_lanes": "前期对线。",
                        "mid_tempo": "中期节奏。",
                        "late_and_roshan": "后期控盾。",
                        "overall_verdict": "整体总结。",
                    },
                    "mvp": mvp_payload,
                    "player_rankings": [
                        {
                            "slot": p["player_slot"],
                            "pos": int(p["pos"]),
                            "hero": p["hero_short_zh"],
                            "lane": "上路",
                            "grok_score": 92 if int(p["pos"]) == 1 else 75,
                            "grok_share_pct": 20.0,
                        }
                        for p in own_team
                    ],
                    "windows": [],
                }
            else:
                m = re.search(r"并发分片 Pos (\d)", user_msg)
                pos_i = int(m.group(1))
                p_orig = next(p for p in own_team if int(p["pos"]) == pos_i)
                resp_obj = {
                    "players": [
                        {
                            "slot": p_orig["player_slot"],
                            "pos": pos_i,
                            "hero": p_orig["hero_short_zh"],
                            "grok_score": 92 if pos_i == 1 else 75,
                            "grok_share_pct": 20.0,
                            "headline": f"{pos_i}号位表现",
                            "deep_verdict": "综合复盘内容。",
                            "good": ["亮点"],
                            "bad": ["不足"],
                            "practice": "建议",
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
            ), patch.dict(ai_coach_engine.__dict__, {"REPORTS_DIR": tmpdir}), patch(
                "urllib.request.urlopen", side_effect=fake_urlopen_retry_succeeds
            ):
                res = ai_coach_engine.call_llm_coach_review(report)

        self.assertEqual(global_calls["count"], 2, "Expected global call to retry when mvp.slot and mvp.reason disagreed")
        self.assertTrue(res.get("ok"), f"Expected retry to succeed, got {res}")
        self.assertEqual(res["structured"]["mvp"]["slot"], p1["player_slot"])
        self.assertIn(p1["hero_short_zh"], res["structured"]["mvp"]["reason"])

        # Subcase B: mvp.slot is not highest grok_score on BOTH attempts -> must fail, NEVER silently overwrite mvp.slot!
        def fake_urlopen_always_bad_mvp_score(req, timeout=36):
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            resp_obj = {
                "title": "全局标题",
                "summary": "全局摘要。",
                "verdict": "全局判词。",
                "team_practice": "全局建议。",
                "stage_reviews": {
                    "early_lanes": "前期对线。",
                    "mid_tempo": "中期节奏。",
                    "late_and_roshan": "后期控盾。",
                    "overall_verdict": "整体总结。",
                },
                "mvp": {
                    "slot": p2["player_slot"],
                    "reason": f"2号位{p2['hero_short_zh']}拿MVP",
                },
                "player_rankings": [
                    {
                        "slot": p["player_slot"],
                        "pos": int(p["pos"]),
                        "hero": p["hero_short_zh"],
                        "lane": "上路",
                        "grok_score": 95 if int(p["pos"]) == 1 else 70,
                        "grok_share_pct": 20.0,
                    }
                    for p in own_team
                ],
                "windows": [],
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
            ), patch.dict(ai_coach_engine.__dict__, {"REPORTS_DIR": tmpdir}), patch(
                "urllib.request.urlopen", side_effect=fake_urlopen_always_bad_mvp_score
            ):
                res_bad = ai_coach_engine.call_llm_coach_review(report)
        self.assertFalse(res_bad.get("ok"), "Expected failure when mvp.slot disagrees with top grok_score across retries")

    def test_3_global_ranking_fewer_than_5_entries_fails(self):
        """全局排名不足 5 条时必须算失败，不得悄悄跳过退回分片分数。"""
        incomplete_global = {
            "title": "标题",
            "summary": "摘要",
            "verdict": "判词",
            "team_practice": "建议",
            "stage_reviews": {
                "early_lanes": "前期",
                "mid_tempo": "中期",
                "late_and_roshan": "后期",
                "overall_verdict": "总评",
            },
            "mvp": {"slot": 0, "reason": "原因"},
            "player_rankings": [
                {"slot": 0, "pos": 1, "hero": "主宰", "grok_score": 88, "grok_share_pct": 35.0},
                {"slot": 1, "pos": 2, "hero": "帕克", "grok_score": 76, "grok_share_pct": 25.0},
                {"slot": 2, "pos": 3, "hero": "斧王", "grok_score": 72, "grok_share_pct": 20.0},
            ],
        }
        ok, err = ai_coach_engine.validate_coaching_schema(incomplete_global, partial_mode="global")
        self.assertFalse(ok, f"Expected partial_mode='global' with only 3 rankings to fail, got ok={ok}, err={err}")

        empty_global = dict(incomplete_global, player_rankings=[])
        ok2, err2 = ai_coach_engine.validate_coaching_schema(empty_global, partial_mode="global")
        self.assertFalse(ok2, f"Expected partial_mode='global' with 0 rankings to fail, got ok={ok2}, err={err2}")

    def test_4_frontend_uses_backend_share_pct_directly_without_renormalizing(self):
        """前端直接用后端的占比，不重新归一化，也没有 ?? 20 兜底。"""
        report = json.loads(json.dumps(self.sample_report))
        focus_side = "radiant" if (report.get("focus_side") or "radiant") in ("radiant", "天辉") else "dire"
        own_list = report["radiant_pos_1_to_5"] if focus_side == "radiant" else report["dire_pos_1_to_5"]
        expected_contrib = [31.4, 22.0, 18.5, 14.1, None]
        expected_blame = [38.2, 24.5, 15.0, 12.3, None]
        for idx, p in enumerate(own_list[:5]):
            p["contrib_share_pct"] = expected_contrib[idx]
            p["blame_share_pct"] = expected_blame[idx]
        report["grok_coaching"] = None

        node_script = r"""
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync("static/app.js", "utf8");
const rep = JSON.parse(fs.readFileSync(process.env.REP_PATH, "utf8"));
const elStub = () => ({
  style: {}, classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
  addEventListener(){}, removeEventListener(){}, setAttribute(){}, getAttribute(){ return null; },
  querySelector(){ return null; }, querySelectorAll(){ return []; }, innerHTML: "", textContent: ""
});
const ctx = {
  window: { location: { search: "", pathname: "/", origin: "http://localhost" }, addEventListener(){}, matchMedia(){ return { matches: false, addEventListener(){} }; } },
  document: { getElementById(){ return elStub(); }, querySelector(){ return null; }, querySelectorAll(){ return []; }, createElement(){ return elStub(); }, addEventListener(){}, body: elStub(), documentElement: elStub() },
  localStorage: { getItem(){ return null; }, setItem(){}, removeItem(){} },
  sessionStorage: { getItem(){ return null; }, setItem(){} },
  navigator: { clipboard: {} },
  URLSearchParams, URL, console, Math, Number, String, Boolean, Array, Object, Map, Set, Date, JSON, RegExp, parseInt, parseFloat, isNaN, isFinite, encodeURIComponent, decodeURIComponent,
  fetch: async () => ({ ok: true, json: async () => ({}) }),
  setTimeout: () => 0, clearTimeout(){}, setInterval: () => 0, clearInterval(){}, requestAnimationFrame: () => 0
};
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(code, ctx);
const rk = ctx.getCanonicalSideRanking(rep, process.env.SIDE);
const out = {
  contrib: Array.from(rk.contribMap.entries()),
  blame: Array.from(rk.blameMap.entries()),
};
process.stdout.write(JSON.stringify(out));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
            json.dump(report, tf, ensure_ascii=False)
            rep_path = tf.name
        try:
            proc = subprocess.run(
                ["node", "-e", node_script],
                cwd=REPO_ROOT,
                env={**os.environ, "REP_PATH": rep_path, "SIDE": focus_side},
                capture_output=True,
                text=True,
                check=True,
            )
            parsed = json.loads(proc.stdout)
            contrib_by_slot = dict(parsed["contrib"])
            blame_by_slot = dict(parsed["blame"])
            for idx, p in enumerate(own_list[:5]):
                slot = int(p["player_slot"])
                self.assertEqual(contrib_by_slot[slot], expected_contrib[idx])
                self.assertEqual(blame_by_slot[slot], expected_blame[idx])
        finally:
            if os.path.exists(rep_path):
                os.remove(rep_path)


if __name__ == "__main__":
    unittest.main()
