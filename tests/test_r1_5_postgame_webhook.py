# -*- coding: utf-8 -*-
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import dota_analyst
from tools import postgame_webhook_notifier

REPO_ROOT = Path(__file__).resolve().parent.parent


class _FakeSupabaseServer:
    def __init__(self):
        self.notified_rows = {}
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def do_GET(self):
                if self.path.startswith("/rest/v1/postgame_notified_matches"):
                    body = json.dumps([{"match_id": mid} for mid in sorted(parent.notified_rows)]).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8") if length > 0 else "[]"
                if self.path.startswith("/rest/v1/postgame_notified_matches"):
                    items = json.loads(raw)
                    if isinstance(items, dict):
                        items = [items]
                    for it in items:
                        if it.get("match_id"):
                            parent.notified_rows[int(it["match_id"])] = it
                    self.send_response(201)
                    self.end_headers()
                    return
                self.send_response(404)
                self.end_headers()

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.httpd.shutdown()
        self.httpd.server_close()


class TestR15PostgameWebhook(unittest.TestCase):
    """R1-5 · 修好赛后推送，修好之前不定时运行"""

    def test_workflow_has_no_schedule_and_uses_real_domain(self):
        wf_text = (REPO_ROOT / ".github" / "workflows" / "postgame_notify.yml").read_text(encoding="utf-8")
        self.assertNotIn("schedule:", wf_text)
        self.assertNotIn("cron:", wf_text)
        self.assertIn("workflow_dispatch:", wf_text)
        self.assertIn("https://dota-ai-analyst.vercel.app", wf_text)
        self.assertNotIn("dota-5stack-ledger.vercel.app", wf_text)

        notifier_src = (REPO_ROOT / "tools" / "postgame_webhook_notifier.py").read_text(encoding="utf-8")
        self.assertNotIn("dota-5stack-ledger.vercel.app", notifier_src)
        self.assertIn("https://dota-ai-analyst.vercel.app", notifier_src)

    def test_empty_webhook_exits_immediately_without_network(self):
        recent_calls = []

        def fake_recent(aid: int):
            recent_calls.append(aid)
            return []

        res = postgame_webhook_notifier.run_postgame_notification_cycle(
            webhook_url="",
            fetch_recent_fn=fake_recent,
        )
        self.assertEqual(len(recent_calls), 0)
        self.assertEqual(res.get("notified_count"), 0)

    def test_three_ephemeral_runs_notify_once_and_call_real_parse_request(self):
        raw_match = json.loads((REPO_ROOT / "reports" / "raw_9043295657.json").read_text(encoding="utf-8"))
        mid = int(raw_match["match_id"])
        roster = dota_analyst.load_roster()
        expected_roster_aids = {
            aid for m in dota_analyst.iter_roster_accounts(roster) for aid in m["account_ids"]
        }

        queried_aids = set()
        sent_webhooks = []
        fetch_match_calls = {"n": 0}

        def fake_fetch_recent(aid: int):
            queried_aids.add(int(aid))
            return [{"match_id": mid, "start_time": 1762000000, "player_slot": 0, "radiant_win": True}]

        def fake_fetch_match(match_id: int):
            fetch_match_calls["n"] += 1
            if fetch_match_calls["n"] == 1:
                unparsed = dict(raw_match)
                unparsed.pop("version", None)
                return unparsed
            return raw_match

        def fake_send_webhook(url: str, payload: dict):
            sent_webhooks.append((url, payload))
            return True

        with _FakeSupabaseServer() as supa:
            env_patch = {
                "SUPABASE_URL": supa.url,
                "SUPABASE_SERVICE_ROLE_KEY": "fake-service-role-key",
                "PUBLIC_APP_URL": "",
            }
            with patch.dict(os.environ, env_patch, clear=False), patch.object(
                dota_analyst, "api_post", return_value={"job": {"jobId": 98765}}
            ) as mock_api_post:
                # Simulate 3 separate GitHub Actions runs, each with a brand-new empty local temp directory
                for run_idx in range(3):
                    with tempfile.TemporaryDirectory() as fresh_runner_dir:
                        fresh_state = Path(fresh_runner_dir) / "ephemeral_state.json"
                        fresh_reports = Path(fresh_runner_dir) / "reports"
                        res = postgame_webhook_notifier.run_postgame_notification_cycle(
                            roster=roster,
                            webhook_url="https://hooks.example.invalid/postgame",
                            state_path=fresh_state,
                            reports_dir=fresh_reports,
                            fetch_recent_fn=fake_fetch_recent,
                            fetch_match_fn=fake_fetch_match,
                            # Intentionally use default request_parse_fn (_default_request_parse)!
                            send_webhook_fn=fake_send_webhook,
                            poll_wait_sec=0.0,
                        )
                        if run_idx == 0:
                            self.assertEqual(res["notified_count"], 1)
                        else:
                            self.assertEqual(res["notified_count"], 0)

                # Asserts:
                # 1) Sent ONLY 1 time across all 3 ephemeral runs
                self.assertEqual(len(sent_webhooks), 1)
                self.assertIn(mid, supa.notified_rows)
                # 2) Default URL points to https://dota-ai-analyst.vercel.app
                self.assertTrue(
                    sent_webhooks[0][1]["report_url"].startswith("https://dota-ai-analyst.vercel.app/"),
                    sent_webhooks[0][1]["report_url"],
                )
                # 3) Real _default_request_parse invoked dota_analyst.api_post("/request/<id>")
                mock_api_post.assert_called_once_with(f"/request/{mid}")
                # 4) Covered all roster accounts, not just main_account_id
                self.assertEqual(queried_aids, expected_roster_aids)


if __name__ == "__main__":
    unittest.main()
