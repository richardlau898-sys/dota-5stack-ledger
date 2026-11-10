import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "supabase_schema.sql"


class TestF1FullHistorySync(unittest.TestCase):
    def test_supabase_schema_defines_player_matches_table(self):
        """supabase_schema.sql must define public.player_matches table for F1."""
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS public.player_matches", sql)
        self.assertIn("PRIMARY KEY (account_id, match_id)", sql)

    def test_incremental_sync_rate_limit_and_query_params(self):
        """sync_player_matches builds significant=0 & project params, respects incremental max_match_id and rate limit."""
        from tools.sync_full_match_history import (
            MATCH_PROJECT_FIELDS,
            aggregate_full_history_stats,
            build_player_matches_url,
            sync_player_matches_incremental,
        )

        url = build_player_matches_url(
            account_id=86080912,
            included_account_id=125383759,
            limit=100,
        )
        self.assertIn("/players/86080912/matches?", url)
        self.assertIn("significant=0", url)
        self.assertIn("included_account_id=125383759", url)
        for field in ("hero_id", "start_time", "duration", "player_slot", "radiant_win", "party_size"):
            self.assertIn(field, MATCH_PROJECT_FIELDS)
            self.assertIn(f"project={field}", url)

        fake_api_matches = [
            {
                "match_id": 9005,
                "player_slot": 0,
                "radiant_win": True,
                "hero_id": 8,
                "duration": 2400,
                "start_time": 1760005000,
                "kills": 12,
                "deaths": 2,
                "assists": 10,
                "party_size": 5,
                "lane_role": 1,
            },
            {
                "match_id": 9004,
                "player_slot": 128,
                "radiant_win": True,
                "hero_id": 8,
                "duration": 2100,
                "start_time": 1760001000,
                "kills": 4,
                "deaths": 7,
                "assists": 6,
                "party_size": 5,
                "lane_role": 1,
            },
            {
                "match_id": 9001,
                "player_slot": 0,
                "radiant_win": True,
                "hero_id": 8,
                "duration": 1800,
                "start_time": 1759990000,
                "kills": 9,
                "deaths": 1,
                "assists": 8,
                "party_size": 5,
                "lane_role": 1,
            },
        ]
        calls = []

        def fake_fetcher(req_url: str):
            calls.append(req_url)
            return fake_api_matches

        existing_rows = [
            {
                "account_id": 86080912,
                "match_id": 9001,
                "player_slot": 0,
                "radiant_win": True,
                "won": True,
                "hero_id": 8,
                "pos": 1,
                "party_size": 5,
            }
        ]
        merged, sync_meta = sync_player_matches_incremental(
            account_id=86080912,
            existing_rows=existing_rows,
            fetcher=fake_fetcher,
            daily_used=10,
            daily_limit=2000,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(sync_meta["new_matches_added"], 2)
        self.assertEqual(sync_meta["max_match_id"], 9005)
        self.assertEqual(len(merged), 3)

    def test_aggregation_hero_position_and_party_combinations_respect_t1_9(self):
        """aggregate_full_history_stats computes hero, position, and party combination winrates respecting min_games=10."""
        from tools.sync_full_match_history import aggregate_full_history_stats

        rows = []
        # 12 games together on match_ids 1001..1012 for accounts 86080912 (hero 8, pos 1) and 125383759 (hero 26, pos 5)
        for i in range(12):
            mid = 1001 + i
            won = i < 9  # 9 wins out of 12 = 75.0%
            rows.append({
                "account_id": 86080912,
                "match_id": mid,
                "player_slot": 0,
                "radiant_win": won,
                "won": won,
                "hero_id": 8,
                "pos": 1,
                "party_size": 5,
                "duration": 2200,
                "start_time": 1760000000 + i * 3600,
            })
            rows.append({
                "account_id": 125383759,
                "match_id": mid,
                "player_slot": 4,
                "radiant_win": won,
                "won": won,
                "hero_id": 26,
                "pos": 5,
                "party_size": 5,
                "duration": 2200,
                "start_time": 1760000000 + i * 3600,
            })
        # Add 3 games on hero 14 (< 10 games -> insufficient_sample=True)
        for i in range(3):
            mid = 2001 + i
            rows.append({
                "account_id": 86080912,
                "match_id": mid,
                "player_slot": 0,
                "radiant_win": False,
                "won": False,
                "hero_id": 14,
                "pos": 4,
                "party_size": 2,
                "duration": 2000,
                "start_time": 1760500000 + i * 3600,
            })

        stats = aggregate_full_history_stats(
            rows,
            roster_names={86080912: "Flame", 125383759: "Siesta"},
            min_games=10,
        )
        p_flame = stats["players"][86080912]
        hero8 = next(h for h in p_flame["hero_winrates"] if h["hero_id"] == 8)
        self.assertEqual(hero8["games"], 12)
        self.assertEqual(hero8["wins"], 9)
        self.assertEqual(hero8["win_rate"], 75.0)
        self.assertFalse(hero8["insufficient_sample"])

        hero14 = next(h for h in p_flame["hero_winrates"] if h["hero_id"] == 14)
        self.assertEqual(hero14["games"], 3)
        self.assertIsNone(hero14["win_rate"])
        self.assertTrue(hero14["insufficient_sample"])

        pos1 = next(p for p in p_flame["position_winrates"] if p["pos"] == 1)
        self.assertEqual(pos1["games"], 12)
        self.assertEqual(pos1["win_rate"], 75.0)

        combos = stats["combo_winrates"]
        self.assertTrue(any(c["games"] == 12 and c["win_rate"] == 75.0 for c in combos))


if __name__ == "__main__":
    unittest.main()
