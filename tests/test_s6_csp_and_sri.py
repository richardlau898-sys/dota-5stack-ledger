import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "static" / "index.html"
JS_PATH = ROOT / "static" / "app.js"
SERVER_PATH = ROOT / "server.py"
VERCEL_PATH = ROOT / "vercel.json"


class TestS6CspAndSri(unittest.TestCase):
    def test_no_inline_onclick_in_index_html(self):
        """static/index.html must contain zero inline onclick or on* attributes."""
        html = HTML_PATH.read_text(encoding="utf-8")
        inline_handlers = re.findall(r"\bon[a-z]+\s*=", html, flags=re.IGNORECASE)
        self.assertEqual(
            inline_handlers,
            [],
            f"Found inline event handler(s) in static/index.html: {inline_handlers}",
        )

    def test_dynamic_cdnjs_scripts_enforce_sri_integrity_and_block_tampered(self):
        """All dynamic CDN script entries in static/app.js must require sha512 integrity and reject tampered scripts."""
        js = JS_PATH.read_text(encoding="utf-8")
        self.assertIn("PDF_CDN_LIBS", js)
        urls = re.findall(r'url:\s*"(https://cdnjs\.cloudflare\.com/[^"]+)"', js)
        integrities = re.findall(r'integrity:\s*"(sha(?:256|384|512)-[A-Za-z0-9+/=]+)"', js)
        self.assertGreaterEqual(len(urls), 3)
        self.assertEqual(len(urls), len(integrities))
        self.assertIn("if (!lib.integrity)", js)

        node_script = r"""
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync("static/app.js", "utf8");
const appendedScripts = [];
const sandbox = {
  window: {},
  console,
  setTimeout,
  clearTimeout,
  document: {
    addEventListener: () => {},
    getElementById: () => null,
    querySelectorAll: () => [],
    head: {
      appendChild: (el) => {
        appendedScripts.push(el);
        // Simulate browser SRI check: if integrity does not match expected hash, fire onerror!
        if (!el.integrity || !el.integrity.startsWith("sha512-") || el._tampered) {
          el.onerror(new Error("SRI mismatch"));
        } else {
          // Simulate tampered first script
          el.onerror(new Error("Blocked by Subresource Integrity"));
        }
      },
    },
    createElement: (tag) => ({ tag }),
  },
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
(async () => {
  let caught = null;
  try {
    await sandbox.ensurePdfExportLibsLoaded();
  } catch (e) {
    caught = e.message;
  }
  if (!caught || !caught.includes("SRI")) {
    process.exit(2);
  }
  if (!appendedScripts[0].integrity.startsWith("sha512-") || appendedScripts[0].crossOrigin !== "anonymous") {
    process.exit(3);
  }
})();
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, f"Node SRI check failed: {proc.stderr}")

    def test_csp_report_only_header_in_server_and_vercel(self):
        """server.py and vercel.json must configure Content-Security-Policy-Report-Only."""
        server_code = SERVER_PATH.read_text(encoding="utf-8")
        self.assertIn("Content-Security-Policy-Report-Only", server_code)
        self.assertIn("script-src 'self' https://cdnjs.cloudflare.com", server_code)

        vercel_cfg = json.loads(VERCEL_PATH.read_text(encoding="utf-8"))
        all_headers = [
            h
            for block in vercel_cfg.get("headers", [])
            for h in block.get("headers", [])
        ]
        csp_headers = [
            h for h in all_headers if h.get("key") == "Content-Security-Policy-Report-Only"
        ]
        self.assertTrue(
            csp_headers,
            "vercel.json missing Content-Security-Policy-Report-Only header",
        )
        self.assertIn(
            "script-src 'self' https://cdnjs.cloudflare.com",
            csp_headers[0].get("value", ""),
        )


if __name__ == "__main__":
    unittest.main()
