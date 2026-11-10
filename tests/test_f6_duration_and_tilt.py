# -*- coding: utf-8 -*-
"""
F6 · 时长画像和连打疲劳 单元测试
验证：
1. 按比赛时长分桶 (<30m, 30–40m, 40–50m, >=50m) 的胜率计算。
2. 按“当晚第几局”分桶（两局开始时间间隔 < 90 分钟即 5400 秒算同一晚）的胜率计算。
3. 严格遵守 T1-9 最小样本量规则（< 10 局 win_rate=None, insufficient_sample=True）。
4. 与 F1 (tools.sync_full_match_history.aggregate_full_history_stats) 和跨局账本 (build_squad_history_ledger) 打通。
"""
import unittest

import draft_and_phase_coach
import squad_growth_metrics
from tools import sync_full_match_history


class TestF6DurationAndTilt(unittest.TestCase):
    def test_duration_and_session_buckets_with_min_games_rule(self):
        """验证时长分桶与 90 分钟间隔同晚连打分桶，以及 <10 局与 >=10 局最小样本量规则"""
        rows = []
        base_time = 1730000000
        # 构造 12 场同一晚的第 1 局（每场之间间隔 >= 90m 即 7200s），时长均在 30-40m (2100s)，赢 9 场
        for i in range(12):
            st = base_time + i * 20000
            rows.append({
                "account_id": 135243282,
                "match_id": 900000 + i * 10,
                "player_slot": 0,
                "radiant_win": i < 9,
                "won": i < 9,
                "hero_id": 8,
                "duration": 2100,
                "start_time": st,
            })
            # 紧接着每晚打第 2 局（间隔 3600s < 5400s），时长 >=50m (3200s)，赢 3 场（共 12 场）
            rows.append({
                "account_id": 135243282,
                "match_id": 900000 + i * 10 + 1,
                "player_slot": 0,
                "radiant_win": i < 3,
                "won": i < 3,
                "hero_id": 17,
                "duration": 3200,
                "start_time": st + 3600,
            })
        # 再加 4 场当晚第 3 局（<10 局样本不足），时长 <30m (1500s)
        for i in range(4):
            st = base_time + i * 20000 + 6600  # 距离第 2 局 3000s (< 5400s)
            rows.append({
                "account_id": 135243282,
                "match_id": 900000 + i * 10 + 2,
                "player_slot": 0,
                "radiant_win": False,
                "won": False,
                "hero_id": 2,
                "duration": 1500,
                "start_time": st,
            })

        res = squad_growth_metrics.compute_duration_and_session_tilt_buckets(rows, min_games=10, session_gap_sec=5400)
        dur_map = {b["key"]: b for b in res["duration_buckets"]}
        sess_map = {b["game_index"]: b for b in res["session_game_buckets"]}

        # 30-40m 有 12 局 >= 10，胜率 9/12 = 75.0%
        self.assertEqual(dur_map["30_to_40m"]["games"], 12)
        self.assertEqual(dur_map["30_to_40m"]["wins"], 9)
        self.assertEqual(dur_map["30_to_40m"]["win_rate"], 75.0)
        self.assertFalse(dur_map["30_to_40m"]["insufficient_sample"])

        # >=50m 有 12 局 >= 10，胜率 3/12 = 25.0%
        self.assertEqual(dur_map["over_50m"]["games"], 12)
        self.assertEqual(dur_map["over_50m"]["wins"], 3)
        self.assertEqual(dur_map["over_50m"]["win_rate"], 25.0)
        self.assertFalse(dur_map["over_50m"]["insufficient_sample"])

        # <30m 只有 4 局 < 10，win_rate 必须为 None
        self.assertEqual(dur_map["under_30m"]["games"], 4)
        self.assertIsNone(dur_map["under_30m"]["win_rate"])
        self.assertTrue(dur_map["under_30m"]["insufficient_sample"])

        # 当晚第 1 局 12 场 75.0%，第 2 局 12 场 25.0%，第 3 局 4 场 (<10 -> None)
        self.assertEqual(sess_map[1]["games"], 12)
        self.assertEqual(sess_map[1]["win_rate"], 75.0)
        self.assertEqual(sess_map[2]["games"], 12)
        self.assertEqual(sess_map[2]["win_rate"], 25.0)
        self.assertEqual(sess_map[3]["games"], 4)
        self.assertIsNone(sess_map[3]["win_rate"])
        self.assertTrue(sess_map[3]["insufficient_sample"])

    def test_f1_aggregate_full_history_stats_includes_duration_and_session_tilt(self):
        """验证 F1 aggregate_full_history_stats 输出直接包含 duration_and_session_tilt"""
        rows = [
            {
                "account_id": 135243282,
                "match_id": 800001 + i,
                "player_slot": 0,
                "radiant_win": True,
                "hero_id": 8,
                "duration": 2200,
                "start_time": 1730000000 + i * 3000,
            }
            for i in range(10)
        ]
        agg = sync_full_match_history.aggregate_full_history_stats(rows, min_games=10)
        self.assertIn("duration_and_session_tilt", agg)
        dt = agg["duration_and_session_tilt"]
        self.assertIn("duration_buckets", dt)
        self.assertIn("session_game_buckets", dt)


if __name__ == "__main__":
    unittest.main()
