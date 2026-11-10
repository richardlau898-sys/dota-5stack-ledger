import os
import unittest
from unittest.mock import patch

import server


class TestS2TeamTokenAuth(unittest.TestCase):
    """S2 · 写入和花钱的接口加车队口令 & GET 不得调用 LLM & 非花名册比赛拒绝落库"""

    def test_check_team_token_auth_four_cases(self):
        # 1. 有口令（正确口令）
        ok, status, _ = server.check_team_token_auth(
            provided_token="secret-squad-token-123",
            expected_token="secret-squad-token-123",
            is_vercel=True,
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)

        # 2. 无口令
        ok, status, _ = server.check_team_token_auth(
            provided_token="",
            expected_token="secret-squad-token-123",
            is_vercel=False,
        )
        self.assertFalse(ok)
        self.assertEqual(status, 401)

        # 3. 错口令
        ok, status, _ = server.check_team_token_auth(
            provided_token="wrong-token",
            expected_token="secret-squad-token-123",
            is_vercel=False,
        )
        self.assertFalse(ok)
        self.assertEqual(status, 401)

        # 4a. 未配置口令（Vercel 生产环境一律返回 503）
        ok, status, _ = server.check_team_token_auth(
            provided_token="any",
            expected_token="",
            is_vercel=True,
        )
        self.assertFalse(ok)
        self.assertEqual(status, 503)

        # 4b. 未配置口令（本地开发放行）
        ok, status, _ = server.check_team_token_auth(
            provided_token="",
            expected_token="",
            is_vercel=False,
        )
        self.assertTrue(ok)
        self.assertEqual(status, 200)

    def test_get_or_build_match_report_never_calls_llm(self):
        with patch.object(server, "_has_complete_grok_coaching", return_value=False):
            with patch.object(server, "call_llm_coach_review") as mock_llm:
                rep = server.get_or_build_match_report(
                    9083213997,
                    allow_build=False,
                    require_ai=True,
                    skip_llm=False,
                )
                self.assertIsNotNone(rep)
                mock_llm.assert_not_called()

    def test_reject_match_without_roster_players(self):
        roster = {
            "main_account_id": 86080912,
            "players": {"86080912": {"name": "Main"}, "125236640": {"name": "Friend"}},
        }
        stranger_raw = {
            "match_id": 9999999999,
            "version": 22,
            "players": [{"account_id": 111111 + i, "player_slot": i} for i in range(10)],
        }
        self.assertFalse(server.match_has_roster_player(stranger_raw, roster))

        squad_raw = {
            "match_id": 9999999998,
            "version": 22,
            "players": [{"account_id": 86080912, "player_slot": 0}]
            + [{"account_id": 222222 + i, "player_slot": i + 1} for i in range(9)],
        }
        self.assertTrue(server.match_has_roster_player(squad_raw, roster))


if __name__ == "__main__":
    unittest.main()
