#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回归测试：左侧边栏「最近比赛记录」本人英雄、KDA 与开黑人数解析
复现并验证：
1. #9083213997 中本人 (86080912 Flame = ez mute) 操刀 2 号位「风暴之灵」(11/11/11, 5人黑)，
   队友 Merl 5 号位「森海飞霞」为败方 SVP；当该局仅在 squad_ledger.analyzed_matches 中时，
   边栏必须显示「风暴之灵 · 5人黑 · KDA 11/11/11」，绝不能回退显示 SVP「森海飞霞 · 单排 · KDA 比分 ...」。
2. 匿名比赛 (#8646427108) 无本人账号时，my_hero/my_kda/party_size 输出 None，前端显示「无数据」，
   绝不冒用 mvp_hero「狙击手」或伪造「单排」「0/0/0」。
3. 未带口令的离线缓存 (allow_network=False) 不得污染带口令请求 (allow_network=True) 的实时拉取。
4. 前端 /api/init 与 /api/player 请求在本地存有车队口令时必须附带 X-Team-Token 请求头。
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cloud_store
import draft_and_phase_coach
import server

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestSidebarMyHeroResolution(unittest.TestCase):
    def setUp(self) -> None:
        self.roster = json.loads((REPO_ROOT / "roster.json").read_text(encoding="utf-8"))

    def _build_sample_ledger(self) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for mid in (9083213997, 8646427108):
                src = REPO_ROOT / "reports" / f"match_{mid}.json"
                shutil.copy2(src, tmp_dir / src.name)
            with (
                patch.object(cloud_store, "cloud_fetch_match_players", return_value=[]),
                patch.object(cloud_store, "cloud_fetch_player_goals", return_value={}),
                patch.object(cloud_store, "cloud_fetch_player_matches", return_value=[]),
            ):
                return draft_and_phase_coach.build_squad_history_ledger(tmp_dir, self.roster, [])

    def test_ledger_analyzed_matches_exports_my_hero_kda_party_and_null_for_anonymous(self) -> None:
        ledger = self._build_sample_ledger()
        by_mid = {int(m["match_id"]): m for m in ledger["analyzed_matches"]}

        m_storm = by_mid[9083213997]
        self.assertEqual(m_storm.get("mvp_hero"), "森海飞霞")
        self.assertEqual(m_storm.get("my_hero"), "风暴之灵")
        self.assertEqual(m_storm.get("my_kda"), "11/11/11")
        self.assertEqual(m_storm.get("party_size"), 5)
        self.assertEqual(m_storm.get("party_label"), "5人黑")
        self.assertIn("storm_spirit", m_storm.get("my_hero_img") or "")

        m_anon = by_mid[8646427108]
        self.assertEqual(m_anon.get("mvp_hero"), "狙击手")
        self.assertIsNone(m_anon.get("my_hero"))
        self.assertIsNone(m_anon.get("my_kda"))
        self.assertIsNone(m_anon.get("my_grok_score"))
        self.assertIsNone(m_anon.get("my_grok_share_pct"))
        self.assertIsNone(m_anon.get("party_size"))
        self.assertIsNone(m_anon.get("party_label"))

    def test_sidebar_renders_my_hero_not_mvp_hero_when_not_in_recent_matches(self) -> None:
        ledger = self._build_sample_ledger()
        payload = {
            "roster": self.roster,
            "ledger": ledger,
        }
        node_script = r"""
const fs = require("fs");
const vm = require("vm");
const data = JSON.parse(fs.readFileSync(0, "utf8"));
const js = fs.readFileSync("static/app.js", "utf8");

function makeEl(id = "") {
  return {
    id, innerHTML: "", textContent: "", value: "", hidden: false, open: false,
    disabled: false, style: {}, dataset: {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener() {}, removeEventListener() {},
    setAttribute() {}, getAttribute() { return null; },
    querySelector() { return null; }, querySelectorAll() { return []; },
    appendChild() {}, remove() {}, close() { this.open = false; }, showModal() { this.open = true; },
    getContext() {
      return {
        clearRect() {}, fillRect() {}, beginPath() {}, moveTo() {}, lineTo() {},
        arc() {}, fill() {}, stroke() {}, fillText() {}, save() {}, restore() {},
        setLineDash() {}, createLinearGradient() { return { addColorStop() {} }; },
      };
    },
  };
}

const elements = new Map();
const lsMap = new Map();
const sandbox = {
  console, Math, Date, JSON, Number, String, Boolean, Array, Object, RegExp, Map, Set, Promise,
  Error, TypeError, parseInt, parseFloat, isNaN, isFinite, encodeURIComponent, decodeURIComponent,
  setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
  requestAnimationFrame: () => 0,
  URLSearchParams,
  localStorage: { getItem: (k) => lsMap.get(k) ?? null, setItem: (k, v) => lsMap.set(k, String(v)), removeItem: (k) => lsMap.delete(k) },
  sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  indexedDB: { open: () => ({ onupgradeneeded: null, onsuccess: null, onerror: null }) },
  navigator: { clipboard: { writeText: () => Promise.resolve() } },
  location: { search: "", pathname: "/", href: "http://localhost/", origin: "http://localhost", hash: "" },
  history: { pushState: () => {}, replaceState: () => {}, state: {} },
  scrollTo: () => {}, innerWidth: 1440,
  addEventListener: () => {}, removeEventListener: () => {},
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

sandbox.__state.roster = data.roster;
sandbox.__state.squadLedger = data.ledger;
sandbox.__state.profileData = {
  profile: { personaname: "Flame = ez mute" },
  wl: { win_rate: 50.0 },
  recent_matches: [],
};
sandbox.renderSidebarMatches();
const html = elements.get("ws-sidebar-match-list")?.innerHTML || "";
process.stdout.write(JSON.stringify({ html }));
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            cwd=REPO_ROOT,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            check=True,
        )
        html = json.loads(proc.stdout)["html"]

        # Split blocks per match id
        self.assertIn('data-ws-match-id="9083213997"', html)
        self.assertIn('data-ws-match-id="8646427108"', html)
        parts = html.split('data-ws-match-id="')
        by_id_html = {}
        for chunk in parts[1:]:
            mid_str, rest = chunk.split('"', 1)
            by_id_html[mid_str] = rest

        storm_card = by_id_html["9083213997"]
        self.assertIn('<strong class="ws-match-hero">风暴之灵</strong>', storm_card)
        self.assertNotIn('<strong class="ws-match-hero">森海飞霞</strong>', storm_card)
        self.assertIn('<span class="ws-match-party">5人黑</span>', storm_card)
        self.assertNotIn('<span class="ws-match-party">单排</span>', storm_card)
        self.assertIn("KDA <b>11/11/11</b>", storm_card)
        self.assertNotIn("KDA <b>比分", storm_card)

        anon_card = by_id_html["8646427108"]
        self.assertIn('<strong class="ws-match-hero">无数据</strong>', anon_card)
        self.assertNotIn('<strong class="ws-match-hero">狙击手</strong>', anon_card)
        self.assertIn('<span class="ws-match-party">无数据</span>', anon_card)
        self.assertNotIn('<span class="ws-match-party">单排</span>', anon_card)
        self.assertIn("KDA <b>无数据</b>", anon_card)
        self.assertNotIn("0/0/0", anon_card)

    def test_recent_matches_cache_does_not_poison_authenticated_fetch_with_offline_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            stale_raw = [
                {
                    "match_id": 9080302651,
                    "player_slot": 1,
                    "radiant_win": False,
                    "start_time": 1794067647,
                    "duration": 2234,
                    "hero_id": 11,
                    "kills": 1,
                    "deaths": 10,
                    "assists": 5,
                    "party_size": 3,
                    "version": 22,
                }
            ]
            fresh_raw = [
                {
                    "match_id": 9085834639,
                    "player_slot": 2,
                    "radiant_win": True,
                    "start_time": 1794475000,
                    "duration": 2567,
                    "hero_id": 17,
                    "kills": 10,
                    "deaths": 6,
                    "assists": 13,
                    "party_size": 3,
                    "version": 22,
                }
            ]
            (tmp_dir / "recent_matches_86080912.json").write_text(
                json.dumps(stale_raw, ensure_ascii=False), encoding="utf-8"
            )
            server._RECENT_MATCHES_CACHE.clear()
            with (
                patch.object(server, "REPORTS_DIR", tmp_dir),
                patch.object(server, "TMP_REPORTS_DIR", tmp_dir),
                patch.object(server, "is_match_already_analyzed", return_value=False),
                patch.object(server, "api_get", return_value=fresh_raw) as mock_api_get,
            ):
                offline_items = server.fetch_recent_matches_formatted(86080912, limit=5, allow_network=False)
                self.assertEqual(offline_items[0]["match_id"], 9080302651)
                mock_api_get.assert_not_called()

                online_items = server.fetch_recent_matches_formatted(86080912, limit=5, allow_network=True)
                mock_api_get.assert_called_once()
                self.assertEqual(online_items[0]["match_id"], 9085834639)
                self.assertEqual(online_items[0]["hero_short_zh"], "风暴之灵")
                self.assertEqual(online_items[0]["kda"], "10/6/13")
                self.assertEqual(online_items[0]["party_label"], "3人黑")

    def test_init_and_player_fetch_attach_team_token_header(self) -> None:
        node_script = r"""
const fs = require("fs");
const vm = require("vm");
const js = fs.readFileSync("static/app.js", "utf8");

function makeEl(id = "") {
  return {
    id, innerHTML: "", textContent: "", value: "", hidden: false, open: false,
    disabled: false, style: {}, dataset: {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener() {}, removeEventListener() {},
    setAttribute() {}, getAttribute() { return null; },
    querySelector() { return null; }, querySelectorAll() { return []; },
    appendChild() {}, remove() {}, close() { this.open = false; }, showModal() { this.open = true; },
  };
}
const elements = new Map();
const lsMap = new Map([["dota_ledger_team_token", "test-token-123"]]);
const calls = [];
const sandbox = {
  console, Math, Date, JSON, Number, String, Boolean, Array, Object, RegExp, Map, Set, Promise,
  Error, TypeError, parseInt, parseFloat, isNaN, isFinite, encodeURIComponent, decodeURIComponent,
  setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
  requestAnimationFrame: () => 0,
  URLSearchParams,
  localStorage: { getItem: (k) => lsMap.get(k) ?? null, setItem: (k, v) => lsMap.set(k, String(v)), removeItem: (k) => lsMap.delete(k) },
  sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  indexedDB: { open: () => ({ onupgradeneeded: null, onsuccess: null, onerror: null }) },
  navigator: { clipboard: { writeText: () => Promise.resolve() } },
  location: { search: "", pathname: "/", href: "http://localhost/", origin: "http://localhost", hash: "" },
  history: { pushState: () => {}, replaceState: () => {}, state: {} },
  scrollTo: () => {}, innerWidth: 1440,
  addEventListener: () => {}, removeEventListener: () => {},
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  fetch: (url, opts) => {
    calls.push({ url: String(url), headers: (opts && opts.headers) || {} });
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ ok: true, roster: { main_account_id: 86080912 }, profile: {}, recent_matches: [], squad_ledger: {}, heroes_catalog: [] }),
    });
  },
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
vm.runInContext(js.replace(/initApp\(\);/g, "// initApp();"), sandbox);
(async () => {
  await sandbox.initApp();
  await sandbox.handleSmartQuery("Siesta");
  process.stdout.write(JSON.stringify({ calls }));
})();
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        calls = json.loads(proc.stdout)["calls"]
        init_call = next((c for c in calls if c["url"].startswith("/api/init")), None)
        player_call = next((c for c in calls if c["url"].startswith("/api/player")), None)
        self.assertIsNotNone(init_call)
        self.assertEqual(init_call["headers"].get("X-Team-Token"), "test-token-123")
        self.assertIsNotNone(player_call)
        self.assertEqual(player_call["headers"].get("X-Team-Token"), "test-token-123")


if __name__ == "__main__":
    unittest.main()
