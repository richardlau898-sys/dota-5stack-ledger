# -*- coding: utf-8 -*-
"""英雄攻略页：数据汇总、采集限额、服务器接口与页面路由。

样本：tests/fixtures/hero_builds/ 下的 12 场真实 7.42 神话段天梯比赛（OpenDota 公开数据，
不含账号与昵称），以及按这些比赛裁剪过的 OpenDota 常量和 Valve 官方中文数据。
全部离线运行。
"""
import collections
import contextlib
import gzip
import io
import itertools
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

import hero_builds_store
import server
from tools.hero_builds import build as hb_build
from tools.hero_builds import collect as hb_collect

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "hero_builds"
CACHE = str(FIX / "cache")
CONST = str(FIX / "const")
INVENTORY_SLOTS = ("item_0", "item_1", "item_2", "item_3", "item_4", "item_5",
                   "backpack_0", "backpack_1", "backpack_2")


def _raw_matches():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((FIX / "cache" / "matches").glob("*.json"))]


class TestHeroBuildsAggregation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index, cls.heroes = hb_build.build(CACHE, CONST)
        cls.matches = _raw_matches()
        cls.item_ids = json.loads((FIX / "const" / "item_ids.json").read_text(encoding="utf-8"))

    def test_counts_and_patch(self):
        self.assertEqual(self.index["matches"], len(self.matches))
        self.assertEqual(sum(h["games"] for h in self.index["heroes"]), 10 * len(self.matches))
        self.assertEqual(self.index["patch_id"], 61)
        self.assertEqual(self.index["patch_name"], "7.42")
        self.assertTrue(self.index["has_patch_notes"])

    def test_upgrade_levels_come_from_the_data(self):
        by_level = collections.defaultdict(collections.Counter)
        for m in self.matches:
            for p in m["players"]:
                by_level[p["level"]][len(p["ability_upgrades_arr"] or [])] += 1
        expected = {lv: c.most_common(1)[0][0] for lv, c in by_level.items() if sum(c.values()) >= 8}
        got = {int(k): v for k, v in self.index["upgrades_at_level"].items()}
        for lv, cnt in expected.items():
            self.assertEqual(got[lv], cnt, f"level {lv}")
        levels = sorted(got)
        for a, b in zip(levels, levels[1:]):
            self.assertLessEqual(got[a], got[b])
            self.assertLessEqual(got[b], b + 1)

    def test_talent_text_filled_from_official_numbers(self):
        jugg = self.heroes[8]["scopes"]["all"]["talents"]
        texts = [o["zh"] for t in jugg for o in t["options"]]
        self.assertIn("-12秒 治疗守卫冷却", texts)
        self.assertIn("剑刃风暴期间+45 移动速度", texts)

    def test_win_rate_matches_the_raw_matches(self):
        n = w = 0
        for m in self.matches:
            for p in m["players"]:
                if p["hero_id"] == 8:
                    n += 1
                    w += (p["player_slot"] < 128) == bool(m["radiant_win"])
        s = self.heroes[8]["scopes"]["all"]
        self.assertEqual(s["n"], n)
        self.assertEqual(s["wr"], round(100.0 * w / n, 1))

    def test_scepter_is_counted_from_final_inventory(self):
        per_hero = collections.Counter()
        games = collections.Counter()
        for m in self.matches:
            for p in m["players"]:
                games[p["hero_id"]] += 1
                if "ultimate_scepter" in {self.item_ids.get(str(p.get(k))) for k in INVENTORY_SLOTS if p.get(k)}:
                    per_hero[p["hero_id"]] += 1
        self.assertTrue(per_hero, "fixture should contain at least one Scepter in an inventory")
        for hid, cnt in per_hero.items():
            got = self.heroes[hid]["scopes"]["all"]["scepter_pct"]
            self.assertEqual(got, round(100.0 * cnt / games[hid], 1))

    def test_neutral_tiers_come_from_official_item_list(self):
        itemlist = json.loads((FIX / "const" / "df_itemlist.json").read_text(encoding="utf-8"))
        tier_by_key = {x["name"].replace("item_", "", 1): x["neutral_item_tier"] + 1
                       for x in itemlist["result"]["data"]["itemabilities"] if x["neutral_item_tier"] >= 0}
        seen = 0
        for full in self.heroes.values():
            for scope in full["scopes"].values():
                for tier in scope["neutral"]:
                    for it in tier["items"]:
                        self.assertEqual(tier_by_key[it["k"]], tier["tier"], it["k"])
                        seen += 1
        self.assertGreater(seen, 0)

    def test_no_placeholders_or_leaked_values(self):
        text = json.dumps({"index": self.index, "heroes": self.heroes}, ensure_ascii=False)
        for bad in ("{s:", "NaN", "undefined", "None", "+-"):
            self.assertNotIn(bad, text)

    def test_patch_notes_dropped_when_they_belong_to_another_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            const = os.path.join(tmp, "const")
            shutil.copytree(CONST, const)
            pn_path = os.path.join(const, "df_patchnotes.json")
            with open(pn_path, encoding="utf-8") as fh:
                pn = json.load(fh)
            pn["patch_name"] = pn["patch_number"] = "7.99"
            with open(pn_path, "w", encoding="utf-8") as fh:
                json.dump(pn, fh, ensure_ascii=False)
            index, heroes = hb_build.build(CACHE, const)
        self.assertFalse(index["has_patch_notes"])
        self.assertTrue(all(not h["patch_notes"] for h in heroes.values()))

    def test_bundle_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = os.path.join(tmp, "out", "hero_builds.json.gz")
            hb_build.write_outputs(self.index, self.heroes, bundle=bundle, out_dir=os.path.join(tmp, "dir"))
            with open(bundle, "rb") as fh:
                data = json.loads(gzip.decompress(fh.read()))
            self.assertEqual(data["index"]["matches"], self.index["matches"])
            self.assertEqual(set(data["heroes"]), {str(k) for k in self.heroes})
            self.assertTrue(os.path.exists(os.path.join(tmp, "dir", "heroes", "8.json")))


