import inspect
import json
import pathlib
import subprocess
import tempfile
import unittest

import dota_analyst
from tests.helpers import build_all_sample_reports

ROOT = pathlib.Path(__file__).resolve().parent.parent


def iter_all_conclusions(report: dict):
    """Yield (path, conclusion_dict) for every conclusion object in a report."""
    for side_key in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
        for idx, p in enumerate(report.get(side_key) or []):
            for c in p.get("conclusions") or []:
                yield f"{side_key}[{idx}].conclusions", c

    mvp = report.get("mvp") or {}
    for c in mvp.get("conclusions") or []:
        yield "mvp.conclusions", c

    nar = report.get("match_narrative") or {}
    for c in nar.get("conclusions") or []:
        yield "match_narrative.conclusions", c

    phases = report.get("phases_data") or []
    ph_list = phases if isinstance(phases, list) else list(phases.values())
    for ph in ph_list:
        if not isinstance(ph, dict):
            continue
        pk = ph.get("key", "phase")
        for c in ph.get("conclusions") or []:
            yield f"phases_data.{pk}.conclusions", c
        for pp in ph.get("players") or []:
            if isinstance(pp, dict):
                for c in pp.get("conclusions") or []:
                    yield f"phases_data.{pk}.players[{pp.get('pos')}].conclusions", c

    for side_k, da in (report.get("draft_analysis_by_side") or {}).items():
        if isinstance(da, dict):
            for c in da.get("conclusions") or []:
                yield f"draft_analysis_by_side.{side_k}.conclusions", c

    df = report.get("deep_forensics") or {}
    for mod_key, mod_val in df.items():
        if not mod_key.endswith("_by_side") or not isinstance(mod_val, dict):
            continue
        for side_k in ("radiant", "dire"):
            sb = mod_val.get(side_k)
            if isinstance(sb, dict):
                for c in sb.get("conclusions") or []:
                    yield f"deep_forensics.{mod_key}.{side_k}.conclusions", c
            elif isinstance(sb, list):
                for idx, elem in enumerate(sb):
                    if isinstance(elem, dict):
                        for c in elem.get("conclusions") or []:
                            yield f"deep_forensics.{mod_key}.{side_k}[{idx}].conclusions", c


