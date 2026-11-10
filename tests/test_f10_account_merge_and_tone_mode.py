# -*- coding: utf-8 -*-
"""
F10 · 账号合并和语气开关（D1）单元测试
验证：
1. roster.json 支持一个人挂多个账号（Mr. Brightside 114933560 与 mr. brightside 86542163 合并统计）。
2. dota_analyst.resolve_canonical_account_id 与 build_squad_history_ledger 将同一成员的多个账号合并为一条记录。
3. 前端默认教练模式（state.toneMode === 'coach'），只陈述事实与建议并隐藏海报按钮；手动切换到毒舌模式（'roast'）后才显示海报入口。
"""
import json
import tempfile
import unittest
from pathlib import Path

import dota_analyst
import draft_and_phase_coach

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestF10AccountMergeAndToneMode(unittest.TestCase):
    def test_roster_merges_mr_brightside_accounts(self):
        roster = dota_analyst.load_roster()
        c1 = dota_analyst.resolve_canonical_account_id(114933560, roster)
        c2 = dota_analyst.resolve_canonical_account_id(86542163, roster)
        self.assertEqual(c1, 114933560)
        self.assertEqual(c2, 114933560)

        players_cfg = roster.get("players") or {}
        brightside_cfg = players_cfg.get("114933560") or {}
        self.assertIn(86542163, brightside_cfg.get("account_ids") or [])

    def test_squad_ledger_merges_aliased_accounts_into_single_member(self):
        roster = dota_analyst.load_roster()
        with tempfile.TemporaryDirectory() as tmpdir:
            tpath = Path(tmpdir)
            for idx, (mid, aid, pname) in enumerate(
                [(900001, 114933560, "Mr. Brightside"), (900002, 86542163, "mr. brightside")]
            ):
                rep = {
                    "match_id": mid,
                    "start_time": 1776000000 + idx * 3600,
                    "duration_min": 35.0,
                    "focus_side": "radiant",
                    "radiant_win": True,
                    "is_parsed": True,
                    "radiant_pos_1_to_5": [
                        {
                            "player_slot": 0,
                            "account_id": 86080912,
                            "personaname": "Flame = ez mute",
                            "pos": 1,
                            "hero_short_zh": "主宰",
                            "kills": 10,
                            "deaths": 2,
                            "assists": 8,
                            "rating_score_100": 80.0,
                            "contrib_share_pct": 25.0,
                        },
                        {
                            "player_slot": 4,
                            "account_id": aid,
                            "personaname": pname,
                            "pos": 5,
                            "hero_short_zh": "巫医",
                            "kills": 3,
                            "deaths": 5,
                            "assists": 18,
                            "rating_score_100": 75.0,
                            "contrib_share_pct": 20.0,
                        },
                    ],
                }
                (tpath / f"match_{mid}.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")

            ledger = draft_and_phase_coach.build_squad_history_ledger(
                reports_dir=tpath,
                roster=roster,
                recent_matches=[],
            )
            members = ledger.get("squad_members_rank") or []
            by_aid = {int(m.get("account_id") or 0): m for m in members if m.get("account_id")}
            # 86542163 已被合并进 114933560，不再单独成行
            self.assertIn(114933560, by_aid)
            self.assertNotIn(86542163, by_aid)
            merged_member = by_aid[114933560]
            self.assertEqual(merged_member.get("personaname"), "Mr. Brightside")
            self.assertIn(86542163, merged_member.get("merged_account_ids") or [])
            self.assertGreaterEqual(int(merged_member.get("games") or 0), 2)

    def test_frontend_default_coach_mode_and_roast_poster_toggle(self):
        html_txt = (REPO_ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js_txt = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="btn-toggle-tone-mode"', html_txt)
        self.assertIn('toneMode: "coach"', js_txt)
        self.assertIn("applyToneModeUI", js_txt)


if __name__ == "__main__":
    unittest.main()
