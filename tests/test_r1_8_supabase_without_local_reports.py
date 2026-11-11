# -*- coding: utf-8 -*-
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import cloud_store
import dota_analyst
import draft_and_phase_coach
import server

REPO_ROOT = Path(__file__).resolve().parent.parent


class _FakeSupabaseHTTP:
    """本地假 Supabase REST + Storage 服务，用于验证无本地 reports/ 目录时的完整读写"""

    def __init__(self):
        self.reports_table = {}  # match_id -> row
        self.match_players_rows = {}  # (match_id, player_slot) -> row
        self.storage_objects = {}  # path -> bytes
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def _send_json(self, payload, status=200):
                raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(parsed.query)
                path = parsed.path

                if path == "/rest/v1/dota_match_reports":
                    rows = list(parent.reports_table.values())
                    mid_filter = (qs.get("match_id") or [""])[0]
                    if mid_filter.startswith("eq."):
                        target_mid = int(mid_filter.split(".", 1)[1])
                        rows = [r for r in rows if int(r["match_id"]) == target_mid]
                    rows.sort(key=lambda r: int(r["match_id"]), reverse=True)
                    self._send_json(rows)
                    return

                if path == "/rest/v1/match_players":
                    rows = list(parent.match_players_rows.values())
                    aid_filter = (qs.get("account_id") or [""])[0]
                    if aid_filter.startswith("eq."):
                        target_aid = int(aid_filter.split(".", 1)[1])
                        rows = [r for r in rows if r.get("account_id") == target_aid]
                    rows.sort(key=lambda r: (int(r["match_id"]), -int(r["player_slot"])), reverse=True)
                    limit_str = (qs.get("limit") or [""])[0]
                    if limit_str.isdigit():
                        rows = rows[: int(limit_str)]
                    self._send_json(rows)
                    return

                if path.startswith("/storage/v1/object/"):
                    obj_key = path.split("/storage/v1/object/", 1)[1]
                    if obj_key in parent.storage_objects:
                        raw = parent.storage_objects[obj_key]
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(raw)))
                        self.end_headers()
                        self.wfile.write(raw)
                        return

                self._send_json({"error": "not_found"}, status=404)

            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length > 0 else b""

                if path == "/rest/v1/dota_match_reports":
                    item = json.loads(body.decode("utf-8"))
                    items = item if isinstance(item, list) else [item]
                    for it in items:
                        parent.reports_table[int(it["match_id"])] = it
                    self._send_json({"ok": True}, status=201)
                    return

                if path == "/rest/v1/match_players":
                    items = json.loads(body.decode("utf-8"))
                    if isinstance(items, dict):
                        items = [items]
                    for it in items:
                        key = (int(it["match_id"]), int(it["player_slot"]))
                        parent.match_players_rows[key] = it
                    self._send_json({"ok": True}, status=201)
                    return

                if path.startswith("/storage/v1/object/"):
                    obj_key = path.split("/storage/v1/object/", 1)[1]
                    parent.storage_objects[obj_key] = body
                    self._send_json({"ok": True}, status=200)
                    return

                self._send_json({"error": "not_found"}, status=404)

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.httpd.shutdown()
        self.httpd.server_close()


