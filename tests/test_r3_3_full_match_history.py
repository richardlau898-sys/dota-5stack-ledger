import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class TestR33FullMatchHistory(unittest.TestCase):
    def test_1_no_inferred_pos_and_no_default_party_size(self):
        """R3-3: 位置读不到就留空（不从 lane_role/is_roaming/default_pos 推断），party_size 缺失时不默认成 1 或 5。"""
        from tools.sync_full_match_history import (
            aggregate_full_history_stats,
            build_rows_from_local_raw_reports,
            normalize_player_match_row,
        )

        # Safelane hard support has lane_role=1 in OpenDota summary; pos must remain None!
        row_sup = normalize_player_match_row(
            125383759,
            {
                "match_id": 91001,
                "player_slot": 4,
                "radiant_win": True,
                "hero_id": 30,
                "lane_role": 1,
                "is_roaming": False,
                # party_size omitted
            },
            default_pos=5,
        )
        self.assertIsNotNone(row_sup)
        self.assertIsNone(row_sup["pos"], "pos must be None when raw_row lacks explicit pos")
        self.assertIsNone(row_sup["party_size"], "missing party_size must be None, not 1 or 5")
        self.assertEqual(row_sup["lane_role"], 1)

        row_roam = normalize_player_match_row(
            897104282,
            {
                "match_id": 91002,
                "player_slot": 3,
                "radiant_win": False,
                "hero_id": 86,
                "is_roaming": True,
                # lane_role omitted, party_size=None
                "party_size": None,
            },
            default_pos=4,
        )
        self.assertIsNone(row_roam["pos"])
        self.assertIsNone(row_roam["lane_role"])
        self.assertIsNone(row_roam["party_size"])

        # Seed builder must also not default missing party_size to 5 or infer pos
        seed_rows = build_rows_from_local_raw_reports()
        self.assertGreater(len(seed_rows), 0)
        for sr in seed_rows:
            self.assertIsNone(sr["pos"])

        # Aggregation with missing pos and missing party_size must not fabricate position or party_size counts
        sample_rows = [
            {
                "account_id": 125383759,
                "match_id": 92000 + i,
                "player_slot": 4,
                "radiant_win": True,
                "won": True,
                "hero_id": 30,
                "lane_role": 1,
                "party_size": None,
            }
            for i in range(12)
        ]
        stats = aggregate_full_history_stats(sample_rows, roster_names={125383759: "Mori"}, min_games=10)
        p_mori = stats["players"][125383759]
        for pb in p_mori["position_winrates"]:
            self.assertEqual(pb["games"], 0, f"pos {pb['pos']} must have 0 games when pos is None")
        self.assertEqual(stats["party_size_winrates"], [], "None party_size must not create party_size=1 or 5 buckets")

        sql = (ROOT / "supabase_schema.sql").read_text(encoding="utf-8")
        self.assertIn("ALTER COLUMN pos DROP NOT NULL", sql)
        self.assertIn("ALTER COLUMN party_size DROP NOT NULL", sql)

    def test_2_true_incremental_pagination_stops_at_max_existing_match_id(self):
        """R3-3: 增量同步必须分页请求（带 limit/offset），遇到已同步的 max_match_id 立即停止，不拉全量。"""
        from tools.sync_full_match_history import sync_player_matches_incremental

        # Construct 1,750 remote matches: 5250 down to 3501 (250 newer than 5000, 1500 <= 5000)
        remote_all = [
            {
                "match_id": mid,
                "player_slot": 0,
                "radiant_win": (mid % 2 == 0),
                "hero_id": 8,
                "duration": 2200,
                "start_time": 1700000000 + mid * 100,
                "kills": 8,
                "deaths": 3,
                "assists": 9,
                "party_size": 5,
            }
            for mid in range(5250, 3500, -1)
        ]
        calls = []

        def paged_fetcher(url: str):
            calls.append(url)
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            self.assertIn("limit", qs, "incremental sync must pass limit parameter")
            lim = int(qs["limit"][0])
            off = int(qs.get("offset", ["0"])[0])
            return remote_all[off : off + lim]

        existing = [
            {
                "account_id": 86080912,
                "match_id": 5000,
                "player_slot": 0,
                "radiant_win": True,
                "won": True,
                "hero_id": 8,
                "party_size": 5,
            }
        ]
        merged, meta = sync_player_matches_incremental(
            account_id=86080912,
            existing_rows=existing,
            fetcher=paged_fetcher,
            daily_used=0,
            daily_limit=2000,
        )
        # 250 new matches at page_size=100 -> pages at offset 0, 100, 200 (3rd page contains 5050..4951, hits <=5000 and stops!)
        self.assertEqual(len(calls), 3, f"expected 3 paginated requests, got {len(calls)}: {calls}")
        self.assertEqual(meta["new_matches_added"], 250)
        self.assertEqual(meta["max_match_id"], 5250)
        self.assertEqual(len(merged), 251)

    def test_3_sync_roster_passes_included_account_id_and_aggregates_combos(self):
        """R3-3: sync_roster_matches 传入 included_account_id 查询队友同场记录，并聚合进 combo_winrates。"""
        from tools.sync_full_match_history import aggregate_full_history_stats, sync_roster_matches

        roster = {
            "main_account_id": 86080912,
            "players": {
                "86080912": {"name": "Flame", "pos": 2},
                "125383759": {"name": "Mori", "pos": 5},
            },
        }
        seen_urls = []

        def fake_fetcher(url: str):
            seen_urls.append(url)
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            inc = qs.get("included_account_id", [None])[0]
            if "/players/86080912/matches" in parsed.path and inc is None:
                return [
                    {
                        "match_id": 8000 + i,
                        "player_slot": 0,
                        "radiant_win": i < 8,
                        "hero_id": 106,
                        "duration": 2100,
                        "start_time": 1760000000 + i * 3600,
                        "party_size": 2,
                    }
                    for i in range(12)
                ]
            if "/players/86080912/matches" in parsed.path and inc == "125383759":
                # Mori has private profile (returns [] directly), but included_account_id on Flame finds all 12 games!
                return [
                    {
                        "match_id": 8000 + i,
                        "player_slot": 0,
                        "radiant_win": i < 8,
                        "hero_id": 106,
                        "duration": 2100,
                        "start_time": 1760000000 + i * 3600,
                        "party_size": 2,
                    }
                    for i in range(12)
                ]
            return []

        synced_rows, sync_summary = sync_roster_matches(
            roster=roster,
            existing_rows=[],
            fetcher=fake_fetcher,
            min_interval_sec=0.0,
        )
        self.assertTrue(
            any("included_account_id=125383759" in u for u in seen_urls),
            f"expected included_account_id=125383759 in {seen_urls}",
        )
        self.assertEqual(len(synced_rows), 12)
        self.assertTrue(all(125383759 in (r.get("included_roster_ids") or []) for r in synced_rows))

        stats = aggregate_full_history_stats(synced_rows, roster=roster, min_games=10)
        self.assertEqual(len(stats["combo_winrates"]), 1)
        combo = stats["combo_winrates"][0]
        self.assertEqual(combo["account_ids"], [86080912, 125383759])
        self.assertEqual(combo["games"], 12)
        self.assertAlmostEqual(combo["win_rate"], 66.7, places=1)

    def test_4_server_and_ledger_read_player_matches_and_frontend_renders_it(self):
        """R3-3: cloud_store -> build_squad_history_ledger -> static/app.js 全链路接通 player_matches。"""
        import cloud_store
        import dota_analyst
        import draft_and_phase_coach

        self.assertTrue(hasattr(cloud_store, "cloud_fetch_player_matches"))
        roster = dota_analyst.load_roster()
        fake_pm_rows = [
            {
                "account_id": 86080912,
                "match_id": 990000 + i,
                "player_slot": 1,
                "radiant_win": i < 9,
                "won": i < 9,
                "hero_id": 17,
                "hero_short_zh": "风暴之灵",
                "pos": None,
                "lane_role": 2,
                "kills": 11,
                "deaths": 4,
                "assists": 13,
                "duration": 2350,
                "start_time": 1762000000 + i * 4000,
                "party_size": 5,
                "included_roster_ids": [114933560, 125383759],
            }
            for i in range(12)
        ]

        with patch("cloud_store.cloud_fetch_player_matches", return_value=fake_pm_rows):
            draft_and_phase_coach._LEDGER_MEM_CACHE.clear()
            ledger = draft_and_phase_coach.build_squad_history_ledger(ROOT / "reports", roster, [])
            f1 = ledger.get("full_history_stats")
            self.assertIsInstance(f1, dict)
            self.assertEqual(f1.get("synced_rows_count"), 12)
            self.assertEqual(f1.get("synced_players_count"), 1)
            p_main = f1["players"].get("86080912") or f1["players"].get(86080912)
            self.assertIsNotNone(p_main)
            self.assertEqual(p_main["total_games"], 12)
            self.assertEqual(p_main["win_rate"], 75.0)

        app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("squad-full-history-f1", app_js)
        self.assertIn("full_history_stats", app_js)


if __name__ == "__main__":
    unittest.main()