class _FakeResponse:
    def __init__(self, body: bytes, headers=None):
        self._body = body
        self.headers = headers or {}

    def read(self, *args):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestCollector(unittest.TestCase):
    def test_prune_cache_drops_other_patches_and_keeps_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mid, patch_id, start in ((1, 61, 100), (2, 61, 300), (3, 60, 500), (4, 61, 200)):
                with open(os.path.join(tmp, f"{mid}.json"), "w") as fh:
                    json.dump({"match_id": mid, "patch": patch_id, "start_time": start}, fh)
            removed = hb_collect.prune_cache(tmp, 61, keep=2)
            self.assertEqual(removed, 2)
            self.assertEqual(sorted(os.listdir(tmp)), ["2.json", "4.json"])

    @staticmethod
    def _fake_opendota(day_left="2500"):
        """Answers the three OpenDota calls collect.py makes, without any network."""
        patch_list = [{"id": 61, "name": "7.42", "date": "2026-11-18T21:28:07.019Z"}]
        public = [{"match_id": 9100000000 + i, "start_time": 1795280000, "lobby_type": 7, "game_mode": 22,
                   "avg_rank_tier": 75, "duration": 2400} for i in range(3)]
        player = {"player_slot": 0, "hero_id": 8, "ability_upgrades_arr": [5028], "level": 1}

        def opener(req, timeout=None):
            url = req.full_url
            if url.endswith("/constants/patch"):
                body = patch_list
            elif "/publicMatches" in url:
                # first page has 3 matches; asking for older matches returns an empty page
                body = [] if "less_than_match_id" in url else public
            else:
                mid = int(url.rsplit("/", 1)[1])
                body = {"match_id": mid, "patch": 61, "start_time": 1795280000, "duration": 2400,
                        "radiant_win": True, "players": [dict(player) for _ in range(10)]}
            return _FakeResponse(json.dumps(body).encode("utf-8"),
                                 {"x-rate-limit-remaining-day": day_left, "x-rate-limit-remaining-minute": "50"})
        return opener

    def _run_main(self, argv, opener, monotonic_values=None):
        out = io.StringIO()
        patches = [patch.object(hb_collect.urllib.request, "urlopen", side_effect=opener),
                   patch.object(hb_collect.time, "sleep", lambda s: None),
                   patch.object(sys, "argv", ["collect.py"] + argv)]
        if monotonic_values is not None:
            patches.append(patch.object(hb_collect.time, "monotonic", side_effect=monotonic_values))
        with contextlib.ExitStack() as stack, contextlib.redirect_stdout(out):
            for p in patches:
                stack.enter_context(p)
            code = hb_collect.main()
        return code, out.getvalue()

    def test_time_budget_stops_cleanly_and_keeps_what_was_collected(self):
        with tempfile.TemporaryDirectory() as tmp:
            # deadline set at t=0 (10 minutes); the page and the first match are fetched in time,
            # then the clock jumps past the deadline before the second match.
            clock = itertools.chain([0, 0, 0], itertools.repeat(10_000))
            code, out = self._run_main(["--cache", tmp, "--max-matches", "100", "--max-minutes", "10",
                                        "--per-min", "6000"], self._fake_opendota(), clock)
            saved = os.listdir(os.path.join(tmp, "matches"))
        self.assertEqual(code, 0)
        self.assertEqual(len(saved), 1)
        self.assertIn("time budget of 10 minutes reached", out)

    def test_without_a_time_budget_everything_is_collected(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self._run_main(["--cache", tmp, "--max-matches", "100", "--per-min", "6000"],
                                       self._fake_opendota())
            saved = os.listdir(os.path.join(tmp, "matches"))
        self.assertEqual(code, 0)
        self.assertEqual(len(saved), 3)
        self.assertNotIn("time budget", out)

    def test_daily_reserve_is_a_clean_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self._run_main(["--cache", tmp, "--day-reserve", "1200", "--per-min", "6000"],
                                       self._fake_opendota(day_left="1100"))
            saved = os.listdir(os.path.join(tmp, "matches"))
        self.assertEqual(code, 0)
        self.assertEqual(saved, [])
        self.assertIn("daily quota reserve reached", out)

    def test_limiter_stops_before_using_the_daily_reserve(self):
        lim = hb_collect.Limiter(per_min=6000, day_reserve=1200)
        resp = _FakeResponse(b"[]", {"x-rate-limit-remaining-day": "1100", "x-rate-limit-remaining-minute": "50"})
        with patch.object(hb_collect.urllib.request, "urlopen", return_value=resp) as mocked:
            self.assertEqual(lim.get("/heroes"), [])
            with self.assertRaises(SystemExit):
                lim.get("/heroes")
            self.assertEqual(mocked.call_count, 1)


class _TestableHandler(server.DotaAnalystHandler):
    def __init__(self, method: str, path: str, headers: dict = None):
        self.command = method
        self.path = path
        self.request_version = "HTTP/1.1"
        self.headers = dict(headers or {})
        self.rfile = io.BytesIO(b"")
        self.wfile = io.BytesIO()
        self.resp_status = None
        self.resp_headers = {}

    def address_string(self) -> str:
        return "127.0.0.1"

    def send_response(self, code, message=None):
        self.resp_status = code

    def send_header(self, keyword, value):
        self.resp_headers[keyword] = value

    def end_headers(self):
        pass


class TestHeroBuildsServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        index, heroes = hb_build.build(CACHE, CONST)
        payload = {"index": index, "heroes": {str(k): v for k, v in heroes.items()}}
        cls.bundle_bytes = gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def setUp(self):
        hero_builds_store.reset_cache_for_tests()

    def tearDown(self):
        hero_builds_store.reset_cache_for_tests()

    def _get(self, path):
        h = _TestableHandler("GET", path)
        h.do_GET()
        body = h.wfile.getvalue().decode("utf-8")
        return h, body

    def test_index_and_hero_need_no_token_and_are_cacheable(self):
        with patch.object(hero_builds_store.urllib.request, "urlopen",
                          return_value=_FakeResponse(self.bundle_bytes)) as mocked:
            h, body = self._get("/api/hero_builds")
            self.assertEqual(h.resp_status, 200)
            data = json.loads(body)
            self.assertTrue(data["ok"])
            self.assertEqual(data["index"]["matches"], 12)
            self.assertIn("public", h.resp_headers.get("Cache-Control", ""))
            h2, body2 = self._get("/api/hero_builds/8")
            self.assertEqual(h2.resp_status, 200)
            self.assertEqual(json.loads(body2)["hero"]["id"], 8)
            self.assertEqual(mocked.call_count, 1, "bundle should be downloaded once and reused")

    def test_bad_and_unknown_hero_ids(self):
        with patch.object(hero_builds_store.urllib.request, "urlopen",
                          return_value=_FakeResponse(self.bundle_bytes)):
            for path, status in (("/api/hero_builds/abc", 400), ("/api/hero_builds/..%2fx", 400),
                                 ("/api/hero_builds/99999", 400), ("/api/hero_builds/9999", 404)):
                h, body = self._get(path)
                self.assertEqual(h.resp_status, status, path)
                self.assertFalse(json.loads(body)["ok"])

    def test_download_failure_returns_plain_message(self):
        err = urllib.error.URLError("boom /etc/passwd")
        with patch.object(hero_builds_store.urllib.request, "urlopen", side_effect=err):
            h, body = self._get("/api/hero_builds")
        self.assertEqual(h.resp_status, 503)
        for leak in ("boom", "passwd", "URLError", "Traceback"):
            self.assertNotIn(leak, body)
        self.assertIn("英雄攻略数据暂时取不到", json.loads(body)["error"])

    def test_old_data_is_served_when_a_refresh_fails(self):
        with patch.object(hero_builds_store.urllib.request, "urlopen",
                          return_value=_FakeResponse(self.bundle_bytes)):
            bundle, stale = hero_builds_store.get_bundle(now=1000.0)
        self.assertFalse(stale)
        later = 1000.0 + hero_builds_store.REFRESH_SECONDS + 1
        with patch.object(hero_builds_store.urllib.request, "urlopen", side_effect=OSError("down")):
            bundle2, stale2 = hero_builds_store.get_bundle(now=later)
        self.assertTrue(stale2)
        self.assertEqual(bundle2["index"]["matches"], 12)

    def test_heroes_page_and_script_are_served(self):
        h, body = self._get("/heroes")
        self.assertEqual(h.resp_status, 200)
        self.assertIn("英雄攻略", body)
        self.assertIn('src="/static/heroes.js"', body)
        self.assertNotRegex(body, r"<script>(?!\s*</script>)", "no inline scripts (CSP)")
        h2, _ = self._get("/static/heroes.js")
        self.assertEqual(h2.resp_status, 200)

    def test_vercel_rewrite_and_sidebar_link(self):
        vercel = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        self.assertIn({"source": "/heroes", "destination": "/static/heroes.html"}, vercel["rewrites"])
        self.assertIn('href="/heroes"', (ROOT / "static" / "index.html").read_text(encoding="utf-8"))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_heroes_js_parses(self):
        subprocess.run(["node", "--check", str(ROOT / "static" / "heroes.js")], check=True)


if __name__ == "__main__":
    unittest.main()