class TestR18SupabaseTruthfulP3(unittest.TestCase):
    """R1-8 · P3 如实收尾"""

    def test_1_server_never_reads_tests_fixtures(self):
        server_src = (REPO_ROOT / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("fixtures", server_src)

    def test_2_migrate_script_fails_when_supabase_unconfigured_or_unreachable(self):
        from tools import migrate_reports_to_supabase

        script = REPO_ROOT / "tools" / "migrate_reports_to_supabase.py"
        with tempfile.TemporaryDirectory() as sample_dir:
            sdir = Path(sample_dir)
            shutil.copy2(REPO_ROOT / "reports" / "raw_9043295657.json", sdir / "raw_9043295657.json")

            with patch.object(cloud_store, "get_cloud_config", return_value={"supabase_url": "", "supabase_key": "", "supabase_bucket": "dota-reports"}):
                stats_unconf = migrate_reports_to_supabase.migrate_all(sdir, dry_run=False)
                self.assertFalse(stats_unconf["supabase_configured"])
                self.assertEqual(stats_unconf["reports_migrated"], 0, "未连接 Supabase 时 reports_migrated 必须为 0")

            # CLI exit code when Supabase is unreachable -> must be 1 (not 0 and not argparse 2)
            bad_env = {
                k: v
                for k, v in os.environ.items()
                if k not in ("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY", "SUPABASE_KEY")
            }
            bad_env["PYTHONPATH"] = str(REPO_ROOT)
            bad_env["SUPABASE_URL"] = "http://127.0.0.1:1"
            bad_env["SUPABASE_SERVICE_ROLE_KEY"] = "invalid-key"
            res_unreachable = subprocess.run(
                [sys.executable, "-c", f"import sys; from pathlib import Path; from tools import migrate_reports_to_supabase as m; m.REPORTS_DIR = Path({str(sdir)!r}); raise SystemExit(m.main())"],
                env=bad_env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_unreachable.returncode, 1, f"连不上 Supabase 时迁移脚本退出码应为 1，实际为 {res_unreachable.returncode}: {res_unreachable.stderr}")

    def test_3_init_and_match_endpoints_work_from_fake_supabase_without_reports_dir(self):
        from tools.migrate_reports_to_supabase import migrate_all

        with _FakeSupabaseHTTP() as supa, tempfile.TemporaryDirectory() as work_tmp:
            work_path = Path(work_tmp)
            seed_dir = work_path / "seed_reports"
            seed_dir.mkdir()
            sample_mids = [9043295657, 9046276667]
            for mid in sample_mids:
                shutil.copy2(REPO_ROOT / "reports" / f"raw_{mid}.json", seed_dir / f"raw_{mid}.json")

            env_patch = {
                "SUPABASE_URL": supa.url,
                "SUPABASE_SERVICE_ROLE_KEY": "fake-supa-service-key",
                "TEAM_TOKEN": "r1_8_secret_token_32chars_minimum_xyz",
            }
            with patch.dict(os.environ, env_patch, clear=False):
                cloud_store._CLOUD_IDS_CACHE.update({"ts": 0.0, "ids": set()})
                mig_stats = migrate_all(seed_dir, dry_run=False)
                self.assertTrue(mig_stats["supabase_configured"])
                self.assertEqual(mig_stats["reports_migrated"], 2)
                self.assertEqual(len(supa.match_players_rows), 20)

                # Now point REPORTS_DIR and TMP_REPORTS_DIR to non-existent directories!
                missing_reports_dir = work_path / "deleted_reports_dir"
                missing_tmp_dir = work_path / "deleted_tmp_dir"
                self.assertFalse(missing_reports_dir.exists())
                self.assertFalse(missing_tmp_dir.exists())

                server._RECENT_MATCHES_CACHE.clear()
                draft_and_phase_coach._LEDGER_MEM_CACHE.clear()
                cloud_store._CLOUD_IDS_CACHE.update({"ts": 0.0, "ids": set()})

                app_httpd = HTTPServer(("127.0.0.1", 0), server.DotaAnalystHandler)
                app_port = app_httpd.server_port
                app_thread = threading.Thread(target=app_httpd.serve_forever, daemon=True)
                app_thread.start()
                try:
                    with patch.object(server, "REPORTS_DIR", missing_reports_dir), patch.object(
                        server, "TMP_REPORTS_DIR", missing_tmp_dir
                    ), patch.object(dota_analyst, "REPORTS_DIR", missing_reports_dir), patch.object(
                        cloud_store, "REPORTS_DIR", missing_reports_dir
                    ), patch.object(
                        cloud_store, "TMP_REPORTS_DIR", missing_tmp_dir
                    ), patch.object(
                        dota_analyst, "api_get", side_effect=AssertionError("禁止请求 OpenDota")
                    ):
                        # 1. GET /api/init without local reports/
                        with urllib.request.urlopen(f"http://127.0.0.1:{app_port}/api/init", timeout=10) as resp:
                            self.assertEqual(resp.status, 200)
                            init_body = json.loads(resp.read().decode("utf-8"))
                        self.assertTrue(init_body.get("ok"))
                        recent = init_body.get("recent_matches") or []
                        self.assertGreaterEqual(len(recent), 2, "比赛列表应从 Supabase match_players 读取非空记录")
                        self.assertTrue(all(m.get("is_analyzed") for m in recent))

                        ledger = init_body.get("squad_ledger") or {}
                        self.assertGreaterEqual(
                            len(ledger.get("analyzed_matches") or []),
                            2,
                            "总账 analyzed_matches 应从 Supabase match_players 构建",
                        )
                        self.assertGreaterEqual(
                            len(ledger.get("squad_members_rank") or []),
                            5,
                            "总账 squad_members_rank 应从 Supabase match_players 构建",
                        )

                        # 2. GET /api/match/<id> without local reports/
                        target_mid = sample_mids[0]
                        with urllib.request.urlopen(
                            f"http://127.0.0.1:{app_port}/api/match/{target_mid}", timeout=10
                        ) as resp2:
                            self.assertEqual(resp2.status, 200)
                            match_body = json.loads(resp2.read().decode("utf-8"))
                        self.assertTrue(match_body.get("ok"))
                        self.assertEqual(int(match_body["report"]["match_id"]), target_mid)
                        self.assertFalse(missing_reports_dir.exists(), "只读请求不应创建本地 reports/ 目录")
                finally:
                    app_httpd.shutdown()
                    app_httpd.server_close()


if __name__ == "__main__":
    unittest.main()