class TestR26HonestEvidenceAndNoFallbacks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reports_map = build_all_sample_reports()

    def test_1_no_text_guessing_classifier_and_all_measured_declare_source_fields(self) -> None:
        self.assertFalse(
            hasattr(dota_analyst, "classify_text_evidence"),
            "classify_text_evidence text-guessing function must be removed",
        )
        src = inspect.getsource(dota_analyst)
        self.assertNotIn("classify_text_evidence", src)

        total_conclusions = 0
        measured_conclusions = 0
        missing_sources = []

        for mid, rep in self.reports_map.items():
            for path, c in iter_all_conclusions(rep):
                total_conclusions += 1
                ev = c.get("evidence")
                self.assertIn(ev, {"measured", "inferred", "template"}, f"{mid} {path}: invalid evidence {ev}")
                if ev == "measured":
                    measured_conclusions += 1
                    sf = c.get("source_fields")
                    if not isinstance(sf, list) or len(sf) == 0 or not all(isinstance(x, str) and x for x in sf):
                        missing_sources.append(f"{mid} {path}: {c.get('text', '')[:50]}")

        self.assertGreater(total_conclusions, 100)
        self.assertEqual(
            missing_sources,
            [],
            f"{len(missing_sources)} measured conclusions lack declared source_fields: {missing_sources[:8]}",
        )
        measured_ratio = measured_conclusions / total_conclusions
        self.assertLess(
            measured_ratio,
            0.80,
            f"Measured ratio is still {measured_ratio:.1%} ({measured_conclusions}/{total_conclusions}); inferred/template rules are still mislabeled",
        )

    def test_2_smoke_solo_and_unused_rules_are_strictly_inferred(self) -> None:
        violations = []
        inferred_keywords = (
            "开雾",
            "诡计之雾",
            "团战外阵亡",
            "非团战单人阵亡",
            "非团战阵亡",
            "落单",
            "未使用",
            "未按",
            "无技能释放",
        )

        for mid, rep in self.reports_map.items():
            df = rep.get("deep_forensics") or {}
            for side_k in ("radiant", "dire"):
                # 1) Smoke events & per_player_smokes & team_metrics smoke_effectiveness
                ss = (df.get("stacking_and_smoke_by_side") or {}).get(side_k) or {}
                for ev_item in ss.get("smoke_events") or []:
                    if ev_item.get("evidence") != "inferred":
                        violations.append(f"{mid} smoke_events.{side_k}: {ev_item.get('evidence')}")
                for ps_item in ss.get("per_player_smokes") or []:
                    if ps_item.get("evidence") != "inferred":
                        violations.append(f"{mid} per_player_smokes.{side_k}: {ps_item.get('evidence')}")

                tm_smoke = ((rep.get("team_metrics_by_side") or {}).get(side_k) or {}).get("smoke_effectiveness") or {}
                if tm_smoke and tm_smoke.get("evidence") != "inferred":
                    violations.append(f"{mid} team_metrics.smoke_effectiveness.{side_k}: {tm_smoke.get('evidence')}")
                for sw in tm_smoke.get("smoke_windows") or []:
                    if sw.get("evidence") != "inferred":
                        violations.append(f"{mid} smoke_windows.{side_k}: {sw.get('evidence')}")

                # 2) Map space / non-teamfight ("落单") deaths
                ms = (df.get("map_space_by_side") or {}).get(side_k) or {}
                if ms.get("evidence") != "inferred":
                    violations.append(f"{mid} map_space_by_side.{side_k}: {ms.get('evidence')}")
                for sp_ev in ms.get("solo_pickoff_events") or []:
                    if sp_ev.get("evidence") != "inferred":
                        violations.append(f"{mid} solo_pickoff_events.{side_k}: {sp_ev.get('evidence')}")
                for sp_row in ms.get("player_space_rows") or []:
                    if sp_row.get("evidence") != "inferred":
                        violations.append(f"{mid} player_space_rows.{side_k}: {sp_row.get('evidence')}")

                # 3) Unpressed saves ("未使用")
                us = (df.get("unpressed_saves_by_side") or {}).get(side_k) or {}
                if us.get("evidence") != "inferred":
                    violations.append(f"{mid} unpressed_saves_by_side.{side_k}: {us.get('evidence')}")
                for inc in us.get("incidents") or []:
                    if inc.get("evidence") != "inferred":
                        violations.append(f"{mid} unpressed_saves.incidents.{side_k}: {inc.get('evidence')}")
                for pr in us.get("player_rows") or []:
                    if pr.get("evidence") != "inferred":
                        violations.append(f"{mid} unpressed_saves.player_rows.{side_k}: {pr.get('evidence')}")

            # 4) Check every conclusion across the report
            for path, c in iter_all_conclusions(rep):
                txt = str(c.get("text") or "")
                if any(kw in txt for kw in inferred_keywords) and c.get("evidence") == "measured":
                    violations.append(f"{mid} {path} marked measured: {txt[:60]}")

        self.assertEqual(violations, [], f"Inferred rules mislabeled ({len(violations)}): {violations[:12]}")

    def test_3_frontend_numeric_fallbacks_eliminated(self) -> None:
        app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        forbidden_patterns = [
            "?? 50",
            "?? 20",
            "?? 22",
            "?? 25",
            "?? 75",
            "?? 360",
            "?? 6.0",
            "|| 6.0",
            "|| 7.5",
            "rawScore || 70",
            "avg_rating || 75",
            "lane_eff || 80",
            "lane_eff || 69",
            "lane_eff || 65",
            "lane_efficiency_pct || 60",
            "party_size || 5",
            "time_sec || 1800",
            "blinkItem.sec || 1200",
            "duration_sec || 30",
            "nx || 50",
            "ny || 50",
        ]
        found = [pat for pat in forbidden_patterns if pat in app_js]
        self.assertEqual(found, [], f"Forbidden numeric fallbacks remain in static/app.js: {found}")

        # Verify rendering null fields displays 无数据 rather than 50% / 360 秒
        sample_rep = next(r for r in self.reports_map.values() if r.get("is_parsed"))
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tf:
            json.dump(sample_rep, tf, ensure_ascii=False)
            tmp_path = tf.name
        try:
            node_code = r"""
const fs = require("fs");
const vm = require("vm");
const rep = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
const js = fs.readFileSync("static/app.js", "utf8");
for (const r of rep.deep_forensics.role_mirror_by_side.radiant.mirror_rows) {
  r.own_bm_avg = null;
  r.opp_bm_avg = null;
  r.own_bm_top = [{ label_zh: "GPM", pct: null }];
}
rep.deep_forensics.support_vision_by_side.radiant.god_tier_wards = [
  { time_str: "10:00", planter_hero: "测试辅助", zone_zh: "河道", coords: "50,50", posture_zh: "河道眼", lifespan_sec: null }
];
for (const w of rep.deep_forensics.support_vision_by_side.radiant.obs_records || []) {
  w.lifespan_sec = null;
  w.fate_zh = null;
}
rep.deep_forensics.support_vision_by_side.radiant.avg_lifespan_sec = null;
const sandbox = {
  console, setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {},
  requestAnimationFrame: () => {}, URLSearchParams,
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  location: { search: "", pathname: "/", href: "http://localhost/", origin: "http://localhost", hash: "" },
  history: { pushState: () => {}, replaceState: () => {}, state: {} },
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  document: { getElementById: () => null, querySelectorAll: () => [], addEventListener: () => {} },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(js.replace(/initApp\(\);/g, "// initApp();"), sandbox);
const mirrorHtml = sandbox.renderMicroRoleMirrorPane(rep, rep.deep_forensics, "radiant", "天辉", "夜魇");
const visionHtml = sandbox.renderMicroSupportVisionPane(rep, rep.deep_forensics, "radiant", "天辉");
console.log(JSON.stringify({
  hasFake50: mirrorHtml.includes("全球超越 50%"),
  hasNoDataInMirror: mirrorHtml.includes("无数据"),
  hasFake360: visionHtml.includes("足足存活 <b>360 秒"),
  hasNoDataInVision: visionHtml.includes("足足存活 <b>无数据</b>"),
}));
"""
            proc = subprocess.run(
                ["node", "-e", node_code, tmp_path],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=True,
            )
            out = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertFalse(out["hasFake50"], "Mirror pane rendered fake '全球超越 50%' when benchmark is null")
            self.assertTrue(out["hasNoDataInMirror"], "Mirror pane must show '无数据' when benchmark is null")
            self.assertFalse(out["hasFake360"], "Vision pane rendered fake '360 秒' when lifespan_sec is null")
            self.assertTrue(out["hasNoDataInVision"], "Vision pane must show '无数据' when god_tier_wards lifespan_sec is null")
        finally:
            pathlib.Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
