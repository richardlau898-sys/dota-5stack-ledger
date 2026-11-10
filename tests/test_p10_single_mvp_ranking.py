import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from dota_analyst import analyze_match_data, load_roster
from tests.helpers import load_all_raw_matches

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestP10SingleMvpRanking(unittest.TestCase):
    def test_1_backend_computes_canonical_rankings_by_side(self):
        roster = load_roster()
        raw_matches = load_all_raw_matches()
        for mid, raw in list(raw_matches.items())[:8]:
            rep = analyze_match_data(raw, roster)
            mvp_block = rep.get("mvp") or {}
            rankings = mvp_block.get("rankings_by_side")
            self.assertIsInstance(rankings, dict, f"match {mid} missing mvp.rankings_by_side")
            for side in ("radiant", "dire"):
                self.assertIn(side, rankings)
                side_rank = rankings[side]
                for key in (
                    "mvp_slot",
                    "runner_up_slot",
                    "culprit_slot",
                    "second_culprit_slot",
                    "contrib_order_slots",
                    "blame_order_slots",
                ):
                    self.assertIn(key, side_rank, f"match {mid} {side} missing {key}")
                self.assertEqual(len(side_rank["contrib_order_slots"]), 5)
                self.assertEqual(len(side_rank["blame_order_slots"]), 5)
                self.assertEqual(side_rank["mvp_slot"], side_rank["contrib_order_slots"][0])
                self.assertEqual(side_rank["culprit_slot"], side_rank["blame_order_slots"][0])

            for p in rep["radiant_pos_1_to_5"] + rep["dire_pos_1_to_5"]:
                self.assertIn("score_100", p)
                self.assertIn("contrib_rank", p)
                self.assertIn("blame_rank", p)

    def test_2_five_frontend_Consumers_read_identical_mvp_and_culprit(self):
        roster = load_roster()
        raw_matches = load_all_raw_matches()
        reports = [analyze_match_data(raw, roster) for _, raw in list(raw_matches.items())[:6]]

        script = r"""
const fs = require("fs");
const vm = require("vm");

let code = fs.readFileSync("static/app.js", "utf8");
code = code.replace(/document\.addEventListener\(\s*["']DOMContentLoaded["'][\s\S]*$/, "");
code += "\nglobalThis.state = state;\n";

let lastSpokenText = "";
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
        toggle(c, force) { return Boolean(force); },
        contains(c) { return this._set.has(c); }
      },
      setAttribute() {},
      getAttribute() { return null; },
      addEventListener() {},
      removeEventListener() {},
      querySelector() { return null; },
      querySelectorAll() { return []; },
      scrollTo() {},
    };
  }
  return elements[id];
}

function SpeechSynthesisUtteranceMock(text) {
  this.text = text;
}

const sandbox = {
  window: {
    location: { search: "", pathname: "/", href: "http://localhost/" },
    history: { pushState() {}, replaceState() {} },
    addEventListener() {},
    removeEventListener() {},
    scrollTo() {},
    speechSynthesis: {
      speaking: false,
      cancel() {},
      speak(u) { lastSpokenText = u.text; }
    },
    SpeechSynthesisUtterance: SpeechSynthesisUtteranceMock,
  },
  SpeechSynthesisUtterance: SpeechSynthesisUtteranceMock,
  document: {
    getElementById: (id) => getEl(id),
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: (tag) => getEl("created_" + tag + "_" + Math.random()),
    body: getEl("body"),
  },
  localStorage: { _s: {}, getItem(k) { return this._s[k] || null; }, setItem(k, v) { this._s[k] = String(v); }, removeItem(k) { delete this._s[k]; } },
  sessionStorage: { _s: {}, getItem(k) { return this._s[k] || null; }, setItem(k, v) { this._s[k] = String(v); }, removeItem(k) { delete this._s[k]; } },
  Intl, Date, Math, Number, String, Boolean, Array, Object, Set, Map, RegExp, Error, Promise, JSON, URIError,
  encodeURIComponent, decodeURIComponent, parseInt, parseFloat, isNaN, isFinite,
  console: { log() {}, warn() {}, error() {} },
  fetch: async () => ({ status: 200, json: async () => ({ ok: true }), text: async () => "{}" }),
  setTimeout: () => 1,
  clearTimeout: () => {},
  setInterval: () => 1,
  clearInterval: () => {},
  requestAnimationFrame: (fn) => fn(),
};
sandbox.window.document = sandbox.document;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);
vm.runInContext(code, sandbox);

if (typeof sandbox.getCanonicalSideRanking !== "function") {
  throw new Error("getCanonicalSideRanking helper is not defined in static/app.js");
}

const reports = JSON.parse(fs.readFileSync(process.env.REPORTS_FILE, "utf8"));
for (const rep of reports) {
  for (const perspective of ["radiant", "dire"]) {
    sandbox.state.perspective = perspective;
    sandbox.state.currentReport = rep;
    sandbox.hydrateReportData(rep);

    const ranking = sandbox.getCanonicalSideRanking(rep, perspective);
    const expectedMvp = ranking.mvpPlayer;
    const expectedCulprit = ranking.culpritPlayer;
    if (!expectedMvp || !expectedCulprit) {
      throw new Error("Missing mvpPlayer or culpritPlayer from getCanonicalSideRanking");
    }

    // 1. Verdict & Blame cards
    sandbox.state.verdictActiveCard = "focus";
    sandbox.renderVerdictAndBlameSection(rep);
    const mvpCardHtml = getEl("verdict-grid-3col").innerHTML;
    const expectedCardHero = ranking.ownWon ? expectedMvp.hero_short_zh : expectedCulprit.hero_short_zh;
    if (!mvpCardHtml.includes(expectedCardHero)) {
      throw new Error(`Card hero mismatch on ${rep.match_id} (${perspective}): expected ${expectedCardHero}`);
    }

    // 2. Workstation FactCheck key numbers table
    sandbox.renderWorkstationFactCheckSection(rep);
    const fcHtml = getEl("ws-factcheck-section").innerHTML;
    if (!fcHtml.includes(expectedMvp.hero_short_zh)) {
      throw new Error(`FactCheck table missing MVP ${expectedMvp.hero_short_zh}`);
    }

    // 3. Players Forensics spotlight default
    sandbox.state.activeTeamTab = "own";
    sandbox.state.forensicSelectedSlot = "focus";
    sandbox.renderPlayersForensicsList(rep);
    const playersHtml = getEl("players-forensics-container").innerHTML;
    const expectedSpotlight = ranking.ownWon ? expectedMvp : expectedCulprit;
    if (!playersHtml.includes(expectedSpotlight.hero_short_zh)) {
      throw new Error(`Players forensics spotlight mismatch: expected ${expectedSpotlight.hero_short_zh}`);
    }

    // 4. Fullscreen / PDF structured report
    const fsHtml = sandbox.buildStructuredFullReportHtml(rep);
    const expectedHeadlineHero = ranking.ownWon ? expectedMvp.hero_short_zh : expectedCulprit.hero_short_zh;
    if (!fsHtml.includes(`${expectedHeadlineHero} (`)) {
      throw new Error(`Fullscreen/PDF headline hero mismatch: expected ${expectedHeadlineHero}`);
    }

    // 5. Voice broadcast
    lastSpokenText = "";
    sandbox.window.speechSynthesis.speaking = false;
    sandbox.toggleVoiceBroadcast();
    if (!lastSpokenText.includes(expectedMvp.hero_short_zh)) {
      throw new Error(`Voice broadcast MVP mismatch: expected ${expectedMvp.hero_short_zh} in '${lastSpokenText}'`);
    }
    if (!ranking.ownWon && !lastSpokenText.includes(expectedCulprit.hero_short_zh)) {
      throw new Error(`Voice broadcast culprit mismatch: expected ${expectedCulprit.hero_short_zh} in '${lastSpokenText}'`);
    }
  }
}

console.log("P10_OK");
"""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(reports, tmp, ensure_ascii=False)
            tmp_path = tmp.name
        try:
            env = dict(**subprocess.os.environ, REPORTS_FILE=tmp_path)
            proc = subprocess.run(
                ["node", "-e", script],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(proc.returncode, 0, f"Node test failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
            self.assertIn("P10_OK", proc.stdout)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
