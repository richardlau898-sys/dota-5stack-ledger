# -*- coding: utf-8 -*-
"""
R0-5 · 删除其他编出来的数值（每一行配一个测试，用真实样本断言不再出现上述值）
1. microscope_sections/space_damage_econ.py 买活损失：不再给买过活且无金钱来源 2 的玩家写 buyback_loss=0 / 显示“买活-0”，改用 buyback_log 次数显示“买活 N 次（金额无数据）”。
2. microscope_sections/space_damage_econ.py & draft_and_phase_coach.py：彻底删除写死为 0 的“未开雾危险区阵亡”指标（unsmoked_blind_cnt / total_unsmoked_blind_feeds / unsmoked_blind_total）。
3. microscope_sections/hero_execution.py：删除凤凰蛋写死的 survived_cnt 与 shattered_cnt 字段。
4. dota_analyst.py 证据标注：删除为凑测试加的填充结论（如“英雄微操审计”“阵容与分路分析”“阶段统计”及模块键名填充）。
5. ai_coach_engine.py:2533：补丁号读不到时传给模型的 patch 为 null，不再写死 "7.39"。
6. dota_constants_zh.py:1645-1650：删除公式猜补丁名，提交真实 .cache/patch_constants.json 查表得到（如 59 -> "7.40"），查不到显示补丁编号。
"""
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_coach_engine
import dota_analyst
import dota_constants_zh
import draft_and_phase_coach
from tests.helpers import build_all_sample_reports, iter_report_strings, load_all_raw_matches

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestR05RemoveFabricatedValues(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_matches = load_all_raw_matches()
        cls.reports = build_all_sample_reports(force_rebuild=True)

    def test_1_buyback_uses_buyback_log_count_and_no_amount_data_label(self):
        """第 1 行：买过活且无 gold_reasons['2'] 的玩家显示‘买活 N 次（金额无数据）’，不再出现‘买活 -0’/‘买活-0’"""
        buyback_players_checked = 0
        for mid, report in self.reports.items():
            raw = self.raw_matches[mid]
            if not raw.get("version"):
                continue
            raw_by_hero_id = {int(rp.get("hero_id") or 0): rp for rp in (raw.get("players") or [])}
            econ_sec = (report.get("deep_forensics") or {}).get("economy_and_pings_by_side") or {}
            for side, side_key in (("radiant", "radiant_pos_1_to_5"), ("dire", "dire_pos_1_to_5")):
                hid_by_zh = {p.get("hero_short_zh"): int(p.get("hero_id") or 0) for p in (report.get(side_key) or [])}
                for row in (econ_sec.get(side) or {}).get("econ_rows") or []:
                    hid = hid_by_zh.get(row.get("hero_short_zh"), 0)
                    rp = raw_by_hero_id.get(hid) or {}
                    bb_cnt = len(rp.get("buyback_log") or [])
                    has_gr_2 = (rp.get("gold_reasons") or {}).get("2") is not None
                    self.assertEqual(row.get("buyback_count"), bb_cnt)
                    if bb_cnt > 0 and not has_gr_2:
                        buyback_players_checked += 1
                        self.assertIsNone(row.get("buyback_loss"))
                        self.assertEqual(row.get("buyback_text"), f"买活 {bb_cnt} 次（金额无数据）")
            for _path, s in iter_report_strings(report):
                self.assertNotIn("买活 -0", s)
                self.assertNotIn("买活-0", s)

        self.assertGreaterEqual(buyback_players_checked, 60, "真实样本应覆盖至少 60 名买过活的玩家")
        app_js = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("买活-${fmtNum(r.buyback_loss || 0)}", app_js)
        self.assertIn("金额无数据", app_js)

    def test_2_unsmoked_blind_metric_completely_removed(self):
        """第 2 行：删除‘未开雾危险区阵亡’指标，报告与总账中均不再出现"""
        for mid, report in self.reports.items():
            ms_by_side = (report.get("deep_forensics") or {}).get("map_space_by_side") or {}
            for side in ("radiant", "dire"):
                ms = ms_by_side.get(side) or {}
                self.assertNotIn("total_unsmoked_blind_feeds", ms, f"match {mid} 仍含 total_unsmoked_blind_feeds")
                for r in ms.get("player_space_rows") or []:
                    self.assertNotIn("unsmoked_blind_cnt", r, f"match {mid} 仍含 unsmoked_blind_cnt")
            for _path, s in iter_report_strings(report):
                self.assertNotIn("未开雾危险区阵亡", s)

        roster = dota_analyst.load_roster()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            for mid, rep in self.reports.items():
                (tmp_path / f"match_{mid}.json").write_text(
                    json.dumps(rep, ensure_ascii=False), encoding="utf-8"
                )
            ledger = draft_and_phase_coach.build_squad_history_ledger(tmp_path, roster, [])
        self.assertGreater(len(ledger.get("squad_members_rank") or []), 0)
        ledger_dump = json.dumps(ledger, ensure_ascii=False)
        self.assertNotIn("未开雾危险区阵亡", ledger_dump)
        self.assertNotIn("unsmoked_blind", ledger_dump)

    def test_3_phoenix_egg_fabricated_survived_and_shattered_removed(self):
        """第 3 行：凤凰蛋删除写死的 survived_cnt 与 shattered_cnt 字段"""
        phoenix_found = 0
        for mid, report in self.reports.items():
            for side_key in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
                for p in report.get(side_key) or []:
                    if int(p.get("hero_id") or 0) == 110 and p.get("phoenix_egg_audit"):
                        phoenix_found += 1
                        egg = p["phoenix_egg_audit"]
                        self.assertNotIn("survived_cnt", egg, f"match {mid} 凤凰仍含写死的 survived_cnt")
                        self.assertNotIn("shattered_cnt", egg, f"match {mid} 凤凰仍含写死的 shattered_cnt")
                        self.assertNotIn("shatter_rate_pct", egg)
                        self.assertNotIn("survived_waves", egg)
                        self.assertNotIn("shattered_waves", egg)
        self.assertGreater(phoenix_found, 0, "真实样本中必须覆盖至少 1 场已解析凤凰对局")

    def test_4_evidence_annotation_filler_conclusions_removed(self):
        """第 4 行：dota_analyst.annotate_report_evidence 删除‘英雄微操审计’等凑数填充结论"""
        filler_texts = {"英雄微操审计", "阵容与分路分析", "阶段统计", "比赛结算", "全场走势"}
        for mid, report in self.reports.items():
            df = report.get("deep_forensics") or {}
            mod_keys = {k for k in df.keys() if k.endswith("_by_side")}
            for _path, s in iter_report_strings(report):
                self.assertNotIn(s, filler_texts, f"match {mid} 出现凑数填充结论: {s!r} at {_path}")
                self.assertNotIn(s, mod_keys, f"match {mid} 把模块键名 {s!r} 当成结论填充 at {_path}")

    def test_5_missing_patch_sends_null_instead_of_hardcoded_7_39(self):
        """第 5 行：补丁号读不到时 LLM 请求里的 patch 为 null，不再写死 '7.39'"""
        sample_report = dict(next(iter(self.reports.values())))
        sample_report["patch"] = None
        sample_report["patch_str"] = None

        captured_bodies = []

        def fake_urlopen(req, timeout=45):
            captured_bodies.append(json.loads(req.data.decode("utf-8")))
            raise RuntimeError("stop after capturing prompt")

        with patch.object(
            ai_coach_engine,
            "load_env_llm_config",
            return_value={
                "provider": "xai",
                "api_key": "dummy-key",
                "model_name": "grok-4.20-0309-non-reasoning",
                "base_url": "https://api.x.ai/v1",
            },
        ), patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ai_coach_engine.call_llm_coach_review(sample_report)

        self.assertTrue(captured_bodies, "未能捕获 LLM 请求体")
        usr_msg = captured_bodies[0]["messages"][1]["content"]
        self.assertIn('"patch":null', usr_msg.replace(" ", ""))
        self.assertNotIn("7.39", usr_msg)

    def test_6_patch_name_from_committed_opendota_constants_without_formula(self):
        """第 6 行：提交 OpenDota patch 常量表，查表解析补丁名，查不到返回补丁编号，无猜测公式"""
        patch_cache = REPO_ROOT / ".cache" / "patch_constants.json"
        self.assertTrue(patch_cache.exists(), "缺少提交的 .cache/patch_constants.json")
        pdata = json.loads(patch_cache.read_text(encoding="utf-8"))
        self.assertIsInstance(pdata, list)
        self.assertGreaterEqual(len(pdata), 55)

        src = inspect.getsource(dota_constants_zh.resolve_patch_name)
        self.assertNotIn("pid - 19", src)
        self.assertNotIn("pid - 20", src)
        self.assertNotIn('"7.39"', src)

        # 真实查表：OpenDota 中 id=58 是 7.39，id=59 是 7.40（旧公式把 59 猜错成 7.39！）
        self.assertEqual(dota_constants_zh.resolve_patch_name(58), "7.39")
        self.assertEqual(dota_constants_zh.resolve_patch_name(59), "7.40")
        # 查不到的补丁编号原样显示补丁编号
        self.assertEqual(dota_constants_zh.resolve_patch_name(9999), "9999")
        self.assertIsNone(dota_constants_zh.resolve_patch_name(None))

        # 用真实样本验证：样本中 patch=59 的比赛报告现在如实解析为 7.40 而非猜出来的 7.39
        patch59_checked = 0
        for mid, raw in self.raw_matches.items():
            if raw.get("patch") == 59:
                patch59_checked += 1
                rep = dota_analyst.analyze_match_data(raw, dota_analyst.load_roster())
                self.assertEqual(rep["patch_str"], "7.40", f"match {mid} patch=59 应查表得到 7.40")
        self.assertGreater(patch59_checked, 0, "真实样本应包含 patch=59 的比赛")


if __name__ == "__main__":
    unittest.main()
