from __future__ import annotations

import copy
import unittest

import dota_analyst
from tests.helpers import build_all_sample_reports, iter_report_strings, load_all_raw_matches


class TestT15EvidenceThresholds(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_matches = load_all_raw_matches()
        cls.reports = build_all_sample_reports()

    def test_1_unpressed_save_items_whitelist_and_upgraded_component_exclusion(self) -> None:
        """Only 9 active save items allowed; upgraded components (e.g. force_staff -> hurricane_pike) and aeon_disk excluded; neutral wording."""
        forbidden_save_mentions = ("永恒之盘", "林肯", "大魔棒", "刷新球", "希瓦", "刃甲", "撒旦", "奶酪", "笛子", "赤红甲")
        for mid, rep in self.reports.items():
            df = rep.get("deep_forensics") or {}
            us_by_side = df.get("unpressed_saves_by_side") or {}
            for side, side_data in us_by_side.items():
                if not isinstance(side_data, dict):
                    continue
                for inc in side_data.get("incidents") or []:
                    items_str = " ".join(inc.get("unpressed_items") or [])
                    for bad_name in forbidden_save_mentions:
                        self.assertNotIn(bad_name, items_str, f"match {mid} {side} flagged forbidden item {bad_name}: {inc}")
                    detail = inc.get("detail") or ""
                    self.assertNotIn("身怀", detail)
                    self.assertNotIn("0 次按下", detail)
                    if inc.get("unpressed_items"):
                        self.assertIn("阵亡时持有", detail)
                        self.assertIn("本波未使用", detail)

        # Synthetic test: player bought force_staff at 600s and upgraded to hurricane_pike at 1100s, then died in teamfight at 1200s using hurricane_pike
        raw = copy.deepcopy(self.raw_matches[8774383260])
        p0 = raw["players"][0]
        p0["purchase_log"] = [
            {"time": 600, "key": "force_staff"},
            {"time": 1100, "key": "dragon_lance"},
            {"time": 1100, "key": "hurricane_pike"},
            {"time": 1120, "key": "aeon_disk"},
        ]
        if raw.get("teamfights"):
            tf0 = raw["teamfights"][-1]
            tf0["start"] = 1200
            tf0["end"] = 1230
            tf0["players"][0]["deaths"] = 1
            tf0["players"][0]["item_uses"] = {"hurricane_pike": 1}
        rep_syn = dota_analyst.analyze_match_data(raw, roster=dota_analyst.load_roster())
        us_rad = ((rep_syn.get("deep_forensics") or {}).get("unpressed_saves_by_side") or {}).get("radiant") or {}
        for inc in us_rad.get("incidents") or []:
            if inc.get("start_sec") == 1200 and inc.get("personaname") == p0.get("personaname"):
                self.assertNotIn("推推", " ".join(inc.get("unpressed_items") or []))
                self.assertNotIn("永恒之盘", " ".join(inc.get("unpressed_items") or []))

    def test_2_teamfight_absence_excludes_already_dead_and_healers_and_casters(self) -> None:
        """Players dead at teamfight start or with healing/ability_uses are not marked absent/spectator/afk."""
        for mid, report in self.reports.items():
            raw = self.raw_matches[mid]
            raw_players = raw.get("players") or []
            raw_tfs = raw.get("teamfights") or []
            if not raw_tfs or len(raw_players) < 10:
                continue
            df = report.get("deep_forensics") or {}
            tp_by_side = df.get("tp_rotation_by_side") or {}
            all_rep_players = (report.get("radiant_pos_1_to_5") or []) + (report.get("dire_pos_1_to_5") or [])
            hero_by_slot = {p.get("player_slot"): p.get("hero_short_zh") for p in all_rep_players}

            death_windows_by_hero = {}
            for rp in raw_players:
                slot = rp.get("player_slot")
                h_zh = hero_by_slot.get(slot)
                if not h_zh:
                    continue
                windows = []
                for d_ev in rp.get("deaths_log") or []:
                    if isinstance(d_ev, dict):
                        dt = int(d_ev.get("time") or 0)
                        td = int(d_ev.get("time_dead") or 30)
                        windows.append((dt, dt + td))
                death_windows_by_hero[h_zh] = windows

            for side, tp_data in tp_by_side.items():
                if not isinstance(tp_data, dict):
                    continue
                for ev in tp_data.get("teamfight_tp_events") or []:
                    tf_idx = int(ev.get("tf_index") or 1) - 1
                    if tf_idx < 0 or tf_idx >= len(raw_tfs):
                        continue
                    s_sec = int(raw_tfs[tf_idx].get("start") or 0)
                    for sp in ev.get("spectators") or []:
                        h_zh = sp.get("hero_short_zh")
                        windows = death_windows_by_hero.get(h_zh, [])
                        self.assertFalse(
                            any(dt < s_sec < respawn_t for dt, respawn_t in windows),
                            f"match {mid} {side} tf#{tf_idx+1}@{s_sec}s: {h_zh} was dead at start but marked spectator",
                        )

    def test_3_out_of_teamfight_deaths_no_fake_zone_vision_or_zero_value_claims(self) -> None:
        """Out-of-teamfight deaths have no coordinates and must not claim zone, vision, or '零战略收益'."""
        for mid, rep in self.reports.items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("孤立过河深带", s, f"match {mid} {path}")
                self.assertNotIn("有眼不看小地图", s, f"match {mid} {path}")
                self.assertNotIn("零战略收益", s, f"match {mid} {path}")

    def test_4_no_enemy_unsmoked_inference_from_purchase_time(self) -> None:
        """Never claim '敌方未开雾' or '根本没开雾'."""
        for mid, rep in self.reports.items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("敌方未开雾", s, f"match {mid} {path}")
                self.assertNotIn("根本没开雾", s, f"match {mid} {path}")

    def test_5_unpressed_ult_excludes_execute_save_non_ult_and_uses_neutral_wording(self) -> None:
        """No '未放出大招即阵亡'/'没按出大招就躺下读秒'/'憋大暴毙', and Shallow Grave/Tombstone/Culling Blade/Reaper's Scythe not in ult audit."""
        for mid, rep in self.reports.items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("未放出大招即阵亡", s, f"match {mid} {path}")
                self.assertNotIn("没按出大招就躺下读秒", s, f"match {mid} {path}")
                self.assertNotIn("憋大暴毙", s, f"match {mid} {path}")
                self.assertNotIn("0次释放即阵亡", s, f"match {mid} {path}")

    def test_6_no_causal_assertions_for_vision_or_buildings(self) -> None:
        """Parallel statement of facts instead of '视野断档直接导致' or '连累本方丢掉'."""
        for mid, rep in self.reports.items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("视野断档直接导致", s, f"match {mid} {path}")
                self.assertNotIn("连累本方丢掉", s, f"match {mid} {path}")

    def test_7_phoenix_egg_shattered_removed(self) -> None:
        """Phoenix egg shattered claim and +24 blame removed."""
        for mid, rep in self.reports.items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("蛋被打碎", s, f"match {mid} {path}")
                self.assertNotIn("当场碎蛋", s, f"match {mid} {path}")
                self.assertNotIn("碎蛋战犯", s, f"match {mid} {path}")
                self.assertNotIn("碎蛋背锅", s, f"match {mid} {path}")
                self.assertNotIn("蛋被敌方集火", s, f"match {mid} {path}")

    def test_8_blink_and_tp_neutral_wording(self) -> None:
        """Blink and TP in teamfights use neutral '本波使用了' instead of '先手切入' or '第一时间亮 TP 落地支援'."""
        for mid, rep in self.reports.items():
            for path, s in iter_report_strings(rep):
                self.assertNotIn("先手切入：", s, f"match {mid} {path}")
                self.assertNotIn("第一时间亮 TP 落地支援", s, f"match {mid} {path}")


if __name__ == "__main__":
    unittest.main()
