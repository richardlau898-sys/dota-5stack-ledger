# -*- coding: utf-8 -*-
r"""
T3-2 · 未解析的比赛报 500（迁移的前提）回归测试：
1. 用 raw_8646427108.json 生成报告，存入本地假 Supabase，本地 reports/ 与临时目录为空；
   不带口令请求 /api/match/8646427108 及每一个 part 值（summary / timeline / microscope / full），
   全部返回 HTTP 200，ok=true，且对应分节均为 available: false。
2. 当报告文件存在于本地 REPORTS_DIR 时，不带口令请求 /api/match/8646427108?part=summary
   与 /api/match/8646427108 均返回 200 与真实报告，不会吞掉异常伪报 not_analyzed。
3. Python 读取分节的各处先判断 available，不在未解析报告上崩溃或误把 dict 当 list 遍历。
4. 前端渲染未解析比赛 8646427108 的各分节统一显示"需要先解析录像"，不伪造"0 次憋死"/"开雾 0 次"/"0 : 0"。
"""

import json
import os
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import ai_coach_engine
import cloud_store
import dota_analyst
import draft_and_phase_coach
import server
import squad_growth_metrics

REPO_ROOT = Path(__file__).resolve().parent.parent


class _FakeSupabaseHTTP:
    """本地假 Supabase REST + Storage 服务"""

    def __init__(self) -> None:
        self.reports_table: dict[int, dict] = {}
        self.match_players_rows: dict[tuple[int, int], dict] = {}
        self.storage_objects: dict[str, bytes] = {}
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def _send_json(self, payload, status: int = 200) -> None:
                raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(parsed.query)
                path = parsed.path

                if path == "/rest/v1/dota_match_reports":
                    rows = list(parent.reports_table.values())
                    mid_filter = (qs.get("match_id") or [""])[0]
                    if mid_filter.startswith("eq."):
                        target_mid = int(mid_filter.split(".", 1)[1])
                        rows = [r for r in rows if int(r["match_id"]) == target_mid]
                    rows.sort(key=lambda r: int(r["match_id"]), reverse=True)
                    self._send_json(rows)
                    return

                if path == "/rest/v1/match_players":
                    rows = list(parent.match_players_rows.values())
                    self._send_json(rows)
                    return

                if path.startswith("/storage/v1/object/"):
                    obj_key = path.split("/storage/v1/object/", 1)[1]
                    if obj_key in parent.storage_objects:
                        raw = parent.storage_objects[obj_key]
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(raw)))
                        self.end_headers()
                        self.wfile.write(raw)
                        return

                self._send_json({"error": "not_found"}, status=404)

            def do_POST(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length > 0 else b""

                if path == "/rest/v1/dota_match_reports":
                    item = json.loads(body.decode("utf-8"))
                    items = item if isinstance(item, list) else [item]
                    for it in items:
                        parent.reports_table[int(it["match_id"])] = it
                    self._send_json({"ok": True}, status=201)
                    return

                if path == "/rest/v1/match_players":
                    items = json.loads(body.decode("utf-8"))
                    if isinstance(items, dict):
                        items = [items]
                    for it in items:
                        key = (int(it["match_id"]), int(it["player_slot"]))
                        parent.match_players_rows[key] = it
                    self._send_json({"ok": True}, status=201)
                    return

                if path.startswith("/storage/v1/object/"):
                    obj_key = path.split("/storage/v1/object/", 1)[1]
                    parent.storage_objects[obj_key] = body
                    self._send_json({"ok": True}, status=200)
                    return

                self._send_json({"error": "not_found"}, status=404)

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.httpd.shutdown()
        self.httpd.server_close()


class _SilentAppServer:
    """临时本地 HTTP 服务，绑定随机空闲端口"""

    def __init__(self) -> None:
        class QuietHandler(server.DotaAnalystHandler):
            def log_message(self, fmt, *args):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), QuietHandler)
        self.base_url = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.httpd.shutdown()
        self.httpd.server_close()


