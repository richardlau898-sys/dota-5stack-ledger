import unittest
from tests.helpers import build_all_sample_reports, load_all_raw_matches


class TestT16HitRateMeaning(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_matches = load_all_raw_matches()
        cls.reports = build_all_sample_reports()

    def test_1_no_skillshot_percentage_shown_uses_avg_dmg_hits_per_cast(self) -> None:
        """Skillshot and ultimate audits use '每次施放造成 N 次伤害' instead of fake hit_pct percentage."""
        violations = []
        found_avg_dmg_text = False
        for mid, report in self.reports.items():
            df = report.get("deep_forensics") or {}
            he_by_side = df.get("hero_execution_by_side") or {}
            for side, players_list in he_by_side.items():
                if not isinstance(players_list, list):
                    continue
                for p in players_list:
                    for sa in p.get("skillshot_audits") or []:
                        if sa.get("hit_pct") is not None:
                            violations.append(
                                f"match {mid} {side} {p.get('hero_short_zh')} {sa.get('ability_zh')}: hit_pct={sa.get('hit_pct')}"
                            )
                        detail = str(sa.get("detail") or "")
                        if "%" in detail or "命中比" in detail or "命中率" in detail:
                            violations.append(
                                f"match {mid} {side} {p.get('hero_short_zh')}: percentage in skillshot detail: {detail}"
                            )
                        if int(sa.get("damage") or 0) > 0 and "每次施放造成" in detail and "次伤害" in detail:
                            found_avg_dmg_text = True
        self.assertTrue(found_avg_dmg_text, "Expected '每次施放造成 N 次伤害' in skillshot audits with damage")
        self.assertEqual(violations, [], f"Violations: {violations[:5]}")

    def test_2_ability_without_damage_inflictor_is_not_graded(self) -> None:
        """Abilities with no record (or 0 damage) in damage_inflictor must not be graded good/warn/bad."""
        violations = []
        for mid, report in self.reports.items():
            raw = self.raw_matches[mid]
            raw_by_slot = {int(rp.get("player_slot", 0)): rp for rp in (raw.get("players") or [])}
            df = report.get("deep_forensics") or {}
            he_by_side = df.get("hero_execution_by_side") or {}
            for side, players_list in he_by_side.items():
                if not isinstance(players_list, list):
                    continue
                for p in players_list:
                    pslot = int(p.get("player_slot", 0))
                    rp = raw_by_slot.get(pslot, {})
                    di = {k: int(v or 0) for k, v in (rp.get("damage_inflictor") or {}).items()}
                    for ua in p.get("ult_audits") or []:
                        ab_key = ua.get("ability_key")
                        if ab_key and (ab_key not in di or di.get(ab_key, 0) <= 0):
                            if ua.get("grade") != "neutral":
                                violations.append(
                                    f"match {mid} {side} {p.get('hero_short_zh')} ult {ab_key} has 0 damage_inflictor but grade={ua.get('grade')}"
                                )
                    for sa in p.get("skillshot_audits") or []:
                        if int(sa.get("damage") or 0) <= 0:
                            if sa.get("grade") != "neutral":
                                violations.append(
                                    f"match {mid} {side} {p.get('hero_short_zh')} skillshot {sa.get('ability_zh')} has 0 damage_inflictor but grade={sa.get('grade')}"
                                )
        self.assertEqual(violations, [], f"Violations: {violations[:5]}")

    def test_3_faceless_void_chronosphere_never_graded_bad(self) -> None:
        """Faceless Void Chronosphere deals no direct damage and must never receive a 'bad'/'差' grade."""
        void_audits = []
        violations = []
        for mid, report in self.reports.items():
            df = report.get("deep_forensics") or {}
            he_by_side = df.get("hero_execution_by_side") or {}
            for side, players_list in he_by_side.items():
                if not isinstance(players_list, list):
                    continue
                for p in players_list:
                    for ua in p.get("ult_audits") or []:
                        if ua.get("ability_key") == "faceless_void_chronosphere":
                            void_audits.append((mid, ua))
                            if ua.get("grade") in ("bad", "差", "C", "D", "F"):
                                violations.append(f"match {mid}: chronosphere grade={ua.get('grade')}")
                            vtxt = str(ua.get("verdict_text") or "")
                            if "低效" in vtxt or "差" in vtxt:
                                violations.append(f"match {mid}: chronosphere verdict={vtxt}")
        self.assertGreaterEqual(len(void_audits), 4, "Should find at least 4 Faceless Void sample matches")
        self.assertEqual(violations, [], f"Violations: {violations}")


if __name__ == "__main__":
    unittest.main()
