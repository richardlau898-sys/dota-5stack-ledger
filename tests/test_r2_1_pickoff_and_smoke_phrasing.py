import copy
import glob
import json
import os
import re
import subprocess
import tempfile
import unittest

from ai_coach_engine import evaluate_player_deeply
from dota_analyst import analyze_match_data
from draft_and_phase_coach import build_squad_history_ledger

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FORBIDDEN_PHRASES = (
    "落单被抓",
    "单带无故被抓",
    "直接断送",
    "直接让队伍少人",
    "看着小地图",
    "累计白给",
    "开雾撞墙",
    "导致我方",
)


class TestR21PickoffAndSmokePhrasing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        roster_path = os.path.join(ROOT, "roster.json")
        with open(roster_path, "r", encoding="utf-8") as f:
            cls.roster = json.load(f)
        cls.raw_paths = sorted(glob.glob(os.path.join(ROOT, "reports", "raw_*.json")))
        assert len(cls.raw_paths) >= 20, "Expected sample raw_*.json files"
        cls.raws_and_reports = []
        for rp in cls.raw_paths:
            with open(rp, "r", encoding="utf-8") as f:
                raw = json.load(f)
            rep = analyze_match_data(raw, cls.roster)
            # 排除只读历史 AI 判词缓存 (reports/coaching-*.json，规则 13 禁止修改)，仅校验重新生成的引擎报告与前端渲染
            rep.pop("grok_coaching", None)
            cls.raws_and_reports.append((raw, rep))

    def test_1_regenerated_reports_and_ledger_have_zero_forbidden_phrases(self):
        detail_re = re.compile(r"^\[\d{2,3}:\d{2}\] 被 .+ 击杀$")
        phrase_counts = {ph: 0 for ph in FORBIDDEN_PHRASES}

        with tempfile.TemporaryDirectory() as tmpdir:
            for _, rep in self.raws_and_reports:
                mid = rep["match_id"]
                with open(os.path.join(tmpdir, f"match_{mid}.json"), "w", encoding="utf-8") as f:
                    json.dump(rep, f, ensure_ascii=False)
                dumped = json.dumps(rep, ensure_ascii=False)
                for ph in FORBIDDEN_PHRASES:
                    phrase_counts[ph] += dumped.count(ph)

                ms_by_side = (rep.get("deep_forensics") or {}).get("map_space_by_side") or {}
                for side_key in ("radiant", "dire"):
                    side_ms = ms_by_side.get(side_key) or {}
                    for ev in side_ms.get("solo_pickoff_events") or []:
                        self.assertRegex(
                            str(ev.get("detail") or ""),
                            detail_re,
                            f"团战外阵亡必须只写时间+被谁击杀，实际为: {ev.get('detail')}",
                        )

            ledger = build_squad_history_ledger(tmpdir, self.roster, [])
            ledger_dumped = json.dumps(ledger, ensure_ascii=False)
            for ph in FORBIDDEN_PHRASES:
                phrase_counts[ph] += ledger_dumped.count(ph)

        non_zero = {k: v for k, v in phrase_counts.items() if v > 0}
        self.assertEqual(non_zero, {}, f"报告或总账中仍存在禁用措辞: {non_zero}")

    def test_2_smoke_events_strictly_from_teamfights_item_uses(self):
        non_empty_tf_smoke_checked = 0
        for raw, rep in self.raws_and_reports:
            raw_tfs = raw.get("teamfights") or []
            ss_by_side = (rep.get("deep_forensics") or {}).get("stacking_and_smoke_by_side") or {}
            for side_key, idx_range in (("radiant", range(0, 5)), ("dire", range(5, 10))):
                expected_starts = []
                for tf in raw_tfs:
                    tf_pl = tf.get("players") or []
                    used_in_tf = sum(
                        int((tf_pl[j].get("item_uses") or {}).get("smoke_of_deceit") or 0)
                        for j in idx_range
                        if j < len(tf_pl)
                    )
                    if used_in_tf > 0:
                        expected_starts.append(int(tf.get("start") or 0))
                smoke_events = (ss_by_side.get(side_key) or {}).get("smoke_events") or []
                actual_starts = [int(e.get("time_sec") or 0) for e in smoke_events]
                if expected_starts:
                    non_empty_tf_smoke_checked += 1
                self.assertEqual(
                    actual_starts,
                    expected_starts[:8],
                    f"match {raw.get('match_id')} {side_key}: smoke_events 必须严格来自 teamfights.players.item_uses.smoke_of_deceit",
                )
        self.assertGreater(non_empty_tf_smoke_checked, 0, "样本中应至少有一场团战包含 smoke_of_deceit 使用记录")

        # 额外验证：已解析比赛中，有买雾记录但团战里没有 smoke_of_deceit 时，smoke_events 必须为空列表
        sample_raw = copy.deepcopy(next(raw for raw, rep in self.raws_and_reports if rep.get("is_parsed")))
        for p in sample_raw.get("players") or []:
            p.setdefault("purchase_log", []).append({"time": 720, "key": "smoke_of_deceit"})
            p.setdefault("item_uses", {})["smoke_of_deceit"] = 3
        for tf in sample_raw.get("teamfights") or []:
            for tfp in tf.get("players") or []:
                if isinstance(tfp.get("item_uses"), dict):
                    tfp["item_uses"].pop("smoke_of_deceit", None)
        rep_no_tf_smoke = analyze_match_data(sample_raw, self.roster)
        for side_key in ("radiant", "dire"):
            evs = rep_no_tf_smoke["deep_forensics"]["stacking_and_smoke_by_side"][side_key]["smoke_events"]
            self.assertEqual(evs, [], "团战数据无 smoke_of_deceit 时不应输出开雾事件")

    def test_3_inferred_pickoff_rule_adds_zero_blame_points(self):
        # 选用非 late_hyper_carry 的 1/2 号位核心，验证 solo_pickoffs 不会增加分锅点数
        _, sample_rep = next(
            (raw, rep) for raw, rep in self.raws_and_reports if rep.get("is_parsed") and float(rep.get("duration_min") or 0) >= 30
        )
        allies = copy.deepcopy(sample_rep["radiant_pos_1_to_5"])
        opponents = copy.deepcopy(sample_rep["dire_pos_1_to_5"])
        p_base = copy.deepcopy(allies[1])  # 2号位
        p_base["pos"] = 2
        p_base["hero_id"] = 13  # 帕克 (mid_tempo_brawler, 非 glass_cannon_turret / 非 late_hyper_carry)
        p_base["hero_damage"] = 12000
        p_base.setdefault("hero_mechanism_profile", {})["timing_curve"] = "mid_tempo_brawler"
        p_base["hero_mechanism_profile"]["late_harvest_fulfilled"] = False
        p_base["hero_mechanism_profile"]["late_harvest_failed"] = False
        p_base.setdefault("phase_telemetry", {}).update(
            {
                "late_gold_share_pct": 28.0,
                "late_hdmg_share_pct": 12.0,
                "late_gold_gain": 7200,
                "late_hdmg_gain": 3100,
                "solo_pickoffs": [],
            }
        )

        p_with_pickoffs = copy.deepcopy(p_base)
        p_with_pickoffs["phase_telemetry"]["solo_pickoffs"] = [
            {"time": 920, "time_str": "15:20", "killer": "莉娜"},
            {"time": 1280, "time_str": "21:20", "killer": "马尔斯"},
            {"time": 1610, "time_str": "26:50", "killer": "莉娜"},
        ]

        res_without = evaluate_player_deeply(p_base, allies, opponents, False, 35.0, True, False)
        res_with = evaluate_player_deeply(p_with_pickoffs, allies, opponents, False, 35.0, True, False)
        self.assertEqual(
            res_with["raw_blame_points"],
            res_without["raw_blame_points"],
            "推断出的团战外落单规则不得计入分锅点数",
        )

    def test_4_frontend_dom_render_has_zero_forbidden_phrases_and_zero_null(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_files = []
            for _, rep in self.raws_and_reports:
                p = os.path.join(tmpdir, f"match_{rep['match_id']}.json")
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(rep, f, ensure_ascii=False)
                report_files.append(p)

            node_code = r"""
const fs = require("fs");
const vm = require("vm");

const reportFiles = JSON.parse(process.argv[1]);
const forbidden = JSON.parse(process.argv[2]);
const html = fs.readFileSync("static/index.html", "utf8");
const js = fs.readFileSync("static/app.js", "utf8");

const idRegex = /\bid=["']([^"']+)["']/g;
const htmlIds = new Set();
let m;
while ((m = idRegex.exec(html)) !== null) htmlIds.add(m[1]);

const elements = new Map();
const renderedSnippets = [];

function stripTags(s) {
  return String(s || "")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<[^>]+>/g, " ");
}

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
      if ((prop === "innerHTML" || prop === "textContent") && typeof val === "string" && val.length > 0) {
        renderedSnippets.push(stripTags(val));
        if (prop === "innerHTML") {
          let mm;
          const r = /\bid=["']([^"']+)["']/g;
          while ((mm = r.exec(val)) !== null) {
            if (!elements.has(mm[1])) elements.set(mm[1], makeEl(mm[1]));
          }
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

const microTabs = ["all", "stack_smoke", "map_space"];
for (const file of reportFiles) {
  const report = JSON.parse(fs.readFileSync(file, "utf8"));
  for (const side of ["radiant", "dire"]) {
    sandbox.__state.perspective = side;
    sandbox.__state.currentReport = report;
    sandbox.__state.currentMatchId = report.match_id;
    sandbox.renderFullMatchReport(report);
    for (const pk of ["lane", "mid", "late"]) {
      sandbox.__state.activePhaseKey = pk;
      sandbox.renderPhaseSection(report);
    }
    for (const tab of microTabs) {
      sandbox.__state.microTab = tab;
      sandbox.renderTacticalMicroscopeSection(report);
    }
    sandbox.openFullscreenStructuredReport(report);
  }
}

const fullText = renderedSnippets.join("\n");
const counts = {};
for (const ph of forbidden) {
  const parts = fullText.split(ph);
  if (parts.length - 1 > 0) counts[ph] = parts.length - 1;
}
const nullMatches = fullText.match(/null/g) || [];
console.log(JSON.stringify({ counts, nullCount: nullMatches.length, nullSample: (fullText.match(/.{0,15}null.{0,15}/g) || []).slice(0, 5) }));
"""
            proc = subprocess.run(
                ["node", "-e", node_code, json.dumps(report_files), json.dumps(list(FORBIDDEN_PHRASES))],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            out = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual(out["counts"], {}, f"前端渲染文字仍包含禁用短语: {out['counts']}")
            self.assertEqual(out["nullCount"], 0, f"前端渲染文字出现了 null: {out['nullSample']}")


if __name__ == "__main__":
    unittest.main()
