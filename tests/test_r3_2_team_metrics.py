import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestR32TeamMetrics(unittest.TestCase):
    """R3-2 · 团队指标（F3）：买活后再死精确按 kills_log 计算、高危眼位配对 obs_log/obs_left_log、开雾按团战 item_uses、禁止吞异常。"""

    def test_1_buyback_diebacks_matches_independent_kills_log_across_all_samples(self):
        from dota_analyst import analyze_match_data, get_hero_constants_map
        import squad_growth_metrics

        # 断言 _collect_hero_death_timestamps 不再吞异常 (except Exception: pass)
        src = Path(squad_growth_metrics.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_collect_hero_death_timestamps":
                for sub in ast.walk(node):
                    self.assertNotIsInstance(
                        sub,
                        ast.Try,
                        "_collect_hero_death_timestamps must not wrap hero mapping in try/except",
                    )

        hmap, _ = get_hero_constants_map()
        roster = json.loads((ROOT / "roster.json").read_text(encoding="utf-8"))

        expected_total = 0
        actual_total = 0

        for raw_path in sorted((ROOT / "reports").glob("raw_*.json")):
            raw_m = json.loads(raw_path.read_text(encoding="utf-8"))
            if not raw_m.get("version"):
                continue

            # 独立用 kills_log + buyback_log 计算本局买活后 60 秒内再死次数
            npc_to_slot = {}
            for p in raw_m.get("players") or []:
                slot = int(p.get("player_slot") or 0)
                hid = int(p.get("hero_id") or 0)
                npc = (hmap.get(hid) or {}).get("npc") or p.get("hero_name") or ""
                if npc:
                    npc_to_slot[npc] = slot

            deaths_by_slot = {}
            for p in raw_m.get("players") or []:
                for kl in p.get("kills_log") or []:
                    t_key = str(kl.get("key") or "")
                    if t_key in npc_to_slot and kl.get("time") is not None:
                        deaths_by_slot.setdefault(npc_to_slot[t_key], set()).add(int(kl["time"]))

            exp_match = 0
            for p in raw_m.get("players") or []:
                slot = int(p.get("player_slot") or 0)
                d_sorted = sorted(deaths_by_slot.get(slot, set()))
                for bb in p.get("buyback_log") or []:
                    if isinstance(bb, dict) and bb.get("time") is not None:
                        bb_t = int(bb["time"])
                        if any(0 < dt - bb_t <= 60 for dt in d_sorted):
                            exp_match += 1

            rep = analyze_match_data(raw_m, roster)
            tm_by_side = rep["team_metrics_by_side"]
            act_match = len(tm_by_side["radiant"]["buyback_diebacks"]) + len(
                tm_by_side["dire"]["buyback_diebacks"]
            )
            self.assertEqual(
                act_match,
                exp_match,
                f"Match {raw_m.get('match_id')}: buyback_diebacks {act_match} != kills_log ground truth {exp_match}",
            )
            expected_total += exp_match
            actual_total += act_match

        self.assertGreater(expected_total, 0)
        self.assertEqual(actual_total, expected_total)

    def test_2_ward_lifespan_paired_and_high_risk_wards_non_empty_on_samples(self):
        from dota_analyst import analyze_match_data
        from squad_growth_metrics import aggregate_high_risk_ward_spots

        roster = json.loads((ROOT / "roster.json").read_text(encoding="utf-8"))
        sample_reports = []
        matches_with_short_wards = 0
        wards_with_lifespan = 0

        for raw_path in sorted((ROOT / "reports").glob("raw_*.json")):
            raw_m = json.loads(raw_path.read_text(encoding="utf-8"))
            if not raw_m.get("version"):
                continue
            rep = analyze_match_data(raw_m, roster)
            sample_reports.append(rep)

            for w in (rep.get("vision_and_map_data") or {}).get("wards") or []:
                if w.get("type") == "obs" and w.get("lifespan_sec") is not None:
                    wards_with_lifespan += 1

            tm = rep["team_metrics_by_side"]
            if tm["radiant"]["short_lived_wards_under_2m"] or tm["dire"]["short_lived_wards_under_2m"]:
                matches_with_short_wards += 1

        self.assertGreater(wards_with_lifespan, 50, "obs wards must populate lifespan_sec from obs_log/obs_left_log")
        self.assertGreaterEqual(
            matches_with_short_wards,
            1,
            "At least one sample match must have non-empty short_lived_wards_under_2m",
        )

        cross_spots = aggregate_high_risk_ward_spots(sample_reports)
        self.assertGreaterEqual(
            len(cross_spots),
            1,
            "Cross-match high_risk_ward_spots from generated reports must be non-empty on sample set",
        )

    def test_3_smoke_effectiveness_never_infers_from_purchase_log(self):
        from squad_growth_metrics import build_team_metrics_by_side

        synthetic_match = {
            "radiant_win": True,
            "radiant_gold_adv": [0, 1000],
            "objectives": [],
            "teamfights": [
                {
                    "start": 800,
                    "end": 830,
                    "players": [{"deaths": 0, "item_uses": {}} for _ in range(10)],
                }
            ],
            "players": [
                {
                    "player_slot": 0,
                    "hero_id": 1,
                    "purchase_log": [{"time": 790, "key": "smoke_of_deceit"}],
                    "item_uses": {"smoke_of_deceit": 1},
                    "kills_log": [],
                    "buyback_log": [],
                }
            ],
        }
        synthetic_report = {
            "is_parsed": True,
            "radiant_win": True,
            "radiant_gold_adv": [0, 1000],
            "radiant_pos_1_to_5": [{"player_slot": 0, "pos": 5, "hero_short_zh": "敌法师", "personaname": "P1"}],
            "dire_pos_1_to_5": [],
        }
        tm = build_team_metrics_by_side(synthetic_match, synthetic_report)
        self.assertEqual(
            tm["radiant"]["smoke_effectiveness"]["smoke_windows"],
            [],
            "Purchase without teamfight item_uses.smoke_of_deceit must produce 0 smoke_windows",
        )


if __name__ == "__main__":
    unittest.main()
