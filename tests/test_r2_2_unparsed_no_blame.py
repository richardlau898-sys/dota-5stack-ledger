import copy
import json
import pathlib
import re
import subprocess
import tempfile
import unittest

import dota_analyst
from tests.helpers import iter_report_strings

ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestR22UnparsedNoBlame(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.roster = dota_analyst.load_roster()
        raw_path = ROOT / "reports" / "raw_8646427108.json"
        cls.raw_unparsed = json.loads(raw_path.read_text(encoding="utf-8"))
        cls.rep_unparsed = dota_analyst.analyze_match_data(cls.raw_unparsed, cls.roster)
        cls.rep_unparsed.pop("grok_coaching", None)

    def test_1_unparsed_match_8646427108_does_not_compute_blame_or_late_harvest_failure(self) -> None:
        self.assertFalse(self.rep_unparsed.get("is_parsed"))
        all_players = (self.rep_unparsed.get("radiant_pos_1_to_5") or []) + (
            self.rep_unparsed.get("dire_pos_1_to_5") or []
        )
        self.assertEqual(len(all_players), 10)
        for p in all_players:
            hero = p.get("hero_short_zh")
            hmp = p.get("hero_mechanism_profile") or {}
            self.assertFalse(
                hmp.get("late_harvest_failed"),
                f"{hero}: 未解析比赛后期数据为空时不得判 late_harvest_failed",
            )
            self.assertFalse(
                hmp.get("late_harvest_fulfilled"),
                f"{hero}: 未解析比赛后期数据为空时不得判 late_harvest_fulfilled",
            )
            self.assertFalse(
                hmp.get("mid_tempo_wasted"),
                f"{hero}: 未解析比赛中期数据为空时不得判 mid_tempo_wasted",
            )
            for w in p.get("weaknesses") or []:
                self.assertNotIn("后期收割违约", w)
                self.assertNotIn("只刷不C", w)
            self.assertIsNone(
                p.get("raw_blame_points"),
                f"{hero}: 未解析比赛不得计算 raw_blame_points，实际为 {p.get('raw_blame_points')}",
            )
            self.assertIsNone(
                p.get("blame_share_pct"),
                f"{hero}: 未解析比赛不得计算 blame_share_pct，实际为 {p.get('blame_share_pct')}",
            )
            self.assertIsNone(
                p.get("blame_rank"),
                f"{hero}: 未解析比赛不得计算 blame_rank，实际为 {p.get('blame_rank')}",
            )

        mvp = self.rep_unparsed.get("mvp") or {}
        self.assertTrue(mvp.get("no_clear_culprit"))
        self.assertIsNone((mvp.get("culprit_player") or {}).get("blame_share_pct"))
        self.assertIsNone((mvp.get("second_culprit_player") or {}).get("blame_share_pct"))
        self.assertEqual(mvp.get("focus_team_blame_ranking"), [])

    def test_2_unparsed_match_8646427108_has_zero_zero_based_verdicts(self) -> None:
        forbidden_regex = re.compile(
            r"(?<![\d.])(0\.0%|0%|0分00秒|0分0秒|0m00s|0\.0\s*秒|\+0\s*金|0\s*伤害|0\s*块钱)"
            r"|20%后期伤害|后期收割违约|刷满经济后期未收割|头号战犯|重点背锅|背锅占比"
            r"|(?<![a-zA-Z])(None|null)(?![a-zA-Z])"
        )
        violations = []
        for path, val in iter_report_strings(self.rep_unparsed):
            m = forbidden_regex.search(val)
            if m:
                violations.append(f"{path} [{m.group(0)}]: {val[:140]}")

        md_text = dota_analyst.render_markdown_report(self.rep_unparsed)
        for line_no, line in enumerate(md_text.splitlines(), start=1):
            m = forbidden_regex.search(line)
            if m:
                violations.append(f"markdown:{line_no} [{m.group(0)}]: {line[:140]}")

        self.assertEqual(
            violations,
            [],
            f"未解析样本 8646427108 仍存在基于 0 或默认值的判词 ({len(violations)} 处): {violations[:8]}",
        )

    def test_3_stripped_losing_match_and_frontend_dom_render_no_blame_fallbacks(self) -> None:
        parsed_raw = json.loads((ROOT / "reports" / "raw_8774383260.json").read_text(encoding="utf-8"))
        stripped = copy.deepcopy(parsed_raw)
        for k in ("version", "teamfights", "objectives", "radiant_gold_adv", "radiant_xp_adv", "picks_bans"):
            stripped.pop(k, None)
        for rp in stripped.get("players") or []:
            for pk in (
                "lh_t",
                "dn_t",
                "gold_t",
                "xp_t",
                "purchase_log",
                "ability_uses",
                "item_uses",
                "damage_inflictor",
                "damage_targets",
                "obs_log",
                "sen_log",
                "kills_log",
                "deaths_log",
                "life_state_dead",
                "gold_reasons",
                "stuns",
            ):
                rp.pop(pk, None)

        rep_stripped = dota_analyst.analyze_match_data(stripped, self.roster)
        rep_stripped.pop("grok_coaching", None)
        self.assertFalse(rep_stripped.get("is_parsed"))
        for p in (rep_stripped.get("radiant_pos_1_to_5") or []) + (rep_stripped.get("dire_pos_1_to_5") or []):
            self.assertIsNone(p.get("raw_blame_points"))
            self.assertIsNone(p.get("blame_share_pct"))

        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tf:
            json.dump([self.rep_unparsed, rep_stripped], tf, ensure_ascii=False)
            tmp_path = tf.name

        try:
            node_code = r"""
const fs = require("fs");
const vm = require("vm");

const reports = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
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
const sandbox = {
  console: { ...console, error: (...args) => errors.push(args.map(String).join(" ")) },
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {},
  requestAnimationFrame: () => {}, devicePixelRatio: 2, URLSearchParams,
  URL: { createObjectURL: () => "blob:mock", revokeObjectURL: () => {} },
  Blob: class {}, Image: class { set src(v) {} },
  Audio: class { play() { return Promise.resolve(); } pause() {} },
  speechSynthesis: { cancel: () => {}, speak: () => {}, getVoices: () => [] },
  SpeechSynthesisUtterance: class {},
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
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

function visibleText() {
  const chunks = [];
  for (const [, el] of elements) {
    if (el.innerHTML) {
      chunks.push(
        el.innerHTML
          .replace(/<script[\s\S]*?<\/script>/gi, " ")
          .replace(/<style[\s\S]*?<\/style>/gi, " ")
          .replace(/<[^>]+>/g, " ")
      );
    }
    if (el.textContent) chunks.push(el.textContent);
  }
  return chunks.join(" ");
}

const domIssues = [];
for (const rep of reports) {
  for (const side of ["radiant", "dire"]) {
    for (const [, el] of elements) { el.innerHTML = ""; el.textContent = ""; }
    sandbox.__state.perspective = side;
    sandbox.__state.currentReport = rep;
    sandbox.__state.currentMatchId = rep.match_id;
    sandbox.renderFullMatchReport(rep);
    const txt = visibleText();
    for (const bad of ["0分00秒", "0分0秒", "背锅 20.0%", "分锅: 20%", "分锅 20.0%", "20%后期伤害", "后期收割违约"]) {
      if (txt.includes(bad)) domIssues.push(`${rep.match_id}:${side} contains ${bad}`);
    }
    if (/(?<![\d.])0\.0%/.test(txt)) {
      const m0 = txt.match(/.{0,25}(?<![\d.])0\.0%.{0,25}/);
      domIssues.push(`${rep.match_id}:${side} contains 0.0%: ${m0 ? m0[0] : "0.0%"}`);
    }
    if (/(?<![a-zA-Z])(null|undefined|NaN)(?![a-zA-Z])/.test(txt)) {
      const m = txt.match(/.{0,25}(?<![a-zA-Z])(null|undefined|NaN)(?![a-zA-Z]).{0,25}/);
      domIssues.push(`${rep.match_id}:${side} contains token: ${m ? m[0] : "bad"}`);
    }
  }
}
console.log(JSON.stringify({ errors, domIssues }));
"""
            proc = subprocess.run(
                ["node", "-e", node_code, tmp_path],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=True,
            )
            res = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual(res["errors"], [], f"DOM render console.error: {res['errors']}")
            self.assertEqual(res["domIssues"], [], f"Unparsed DOM fallback issues: {res['domIssues']}")
        finally:
            pathlib.Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
