# -*- coding: utf-8 -*-
"""
R1-1 · 不带口令的 GET 必须只读
验证：
1. 用 mock 记录所有文件写入 (Path.write_text / Path.write_bytes / open 写模式) 与全部网络请求 (urlopen / api_get / api_post)：
   不带口令请求 3 类比赛（版本最新、版本旧含非花名册老比赛 8774383260 与匿名比赛 8646427108、从没分析过），
   断言写入数为 0、网络请求数为 0；前两类返回 HTTP 200，版本旧的返回 "stale": True。
2. 不带口令的 GET /api/init 与 GET /api/match_icons 同样 0 文件写入、0 外部网络请求。
3. 前端对 stale 报告渲染 "报告版本较旧，需要口令重算"。
"""
import builtins
import copy
import io
import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

import cloud_store
import draft_and_phase_coach
import dota_analyst
import server

REPO_ROOT = Path(__file__).resolve().parent.parent


def _invoke_get(path_str: str, headers: dict = None):
    status_holder = {"code": 200}
    handler = server.DotaAnalystHandler.__new__(server.DotaAnalystHandler)
    handler.path = path_str
    handler.headers = headers or {}
    handler.wfile = io.BytesIO()
    handler.send_response = lambda code: status_holder.__setitem__("code", int(code))
    handler.send_header = lambda k, v: None
    handler.end_headers = lambda: None
    handler.address_string = lambda: "127.0.0.1"
    handler.do_GET()
    raw = handler.wfile.getvalue().decode("utf-8")
    return status_holder["code"], json.loads(raw)


