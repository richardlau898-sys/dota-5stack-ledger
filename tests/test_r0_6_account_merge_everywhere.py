# -*- coding: utf-8 -*-
"""
R0-6 · 账号合并（D7 已确认 86542163 与 114933560 为同一人）
验证：
1. roster.json 中未经验证手工改写的 114933560 with_games (964->849) 与 win_rate_pct (49.0->48.5) 已恢复为原始真实值；
   经 Richard D7 确认后 merge_accounts_enabled 为 true。
2. 账号合并通过统一花名册在总账 (Ledger + 双人路组合)、F1 (aggregate_full_history_stats)、
   F4 (build_personal_trends_and_goals)、F8 (postgame_webhook_notifier) 以及单场报告生成 (analyze_match_data) 全局生效；
   当 merge_accounts_enabled=False 时可随时关闭并保持独立。
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import dota_analyst
import draft_and_phase_coach
import squad_growth_metrics
from tools import postgame_webhook_notifier, sync_full_match_history

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestR06AccountMergeEverywhere(unittest.TestCase):
    def test_roster_json_restores_raw_stats_and_enables_d7_confirmed_merge(self):
        roster = json.loads((REPO_ROOT / "roster.json").read_text(encoding="utf-8"))
        self.assertIs(roster.get("merge_accounts_enabled"), True)
        players = roster.get("players") or {}
        b_main = players.get("114933560") or {}
        b_alt = players.get("86542163") or {}
        self.assertEqual(b_main.get("with_games"), 849, "114933560 的 with_games 必须恢复为原始值 849，不得手写 964")
        self.assertEqual(b_main.get("win_rate_pct"), 48.5, "114933560 的 win_rate_pct 必须恢复为原始值 48.5，不得手写 49.0")
        self.assertEqual(b_alt.get("with_games"), 115)
        self.assertEqual(b_alt.get("win_rate_pct"), 53.0)

    def test_merge_applies_to_report_f1_f4_f8_and_ledger_and_respects_toggle(self):
        roster = json.loads((REPO_ROOT / "roster.json").read_text(encoding="utf-8"))
        raw_base = json.loads((REPO_ROOT / "reports" / "raw_9043295657.json").read_text(encoding="utf-8"))

        # 构造同一人分别用 114933560 与 86542163 出战的两场真实结构样本
        raw_m1 = copy.deepcopy(raw_base)
        raw_m2 = copy.deepcopy(raw_base)
        raw_m2["match_id"] = int(raw_base["match_id"]) + 1
        raw_m2["start_time"] = int(raw_base["start_time"]) + 3600
        swapped = False
        for p in raw_m2["players"]:
            if p.get("account_id") == 114933560:
                p["account_id"] = 86542163
                p["personaname"] = "mr. brightside"
                swapped = True
        self.assertTrue(swapped)

        rep1 = dota_analyst.analyze_match_data(raw_m1, roster=roster)
        rep2 = dota_analyst.analyze_match_data(raw_m2, roster=roster)

        # 1) 单场报告生成：小号 86542163 识别为同一车队成员 Mr. Brightside 且 canonical_account_id=114933560
        all_p2 = (rep2.get("radiant_pos_1_to_5") or []) + (rep2.get("dire_pos_1_to_5") or [])
        alt_p = next((p for p in all_p2 if p.get("account_id") == 86542163), None)
        self.assertIsNotNone(alt_p)
        self.assertEqual(alt_p.get("canonical_account_id"), 114933560)
        self.assertEqual(alt_p.get("friend_tag"), "车队好友 · Mr. Brightside")

        # 关闭合并开关时保持独立
        roster_off = copy.deepcopy(roster)
        roster_off["merge_accounts_enabled"] = False
        rep2_off = dota_analyst.analyze_match_data(raw_m2, roster=roster_off)
        all_p2_off = (rep2_off.get("radiant_pos_1_to_5") or []) + (rep2_off.get("dire_pos_1_to_5") or [])
        alt_p_off = next((p for p in all_p2_off if p.get("account_id") == 86542163), None)
        self.assertEqual(alt_p_off.get("canonical_account_id"), 86542163)
        self.assertEqual(alt_p_off.get("friend_tag"), "车队好友 · mr. brightside")

        # 2) F4 个人趋势：两场合并到 114933560 (games_count == 2)，不再拆成两条趋势
        trends = squad_growth_metrics.build_personal_trends_and_goals([rep1, rep2], roster=roster)
        t_players = trends.get("players") or {}
        self.assertIn("114933560", t_players)
        self.assertNotIn("86542163", t_players)
        self.assertEqual(t_players["114933560"]["games_count"], 2)
        self.assertEqual(t_players["114933560"]["personaname"], "Mr. Brightside")

        # 3) F1 全量历史聚合：86542163 与 114933560 的对局合并入 114933560
        f1_rows = [
            {
                "account_id": 114933560,
                "match_id": 1001,
                "player_slot": 0,
                "radiant_win": True,
                "hero_id": 1,
                "duration": 2100,
                "start_time": 1760000000,
            },
            {
                "account_id": 86542163,
                "match_id": 1002,
                "player_slot": 0,
                "radiant_win": False,
                "hero_id": 2,
                "duration": 2200,
                "start_time": 1760003600,
            },
        ]
        f1_stats = sync_full_match_history.aggregate_full_history_stats(f1_rows, roster=roster)
        self.assertIn(114933560, f1_stats["players"])
        self.assertNotIn(86542163, f1_stats["players"])
        self.assertEqual(f1_stats["players"][114933560]["total_games"], 2)
        self.assertEqual(f1_stats["players"][114933560]["personaname"], "Mr. Brightside")

        # 4) 总账与双人路组合：两场合并为同一成员与同一双人组合
        with tempfile.TemporaryDirectory() as tmpdir:
            tpath = Path(tmpdir)
            (tpath / f"match_{rep1['match_id']}.json").write_text(json.dumps(rep1, ensure_ascii=False), encoding="utf-8")
            (tpath / f"match_{rep2['match_id']}.json").write_text(json.dumps(rep2, ensure_ascii=False), encoding="utf-8")
            ledger = draft_and_phase_coach.build_squad_history_ledger(tpath, roster, [])
            by_aid = {int(m["account_id"]): m for m in (ledger.get("squad_members_rank") or []) if m.get("account_id")}
            self.assertIn(114933560, by_aid)
            self.assertNotIn(86542163, by_aid)
            self.assertEqual(by_aid[114933560]["games"], 2)

            # F8: 轮询同时覆盖 114933560 和 86542163 两个 Steam 账号
            queried = []
            postgame_webhook_notifier.run_postgame_notification_cycle(
                roster=roster,
                webhook_url="https://example.invalid/hook",
                state_path=tpath / "state.json",
                reports_dir=tpath,
                fetch_recent_fn=lambda aid: (queried.append(int(aid)) or []),
                fetch_match_fn=lambda _m: {},
                request_parse_fn=lambda _m: {},
                send_webhook_fn=lambda _u, _p: True,
            )
            self.assertIn(114933560, queried)
            self.assertIn(86542163, queried)


if __name__ == "__main__":
    unittest.main()
