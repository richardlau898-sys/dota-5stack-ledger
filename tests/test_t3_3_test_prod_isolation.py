# -*- coding: utf-8 -*-
"""
T3-3 · 测试与生产隔离 单元测试
验收要求：
1. 临时目录可通过环境变量 DOTA_TMP_DIR 配置（未设置时默认值保持 /tmp/dota_reports 不变），测试统一指向临时目录，绝不读写 /tmp/dota_reports。
2. tests/test_p3_supabase_single_source.py 的 test_5 正确 mock server 导入的云端函数，断网下通过。
3. tools/no_network_site/sitecustomize.py 在断网模式下拦截所有非本机回环（non-loopback）的 socket 联网请求并直接抛错，同时允许 127.0.0.1 本地测试服务。
4. CI 与测试入口启用 DOTA_TMP_DIR 与禁止外网连接；测试前后 /tmp/dota_reports 的文件列表和修改时间完全一致。
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
NO_NETWORK_SITE_DIR = REPO_ROOT / "tools" / "no_network_site"


def _snapshot_dir_state(target_dir: Path):
    if not target_dir.exists():
        return None
    entries = []
    for p in sorted(target_dir.rglob("*")):
        st = p.stat()
        entries.append((str(p.relative_to(target_dir)), st.st_mtime_ns, st.st_size))
    return entries


class _OfflineSocketBlocker:
    """Context manager blocking non-loopback network connections to verify test_5 offline."""

    def __enter__(self):
        self._orig_getaddrinfo = socket.getaddrinfo
        self._orig_connect = socket.socket.connect

        def _is_loopback(host):
            h = str(host or "").strip().lower().strip("[]")
            return h in ("", "localhost", "127.0.0.1", "::1", "0.0.0.0", "::") or h.startswith("127.")

        orig_gai = self._orig_getaddrinfo
        orig_conn = self._orig_connect

        def guarded_getaddrinfo(host, port, *args, **kwargs):
            if not _is_loopback(host):
                raise OSError(f"Offline test blocked DNS lookup to external host: {host!r}")
            return orig_gai(host, port, *args, **kwargs)

        def guarded_connect(sock_self, address):
            if isinstance(address, tuple) and len(address) >= 1:
                if not _is_loopback(address[0]):
                    raise OSError(f"Offline test blocked socket.connect to external address: {address!r}")
            return orig_conn(sock_self, address)

        socket.getaddrinfo = guarded_getaddrinfo
        socket.socket.connect = guarded_connect
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        socket.getaddrinfo = self._orig_getaddrinfo
        socket.socket.connect = self._orig_connect


class TestT33TestProdIsolation(unittest.TestCase):
    def test_1_dota_tmp_dir_env_configurable_and_default_preserved(self):
        """DOTA_TMP_DIR 可覆盖所有模块的临时目录，未设置时默认仍为 /tmp/dota_reports"""
        before_snap = _snapshot_dir_state(Path("/tmp/dota_reports"))
        with tempfile.TemporaryDirectory() as custom_tmp:
            custom_path = str(Path(custom_tmp).resolve())
            code = (
                "import json, cloud_store, server, draft_and_phase_coach, dota_analyst;"
                "ledger_p = str(draft_and_phase_coach._ledger_cache_file_path(dota_analyst.REPORTS_DIR));"
                "print(json.dumps({"
                "'cloud_tmp': str(cloud_store.get_tmp_reports_dir().resolve()),"
                "'server_tmp': str(server._get_tmp_reports_dir().resolve()),"
                "'ledger_cache': ledger_p"
                "}))"
            )
            env_custom = dict(os.environ, DOTA_TMP_DIR=custom_path, PYTHONPATH=str(REPO_ROOT))
            proc = subprocess.run(
                [sys.executable, "-c", code],
                env=env_custom,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, f"Subprocess failed: {proc.stderr}")
            data = json.loads(proc.stdout.strip())
            self.assertEqual(data["cloud_tmp"], custom_path)
            self.assertEqual(data["server_tmp"], custom_path)
            self.assertEqual(Path(data["ledger_cache"]).resolve(), (Path(custom_path) / "squad_ledger.json").resolve())

            # Verify default when DOTA_TMP_DIR is unset remains /tmp/dota_reports
            env_default = {k: v for k, v in os.environ.items() if k != "DOTA_TMP_DIR"}
            env_default["PYTHONPATH"] = str(REPO_ROOT)
            code_def = (
                "import json, cloud_store, server;"
                "print(json.dumps({"
                "'cloud_def': str(cloud_store.get_tmp_reports_dir()),"
                "'server_def': str(server._get_tmp_reports_dir())"
                "}))"
            )
            proc_def = subprocess.run(
                [sys.executable, "-c", code_def],
                env=env_default,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc_def.returncode, 0, f"Default check failed: {proc_def.stderr}")
            def_data = json.loads(proc_def.stdout.strip())
            self.assertEqual(def_data["cloud_def"], "/tmp/dota_reports")
            self.assertEqual(def_data["server_def"], "/tmp/dota_reports")

        after_snap = _snapshot_dir_state(Path("/tmp/dota_reports"))
        self.assertEqual(before_snap, after_snap, "/tmp/dota_reports must not be modified")

    def test_2_p3_test_5_passes_strictly_offline(self):
        """tests/test_p3_supabase_single_source.py 的 test_5 在完全断网时通过且零外网调用"""
        from tests.test_p3_supabase_single_source import TestP3SupabaseSingleSource

        TestP3SupabaseSingleSource.setUpClass()
        case = TestP3SupabaseSingleSource(
            "test_5_engine_version_triggers_rebuild_when_stale_and_works_without_local_reports_dir"
        )
        with _OfflineSocketBlocker():
            case.test_5_engine_version_triggers_rebuild_when_stale_and_works_without_local_reports_dir()

    def test_3_sitecustomize_blocks_external_network_and_allows_loopback(self):
        """tools/no_network_site/sitecustomize.py 拦截外网连接但放行 127.0.0.1 本地回环"""
        site_file = NO_NETWORK_SITE_DIR / "sitecustomize.py"
        self.assertTrue(site_file.exists(), f"Missing {site_file}")

        env = dict(
            os.environ,
            PYTHONPATH=f"{NO_NETWORK_SITE_DIR}{os.pathsep}{REPO_ROOT}",
        )
        env.pop("DOTA_ALLOW_TEST_NETWORK", None)

        # 1) External connection to api.opendota.com must raise immediately
        ext_code = (
            "import urllib.request\n"
            "urllib.request.urlopen('https://api.opendota.com/api/matches/9046276667', timeout=2)\n"
        )
        ext_proc = subprocess.run(
            [sys.executable, "-c", ext_code],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(ext_proc.returncode, 0, "External network call must fail under no_network_site")
        self.assertIn("api.opendota.com", ext_proc.stderr)

        # 2) Loopback HTTPServer on 127.0.0.1 must still succeed
        loop_code = (
            "import threading, urllib.request\n"
            "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
            "class H(BaseHTTPRequestHandler):\n"
            "    def do_GET(self):\n"
            "        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')\n"
            "    def log_message(self, *a): pass\n"
            "srv = HTTPServer(('127.0.0.1', 0), H)\n"
            "t = threading.Thread(target=srv.handle_request, daemon=True); t.start()\n"
            "with urllib.request.urlopen(f'http://127.0.0.1:{srv.server_port}/', timeout=3) as r:\n"
            "    assert r.read() == b'ok'\n"
            "srv.server_close()\n"
            "print('LOOPBACK_OK')\n"
        )
        loop_proc = subprocess.run(
            [sys.executable, "-c", loop_code],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(loop_proc.returncode, 0, f"Loopback failed: {loop_proc.stderr}")
        self.assertIn("LOOPBACK_OK", loop_proc.stdout)

    def test_4_test_suite_and_ci_isolate_tmp_dir_and_block_network(self):
        """tests 包初始化自动将 DOTA_TMP_DIR 指向独立临时目录，且 CI 配置启用 no_network_site 与 DOTA_TMP_DIR"""
        active_tmp = (os.environ.get("DOTA_TMP_DIR") or "").strip()
        self.assertTrue(active_tmp, "Running unittest must set DOTA_TMP_DIR automatically")
        self.assertNotEqual(
            Path(active_tmp).resolve(),
            Path("/tmp/dota_reports").resolve(),
            "DOTA_TMP_DIR during tests must NOT point to /tmp/dota_reports",
        )

        ci_txt = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("no_network_site", ci_txt)
        self.assertIn("DOTA_TMP_DIR", ci_txt)


if __name__ == "__main__":
    unittest.main()