def _http_get_json(url: str) -> tuple[int, dict]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        exc.close()
        try:
            body = json.loads(raw)
        except Exception:
            body = {"_raw": raw}
        return exc.code, body


class TestT32UnparsedMatch500(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_8646427108 = json.loads(
            (REPO_ROOT / "reports" / "raw_8646427108.json").read_text(encoding="utf-8")
        )
        cls.roster = json.loads((REPO_ROOT / "roster.json").read_text(encoding="utf-8"))
        cls.report_8646427108 = dota_analyst.analyze_match_data(
            cls.raw_8646427108, roster=cls.roster
        )

    def test_1_supabase_unparsed_match_all_parts_return_200_with_available_false(self) -> None:
        """存入本地假 Supabase 后，不带口令请求每一个 part 值均返回 200，且对应分节为 available: false"""
        with tempfile.TemporaryDirectory() as empty_rep_dir, tempfile.TemporaryDirectory() as empty_tmp_dir:
            rep_path = Path(empty_rep_dir)
            tmp_path = Path(empty_tmp_dir)
            with _FakeSupabaseHTTP() as fake_sb:
                env_patch = {
                    "SUPABASE_URL": fake_sb.url,
                    "SUPABASE_SERVICE_ROLE_KEY": "fake-service-role-key",
                    "TEAM_TOKEN": "test-team-token-secret",
                    "VERCEL": "1",
                }
                with (
                    patch.dict(os.environ, env_patch, clear=False),
                    patch.object(server, "REPORTS_DIR", rep_path),
                    patch.object(server, "TMP_REPORTS_DIR", tmp_path),
                    patch.object(cloud_store, "TMP_REPORTS_DIR", tmp_path),
                ):
                    saved_ok = cloud_store.cloud_save_match_report(
                        8646427108, dict(self.report_8646427108)
                    )
                    self.assertTrue(saved_ok, "Saving report to fake Supabase should succeed")
                    # 清空临时目录，确保接下来全部从假 Supabase 读取
                    for f in tmp_path.glob("*"):
                        if f.is_file():
                            f.unlink()

                    with _SilentAppServer() as app_srv:
                        # 1. ?part=summary
                        code_sum, body_sum = _http_get_json(
                            f"{app_srv.base_url}/api/match/8646427108?part=summary"
                        )
                        self.assertEqual(code_sum, 200, f"part=summary returned {code_sum}: {body_sum}")
                        self.assertTrue(body_sum.get("ok"))
                        self.assertNotIn("not_analyzed", body_sum)
                        rep_sum = body_sum["report"]
                        self.assertIs(rep_sum.get("is_parsed"), False)
                        df_sum = rep_sum["deep_forensics"]
                        self.assertIs(df_sum.get("available"), False)
                        for sec_k in ("unpressed_saves_by_side", "stacking_and_smoke_by_side"):
                            sec = df_sum.get(sec_k)
                            self.assertIsInstance(sec, dict, f"summary.{sec_k} must be dict")
                            self.assertIs(sec.get("available"), False, f"summary.{sec_k}.available must be False: {sec}")
                            for side_k in ("dire", "radiant"):
                                self.assertIs(
                                    (sec.get(side_k) or {}).get("available"),
                                    False,
                                    f"summary.{sec_k}.{side_k}.available must be False: {sec}",
                                )

                        # 2. ?part=timeline
                        code_tl, body_tl = _http_get_json(
                            f"{app_srv.base_url}/api/match/8646427108?part=timeline"
                        )
                        self.assertEqual(code_tl, 200, f"part=timeline returned {code_tl}: {body_tl}")
                        self.assertTrue(body_tl.get("ok"))
                        self.assertNotIn("not_analyzed", body_tl)
                        df_tl = body_tl["report"]["deep_forensics"]
                        self.assertIs(df_tl.get("available"), False)
                        for sec_k in ("minute_snapshots", "teamfight_forensics", "unpressed_saves_by_side"):
                            sec = df_tl.get(sec_k)
                            self.assertIsInstance(sec, dict, f"timeline.{sec_k} must be dict")
                            self.assertIs(sec.get("available"), False, f"timeline.{sec_k}.available must be False: {sec}")

                        # 3. ?part=microscope
                        code_mic, body_mic = _http_get_json(
                            f"{app_srv.base_url}/api/match/8646427108?part=microscope"
                        )
                        self.assertEqual(code_mic, 200, f"part=microscope returned {code_mic}: {body_mic}")
                        self.assertTrue(body_mic.get("ok"))
                        self.assertNotIn("not_analyzed", body_mic)
                        rep_mic = body_mic["report"]
                        for idx, pd in enumerate(rep_mic.get("phases_data") or []):
                            self.assertIs(pd.get("available"), False, f"phases_data[{idx}].available must be False")
                        df_mic = rep_mic["deep_forensics"]
                        self.assertIs(df_mic.get("available"), False)
                        micro_sections = (
                            "picks_order",
                            "lane_matchups",
                            "rubick_steal_ledger",
                            "key_spell_targets",
                            "courier_graveyard",
                            "ping_pressure_rank",
                            "focus_fire_matrix",
                            "teamfight_forensics",
                            "hero_execution_by_side",
                            "itemization_audit_by_side",
                            "damage_quality_and_build_by_side",
                            "support_vision_by_side",
                            "stacking_and_smoke_by_side",
                            "laning_mechanics_by_side",
                            "tp_rotation_by_side",
                            "unpressed_saves_by_side",
                            "map_space_by_side",
                            "damage_received_by_side",
                            "economy_and_pings_by_side",
                            "role_mirror_by_side",
                            "macro_objectives_by_side",
                        )
                        for sec_k in micro_sections:
                            sec = df_mic.get(sec_k)
                            self.assertIsInstance(sec, dict, f"microscope.{sec_k} must be dict")
                            self.assertIs(sec.get("available"), False, f"microscope.{sec_k}.available must be False")

                        # 4. 不带 part / ?part=full
                        for suffix in ("", "?part=full"):
                            code_full, body_full = _http_get_json(
                                f"{app_srv.base_url}/api/match/8646427108{suffix}"
                            )
                            self.assertEqual(code_full, 200, f"{suffix or 'full'} returned {code_full}: {body_full}")
                            self.assertTrue(body_full.get("ok"))
                            self.assertNotIn("not_analyzed", body_full)
                            df_full = body_full["report"]["deep_forensics"]
                            self.assertIs(df_full.get("available"), False)
                            self.assertIs((df_full.get("lane_matchups") or {}).get("available"), False)
                            self.assertIs((df_full.get("minute_snapshots") or {}).get("available"), False)

    def test_2_local_report_file_part_summary_not_swallowed_as_not_analyzed(self) -> None:
        """本地存在 match_8646427108.json 时，不带口令请求 ?part=summary 不得吞掉异常返回 not_analyzed"""
        with tempfile.TemporaryDirectory() as local_rep_dir, tempfile.TemporaryDirectory() as empty_tmp_dir:
            rep_path = Path(local_rep_dir)
            tmp_path = Path(empty_tmp_dir)
            (rep_path / "match_8646427108.json").write_text(
                json.dumps(self.report_8646427108, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            env_patch = {
                "SUPABASE_URL": "",
                "SUPABASE_SERVICE_ROLE_KEY": "",
                "TEAM_TOKEN": "test-team-token-secret",
                "VERCEL": "1",
            }
            with (
                patch.dict(os.environ, env_patch, clear=False),
                patch.object(server, "REPORTS_DIR", rep_path),
                patch.object(server, "TMP_REPORTS_DIR", tmp_path),
                patch.object(cloud_store, "TMP_REPORTS_DIR", tmp_path),
                _SilentAppServer() as app_srv,
            ):
                code_sum, body_sum = _http_get_json(
                    f"{app_srv.base_url}/api/match/8646427108?part=summary"
                )
                self.assertEqual(code_sum, 200)
                self.assertTrue(body_sum.get("ok"))
                self.assertFalse(
                    body_sum.get("not_analyzed", False),
                    f"Existing local report must not return not_analyzed: {body_sum}",
                )
                self.assertEqual(body_sum["report"]["match_id"], 8646427108)
                self.assertIs(body_sum["report"]["is_parsed"], False)

    def test_3_python_section_readers_check_available_safely(self) -> None:
        """Python 侧读取 deep_forensics 分节的函数在 available=false 时不报错、不把 dict 误当 list"""
        rep = json.loads(json.dumps(self.report_8646427108))
        ensured = server._ensure_v69_hero_matchup_matrix(rep)
        self.assertIs((ensured["deep_forensics"]["lane_matchups"]).get("available"), False)

        valid_ts, valid_nums = ai_coach_engine._collect_ground_truth_tokens(rep, None)
        self.assertIsInstance(valid_ts, set)
        self.assertIsInstance(valid_nums, set)

        dire_team = rep.get("dire_pos_1_to_5") or []
        rad_team = rep.get("radiant_pos_1_to_5") or []
        if dire_team:
            duty = ai_coach_engine._compute_player_role_duty_audit(
                dire_team[0], dire_team, rad_team, rep.get("deep_forensics") or {}, "dire"
            )
            self.assertEqual(duty.get("solo_pickoffs_count"), 0)

        poster_prompt = ai_coach_engine.build_dota_poster_art_prompt(rep)
        self.assertTrue(poster_prompt.get("prompt"))

        tm_by_side = squad_growth_metrics.build_team_metrics_by_side(self.raw_8646427108, rep)
        self.assertIs(((tm_by_side.get("dire") or {}).get("smoke_effectiveness") or {}).get("available"), False)
        fixes_by_side = squad_growth_metrics.build_next_game_top3_fixes_by_side(
            self.raw_8646427108, rep, tm_by_side
        )
        self.assertIsInstance(fixes_by_side.get("dire"), list)

        with tempfile.TemporaryDirectory() as ledger_dir:
            ldir = Path(ledger_dir)
            (ldir / "match_8646427108.json").write_text(
                json.dumps(rep, ensure_ascii=False), encoding="utf-8"
            )
            with patch.object(cloud_store, "cloud_fetch_match_players", return_value=[]):
                ledger = draft_and_phase_coach.build_squad_history_ledger(ldir, self.roster, [])
            self.assertEqual(len(ledger.get("analyzed_matches") or []), 1)

    def test_4_frontend_renders_need_parse_replay_across_all_unparsed_sections(self) -> None:
        """前端渲染未解析比赛 8646427108 时，摘要/时间轴/阶段/显微镜各未解析分节均显示'需要先解析录像'"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            sum_part = dota_analyst.extract_report_part(self.report_8646427108, "summary")
            tl_part = dota_analyst.extract_report_part(self.report_8646427108, "timeline")
            mic_part = dota_analyst.extract_report_part(self.report_8646427108, "microscope")
            parts_file = Path(tmp_dir) / "parts_8646427108.json"
            parts_file.write_text(
                json.dumps({"summary": sum_part, "timeline": tl_part, "microscope": mic_part}, ensure_ascii=False),
                encoding="utf-8",
            )

            node_script = r"""
const fs = require("fs");
const vm = require("vm");
const html = fs.readFileSync("static/index.html", "utf8");
const js = fs.readFileSync("static/app.js", "utf8");
const parts = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));

const idRegex = /\bid=["']([^"']+)["']/g;
const htmlIds = new Set();
let m;
while ((m = idRegex.exec(html)) !== null) htmlIds.add(m[1]);

const elements = new Map();
function makeEl(id = "") {
  const el = {
    id, innerHTML: "", textContent: "", value: "", options: [], files: [],
    hidden: false, disabled: false, open: false, width: 920, height: 620,
    clientWidth: 920, clientHeight: 420,
    style: new Proxy({}, { set: () => true, get: () => "" }),
    dataset: {},
    classList: { add: () => {}, remove: () => {}, toggle: () => {}, contains: () => false },
    setAttribute: () => {}, getAttribute: () => "", removeAttribute: () => {},
    addEventListener: () => {}, removeEventListener: () => {}, appendChild: () => {},
    querySelector: () => makeEl(), querySelectorAll: () => [],
    getBoundingClientRect: () => ({ width: 800, height: 400, top: 0, left: 0 }),
    getContext: () => new Proxy({}, { get: () => () => ({ width: 50, addColorStop: () => {} }), set: () => true }),
    showModal: function() { this.open = true; },
    close: function() { this.open = false; },
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
    }
  });
}
for (const id of htmlIds) elements.set(id, makeEl(id));

