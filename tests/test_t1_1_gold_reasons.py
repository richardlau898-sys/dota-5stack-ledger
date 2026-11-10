import unittest
from tests.helpers import build_all_sample_reports, load_all_raw_matches


class TestT11GoldReasons(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_matches = load_all_raw_matches()

    def test_gold_reason_keys_constant_shared_and_used(self) -> None:
        import dota_constants_zh
        self.assertTrue(hasattr(dota_constants_zh, "GOLD_REASON_KEYS"))
        gr_keys = dota_constants_zh.GOLD_REASON_KEYS
        self.assertEqual(gr_keys["other"], "0")
        self.assertEqual(gr_keys["death_loss"], "1")
        self.assertEqual(gr_keys["buyback"], "2")
        self.assertEqual(gr_keys["sell_item"], "6")
        self.assertEqual(gr_keys["building"], "11")
        self.assertEqual(gr_keys["hero_kill"], "12")
        self.assertEqual(gr_keys["lane_creep"], "13")
        self.assertEqual(gr_keys["neutral_creep"], "14")
        self.assertEqual(gr_keys["roshan"], "15")
        self.assertEqual(gr_keys["courier"], "16")
        self.assertEqual(gr_keys["bounty_rune"], "17")
        self.assertEqual(gr_keys["ward_kill"], "20")

    def test_death_gold_reason_matches_deaths_log_sum_and_report_econ(self) -> None:
        import dota_constants_zh
        gr_keys = dota_constants_zh.GOLD_REASON_KEYS
        reports = build_all_sample_reports(force_rebuild=True)

        for mid, raw in self.raw_matches.items():
            for rp in raw.get("players") or []:
                gr = rp.get("gold_reasons")
                d_log = rp.get("deaths_log")
                if not isinstance(gr, dict) or not isinstance(d_log, list):
                    continue
                gr_death = abs(int(gr.get(gr_keys["death_loss"]) or 0))
                log_death_sum = sum(abs(int(d.get("gold_lost") or 0)) for d in d_log if isinstance(d, dict))
                self.assertEqual(
                    gr_death,
                    log_death_sum,
                    f"match {mid} slot {rp.get('player_slot')}: abs(gold_reasons['1']) != sum(deaths_log.gold_lost)",
                )

            report = reports[mid]
            df = report.get("deep_forensics") or {}
            econ_by_side = df.get("economy_and_pings_by_side") or {}
            for side, side_key in (("radiant", "radiant_pos_1_to_5"), ("dire", "dire_pos_1_to_5")):
                team_players = report.get(side_key) or []
                p_by_hero = {p.get("hero_short_zh"): p for p in team_players}
                for row in (econ_by_side.get(side) or {}).get("econ_rows") or []:
                    hero_zh = row.get("hero_short_zh")
                    p_obj = p_by_hero.get(hero_zh) or {}
                    # death_loss in microscope must equal death_gold_lost in dota_analyst
                    self.assertEqual(
                        row.get("death_loss"),
                        p_obj.get("death_gold_lost"),
                        f"match {mid} {side} {hero_zh}: microscope death_loss != dota_analyst death_gold_lost",
                    )
                    if int(p_obj.get("buybacks") or 0) == 0:
                        self.assertEqual(
                            int(row.get("buyback_loss") or 0),
                            0,
                            f"match {mid} {side} {hero_zh}: 0 buybacks must have 0 buyback_loss",
                        )


if __name__ == "__main__":
    unittest.main()
