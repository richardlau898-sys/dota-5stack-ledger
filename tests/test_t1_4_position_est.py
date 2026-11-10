from __future__ import annotations

import copy
import unittest

import dota_analyst
from tests.helpers import build_all_sample_reports, load_all_raw_matches


class TestT14PositionEst(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_matches = load_all_raw_matches()
        cls.reports = build_all_sample_reports()

    def test_position_est_used_when_available(self) -> None:
        """All sample matches with OpenDota position_est must match position_est and record pos_source='opendota'."""
        checked_teams = 0
        for mid, raw in self.raw_matches.items():
            rep = self.reports[mid]
            raw_players = raw.get("players") or []
            rad_raw = [p for p in raw_players if p.get("isRadiant") or (p.get("player_slot", 0) < 128)]
            dire_raw = [p for p in raw_players if not (p.get("isRadiant") or (p.get("player_slot", 0) < 128))]
            for side_raw, rep_key in ((rad_raw, "radiant_pos_1_to_5"), (dire_raw, "dire_pos_1_to_5")):
                est_set = {p.get("position_est") for p in side_raw}
                if est_set == {1, 2, 3, 4, 5}:
                    checked_teams += 1
                    est_by_slot = {int(p.get("player_slot", 0)): int(p["position_est"]) for p in side_raw}
                    rep_players = rep.get(rep_key) or []
                    for fp in rep_players:
                        slot = int(fp.get("player_slot", 0))
                        self.assertEqual(
                            fp.get("pos"),
                            est_by_slot[slot],
                            f"match {mid} {rep_key} slot {slot} ({fp.get('hero_short_zh')}) pos={fp.get('pos')} != position_est={est_by_slot[slot]}",
                        )
                        self.assertEqual(fp.get("pos_source"), "opendota")
        self.assertGreaterEqual(checked_teams, 40)

    def test_fallback_when_position_est_missing(self) -> None:
        """When position_est is absent (e.g. match 8646427108), positions 1..5 are inferred and pos_source='inferred'."""
        rep = self.reports[8646427108]
        for rep_key in ("radiant_pos_1_to_5", "dire_pos_1_to_5"):
            rep_players = rep.get(rep_key) or []
            self.assertEqual([fp.get("pos") for fp in rep_players], [1, 2, 3, 4, 5])
            for fp in rep_players:
                self.assertEqual(fp.get("pos_source"), "inferred")

    def test_roster_manual_position_overrides_by_match(self) -> None:
        """roster.json match_position_overrides overrides positions per match and sets pos_source='manual'."""
        raw = copy.deepcopy(self.raw_matches[8774383260])
        roster = copy.deepcopy(dota_analyst.load_roster())
        rad_raw = [p for p in (raw.get("players") or []) if p.get("isRadiant") or (p.get("player_slot", 0) < 128)]
        p4_slot = next(int(p["player_slot"]) for p in rad_raw if p.get("position_est") == 4)
        p5_slot = next(int(p["player_slot"]) for p in rad_raw if p.get("position_est") == 5)
        roster["match_position_overrides"] = {
            "8774383260": {
                f"slot:{p4_slot}": 5,
                f"slot:{p5_slot}": 4,
            }
        }
        rep = dota_analyst.analyze_match_data(raw, roster=roster)
        rad_by_slot = {int(fp.get("player_slot") or 0): fp for fp in (rep.get("radiant_pos_1_to_5") or [])}
        self.assertEqual(rad_by_slot[p4_slot]["pos"], 5)
        self.assertEqual(rad_by_slot[p4_slot]["pos_source"], "manual")
        self.assertEqual(rad_by_slot[p5_slot]["pos"], 4)
        self.assertEqual(rad_by_slot[p5_slot]["pos_source"], "manual")
        self.assertEqual([fp.get("pos") for fp in rep.get("radiant_pos_1_to_5") or []], [1, 2, 3, 4, 5])


if __name__ == "__main__":
    unittest.main()
