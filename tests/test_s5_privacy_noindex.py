import glob
import os
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

import server


class TestS5PrivacyNoindex(unittest.TestCase):
    """S5 · 隐私与收录：meta robots noindex、X-Robots-Tag: noindex、移除代码中写死的 Steam ID 与队友昵称"""

    def test_index_html_has_meta_robots_noindex(self):
        with open("static/index.html", "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn('<meta name="robots" content="noindex"', html)

    def test_server_responses_include_x_robots_tag_noindex(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.DotaAnalystHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
                self.assertEqual(resp.headers.get("X-Robots-Tag"), "noindex")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_no_hardcoded_steam_id_or_squad_nicknames_in_code(self):
        target_files = sorted(glob.glob("*.py")) + sorted(glob.glob("static/*"))
        forbidden_literals = [
            "86080912",
            "Flame = ez mute",
            "Make Your Choice",
            "Mr. Brightside",
            "Paphets",
            "Replica",
            "Siesta",
        ]
        violations = []
        for path in target_files:
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            for lit in forbidden_literals:
                if lit in content:
                    violations.append(f"{path}: contains '{lit}'")
        self.assertEqual(violations, [], "Found hardcoded Steam ID or squad nicknames:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
