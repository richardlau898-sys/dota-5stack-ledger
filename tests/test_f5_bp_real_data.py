# -*- coding: utf-8 -*-
"""
F5 · BP 工具改用真实数据 单元测试
验证：
1. 删除 draft_and_phase_coach.py 中 59 个手写打分英雄字典 HERO_ARCHETYPES 及 919-949 行按英雄 ID 手写的克制分支。
2. 阵容与 BP 分析改用三类真实数据源：
   - 车队自己的全量英雄池（F1 / 历史账本，遵守 T1-9 min_games=10 最小样本量）
   - OpenDota /players/{id}/heroes 的 against_games 与 against_win（算“最常输给谁”，遵守 against_games >= 10）
   - OpenDota /heroStats 分段位选取与胜率（缓存于 .cache/hero_stats.json）
3. 明确不使用 OpenDota /heroes/{id}/matchups 职业比赛数据冒充路人局克制数据。
"""
import ast
import json
import unittest
from pathlib import Path

import dota_analyst
import draft_and_phase_coach
from tools import refresh_constants

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestF5BpRealData(unittest.TestCase):
    def test_no_hardcoded_59_hero_archetypes_or_id_counter_branches(self):
        """检查 draft_and_phase_coach.py 已移除 59 英雄手写 HERO_ARCHETYPES 大字典及手写 ID 克制分支"""
        src = (REPO_ROOT / "draft_and_phase_coach.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "HERO_ARCHETYPES" and isinstance(node.value, ast.Dict):
                    self.fail("draft_and_phase_coach.py 仍包含手写 HERO_ARCHETYPES 字典字面量")
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "HERO_ARCHETYPES" and isinstance(node.value, ast.Dict):
                        self.fail("draft_and_phase_coach.py 仍包含手写 HERO_ARCHETYPES 字典字面量")

        # 检查手写英雄 ID 克制硬编码已删除
        self.assertNotIn("(87, 135, 71, 88)", src)
        self.assertNotIn("(59, 93, 73, 36)", src)
        self.assertNotIn("if 45 in own_hids and 8 in own_hids:", src)

    def test_hero_stats_cache_and_refresh_constants_support(self):
        """验证 .cache/hero_stats.json 存在且包含分段位选取与胜率字段"""
        hero_stats_path = REPO_ROOT / ".cache" / "hero_stats.json"
        self.assertTrue(hero_stats_path.exists(), "缺少 .cache/hero_stats.json")
        data = json.loads(hero_stats_path.read_text(encoding="utf-8"))
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 120)
        first = data[0]
        self.assertIn("id", first)
        self.assertIn("pub_pick", first)
        self.assertIn("pub_win", first)
        self.assertIn("6_pick", first)
        self.assertIn("6_win", first)
        self.assertTrue(hasattr(refresh_constants, "fetch_hero_stats"))

    def test_compute_real_bp_matchup_stats_respects_min_games(self):
        """验证真实 BP 数据引擎：车队英雄池、against_games/against_win 最常输给谁、分段位胜率，严格遵守 T1-9 最小样本量"""
        self.assertTrue(hasattr(draft_and_phase_coach, "compute_real_bp_matchup_stats"))

        mock_squad_pool = {
            8: {"hero_id": 8, "hero_short_zh": "主宰", "games": 16, "wins": 11},
            45: {"hero_id": 45, "hero_short_zh": "帕格纳", "games": 4, "wins": 3},
        }
        mock_against_records = [
            {"hero_id": 76, "against_games": 15, "against_win": 4},   # 4/15 = 26.7% 胜率（最常输给谁，达标 >=10）
            {"hero_id": 93, "against_games": 12, "against_win": 5},   # 5/12 = 41.7% 胜率（达标 >=10）
            {"hero_id": 68, "against_games": 6, "against_win": 1},    # <10 局，不给胜率定性结论
        ]
        own_picks = [
            {"pos": 1, "hero_id": 8, "hero_short_zh": "主宰", "player_name": "Flame = ez mute"},
            {"pos": 5, "hero_id": 45, "hero_short_zh": "帕格纳", "player_name": "Mori"},
        ]
        enemy_picks = [
            {"pos": 2, "hero_id": 76, "hero_short_zh": "殁境神蚀者"},
            {"pos": 5, "hero_id": 68, "hero_short_zh": "远古冰魄"},
        ]

        res = draft_and_phase_coach.compute_real_bp_matchup_stats(
            own_picks=own_picks,
            enemy_picks=enemy_picks,
            squad_hero_pool=mock_squad_pool,
            against_heroes_data=mock_against_records,
        )
        self.assertIn("own_hero_real_stats", res)
        self.assertIn("enemy_against_stats", res)
        self.assertIn("most_lost_against_top", res)
        self.assertIn("data_sources", res)
        self.assertFalse(res["data_sources"].get("uses_pro_only_matchups_endpoint"))

        own_map = {x["hero_id"]: x for x in res["own_hero_real_stats"]}
        # 主宰 16 局 >= 10，有实测 squad_win_rate
        self.assertEqual(own_map[8]["squad_games"], 16)
        self.assertAlmostEqual(own_map[8]["squad_win_rate"], 68.8, places=1)
        self.assertFalse(own_map[8]["squad_insufficient_sample"])
        self.assertIsNotNone(own_map[8]["bracket_win_rate"])

        # 帕格纳 4 局 < 10，squad_win_rate 必须为 None
        self.assertEqual(own_map[45]["squad_games"], 4)
        self.assertIsNone(own_map[45]["squad_win_rate"])
        self.assertTrue(own_map[45]["squad_insufficient_sample"])

        # 敌方英雄 against 统计：76 有 15 局 >= 10，68 只有 6 局 < 10
        opp_map = {x["hero_id"]: x for x in res["enemy_against_stats"]}
        self.assertEqual(opp_map[76]["against_games"], 15)
        self.assertAlmostEqual(opp_map[76]["against_win_rate"], 26.7, places=1)
        self.assertFalse(opp_map[76]["insufficient_sample"])

        self.assertEqual(opp_map[68]["against_games"], 6)
        self.assertIsNone(opp_map[68]["against_win_rate"])
        self.assertTrue(opp_map[68]["insufficient_sample"])

        # 最常输给谁榜单只包含 against_games >= 10 的英雄
        top_lost_ids = [x["hero_id"] for x in res["most_lost_against_top"]]
        self.assertIn(76, top_lost_ids)
        self.assertIn(93, top_lost_ids)
        self.assertNotIn(68, top_lost_ids)
        self.assertEqual(top_lost_ids[0], 76)

    def test_pregame_strategy_plan_includes_real_data_bp_stats(self):
        """验证 build_pregame_strategy_plan 输出包含 real_data_bp_stats"""
        roster = dota_analyst.load_roster()
        heroes_by_id, _ = dota_analyst.get_hero_constants_map()
        plan = draft_and_phase_coach.build_pregame_strategy_plan(
            own_picks=[
                {"pos": 1, "hero_id": 8},
                {"pos": 2, "hero_id": 17},
                {"pos": 3, "hero_id": 2},
                {"pos": 4, "hero_id": 86},
                {"pos": 5, "hero_id": 5},
            ],
            enemy_picks=[
                {"pos": 1, "hero_id": 93},
                {"pos": 2, "hero_id": 76},
            ],
            roster=roster,
            heroes_by_id=heroes_by_id,
        )
        self.assertIn("real_data_bp_stats", plan)
        real_bp = plan["real_data_bp_stats"]
        self.assertEqual(len(real_bp["own_hero_real_stats"]), 5)
        self.assertEqual(len(real_bp["enemy_against_stats"]), 2)


if __name__ == "__main__":
    unittest.main()
