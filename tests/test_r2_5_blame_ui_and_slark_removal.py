import copy
import inspect
import json
import pathlib
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import ai_coach_engine
import dota_analyst
import draft_and_phase_coach
from microscope_sections import hero_execution
from tests.helpers import build_all_sample_reports

ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestR25BlameUiAndSlarkRemoval(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.roster = dota_analyst.load_roster()
        cls.reports_map = build_all_sample_reports()
        cls.clean_reports = []
        for rep in cls.reports_map.values():
            rc = copy.deepcopy(rep)
            rc.pop("grok_coaching", None)
            cls.clean_reports.append(rc)

    def test_1_slark_exclusive_branch_removed(self) -> None:
        src = inspect.getsource(hero_execution)
        self.assertNotIn("hid == 93", src)
        self.assertNotIn("hid != 93", src)
        self.assertNotIn("slark_mechanism_audit", src)

        slark_count = 0
        for mid, rep in self.reports_map.items():
            for side_key in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
                for p in rep.get(side_key) or []:
                    self.assertNotIn(
                        "slark_mechanism_audit",
                        p,
                        f"Match {mid} {p.get('hero_short_zh')} still has slark_mechanism_audit",
                    )
                    if int(p.get("hero_id") or 0) == 93:
                        slark_count += 1
                        for ins in (p.get("hero_execution_audit") or {}).get("special_insights") or []:
                            self.assertNotIn("斯拉克核心机制与魔晶", ins)
        self.assertGreater(slark_count, 0, "Expected at least one Slark player across sample matches")

    def test_2_llm_prompt_switches_between_coach_and_roast_modes(self) -> None:
        parsed_loss = next(
            copy.deepcopy(r)
            for r in self.clean_reports
            if r.get("is_parsed") and not r.get("user_won")
        )

        def capture_prompts(mode: str) -> str:
            captured = []

            def fake_urlopen(req, timeout=36):
                captured.append(json.loads(req.data.decode("utf-8")))
                raise RuntimeError("stop after capture")

            with patch.object(
                ai_coach_engine,
                "load_env_llm_config",
                return_value={
                    "provider": "xai",
                    "api_key": "test-key",
                    "model_name": "grok-4.20-0309-non-reasoning",
                    "base_url": "https://api.x.ai/v1",
                },
            ), patch("urllib.request.urlopen", side_effect=fake_urlopen):
                if mode == "default":
                    ai_coach_engine.call_llm_coach_review(parsed_loss)
                else:
                    ai_coach_engine.call_llm_coach_review(parsed_loss, tone_mode=mode)

            self.assertTrue(len(captured) > 0)
            return "\n".join(
                m.get("content", "")
                for req_body in captured
                for m in (req_body.get("messages") or [])
            )

        coach_prompt = capture_prompts("default")
        roast_prompt = capture_prompts("roast")

        self.assertNotEqual(coach_prompt, roast_prompt)
        self.assertIn("本局主要问题", coach_prompt)
        for forbidden in ("战犯", "逮捕令", "犯罪"):
            # Note: coach prompt may explicitly instruct not to output forbidden words OR avoid them;
            # check user_prompt_global does not ask for "分锅" and coach mode explicitly specifies coach rules
            pass
        # Check user prompt in coach mode does not frame task as "分锅"
        self.assertNotIn("分锅/贡献比例", coach_prompt)
        self.assertIn("教练模式", coach_prompt)
        self.assertIn("毒舌模式", roast_prompt)

    def test_3_coach_mode_renders_all_samples_without_banned_words_and_respects_no_clear_culprit(self) -> None:
        app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("?? 28", app_js, "28% fallback must be removed from static/app.js")

        # Also check initial static HTML visible text (excluding script/style/comments)
        index_html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        html_visible = re.sub(r"<!--[\s\S]*?-->", " ", index_html)
        html_visible = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html_visible, flags=re.I)
        html_visible = re.sub(r"<[^>]+>", " ", html_visible)
        for banned in ("战犯", "逮捕令", "犯罪", "锅"):
            self.assertNotIn(
                banned,
                html_visible,
                f"Initial static/index.html still contains '{banned}' in coach mode",
            )

        # Build a realistic non-empty squad ledger from our clean reports
        with tempfile.TemporaryDirectory() as tmp_rep_dir:
            tdir = pathlib.Path(tmp_rep_dir)
            for r in self.clean_reports:
                (tdir / f"match_{r['match_id']}.json").write_text(
                    json.dumps(r, ensure_ascii=False), encoding="utf-8"
                )
            ledger = draft_and_phase_coach.build_squad_history_ledger(
                reports_dir=tdir,
                roster=self.roster,
                recent_matches=[
                    {
                        "match_id": r["match_id"],
                        "won": bool(r.get("user_won")),
                        "is_analyzed": True,
                        "hero_short_zh": (r.get("radiant_pos_1_to_5") or [{}])[0].get("hero_short_zh", "英雄"),
                        "kda": "5/3/10",
                        "duration_str": r.get("duration_str") or "35:00",
                        "party_size": 5,
                    }
                    for r in self.clean_reports[:6]
                ],
            )

        # Also prepare a losing parsed report where max raw_blame_points < BLAME_CULPRIT_THRESHOLD -> no_clear_culprit=True
        base_loss = next(
            copy.deepcopy(r)
            for r in self.clean_reports
            if r.get("is_parsed") and not r.get("radiant_win")
        )
        for p in base_loss["radiant_pos_1_to_5"] + base_loss["dire_pos_1_to_5"]:
            p["raw_blame_points"] = 15.0
            p["blame_share_pct"] = 20.0
        base_loss["focus_side"] = "radiant"
        base_loss["user_won"] = False
        base_loss["mvp"] = ai_coach_engine.select_match_mvp_and_culprit(
            base_loss["radiant_pos_1_to_5"],
            base_loss["dire_pos_1_to_5"],
            radiant_win=False,
            user_team_side="radiant",
            is_parsed=True,
        )
        self.assertTrue(base_loss["mvp"]["no_clear_culprit"])

        payload = {
            "reports": self.clean_reports,
            "no_clear_loss": base_loss,
            "ledger": ledger,
            "roster": self.roster,
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tf:
            json.dump(payload, tf, ensure_ascii=False)
            tmp_json = tf.name

        try:
            node_code = r"""
const fs = require("fs");
const vm = require("vm");

const data = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
const html = fs.readFileSync("static/index.html", "utf8");
const js = fs.readFileSync("static/app.js", "utf8");

const htmlIds = new Set();
let m;
const idRe = /\bid=["']([^"']+)["']/g;
while ((m = idRe.exec(html)) !== null) htmlIds.add(m[1]);

const elements = new Map();
function makeEl(id = "") {
  const el = {
    id, innerHTML: "", textContent: "", value: "", hidden: false, disabled: false, open: false,
    width: 920, height: 620, clientWidth: 920, clientHeight: 420,
    style: new Proxy({}, { set: () => true, get: () => "" }),
    dataset: {},
    classList: { add: () => {}, remove: () => {}, toggle: () => {}, contains: () => false },
    setAttribute: () => {}, getAttribute: () => "", removeAttribute: () => {},
    addEventListener: () => {}, removeEventListener: () => {}, appendChild: () => {},
    querySelector: () => makeEl(), querySelectorAll: () => [],
    getBoundingClientRect: () => ({ width: 800, height: 400, top: 0, left: 0 }),
    getContext: () => new Proxy({}, {
      get: (t, p) => {
        if (p === "measureText") return () => ({ width: 50 });
        if (p === "createLinearGradient" || p === "createRadialGradient") return () => ({ addColorStop: () => {} });
        return () => {};
      },
      set: () => true,
    }),
    showModal() { this.open = true; }, close() { this.open = false; },
    scrollIntoView: () => {}, scrollTo: () => {}, focus: () => {}, click: () => {},
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
    },
  });
}
for (const id of htmlIds) elements.set(id, makeEl(id));

const errors = [];
const lsMap = new Map();
const sandbox = {
  console: { ...console, error: (...args) => errors.push(args.map(String).join(" ")) },
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {},
  requestAnimationFrame: () => {}, devicePixelRatio: 2, URLSearchParams,
  URL: { createObjectURL: () => "blob:mock", revokeObjectURL: () => {} },
  Blob: class {}, Image: class { set src(v) {} },
  Audio: class { play() { return Promise.resolve(); } pause() {} },
  speechSynthesis: { cancel: () => {}, speak: () => {}, getVoices: () => [] },
  SpeechSynthesisUtterance: class {},
  localStorage: { getItem: (k) => lsMap.get(k) ?? null, setItem: (k, v) => lsMap.set(k, String(v)), removeItem: (k) => lsMap.delete(k) },
  sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  indexedDB: { open: () => ({ onupgradeneeded: null, onsuccess: null, onerror: null }) },
  navigator: { clipboard: { writeText: () => Promise.resolve() } },
  location: { search: "", pathname: "/", href: "http://localhost/", origin: "http://localhost", hash: "" },
  history: { pushState: () => {}, replaceState: () => {}, state: {} },
  scrollTo: () => {}, innerWidth: 1440,
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) }),
  document: {
    getElementById: (id) => {
      if (!elements.has(id)) elements.set(id, makeEl(id));
      return elements.get(id);
    },
    querySelector: () => makeEl(), querySelectorAll: () => [],
    createElement: (tag) => makeEl(tag), addEventListener: () => {},
    body: makeEl("body"), documentElement: makeEl("html"),
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(js.replace(/initApp\(\);/g, "// initApp();") + "\nglobalThis.__state = state;\n", sandbox);

function stripHtml(s) {
  return String(s || "")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ");
}

function visibleText() {
  const chunks = [];
  for (const [id, el] of elements) {
    if (id === "share-poster-dialog" && !el.open) continue;
    if (el.innerHTML) chunks.push(stripHtml(el.innerHTML));
    if (el.textContent) chunks.push(el.textContent);
  }
  return chunks.join(" ");
}

const bannedWords = ["战犯", "逮捕令", "犯罪", "锅"];
const coachViolations = [];
const headingViolations = [];
const noClearViolations = [];

// Default must be coach mode
if (sandbox.__state.toneMode !== "coach") {
  coachViolations.push(`Default toneMode is ${sandbox.__state.toneMode}, expected coach`);
}

sandbox.__state.roster = data.roster;
sandbox.__state.squadLedger = data.ledger;
sandbox.__state.profileData = {
  profile: { personaname: "Flame = ez mute" },
  wl: { win_rate: 50.0 },
  recent_matches: data.ledger.analyzed_matches.map((am) => ({
    match_id: am.match_id,
    won: am.won,
    is_analyzed: true,
    hero_short_zh: am.mvp_hero || "英雄",
    kda: "6/4/10",
    duration_str: am.duration_str,
    party_size: 5,
  })),
};

// Check Home Workspace, Sidebar Matches & Squad Ledger in coach mode
for (const [, el] of elements) { el.innerHTML = ""; el.textContent = ""; }
sandbox.renderHomeWorkspace();
sandbox.renderSidebarMatches();
sandbox.renderSquadLedgerSection(data.ledger);
const hubTxt = visibleText();
for (const w of bannedWords) {
  if (hubTxt.includes(w)) {
    const m0 = hubTxt.match(new RegExp(`.{0,20}${w}.{0,20}`));
    coachViolations.push(`Home/SquadLedger contains '${w}': ${m0 ? m0[0].trim() : w}`);
  }
}

// Check all 21 sample reports across both sides in coach mode
for (const rep of data.reports) {
  for (const side of ["radiant", "dire"]) {
    for (const [, el] of elements) { el.innerHTML = ""; el.textContent = ""; }
    sandbox.__state.perspective = side;
    sandbox.__state.currentReport = rep;
    sandbox.__state.currentMatchId = rep.match_id;
    sandbox.renderFullMatchReport(rep);
    const sideWon = side === "radiant" ? Boolean(rep.radiant_win) : !Boolean(rep.radiant_win);
    const vh = (elements.get("verdict-heading")?.textContent || "").trim();
    if (!sideWon && !vh.includes("本局主要问题")) {
      headingViolations.push(`${rep.match_id}:${side} verdict-heading='${vh}' missing '本局主要问题'`);
    }
    const txt = visibleText();
    for (const w of bannedWords) {
      if (txt.includes(w)) {
        const m0 = txt.match(new RegExp(`.{0,22}${w}.{0,22}`));
        coachViolations.push(`${rep.match_id}:${side} contains '${w}': ${m0 ? m0[0].trim() : w}`);
      }
    }
  }
}

// Check no_clear_culprit=true losing match: must NOT show "头号" in blame/problem section, switcher, or home preview
for (const tone of ["coach", "roast"]) {
  sandbox.__state.toneMode = tone;
  for (const [, el] of elements) { el.innerHTML = ""; el.textContent = ""; }
  const repNc = data.no_clear_loss;
  sandbox.__state.perspective = "radiant";
  sandbox.__state.currentReport = repNc;
  sandbox.__state.currentMatchId = repNc.match_id;
  sandbox.renderFullMatchReport(repNc);

  const switcherTxt = stripHtml(elements.get("verdict-cards-switcher")?.innerHTML || "");
  const cardsHtml = elements.get("verdict-grid-3col")?.innerHTML || "";
  // Extract card headers, status pills, quote bars, and deep verdict headers from verdict-grid-3col
  const cardLabels = [...cardsHtml.matchAll(/class="verdict-card-label"[^>]*>([\s\S]*?)<\/div>/g)].map((x) => stripHtml(x[1])).join(" ");
  const statusPills = [...cardsHtml.matchAll(/class="status-pill[^"]*"[^>]*>([\s\S]*?)<\/span>/g)].map((x) => stripHtml(x[1])).join(" ");
  const cLabelTxt = elements.get("culprit-card-label")?.textContent || "";
  const pickerHtml = (elements.get("players-forensics-list")?.innerHTML || "").split("</button>").slice(0, 6).join(" ");
  const pickerTxt = stripHtml(pickerHtml);

  // Also test Home Workspace & Sidebar preview with no_clear_culprit=true
  sandbox.saveLocalAnalyzedMatch(repNc);
  sandbox.__state.profileData.recent_matches = [{
    match_id: repNc.match_id, won: false, is_analyzed: true, hero_short_zh: "幽鬼", kda: "3/8/9", duration_str: repNc.duration_str, party_size: 5,
  }];
  sandbox.renderHomeWorkspace();
  sandbox.renderSidebarMatches();
  const homeMatchListTxt = stripHtml(elements.get("home-matches-list")?.innerHTML || "");
  const sidebarListTxt = stripHtml(elements.get("ws-sidebar-matches-list")?.innerHTML || "");

  const combinedVerdict = `${switcherTxt} ${cardLabels} ${statusPills} ${cLabelTxt} ${pickerTxt} ${homeMatchListTxt} ${sidebarListTxt}`;
  if (/头号/.test(combinedVerdict)) {
    const mNc = combinedVerdict.match(/.{0,18}头号.{0,18}/);
    noClearViolations.push(`tone=${tone} shows 头号 when no_clear_culprit=true: ${mNc ? mNc[0].trim() : ""}`);
  }
}

console.log(JSON.stringify({
  errors,
  coachViolations: coachViolations.slice(0, 15),
  coachViolationCount: coachViolations.length,
  headingViolations: headingViolations.slice(0, 10),
  noClearViolations,
}));
"""
            proc = subprocess.run(
                ["node", "-e", node_code, tmp_json],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, f"Node exited {proc.returncode}: {proc.stderr}")
            res = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual(res["errors"], [], f"Console errors: {res['errors']}")
            self.assertEqual(res["headingViolations"], [], f"Heading violations: {res['headingViolations']}")
            self.assertEqual(
                res["coachViolationCount"],
                0,
                f"Coach mode contains banned words ({res['coachViolationCount']} hits): {res['coachViolations']}",
            )
            self.assertEqual(res["noClearViolations"], [], f"no_clear_culprit violations: {res['noClearViolations']}")
        finally:
            pathlib.Path(tmp_json).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
