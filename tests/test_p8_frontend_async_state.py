import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestP8FrontendAsyncState(unittest.TestCase):
    def test_rapid_match_switch_and_stale_async_guards(self):
        script = r"""
const fs = require("fs");
const vm = require("vm");

let code = fs.readFileSync("static/app.js", "utf8");
code = code.replace(/document\.addEventListener\(\s*["']DOMContentLoaded["'][\s\S]*$/, "");
code += "\nglobalThis.state = state;\n";

const elements = {};
function getEl(id) {
  if (!elements[id]) {
    elements[id] = {
      id,
      innerHTML: "",
      textContent: "",
      value: "",
      hidden: false,
      disabled: false,
      open: false,
      style: {},
      dataset: {},
      classList: {
        _set: new Set(),
        add(...cls) { cls.forEach((c) => this._set.add(c)); },
        remove(...cls) { cls.forEach((c) => this._set.delete(c)); },
        toggle(c, force) {
          if (force === undefined) {
            if (this._set.has(c)) { this._set.delete(c); return false; }
            this._set.add(c); return true;
          }
          if (force) this._set.add(c); else this._set.delete(c);
          return Boolean(force);
        },
        contains(c) { return this._set.has(c); }
      },
      setAttribute(k, v) { this[k] = v; },
      getAttribute(k) { return this[k] || null; },
      addEventListener() {},
      removeEventListener() {},
      querySelector() { return null; },
      querySelectorAll() { return []; },
      scrollTo() {},
    };
  }
  return elements[id];
}

const pendingFetches = [];
function mockFetch(url, opts) {
  return new Promise((resolve, reject) => {
    pendingFetches.push({ url: String(url), opts, resolve, reject });
  });
}

const sandbox = {
  window: {
    location: { search: "", pathname: "/", href: "http://localhost/" },
    history: { pushState() {}, replaceState() {} },
    addEventListener() {},
    removeEventListener() {},
    scrollTo() {},
  },
  document: {
    getElementById: (id) => getEl(id),
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: (tag) => getEl("created_" + tag + "_" + Math.random()),
    body: getEl("body"),
  },
  localStorage: {
    _store: {},
    getItem(k) { return this._store[k] || null; },
    setItem(k, v) { this._store[k] = String(v); },
    removeItem(k) { delete this._store[k]; },
  },
  sessionStorage: {
    _store: {},
    getItem(k) { return this._store[k] || null; },
    setItem(k, v) { this._store[k] = String(v); },
    removeItem(k) { delete this._store[k]; },
  },
  Intl,
  Date,
  Math,
  Number,
  String,
  Boolean,
  Array,
  Object,
  Set,
  Map,
  RegExp,
  Error,
  Promise,
  JSON,
   URIError,
  encodeURIComponent,
  decodeURIComponent,
  parseInt,
  parseFloat,
  isNaN,
  isFinite,
  console: { log() {}, warn() {}, error() {} },
  fetch: mockFetch,
  setTimeout: (fn) => { sandbox._lastTimerFn = fn; return 1; },
  clearTimeout: () => {},
  setInterval: () => 1,
  clearInterval: () => {},
  requestAnimationFrame: (fn) => fn(),
};
sandbox.window.document = sandbox.document;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);
vm.runInContext(code, sandbox);

function makeReport(matchId, titleText) {
  return {
    match_id: matchId,
    is_parsed: false,
    radiant_win: true,
    player_Zero: true,
    duration_str: "35:00",
    duration_sec: 2100,
    start_time_ts: 1762000000,
    score_radiant: 30,
    score_dire: 20,
    game_mode_name: "全英雄选择",
    lobby_type_name: "天梯",
    overview_pitch: titleText,
    grok_coaching: { title: titleText },
    players_all: [],
    squad_players: [],
  };
}

(async () => {
  // Initial state: match 100 is loaded
  sandbox.state.accountId = 114933560;
  sandbox.state.currentMatchId = 100;
  sandbox.state.currentReport = makeReport(100, "初始比赛 #100");

  // 1) Rapidly click 3 matches: 901, 902, 903
  const p1 = sandbox.loadMatchReport(901, { analyzeNow: true });
  // Before fetch resolves, currentMatchId MUST remain 100 (not mutated before report arrives)
  if (Number(sandbox.state.currentMatchId) !== 100) {
    throw new Error("currentMatchId mutated before report arrived: " + sandbox.state.currentMatchId);
  }
  const p2 = sandbox.loadMatchReport(902, { analyzeNow: true });
  const p3 = sandbox.loadMatchReport(903, { analyzeNow: true });

  if (pendingFetches.length !== 3) {
    throw new Error("Expected 3 fetches, got " + pendingFetches.length);
  }

  // Resolve M3 first, then M2, then M1 last (out of order)
  pendingFetches[2].resolve({
    status: 200,
    text: async () => JSON.stringify({ ok: true, report: makeReport(903, "最终比赛 #903 标题") }),
  });
  await p3;

  pendingFetches[1].resolve({
    status: 200,
    text: async () => JSON.stringify({ ok: true, report: makeReport(902, "过期比赛 #902 标题") }),
  });
  await p2;

  pendingFetches[0].resolve({
    status: 200,
    text: async () => JSON.stringify({ ok: true, report: makeReport(901, "过期比赛 #901 标题") }),
  });
  await p1;

  if (Number(sandbox.state.currentMatchId) !== 903) {
    throw new Error("Expected currentMatchId 903, got " + sandbox.state.currentMatchId);
  }
  if (Number(sandbox.state.currentReport.match_id) !== 903) {
    throw new Error("Expected currentReport.match_id 903, got " + sandbox.state.currentReport.match_id);
  }
  const titleHtml = getEl("match-overview-title").innerHTML;
  const metaText = getEl("match-meta-line").textContent;
  if (!titleHtml.includes("903") || !metaText.includes("903")) {
    throw new Error("Expected title and meta to match 903, got title=" + titleHtml + ", meta=" + metaText);
  }

  // 2) Button state restored on load failure
  pendingFetches.length = 0;
  const failPromise = sandbox.loadMatchReport(904, { analyzeNow: true });
  const confirmBtn = getEl("btn-confirm-analyze-match");
  if (!confirmBtn.disabled) {
    throw new Error("Expected confirm button to be disabled during analyzeNow load");
  }
  pendingFetches[0].resolve({
    status: 500,
    text: async () => JSON.stringify({ ok: false, error: "模拟失败" }),
  });
  await failPromise;
  if (confirmBtn.disabled) {
    throw new Error("Expected confirm button to be re-enabled after failure");
  }

  // 3) Parse poll stale check after await fetch
  pendingFetches.length = 0;
  sandbox.state.pendingMatchId = null;
  sandbox.state.currentMatchId = 903;
  sandbox.state.currentReport = makeReport(903, "比赛 #903");
  sandbox.scheduleAutoReplayParsePoll(903, 2);
  const pollTimerFn = sandbox._lastTimerFn;
  const pollPromise = pollTimerFn();
  // While poll fetch is in flight for 903, user switches to 905
  sandbox.state.currentMatchId = 905;
  sandbox.state.currentReport = makeReport(905, "比赛 #905");
  pendingFetches[0].resolve({
    status: 200,
    json: async () => ({ ok: true, report: Object.assign(makeReport(903, "过期解析 #903"), { is_parsed: true }) }),
  });
  await pollPromise;
  if (Number(sandbox.state.currentReport.match_id) !== 905) {
    throw new Error("Stale parse poll overwrote currentReport with " + sandbox.state.currentReport.match_id);
  }

  // 4) Grok review stale check after switching match
  pendingFetches.length = 0;
  sandbox.state.currentMatchId = 905;
  sandbox.state.currentReport = makeReport(905, "比赛 #905 原始标题");
  sandbox.state.isGeneratingGrok = false;
  const grokPromise = sandbox.triggerGrokReview({ force: true });
  // While Grok request is in flight for 905, user switches to 906
  sandbox.state.currentMatchId = 906;
  sandbox.state.currentReport = makeReport(906, "比赛 #906 标题");
  pendingFetches[0].resolve({
    status: 200,
    text: async () => JSON.stringify({ ok: true, report: makeReport(905, "比赛 #905 Grok新标题") }),
  });
  await grokPromise;
  if (Number(sandbox.state.currentReport.match_id) !== 906) {
    throw new Error("Stale triggerGrokReview overwrote currentReport with " + sandbox.state.currentReport.match_id);
  }

  // 5) Pregame plan stale check
  pendingFetches.length = 0;
  getEl("pregame-plan-output");
  sandbox.state.pregameOwnPicks = [{ pos: 1, hero_id: 1 }];
  const pg1 = sandbox.requestAndRenderPregamePlan({ useLlm: false });
  sandbox.state.pregameOwnPicks = [{ pos: 1, hero_id: 2 }];
  const pg2 = sandbox.requestAndRenderPregamePlan({ useLlm: false });

  // Resolve pg2 first, then pg1 last
  pendingFetches[1].resolve({
    status: 200,
    json: async () => ({ ok: true, plan: { marker: "NEW_PLAN_HERO_2" } }),
  });
  await pg2;
  pendingFetches[0].resolve({
    status: 200,
    json: async () => ({ ok: true, plan: { marker: "STALE_PLAN_HERO_1" } }),
  });
  await pg1;

  if (sandbox.state.pregamePlan?.marker !== "NEW_PLAN_HERO_2") {
    throw new Error("Stale pregame plan overwrote newer plan: " + JSON.stringify(sandbox.state.pregamePlan));
  }

  console.log("P8_OK");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
"""
        proc = subprocess.run(
            ["node", "-e", script],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0, f"Node test failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
        self.assertIn("P8_OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
