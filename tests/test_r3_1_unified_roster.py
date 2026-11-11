# -*- coding: utf-8 -*-
"""
R3-1 · 花名册只有一种读法
验证：
1. dota_analyst.iter_roster_accounts(roster) 存在，返回每个人和他的全部账号（含合并）；
   用仓库真实 roster.json 验证人数（未合并时等于 len(players)，开启合并时等于合并后人数且覆盖全部账号）。
2. *.py 与 tools/*.py 中不再出现 '"friends"' 或 '"teammates"'。
3. F4 (build_personal_trends_and_goals)、F8 (run_postgame_notify_once)、F1 (sync_full_match_history)、
   server.match_has_roster_player 全部通过统一花名册读取全队成员，而不仅限于主账号。
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import dota_analyst
import server
import squad_growth_metrics
from tools import postgame_webhook_notifier, sync_full_match_history

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestR31UnifiedRoster(unittest.TestCase):
    def test_iter_roster_accounts_matches_real_roster_json(self):
        self.assertTrue(
            hasattr(dota_analyst, "iter_roster_accounts"),
            "dota_analyst.iter_roster_accounts 必须存在",
        )
        roster = json.loads((REPO_ROOT / "roster.json").read_text(encoding="utf-8"))
        players_cfg = roster.get("players") or {}
        self.assertGreater(len(players_cfg), 1)

        # 未开启账号合并时：返回的人数严格等于 roster["players"] 的人数
        unmerged_roster = copy.deepcopy(roster)
        unmerged_roster["merge_accounts_enabled"] = False
        unmerged_entries = list(dota_analyst.iter_roster_accounts(unmerged_roster))
        self.assertEqual(len(unmerged_entries), len(players_cfg))

        # 真实 roster.json（含合并配置）时：返回每个独立成员及其全部账号，覆盖全部 players 账号且不重复
        merged_entries = list(dota_analyst.iter_roster_accounts(roster))
        expected_people_count = (
            sum(
                1
                for k, v in players_cfg.items()
                if dota_analyst.resolve_canonical_account_id(k, roster) == int(k)
            )
            if roster.get("merge_accounts_enabled") is not False
            else len(players_cfg)
        )
        self.assertEqual(len(merged_entries), expected_people_count)

        all_covered_aids = [aid for m in merged_entries for aid in m["account_ids"]]
        self.assertEqual(len(set(all_covered_aids)), len(players_cfg))
        by_canon = {int(m["canonical_id"]): m for m in merged_entries}
        if roster.get("merge_accounts_enabled") is not False:
            self.assertIn(114933560, by_canon)
            self.assertIn(86542163, by_canon[114933560]["account_ids"])
            self.assertNotIn(86542163, by_canon)

    def test_no_friends_or_teammates_keys_in_python_sources(self):
        py_files = sorted(list(REPO_ROOT.glob("*.py")) + list((REPO_ROOT / "tools").glob("*.py")))
        offenders = []
        for pf in py_files:
            txt = pf.read_text(encoding="utf-8")
            for lineno, line in enumerate(txt.splitlines(), start=1):
                if '"friends"' in line or '"teammates"' in line:
                    offenders.append(f"{pf.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
        self.assertEqual(offenders, [], f"仍存在残留的 friends/teammates 花名册字段读取:\n" + "\n".join(offenders))

    def test_f4_f8_and_f1_cover_all_roster_members_not_just_main(self):
        roster = json.loads((REPO_ROOT / "roster.json").read_text(encoding="utf-8"))
        raw_sample = json.loads((REPO_ROOT / "reports" / "raw_9043295657.json").read_text(encoding="utf-8"))
        rep = dota_analyst.analyze_match_data(raw_sample, roster=roster)

        # F4: 传入真实 roster.json 与非空报告列表，不应只有主账号 1 个人
        trends = squad_growth_metrics.build_personal_trends_and_goals([rep], roster=roster)
        self.assertGreater(
            len(trends.get("players") or {}),
            1,
            "F4 个人趋势传入真实 roster.json 时必须覆盖本局所有在册队友，不能只有主账号 1 人",
        )

        # F8: 赛后轮询使用真实 roster.json 时，应遍历花名册全部账号而非只查主账号
        queried_aids = []
        with tempfile.TemporaryDirectory() as tmpdir:
            tpath = Path(tmpdir)
            postgame_webhook_notifier.run_postgame_notification_cycle(
                roster=roster,
                webhook_url="https://example.invalid/webhook",
                state_path=tpath / "state.json",
                reports_dir=tpath / "reports",
                fetch_recent_fn=lambda aid: (queried_aids.append(int(aid)) or []),
                fetch_match_fn=lambda _mid: {},
                request_parse_fn=lambda _mid: {},
                send_webhook_fn=lambda _u, _p: True,
            )
        expected_all_aids = {
            aid for m in dota_analyst.iter_roster_accounts(roster) for aid in m["account_ids"]
        }
        self.assertEqual(set(queried_aids), expected_all_aids)

        # F1: 从真实 roster.json 提取 roster_names 并聚合时，队员昵称应来自 players 而非空的 friends
        roster_names = sync_full_match_history.build_roster_names_map(roster)
        self.assertGreaterEqual(len(roster_names), 10)
        self.assertEqual(roster_names.get(85267950), "Siesta")

        # server.match_has_roster_player: 仅含非主账号队友时也应识别为车队比赛
        self.assertTrue(
            server.match_has_roster_player({"players": [{"account_id": 85267950}]}, roster)
        )


if __name__ == "__main__":
    unittest.main()
