# -*- coding: utf-8 -*-
"""
F8 · 赛后自动推送（D5 Webhook）单元测试
验证：
1. tools/postgame_webhook_notifier.py 支持检查花名册成员新比赛、请求 OpenDota 解析、生成报告、组装包含摘要+Top3要改的事+复盘时刻+报告链接的 Webhook 消息并推送，且对已推送 match_id 去重。
2. .github/workflows/postgame_notify.yml 配置了 schedule (cron) 定时任务。
3. 全部 HTTP 与 OpenDota 调用在测试中完全 mock，零真实网络请求。
"""
import json
import tempfile
import unittest
from pathlib import Path

import dota_analyst

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestF8PostgameWebhook(unittest.TestCase):
    def test_github_workflow_schedule_exists(self):
        wf_path = REPO_ROOT / ".github" / "workflows" / "postgame_notify.yml"
        self.assertTrue(wf_path.exists(), "缺少 .github/workflows/postgame_notify.yml")
        wf_text = wf_path.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", wf_text)
        self.assertNotIn("schedule:", wf_text)
        self.assertIn("postgame_webhook_notifier.py", wf_text)

    def test_postgame_webhook_notifier_flow_with_mocks(self):
        from tools import postgame_webhook_notifier

        raw_path = REPO_ROOT / "reports" / "raw_8774383260.json"
        raw_match = json.loads(raw_path.read_text(encoding="utf-8"))
        mid = int(raw_match["match_id"])
        roster = dota_analyst.load_roster()

        parse_requested_mids = []
        webhook_sent_payloads = []

        def mock_fetch_recent(account_id: int):
            return [{"match_id": mid, "start_time": 1762000000, "player_slot": 0, "radiant_win": True}]

        # 第一次拉取时模拟未解析 (version=None)，触发 request_parse 后再返回已解析 raw_match
        fetch_attempts = {"count": 0}

        def mock_fetch_match(match_id: int):
            fetch_attempts["count"] += 1
            if fetch_attempts["count"] == 1:
                unparsed = dict(raw_match)
                unparsed.pop("version", None)
                return unparsed
            return raw_match

        def mock_request_parse(match_id: int):
            parse_requested_mids.append(int(match_id))
            return {"job": {"jobId": 12345}}

        def mock_send_webhook(webhook_url: str, payload: dict):
            webhook_sent_payloads.append((webhook_url, payload))
            return True

        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "notified_matches.json"
            reports_dir = Path(tmpdir) / "reports"
            res1 = postgame_webhook_notifier.run_postgame_notification_cycle(
                roster=roster,
                webhook_url="https://example.invalid/webhook/dota-squad",
                base_app_url="https://dota-ledger.example.invalid",
                state_path=state_file,
                reports_dir=reports_dir,
                fetch_recent_fn=mock_fetch_recent,
                fetch_match_fn=mock_fetch_match,
                request_parse_fn=mock_request_parse,
                send_webhook_fn=mock_send_webhook,
                poll_wait_sec=0.0,
            )

            self.assertEqual(res1["notified_count"], 1)
            self.assertIn(mid, parse_requested_mids)
            self.assertEqual(len(webhook_sent_payloads), 1)

            sent_url, payload = webhook_sent_payloads[0]
            self.assertEqual(sent_url, "https://example.invalid/webhook/dota-squad")
            self.assertEqual(payload["match_id"], mid)
            self.assertIn(f"match={mid}", payload["report_url"])
            self.assertIn(str(mid), payload["content"])
            self.assertTrue(isinstance(payload["next_game_top3_fixes"], list))
            self.assertTrue(isinstance(payload["top3_replay_moments"], list))

            # 第二次运行同一周期：已推送过的比赛不再重复推送
            res2 = postgame_webhook_notifier.run_postgame_notification_cycle(
                roster=roster,
                webhook_url="https://example.invalid/webhook/dota-squad",
                base_app_url="https://dota-ledger.example.invalid",
                state_path=state_file,
                reports_dir=reports_dir,
                fetch_recent_fn=mock_fetch_recent,
                fetch_match_fn=mock_fetch_match,
                request_parse_fn=mock_request_parse,
                send_webhook_fn=mock_send_webhook,
                poll_wait_sec=0.0,
            )
            self.assertEqual(res2["notified_count"], 0)
            self.assertEqual(len(webhook_sent_payloads), 1)


if __name__ == "__main__":
    unittest.main()
