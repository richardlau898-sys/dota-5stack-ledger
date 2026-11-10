import glob
import json
import os
import subprocess
import tempfile
import unittest

from dota_analyst import analyze_match_data


class TestS3XssInjection(unittest.TestCase):
    """S3 · 修复昵称注入（XSS）与后端直接输出 HTML 标签"""

    def test_malicious_personaname_never_unescaped_in_dom_and_no_backend_html_tags(self):
        raw_files = sorted(glob.glob("reports/raw_*.json"))
        self.assertTrue(len(raw_files) > 0, "Expected at least one reports/raw_*.json sample")
        # Pick a parsed sample that triggers unpressed saves / teamfight deaths
        chosen_raw = None
        for rf in raw_files:
            with open(rf, "r", encoding="utf-8") as f:
                candidate = json.load(f)
            if candidate.get("version") and candidate.get("teamfights"):
                rep_probe = analyze_match_data(candidate, {"players": {}})
                inc_r = (rep_probe.get("deep_forensics", {}).get("unpressed_saves_by_side", {}).get("radiant", {}).get("incidents") or [])
                inc_d = (rep_probe.get("deep_forensics", {}).get("unpressed_saves_by_side", {}).get("dire", {}).get("incidents") or [])
                if inc_r or inc_d:
                    chosen_raw = candidate
                    break
        self.assertIsNotNone(chosen_raw)
        raw = chosen_raw

        xss_payload = "<img src=x onerror=alert(1)>"
        raw_copy = dict(raw)
        raw_copy["players"] = []
        for p in raw.get("players", []):
            pc = dict(p)
            pc["personaname"] = xss_payload
            raw_copy["players"].append(pc)

        # Pass empty roster so roster nicknames do not overwrite the XSS personaname
        report = analyze_match_data(raw_copy, {"players": {}})

        # 1. Backend report JSON should not contain raw <b> or </b> HTML tags in lane_chemistry_by_side
        for ln in (report.get("deep_forensics", {}).get("lane_matchups") or []):
            chem = ln.get("lane_chemistry_by_side") or {}
            for side_key, val in chem.items():
                self.assertIsInstance(val, dict)
                self.assertNotIn("<b>", json.dumps(val, ensure_ascii=False))
                self.assertNotIn("</b>", json.dumps(val, ensure_ascii=False))

        # 2. Render all sections and all timeline minutes in headless VM and assert no unescaped <img src=x
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tf:
            json.dump(report, tf, ensure_ascii=False)
            temp_report_path = tf.name

        node_check = r"""
const fs = require("fs");
const vm = require("vm");

const reportPath = process.argv[1];
const html = fs.readFileSync("static/index.html", "utf8");
const js = fs.readFileSync("static/app.js", "utf8");

const idRegex = /\bid=["']([^"']+)["']/g;
const htmlIds = new Set();
let m;
while ((m = idRegex.exec(html)) !== null) htmlIds.add(m[1]);

const leakedSnippets = [];
const elements = new Map();
function makeEl(id = "") {
  const el = {
    id,
    innerHTML: "",
    textContent: "",
    value: "",
    options: [],
    files: [],
    hidden: false,
    disabled: false,
    open: false,
    width: 920,
    height: 620,
    clientWidth: 920,
    clientHeight: 420,
    style: new Proxy({}, { set: () => true, get: () => "" }),
    dataset: {},
    classList: { add: () => {}, remove: () => {}, toggle: () => {}, contains: () => false },
    setAttribute: () => {},
    getAttribute: () => "",
    removeAttribute: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    appendChild: () => {},
    querySelector: () => makeEl(),
    querySelectorAll: () => [],
    getBoundingClientRect: () => ({ width: 800, height: 400, top: 0, left: 0 }),
    getContext: () => new Proxy({}, {
      get: (t, p) => {
        if (p === "measureText") return () => ({ width: 50 });
        if (p === "createLinearGradient" || p === "createRadialGradient") {
          return () => ({ addColorStop: () => {} });
        }
        return () => {};
      },
      set: () => true
    }),
    showModal: function() { this.open = true; },
    close: function() { this.open = false; },
    scrollIntoView: () => {},
    scrollTo: () => {},
    focus: () => {},
    click: () => {},
  };
  return new Proxy(el, {
    set(target, prop, val) {
      target[prop] = val;
      if (prop === "innerHTML" && typeof val === "string") {
        if (val.includes("<img src=x")) {
          const idx = val.indexOf("<img src=x");
          leakedSnippets.push({ id, snippet: val.slice(Math.max(0, idx - 60), idx + 80) });
        }
        let mm;
        const r = /\bid=["']([^"']+)["']/g;
        while ((mm = r.exec(val)) !== null) {
          if (!elements.has(mm[1])) elements.set(mm[1], makeEl(mm[1]));
        }
      }
      return true;
    }
  });
}

for (const id of htmlIds) elements.set(id, makeEl(id));

const sandbox = {
  console,
  setTimeout: () => 1,
  clearTimeout: () => {},
  setInterval: () => 1,
  clearInterval: () => {},
  requestAnimationFrame: () => {},
  devicePixelRatio: 2,
  URLSearchParams,
  URL: { createObjectURL: () => "blob:mock", revokeObjectURL: () => {} },
  Blob: class {},
  Image: class { set src(v) {} },
  Audio: class { play() { return Promise.resolve(); } pause() {} },
  speechSynthesis: { cancel: () => {}, speak: () => {}, getVoices: () => [] },
  SpeechSynthesisUtterance: class {},
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  indexedDB: { open: () => ({ onupgradeneeded: null, onsuccess: null, onerror: null }) },
  navigator: { clipboard: { writeText: () => Promise.resolve() } },
  location: { search: "", pathname: "/", href: "http://localhost/", origin: "http://localhost", hash: "" },
  history: { pushState: () => {}, replaceState: () => {}, state: {} },
  scrollTo: () => {},
  innerWidth: 1440,
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) }),
  document: {
    getElementById: (id) => {
      if (!elements.has(id)) elements.set(id, makeEl(id));
      return elements.get(id);
    },
    querySelector: () => makeEl(),
    querySelectorAll: () => [],
    createElement: (tag) => makeEl(tag),
    addEventListener: () => {},
    body: makeEl("body"),
    documentElement: makeEl("html"),
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);
const patchedJs = js.replace(/initApp\(\);/g, "// initApp();") + "\nglobalThis.__state = state;\n";
vm.runInContext(patchedJs, sandbox);

const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
const microTabs = ["all", "hero_ult", "itemization", "damage_quality", "unpressed_saves", "map_space", "damage_received", "vision", "stack_smoke", "laning", "tp_save", "econ_pings", "role_mirror", "macro_neutrals"];

for (const side of ["radiant", "dire"]) {
  sandbox.__state.perspective = side;
  sandbox.__state.currentReport = report;
  sandbox.__state.currentMatchId = report.match_id;
  sandbox.renderFullMatchReport(report);
  for (const tab of microTabs) {
    sandbox.__state.microTab = tab;
    sandbox.renderTacticalMicroscopeSection(report);
  }
  const snaps = (report.deep_forensics && report.deep_forensics.minute_snapshots) || [];
  for (let m = 0; m < snaps.length; m++) {
    sandbox.setScrubberMinute(m);
  }
  sandbox.openFullscreenStructuredReport(report);
}

if (leakedSnippets.length > 0) {
  console.error("LEAKED_XSS:", JSON.stringify(leakedSnippets, null, 2));
  process.exit(1);
}
"""
        try:
            proc = subprocess.run(
                ["node", "-e", node_check, temp_report_path],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                proc.returncode,
                0,
                f"Unescaped <img src=x found in rendered innerHTML:\n{proc.stderr}\n{proc.stdout}",
            )
        finally:
            if os.path.exists(temp_report_path):
                os.unlink(temp_report_path)


if __name__ == "__main__":
    unittest.main()
