import unittest
from tests.helpers import build_all_sample_reports


class TestR24KillGoldTag(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reports = build_all_sample_reports()

    def test_1_kill_gold_king_tag_falls_around_top_10_percent(self) -> None:
        """Across all 210 parsed players, '⚔️ 以战养战提款王' should land around top ~10% (15..26), not 105/210."""
        total_rows = 0
        tagged_rows = []
        for mid, rep in sorted(self.reports.items()):
            econ = (rep.get("deep_forensics") or {}).get("economy_and_pings_by_side") or {}
            for sk in ("radiant", "dire"):
                sd = econ.get(sk)
                if not isinstance(sd, dict):
                    continue
                for r in sd.get("econ_rows") or []:
                    total_rows += 1
                    if r.get("econ_tag") == "⚔️ 以战养战提款王":
                        tagged_rows.append((mid, r.get("pos"), r.get("hero_short_zh"), r.get("kill_pct"), r.get("kill_gold")))

        self.assertEqual(total_rows, 210)
        self.assertGreaterEqual(len(tagged_rows), 15, f"Too few tagged ({len(tagged_rows)}/210)")
        self.assertLessEqual(len(tagged_rows), 26, f"Too many tagged ({len(tagged_rows)}/210)")
        core_cnt = sum(1 for _, pos, *_ in tagged_rows if int(pos) in (1, 2, 3))
        sup_cnt = sum(1 for _, pos, *_ in tagged_rows if int(pos) in (4, 5))
        self.assertGreaterEqual(core_cnt, 5)
        self.assertGreaterEqual(sup_cnt, 5)


if __name__ == "__main__":
    unittest.main()