const errors = [];
const sandbox = {
  console: { ...console, error: (...args) => errors.push(args.map(String).join(" ")) },
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {},
  requestAnimationFrame: (fn) => fn(), devicePixelRatio: 2, URLSearchParams,
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
    getElementById: (id) => { if (!elements.has(id)) elements.set(id, makeEl(id)); return elements.get(id); },
    querySelector: () => makeEl(), querySelectorAll: () => [],
    createElement: (tag) => makeEl(tag), addEventListener: () => {},
    body: makeEl("body"), documentElement: makeEl("html"),
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(js.replace(/initApp\(\);/g, "// initApp();") + "\nglobalThis.__state = state;\n", sandbox);

const rep = JSON.parse(JSON.stringify(parts.summary));
for (const partObj of [parts.timeline, parts.microscope]) {
  for (const [k, v] of Object.entries(partObj)) {
    if (k === "_loaded_parts") continue;
    if (k === "deep_forensics" && v && typeof v === "object") {
      rep.deep_forensics = { ...(rep.deep_forensics || {}), ...v };
    } else if (v !== undefined) {
      rep[k] = v;
    }
  }
}
rep._loaded_parts = ["summary", "timeline", "microscope"];
sandbox.hydrateReportData(rep);
sandbox.__state.currentReport = rep;
sandbox.__state.currentMatchId = rep.match_id;
sandbox.renderFullMatchReport(rep);

const out = {
  errors,
  factcheck: elements.get("ws-factcheck-section")?.innerHTML || "",
  scrubber: elements.get("minute-scrubber-content")?.innerHTML || "",
  advChart: elements.get("adv-chart-container")?.innerHTML || "",
  nwChart: elements.get("nw-chart-container")?.innerHTML || "",
  minimapSide: elements.get("minimap-stats-side")?.innerHTML || "",
  phasePanel: elements.get("phase-active-panel")?.innerHTML || "",
  keyWindows: elements.get("key-windows-grid")?.innerHTML || "",
  microscope: elements.get("tactical-microscope-body")?.innerHTML || "",
  focusMatrix: elements.get("focus-fire-matrix-container")?.innerHTML || "",
};
process.stdout.write(JSON.stringify(out));
"""
            proc = subprocess.run(
                ["node", "-e", node_script, str(parts_file)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=True,
            )
            rendered = json.loads(proc.stdout)
            self.assertEqual(rendered["errors"], [], f"JS render errors: {rendered['errors']}")
            for key in (
                "factcheck",
                "scrubber",
                "advChart",
                "nwChart",
                "minimapSide",
                "phasePanel",
                "keyWindows",
                "microscope",
                "focusMatrix",
            ):
                self.assertTrue(
                    "需要先解析录像" in rendered[key],
                    f"Unparsed section {key} must display '需要先解析录像', got: {rendered[key][:240]}",
                )
            self.assertNotIn("0 次憋死记录", rendered["factcheck"])
            self.assertNotIn("开雾 0 次", rendered["factcheck"])
            self.assertNotIn("对方五人插下", rendered["minimapSide"])
            self.assertNotIn("+null", rendered["phasePanel"])


if __name__ == "__main__":
    unittest.main()