class TestR11ReadonlyUnauthenticatedGet(unittest.TestCase):
    def test_three_match_classes_and_init_icons_have_zero_writes_and_zero_network_calls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tpath = Path(tmpdir)
            rep_dir = tpath / "reports"
            tmp_rep_dir = tpath / "tmp_reports"
            rep_dir.mkdir(parents=True, exist_ok=True)
            tmp_rep_dir.mkdir(parents=True, exist_ok=True)

            # 1) 最新版本比赛 (latest_mid)
            latest_mid = 9043295657
            latest_rep = json.loads((REPO_ROOT / "reports" / f"match_{latest_mid}.json").read_text(encoding="utf-8"))
            latest_rep["engine_version"] = dota_analyst.ENGINE_VERSION
            (rep_dir / f"match_{latest_mid}.json").write_text(json.dumps(latest_rep, ensure_ascii=False), encoding="utf-8")

            # 2a) 旧版本老比赛 8774383260（玩家不在当前花名册且同目录存在 raw_8774383260.json）
            stale_mid = 8774383260
            stale_rep = json.loads((REPO_ROOT / "reports" / f"match_{stale_mid}.json").read_text(encoding="utf-8"))
            stale_rep["engine_version"] = "2026.04.legacy"
            (rep_dir / f"match_{stale_mid}.json").write_text(json.dumps(stale_rep, ensure_ascii=False), encoding="utf-8")
            (rep_dir / f"raw_{stale_mid}.json").write_text(
                (REPO_ROOT / "reports" / f"raw_{stale_mid}.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            # 2b) 玩家隐藏资料（账号为空）的旧版本未解析比赛 8646427108
            anon_mid = 8646427108
            anon_rep = json.loads((REPO_ROOT / "reports" / f"match_{anon_mid}.json").read_text(encoding="utf-8"))
            anon_rep["engine_version"] = "2026.04.legacy"
            (rep_dir / f"match_{anon_mid}.json").write_text(json.dumps(anon_rep, ensure_ascii=False), encoding="utf-8")

            # 3) 从未分析过的比赛
            never_mid = 9999999123

            writes_recorded = []
            network_calls = []

            orig_open = builtins.open
            orig_write_text = Path.write_text
            orig_write_bytes = Path.write_bytes

            def tracked_open(file, mode="r", *args, **kwargs):
                if any(ch in str(mode) for ch in ("w", "a", "x", "+")):
                    writes_recorded.append(f"open:{file}:{mode}")
                return orig_open(file, mode, *args, **kwargs)

            def tracked_write_text(self_path, data, *args, **kwargs):
                writes_recorded.append(f"write_text:{self_path}")
                return orig_write_text(self_path, data, *args, **kwargs)

            def tracked_write_bytes(self_path, data, *args, **kwargs):
                writes_recorded.append(f"write_bytes:{self_path}")
                return orig_write_bytes(self_path, data, *args, **kwargs)

            def tracked_net(label):
                def _fn(*args, **kwargs):
                    network_calls.append((label, args[0] if args else ""))
                    raise AssertionError(f"Unexpected network call during unauthenticated GET: {label} {args[:1]}")
                return _fn

            env_clean = {k: v for k, v in os.environ.items() if not k.startswith("SUPABASE_")}
            env_clean["TEAM_TOKEN"] = "secret-test-team-token-32chars-min"

            # 清空内存缓存以覆盖冷启动路径
            server._RECENT_MATCHES_CACHE.clear()
            draft_and_phase_coach._LEDGER_MEM_CACHE.clear()

            with patch.dict(os.environ, env_clean, clear=True), \
                 patch.object(server, "REPORTS_DIR", rep_dir), \
                 patch.object(server, "TMP_REPORTS_DIR", tmp_rep_dir), \
                 patch.object(cloud_store, "TMP_REPORTS_DIR", tmp_rep_dir), \
                 patch.object(builtins, "open", tracked_open), \
                 patch.object(Path, "write_text", tracked_write_text), \
                 patch.object(Path, "write_bytes", tracked_write_bytes), \
                 patch.object(urllib.request, "urlopen", tracked_net("urlopen")), \
                 patch.object(server, "api_get", tracked_net("server.api_get")), \
                 patch.object(server, "api_post", tracked_net("server.api_post")), \
                 patch.object(dota_analyst, "api_get", tracked_net("dota_analyst.api_get")), \
                 patch.object(dota_analyst, "api_post", tracked_net("dota_analyst.api_post")):

                # (1) 最新版本比赛 -> 200, 无 stale
                c1, body1 = _invoke_get(f"/api/match/{latest_mid}")
                self.assertEqual(c1, 200)
                self.assertTrue(body1.get("ok"))
                self.assertFalse(bool(body1.get("stale")))
                self.assertFalse(bool(body1["report"].get("stale")))

                # (2a) 版本旧的老比赛 8774383260 -> 200 (绝不返回 403)，带 stale: true，且未重算覆盖 engine_version
                c2, body2 = _invoke_get(f"/api/match/{stale_mid}")
                self.assertEqual(c2, 200)
                self.assertTrue(body2.get("ok"))
                self.assertIs(body2.get("stale"), True)
                self.assertIs(body2["report"].get("stale"), True)
                self.assertEqual(body2["report"].get("engine_version"), "2026.04.legacy")

                # (2b) 隐藏资料未解析比赛 8646427108 -> 200, stale: true, 不去请求 OpenDota
                c2b, body2b = _invoke_get(f"/api/match/{anon_mid}")
                self.assertEqual(c2b, 200)
                self.assertTrue(body2b.get("ok"))
                self.assertIs(body2b["report"].get("stale"), True)

                # (3) 从未分析过的比赛 -> not_analyzed: true, 不请求 OpenDota
                c3, body3 = _invoke_get(f"/api/match/{never_mid}")
                self.assertEqual(c3, 200)
                self.assertTrue(body3.get("ok"))
                self.assertIs(body3.get("not_analyzed"), True)

                # (4) 不带口令的 /api/init 与 /api/match_icons 也不写入文件、不请求外部网络
                c_init, body_init = _invoke_get("/api/init")
                self.assertEqual(c_init, 200)
                self.assertTrue(body_init.get("ok"))

                c_icons, body_icons = _invoke_get(f"/api/match_icons?match_id={stale_mid}")
                self.assertEqual(c_icons, 200)
                self.assertTrue(body_icons.get("ok"))

            self.assertEqual(writes_recorded, [], f"不带口令的 GET 不得写入任何文件: {writes_recorded}")
            self.assertEqual(network_calls, [], f"不带口令的 GET 不得发起任何网络请求: {network_calls}")

    def test_frontend_displays_stale_report_banner(self):
        app_js = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        index_html = (REPO_ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("报告版本较旧，需要口令重算", app_js)
        self.assertIn("stale-report-banner", index_html)


if __name__ == "__main__":
    unittest.main()
