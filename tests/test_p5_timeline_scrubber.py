import json
import subprocess
import unittest
from pathlib import Path

from tests.helpers import build_all_sample_reports

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestP5TimelineScrubber(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reports = build_all_sample_reports()
        cls.parsed_report = next(r for r in reports.values() if r.get("is_parsed"))

    def test_1_floor_minute_index_no_round_30s_early_events(self):
        """时间索引改用 Math.floor 向下取整，避免 01:35 时提前显示第 2 分钟的事件"""
        app_js = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("const idx = Math.round(secNow / 60);", app_js)
        self.assertNotIn("Math.round(clampedSec / 60)", app_js)
        self.assertIn("Math.floor(secNow / 60)", app_js)
        self.assertIn("Math.floor(clampedSec / 60)", app_js)

    def test_2_playback_incremental_dom_and_raf_and_lifecycle_stops(self):
        """播放时不重建整块 minute-scrubber-content DOM；拖动用 requestAnimationFrame 节流；切标签/切模式/页面隐藏时停止定时器"""
        app_js = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("visibilitychange", app_js)

        node_script = r"""
const fs = require("fs");
const vm = require("vm");

const js = fs.readFileSync("static/app.js", "utf8");
const report = JSON.parse(fs.readFileSync(process.env.TEST_REPORT_FILE, "utf8"));

const elements = new Map();
const innerHtmlWrites = new Map();
const docListeners = {};

function makeEl(id = "") {
  const el = {
    id,
    _innerHTML: "",
    textContent: "",
    value: "",
    max: "2400",
    min: "0",
    step: "1",
    options: [],
    files: [],
    hidden: false,
    disabled: false,
    open: false,
    style: {},
    dataset: {},
    listeners: {},
    classList: { add: () => {}, remove: () => {}, toggle: () => {}, contains: () => false },
    setAttribute: function(k, v) { this[k] = v; },
    getAttribute: function(k) { return this[k] || ""; },
    removeAttribute: () => {},
    addEventListener: function(ev, fn) { this.listeners[ev] = fn; },
    removeEventListener: () => {},
    appendChild: () => {},
    querySelector: () => makeEl(),
    querySelectorAll: () => [],
    getBoundingClientRect: () => ({ width: 800, height: 400, top: 0, left: 0 }),
    getContext: () => new Proxy({}, { get: () => () => ({ addColorStop: () => {}, width: 50 }), set: () => true }),
    showModal: function() { this.open = true; },
    close: function() { this.open = false; },
    scrollIntoView: () => {},
    scrollTo: () => {},
    focus: () => {},
    click: () => {},
  };
  Object.defineProperty(el, "innerHTML", {
    get() { return this._innerHTML; },
    set(val) {
      this._innerHTML = val;
      innerHtmlWrites.set(id, (innerHtmlWrites.get(id) || 0) + 1);
      if (typeof val === "string") {
        let mm;
        const r = /\bid=["']([^"']+)["']/g;
        while ((mm = r.exec(val)) !== null) {
          if (!elements.has(mm[1])) elements.set(mm[1], makeEl(mm[1]));
        }
      }
    }
  });
  return el;
}

let rafQueue = [];
const sandbox = {
  console,
  setTimeout: () => 1,
  clearTimeout: () => {},
  setInterval: () => 777,
  clearInterval: () => {},
  requestAnimationFrame: (cb) => { rafQueue.push(cb); return rafQueue.length; },
  devicePixelRatio: 2,
  URLSearchParams,
  URL: { createObjectURL: () => "blob:mock", revokeObjectURL: () => {} },
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
    addEventListener: (ev, fn) => { docListeners[ev] = fn; },
    body: makeEl("body"),
    documentElement: makeEl("html"),
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);
const patchedJs = js.replace(/document\.addEventListener\("DOMContentLoaded",\s*initApp\);/, "") + "\nglobalThis.__state = state;\n";
vm.runInContext(patchedJs, sandbox);

sandbox.bindEvents();
sandbox.__state.currentReport = report;
sandbox.__state.currentMatchId = report.match_id;
sandbox.hydrateReportData(report);
sandbox.renderMinuteScrubber(report);

const writesAfterInit = innerHtmlWrites.get("minute-scrubber-content") || 0;
if (writesAfterInit !== 1) {
  throw new Error("Expected 1 initial innerHTML write to minute-scrubber-content, got " + writesAfterInit);
}

// Scrub 10 consecutive seconds within minute 1 (90s..99s)
const eventsWritesBefore = innerHtmlWrites.get("scrub-events-list") || 0;
for (let s = 90; s < 100; s++) {
  sandbox.setScrubberSecond(s);
}
const writesAfterTicks = innerHtmlWrites.get("minute-scrubber-content") || 0;
if (writesAfterTicks !== 1) {
  throw new Error("minute-scrubber-content innerHTML was rebuilt during playback ticks: " + writesAfterTicks);
}
if (sandbox.__state.scrubberMinute !== 1) {
  throw new Error("At 99s (01:39), scrubberMinute must be 1 (Math.floor), got " + sandbox.__state.scrubberMinute);
}
const eventsWritesAfterSameMin = innerHtmlWrites.get("scrub-events-list") || 0;
if (eventsWritesAfterSameMin > eventsWritesBefore + 1) {
  throw new Error("scrub-events-list should not be rewritten on every second within the same minute");
}

// Verify requestAnimationFrame throttling on input
const rangeEl = sandbox.document.getElementById("minute-scrubber-range");
rafQueue = [];
rangeEl.value = "125";
rangeEl.listeners.input();
rangeEl.value = "126";
rangeEl.listeners.input();
if (rafQueue.length !== 1) {
  throw new Error("Expected 1 queued rAF callback for rapid input events, got " + rafQueue.length);
}
rafQueue[0]();
if (sandbox.__state.scrubberSecond !== 126) {
  throw new Error("Expected rAF callback to apply latest value 126, got " + sandbox.__state.scrubberSecond);
}

// Verify autoplay stops on tab switch, mode switch, and visibilitychange
sandbox.toggleScrubberAutoplay();
if (!sandbox.__state.scrubberPlaying) throw new Error("Expected scrubberPlaying=true");
sandbox.applyPostgameSubTab("summary");
if (sandbox.__state.scrubberPlaying || sandbox.__state.scrubberTimer !== null) {
  throw new Error("Expected applyPostgameSubTab('summary') to stop scrubber autoplay");
}

sandbox.toggleScrubberAutoplay();
if (!sandbox.__state.scrubberPlaying) throw new Error("Expected scrubberPlaying=true");
sandbox.switchWorkspaceMode("home");
if (sandbox.__state.scrubberPlaying || sandbox.__state.scrubberTimer !== null) {
  throw new Error("Expected switchWorkspaceMode('home') to stop scrubber autoplay");
}

sandbox.toggleScrubberAutoplay();
if (!sandbox.__state.scrubberPlaying) throw new Error("Expected scrubberPlaying=true");
sandbox.document.hidden = true;
sandbox.document.visibilityState = "hidden";
if (typeof docListeners.visibilitychange !== "function") {
  throw new Error("Expected visibilitychange listener on document");
}
docListeners.visibilitychange();
if (sandbox.__state.scrubberPlaying || sandbox.__state.scrubberTimer !== null) {
  throw new Error("Expected visibilitychange (hidden) to stop scrubber autoplay");
}
console.log("P5_VM_OK");
"""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
            json.dump(self.parsed_report, tf, ensure_ascii=False)
            tmp_path = tf.name
        try:
            proc = subprocess.run(
                ["node", "-e", node_script],
                cwd=str(REPO_ROOT),
                env={**dict(__import__("os").environ), "TEST_REPORT_FILE": tmp_path},
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(proc.returncode, 0, f"VM test failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
            self.assertIn("P5_VM_OK", proc.stdout)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
