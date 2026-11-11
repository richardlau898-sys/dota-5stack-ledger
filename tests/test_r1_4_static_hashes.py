# -*- coding: utf-8 -*-
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import server

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "tools" / "build_static_hashes.py"


class _TestableHandler(server.DotaAnalystHandler):
    def __init__(self, path: str, headers: dict = None):
        self.command = "GET"
        self.path = path
        self.request_version = "HTTP/1.1"
        self.headers = headers or {}
        self.rfile = io.BytesIO()
        self.wfile = io.BytesIO()
        self.resp_status = None
        self.resp_headers = {}

    def address_string(self) -> str:
        return "127.0.0.1"

    def send_response(self, code, message=None):
        self.resp_status = code

    def send_header(self, keyword, value):
        self.resp_headers[keyword] = value

    def end_headers(self):
        pass


class TestR14StaticHashes(unittest.TestCase):
    """R1-4 · 静态文件哈希自动生成"""

    def test_ci_workflow_runs_static_hash_check_and_repo_is_in_sync(self):
        self.assertTrue(SCRIPT_PATH.exists(), "缺少 tools/build_static_hashes.py")
        ci_text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("tools/build_static_hashes.py --check", ci_text)

        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--check"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"--check failed on repo: {proc.stderr or proc.stdout}")

    def test_modifying_one_character_without_regenerating_fails_check_without_writing(self):
        self.assertTrue(SCRIPT_PATH.exists(), "缺少 tools/build_static_hashes.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            tmp_static = tmp_root / "static"
            tmp_static.mkdir(parents=True)
            for name in ("index.html", "app.js", "styles.css"):
                shutil.copy2(REPO_ROOT / "static" / name, tmp_static / name)
            shutil.copy2(REPO_ROOT / "vercel.json", tmp_root / "vercel.json")

            gen = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--root", str(tmp_root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(gen.returncode, 0, gen.stderr)

            # Mutate 1 character in app.js without re-running generator
            app_js_path = tmp_static / "app.js"
            app_js_path.write_text(app_js_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            html_before = (tmp_static / "index.html").read_bytes()
            vercel_before = (tmp_root / "vercel.json").read_bytes()

            chk = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--check", "--root", str(tmp_root)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(chk.returncode, 0, "Expected --check to fail after modifying 1 char in app.js")
            self.assertEqual((tmp_static / "index.html").read_bytes(), html_before)
            self.assertEqual((tmp_root / "vercel.json").read_bytes(), vercel_before)

    def test_mismatched_hash_returns_404_and_matching_hash_returns_long_cache(self):
        js_hash = hashlib.sha256((REPO_ROOT / "static" / "app.js").read_bytes()).hexdigest()[:8]
        css_hash = hashlib.sha256((REPO_ROOT / "static" / "styles.css").read_bytes()).hexdigest()[:8]

        # Mismatched hashes must return 404
        for bad_path in ("/app.deadbeef.js", "/styles.deadbeef.css"):
            h_bad = _TestableHandler(bad_path)
            h_bad.do_GET()
            self.assertEqual(h_bad.resp_status, 404, f"Expected 404 for {bad_path}, got {h_bad.resp_status}")

        # Exact matching hashes return 200 + immutable 1-year cache
        for ok_path in (f"/app.{js_hash}.js", f"/styles.{css_hash}.css"):
            h_ok = _TestableHandler(ok_path)
            h_ok.do_GET()
            self.assertEqual(h_ok.resp_status, 200, f"Expected 200 for {ok_path}, got {h_ok.resp_status}")
            cc = h_ok.resp_headers.get("Cache-Control", "")
            self.assertIn("max-age=31536000", cc)
            self.assertIn("immutable", cc)

        # vercel.json also pins exact hashes instead of wildcard :hash
        vercel_cfg = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
        rewrite_sources = [rw.get("source") for rw in (vercel_cfg.get("rewrites") or [])]
        self.assertNotIn("/app.:hash.js", rewrite_sources)
        self.assertNotIn("/styles.:hash.css", rewrite_sources)
        self.assertIn(f"/app.{js_hash}.js", rewrite_sources)
        self.assertIn(f"/styles.{css_hash}.css", rewrite_sources)


if __name__ == "__main__":
    unittest.main()
