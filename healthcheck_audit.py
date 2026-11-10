#!/usr/bin/env python3
"""
Full-Stack Automated Health Check & Regression Suite for Dota 2 AI Analyst.
Run before every commit/deploy:
    python3 healthcheck_audit.py
Checks:
1. Python syntax compilation across all .py modules.
2. Backend analyze_match_data() across all raw_*.json files + unparsed/stripped match edge cases.
3. Frontend static syntax check (node --check static/app.js).
4. Frontend headless VM execution of renderFullMatchReport, all 13 microscope tabs,
   all minute scrubber frames (0..max), fullscreen report, poster generator, home workspace,
   and unparsed match report with zero [SafeRender] or uncaught exceptions.
"""
import glob
import json
import os
import py_compile
import subprocess
import sys

from dota_analyst import analyze_match_data, get_hero_constants_map
from draft_and_phase_coach import build_pregame_strategy_plan, build_squad_history_ledger


def run_step(title: str):
    print(f"🔍 [HealthCheck] {title}...")


def main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    # 1. Python syntax check
    run_step("1/4 Compiling all Python modules")
    for py_file in sorted(glob.glob("*.py")):
        py_compile.compile(py_file, doraise=True)
    print("  ✅ All Python modules compiled cleanly.")

    # 2. Backend pipeline + unparsed match edge-case check
    run_step("2/4 Running backend analyze_match_data() on raw matches & unparsed edge case")
    roster = json.load(open("roster.json", "r", encoding="utf-8")) if os.path.exists("roster.json") else {}
    raw_files = sorted(glob.glob("reports/raw_*.json"))
    last_raw = None
    for rf in raw_files:
        with open(rf, "r", encoding="utf-8") as f:
            raw = json.load(f)
        last_raw = raw
        rep = analyze_match_data(raw, roster)
        assert rep["match_id"] == raw["match_id"], f"Match ID mismatch in {rf}"

    if last_raw:
        stripped = dict(last_raw)
        for k in ("teamfights", "objectives", "radiant_gold_adv", "radiant_xp_adv", "picks_bans"):
            stripped.pop(k, None)
        stripped["players"] = [dict(p) for p in stripped.get("players", [])]
        for p in stripped["players"]:
            for pk in (
                "lh_t", "dn_t", "gold_t", "xp_t", "purchase_log",
                "ability_uses", "item_uses", "damage_inflictor",
                "damage_targets", "obs_log", "sen_log", "kills_log",
            ):
                p.pop(pk, None)
        rep_unparsed = analyze_match_data(stripped, roster)
        with open("/tmp/dota_healthcheck_unparsed.json", "w", encoding="utf-8") as f:
            json.dump(rep_unparsed, f, ensure_ascii=False)
    ledger = build_squad_history_ledger("reports", roster, [])
    pregame_sample = build_pregame_strategy_plan(
        [{"pos": 1, "hero_id": 11, "player_name": "Flame = ez mute"}, {"pos": 3, "hero_id": 29, "player_name": "Make Your Choice"}],
        [{"pos": 1, "hero_id": 114}, {"pos": 2, "hero_id": 59}],
        roster,
        get_hero_constants_map()[0],
    )
    with open("/tmp/dota_healthcheck_ledger.json", "w", encoding="utf-8") as f:
        json.dump({"ledger": ledger, "pregame": pregame_sample}, f, ensure_ascii=False)
    print(f"  ✅ Backend verified across {len(raw_files)} raw matches + unparsed edge case + squad ledger & pregame plan.")

    # 3. Node syntax check
    run_step("3/4 Checking static/app.js syntax (node --check)")
    subprocess.run(["node", "--check", "static/app.js"], check=True)
    print("  ✅ static/app.js syntax check passed.")

    # 4. Headless VM execution of all frontend renderers
    run_step("4/4 Executing headless VM DOM render & scrubber suite across all match reports")
    node_script = r"""
const fs = require("fs");
const vm = require("vm");

const html = fs.readFileSync("static/index.html", "utf8");
const js = fs.readFileSync("static/app.js", "utf8");

const idRegex = /\bid=["']([^"']+)["']/g;
const htmlIds = new Set();
let m;
while ((m = idRegex.exec(html)) !== null) htmlIds.add(m[1]);

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

let safeRenderErrors = [];
const customConsole = {
  ...console,
  error: (...args) => {
    safeRenderErrors.push(args.map(a => (a && a.stack) ? a.stack : String(a)).join(" "));
    console.error(...args);
  }
};

const sandbox = {
  console: customConsole,
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

const reportFiles = fs.readdirSync("reports")
  .filter(f => /^match_\d+\.json$/.test(f))
  .map(f => "reports/" + f);
if (fs.existsSync("/tmp/dota_healthcheck_unparsed.json")) {
  reportFiles.push("/tmp/dota_healthcheck_unparsed.json");
}

const microTabs = ["all", "teamfight", "hero_exec", "item_audit", "damage_build", "unpressed_save", "vision_deward", "smoke_stack", "map_space", "laning_mech", "tp_save", "econ_pings", "role_mirror", "macro_neutrals"];

let totalChecks = 0;
for (const file of reportFiles) {
  const report = JSON.parse(fs.readFileSync(file, "utf8"));
  for (const side of ["radiant", "dire"]) {
    sandbox.__state.perspective = side;
    sandbox.__state.currentReport = report;
    sandbox.__state.currentMatchId = report.match_id;
    sandbox.renderFullMatchReport(report);
    totalChecks++;
    for (const tab of microTabs) {
      sandbox.__state.microTab = tab;
      sandbox.renderTacticalMicroscopeSection(report);
      totalChecks++;
    }
    const snaps = (report.deep_forensics && report.deep_forensics.minute_snapshots) || [];
    for (let m = 0; m < snaps.length; m++) {
      sandbox.setScrubberMinute(m);
      totalChecks++;
    }
    sandbox.openFullscreenStructuredReport(report);
    totalChecks++;
    for (const pgTab of ["summary", "timeline", "phases", "microscope", "players", "all"]) {
      sandbox.applyPostgameSubTab(pgTab, { scrollTop: true });
      totalChecks++;
    }
    sandbox.renderWorkstationFactCheckSection(report);
    totalChecks++;
    sandbox.toggleScrubberAutoplay();
    sandbox.stopScrubberAutoplay();
    totalChecks++;
    const allP = [...(report.radiant_pos_1_to_5 || []), ...(report.dire_pos_1_to_5 || [])];
    for (const p of allP.slice(0, 2)) {
      sandbox.openSinglePlayerPosterDialog(report, p.player_slot, "MVP", { autoGenerateAiArt: false });
      totalChecks++;
    }
  }
}
if (fs.existsSync("/tmp/dota_healthcheck_ledger.json")) {
  const extra = JSON.parse(fs.readFileSync("/tmp/dota_healthcheck_ledger.json", "utf8"));
  sandbox.__state.squadLedger = extra.ledger;
  sandbox.__state.pregameOwnPicks = [{ pos: 1, hero_id: 11, player_name: "Flame = ez mute" }, { pos: 3, hero_id: 29, player_name: "Make Your Choice" }];
  sandbox.renderPregameSlots();
  sandbox.renderPregameHeroGrid();
  sandbox.renderPregamePlanOutput(extra.pregame);
  totalChecks += 3;
}
sandbox.renderHomeWorkspace();
totalChecks++;
for (const sf of ["all", "analyzed", "party", "win", "loss"]) {
  sandbox.__state.wsSidebarFilter = sf;
  sandbox.renderWorkstationSidebarMatches();
  totalChecks++;
}
for (const reqId of ["ws-app-shell", "ws-sidebar", "ws-sidebar-match-list", "ws-postgame-view-bar", "ws-factcheck-section"]) {
  if (!htmlIds.has(reqId)) {
    safeRenderErrors.push("Missing required Workstation DOM ID: " + reqId);
  }
}

if (safeRenderErrors.length > 0) {
  console.error("Failed with SafeRender / console.error exceptions:", safeRenderErrors);
  process.exit(1);
}
console.log(`  ✅ Executed ${totalChecks} frontend render & timeline scrubber checks with ZERO errors!`);
"""
    subprocess.run(["node", "-e", node_script], check=True)
    print("\n🎉 ALL FULL-STACK HEALTH CHECKS PASSED!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
