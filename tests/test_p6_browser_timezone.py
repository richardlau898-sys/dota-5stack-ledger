import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import dota_analyst
import server
from tests.helpers import load_all_raw_matches


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestP6BrowserTimezone(unittest.TestCase):
    def test_1_report_and_recent_matches_store_unix_start_time(self):
        """报告与最近比赛列表都存储 Unix 时间戳 start_time，且 summary 分片保留 start_time"""
        raw = next(iter(load_all_raw_matches().values()))
        roster = dota_analyst.load_roster()
        expected_ts = int(raw["start_time"])
        report = dota_analyst.analyze_match_data(raw, roster)
        self.assertEqual(report.get("start_time"), expected_ts)

        summary_part = dota_analyst.extract_report_part(report, "summary")
        self.assertEqual(summary_part.get("start_time"), expected_ts)

        fake_recent = [
            {
                "match_id": 8604323503,
                "player_slot": 0,
                "radiant_win": True,
                "start_time": expected_ts,
                "duration": 2400,
                "hero_id": 1,
                "kills": 10,
                "deaths": 2,
                "assists": 8,
                "party_size": 5,
                "version": 22,
            }
        ]
        server._RECENT_MATCHES_CACHE.clear()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with patch.object(server, "REPORTS_DIR", tmp_path), \
                 patch.object(server, "TMP_REPORTS_DIR", tmp_path / "tmp"), \
                 patch.object(server, "api_get", return_value=fake_recent):
                items = server.fetch_recent_matches_formatted(125383759, limit=1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("start_time"), expected_ts)
        self.assertNotIn("start_time_str", items[0])

    def test_2_same_match_displays_identical_start_time_across_server_timezones(self):
        """同一场比赛在 UTC 服务端（线上）和 Asia/Shanghai 服务端（本地）生成后，在浏览器端显示完全相同的开始时间"""
        raw = next(iter(load_all_raw_matches().values()))
        roster = dota_analyst.load_roster()
        orig_tz = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "UTC"
            if hasattr(time, "tzset"):
                time.tzset()
            rep_utc = dota_analyst.analyze_match_data(raw, roster)

            os.environ["TZ"] = "Asia/Shanghai"
            if hasattr(time, "tzset"):
                time.tzset()
            rep_sh = dota_analyst.analyze_match_data(raw, roster)
        finally:
            if orig_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = orig_tz
            if hasattr(time, "tzset"):
                time.tzset()

        self.assertEqual(rep_utc.get("start_time"), rep_sh.get("start_time"))

        js_harness = r"""
const fs = require("fs");
const vm = require("vm");

const appCode = fs.readFileSync(process.argv[1], "utf-8");
const repUtc = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
const repSh = JSON.parse(fs.readFileSync(process.argv[3], "utf-8"));

const elements = new Map();
function makeEl(id = "") {
  return {
    id,
    innerHTML: "",
    textContent: "",
    value: "",
    hidden: false,
    disabled: false,
    style: {},
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
    getBoundingClientRect: () => ({ width: 800, height: 400 }),
    getContext: () => new Proxy({}, { get: () => () => ({ addColorStop: () => {}, width: 50 }), set: () => true }),
  };
}

const sandbox = {
  console,
  Intl,
  Date,
  setTimeout: () => 1,
  clearTimeout: () => {},
  setInterval: () => 1,
  clearInterval: () => {},
  requestAnimationFrame: () => 1,
  devicePixelRatio: 2,
  URLSearchParams,
  URL: { createObjectURL: () => "", revokeObjectURL: () => {} },
  Blob: class {},
  Image: class {},
  Audio: class { play() { return Promise.resolve(); } pause() {} },
  speechSynthesis: { cancel: () => {}, speak: () => {}, getVoices: () => [] },
  SpeechSynthesisUtterance: class {},
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  indexedDB: { open: () => ({}) },
  navigator: { clipboard: { writeText: () => Promise.resolve() } },
  location: { search: "", pathname: "/", href: "http://localhost/", origin: "http://localhost", hash: "" },
  history: { pushState: () => {}, replaceState: () => {}, state: {} },
  addEventListener: () => {},
  removeEventListener: () => {},
  scrollTo: () => {},
  innerWidth: 1440,
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) }),
  document: {
    hidden: false,
    visibilityState: "visible",
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
vm.createContext(sandbox);
vm.runInContext(appCode, sandbox);

if (typeof sandbox.formatMatchStartTime !== "function") {
  console.error("formatMatchStartTime is not defined on frontend");
  process.exit(1);
}

vm.runInContext(`state.workspaceMode = "postgame";`, sandbox);
sandbox.renderMatchOverview(repUtc);
const metaUtc = elements.get("match-meta-line").textContent;
const subUtc = elements.get("ws-location-subtitle").textContent;

sandbox.renderMatchOverview(repSh);
const metaSh = elements.get("match-meta-line").textContent;
const subSh = elements.get("ws-location-subtitle").textContent;

if (!metaUtc || metaUtc !== metaSh) {
  console.error("Mismatch in match-meta-line:", { metaUtc, metaSh });
  process.exit(1);
}
if (!subUtc || subUtc !== subSh) {
  console.error("Mismatch in ws-location-subtitle:", { subUtc, subSh });
  process.exit(1);
}
console.log("P6_OK", sandbox.formatMatchStartTime(repUtc));
"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            p_utc = Path(tmpdir) / "utc.json"
            p_sh = Path(tmpdir) / "sh.json"
            p_utc.write_text(json.dumps(rep_utc, ensure_ascii=False), encoding="utf-8")
            p_sh.write_text(json.dumps(rep_sh, ensure_ascii=False), encoding="utf-8")
            env = dict(os.environ, TZ="Asia/Shanghai")
            proc = subprocess.run(
                ["node", "-e", js_harness, str(REPO_ROOT / "static" / "app.js"), str(p_utc), str(p_sh)],
                capture_output=True,
                text=True,
                env=env,
                timeout=15,
            )
            self.assertEqual(proc.returncode, 0, f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
            self.assertIn("P6_OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
