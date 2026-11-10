import io
import json
import re
import unittest
from pathlib import Path

import server

REPO_ROOT = Path(__file__).resolve().parent.parent


class _DummySocket:
    def makefile(self, *args, **kwargs):
        return io.BytesIO()


class _TestableHandler(server.DotaAnalystHandler):
    def __init__(self, path: str, headers: dict = None):
        self.path = path
        self.command = "GET"
        self.request_version = "HTTP/1.1"
        self.headers = headers or {}
        self.rfile = io.BytesIO()
        self.wfile = io.BytesIO()
        self.resp_status = None
        self.resp_headers = {}

    def send_response(self, code, message=None):
        self.resp_status = code

    def send_header(self, keyword, value):
        self.resp_headers[keyword] = value

    def end_headers(self):
        pass


class TestP4StaticAssets(unittest.TestCase):
    def test_1_vercel_json_only_api_routes_to_function_and_spa_fallbacks(self):
        """只有 /api/* 走 Python 函数，/match/* 和 /pregame 回落到静态 index.html，静态资源配置长期缓存"""
        vercel_cfg = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
        rewrites = vercel_cfg.get("rewrites") or []
        self.assertTrue(len(rewrites) > 0)

        for rw in rewrites:
            src = rw.get("source", "")
            dst = rw.get("destination", "")
            if "/api/index.py" in dst:
                self.assertTrue(
                    src.startswith("/api/"),
                    f"Only /api/* may route to /api/index.py, found source={src}",
                )

        sources_to_dst = {rw.get("source"): rw.get("destination") for rw in rewrites}
        self.assertIn("/match/(.*)", sources_to_dst)
        self.assertEqual(sources_to_dst["/match/(.*)"], "/static/index.html")
        self.assertIn("/pregame", sources_to_dst)
        self.assertEqual(sources_to_dst["/pregame"], "/static/index.html")

        headers_cfg = vercel_cfg.get("headers") or []
        has_immutable = any(
            "max-age=31536000" in h.get("value", "") and "immutable" in h.get("value", "")
            for item in headers_cfg
            for h in (item.get("headers") or [])
            if h.get("key", "").lower() == "cache-control"
        )
        self.assertTrue(has_immutable, "vercel.json must configure long-term immutable Cache-Control for static assets")

    def test_2_index_html_has_content_hashed_assets_and_no_cdnjs_scripts(self):
        """首屏 index.html 不请求 cdnjs，且 JS/CSS 文件名带内容哈希"""
        html = (REPO_ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("cdnjs.cloudflare.com", html)
        self.assertRegex(html, r'href="/styles\.[0-9a-f]{8,}\.css"')
        self.assertRegex(html, r'src="/app\.[0-9a-f]{8,}\.js"')

    def test_3_pdf_libs_and_cjk_font_lazy_loaded_only_on_export(self):
        """PDF 库和中文字体在第一次点导出时再加载，打开全屏报告时不预加载字体"""
        app_js = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("/styles.css?v=4.6", app_js)
        self.assertIn("ensurePdfExportLibsLoaded", app_js)

        m = re.search(
            r"function openFullscreenStructuredReport\b[\s\S]*?(?=\n(?:async\s+)?function\s+)",
            app_js,
        )
        self.assertIsNotNone(m)
        open_fs_body = m.group(0)
        self.assertNotIn("ensureCjkVectorFontBase64()", open_fs_body)
        self.assertNotIn("ensureMatchIconsMap(", open_fs_body)

    def test_4_server_caches_static_js_css_with_etag_and_304(self):
        """第二次访问时 app.<hash>.js 命中缓存返回 304，且带长期缓存响应头"""
        html = (REPO_ROOT / "static" / "index.html").read_text(encoding="utf-8")
        m = re.search(r'src="(/app\.[0-9a-f]{8,}\.js)"', html)
        self.assertIsNotNone(m, "index.html must reference /app.<hash>.js")
        hashed_js_path = m.group(1)

        h1 = _TestableHandler(hashed_js_path)
        h1.do_GET()
        self.assertEqual(h1.resp_status, 200)
        self.assertIn("max-age=31536000", h1.resp_headers.get("Cache-Control", ""))
        self.assertIn("immutable", h1.resp_headers.get("Cache-Control", ""))
        etag = h1.resp_headers.get("ETag")
        self.assertTrue(etag, "Static asset response must include ETag")
        self.assertGreater(len(h1.wfile.getvalue()), 1000)

        h2 = _TestableHandler(hashed_js_path, headers={"If-None-Match": etag})
        h2.do_GET()
        self.assertEqual(h2.resp_status, 304)
        self.assertEqual(len(h2.wfile.getvalue()), 0)


if __name__ == "__main__":
    unittest.main()
