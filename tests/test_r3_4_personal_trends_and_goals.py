import http.client
import json
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class TestR34PersonalTrendsAndGoals(unittest.TestCase):
    def test_1_no_hardcoded_default_goals_and_recent_7_games_label(self):
        """R3-4: 未设置目标的队员 weekly_goal 必须为 None（去掉写死的 0.85 / 2.0 默认值），设置后标注「最近 7 局」。"""
        import dota_analyst
        from squad_growth_metrics import build_personal_trends_and_goals

        roster = dota_analyst.load_roster()
        reports = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((ROOT / "reports").glob("match_*.json"))
        ]
        res_empty = build_personal_trends_and_goals(reports, roster=roster, weekly_goals={})
        self.assertGreater(len(res_empty["players"]), 0)
        for aid, pdata in res_empty["players"].items():
            self.assertIsNone(
                pdata.get("weekly_goal"),
                f"player {aid} without configured goal must have weekly_goal=None, got {pdata.get('weekly_goal')}",
            )

        res_with_goal = build_personal_trends_and_goals(
            reports,
            roster=roster,
            weekly_goals={
                "86080912": {
                    "metric": "non_teamfight_deaths_after_10m",
                    "direction": "max",
                    "target": 1.8,
                }
            },
        )
        g_main = res_with_goal["players"]["86080912"]["weekly_goal"]
        self.assertIsInstance(g_main, dict)
        self.assertEqual(g_main["target"], 1.8)
        self.assertEqual(g_main["window_label_zh"], "最近 7 局")
        other_aids = [k for k in res_with_goal["players"] if k != "86080912"]
        self.assertGreater(len(other_aids), 0)
        for o_aid in other_aids:
            self.assertIsNone(res_with_goal["players"][o_aid]["weekly_goal"])

    def test_2_supabase_schema_and_cloud_store_player_goals(self):
        """R3-4: supabase_schema.sql 定义 public.player_goals，cloud_store 支持读写 Supabase。"""
        import cloud_store

        sql = (ROOT / "supabase_schema.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS public.player_goals", sql)
        self.assertTrue(hasattr(cloud_store, "cloud_fetch_player_goals"))
        self.assertTrue(hasattr(cloud_store, "cloud_upsert_player_goal"))

        captured_reqs = []

        class _FakeResp:
            def __init__(self, status=201, body=b"[]"):
                self.status = status
                self._body = body

            def read(self):
                return self._body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(req, timeout=8):
            captured_reqs.append((req.get_method(), req.full_url, req.data))
            if req.get_method() == "GET":
                payload = json.dumps([
                    {
                        "account_id": 86080912,
                        "metric": "lane_nw_diff_10m",
                        "direction": "min",
                        "target": 200,
                        "label_zh": "对位10分钟净值差 >= +200",
                    }
                ]).encode("utf-8")
                return _FakeResp(200, payload)
            return _FakeResp(201, b"")

        cfg = {"supabase_url": "https://example.supabase.co", "supabase_key": "test-key", "supabase_bucket": "dota-reports"}
        cloud_store._PLAYER_GOALS_CACHE["ts"] = 0.0
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ok = cloud_store.cloud_upsert_player_goal(
                86080912,
                {
                    "metric": "lane_nw_diff_10m",
                    "direction": "min",
                    "target": 200.0,
                    "label_zh": "对位10分钟净值差 >= +200",
                },
                cfg=cfg,
            )
            self.assertTrue(ok)
            goals = cloud_store.cloud_fetch_player_goals(cfg=cfg)
            self.assertIn("86080912", goals)
            self.assertEqual(goals["86080912"]["target"], 200.0)
            self.assertTrue(any("/rest/v1/player_goals" in u for _, u, _ in captured_reqs))

    def test_3_post_api_player_goals_auth_and_persistence(self):
        """R3-4: POST /api/player_goals 需要口令校验，保存后更新总账 personal_trends_and_goals。"""
        from http.server import HTTPServer
        import server

        saved_store = {}

        def fake_upsert(aid, goal, cfg=None):
            if goal is None:
                saved_store.pop(str(aid), None)
            else:
                saved_store[str(aid)] = dict(goal)
            return True

        def fake_fetch(cfg=None):
            return dict(saved_store)

        with patch.dict(os.environ, {"TEAM_TOKEN": "secret-r34-token"}, clear=False), \
             patch("cloud_store.cloud_upsert_player_goal", side_effect=fake_upsert), \
             patch("cloud_store.cloud_fetch_player_goals", side_effect=fake_fetch):
            httpd = HTTPServer(("127.0.0.1", 0), server.DotaAnalystHandler)
            port = httpd.server_address[1]
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                # 1. Without token -> 401
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                conn.request(
                    "POST",
                    "/api/player_goals",
                    body=json.dumps({"account_id": 86080912, "metric": "non_teamfight_deaths_after_10m", "target": 1.5}),
                    headers={"Content-Type": "application/json"},
                )
                r401 = conn.getresponse()
                r401.read()
                self.assertEqual(r401.status, 401)
                conn.close()

                # 2. With valid token -> 200 and goal persisted in returned personal_trends_and_goals
                conn2 = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
                conn2.request(
                    "POST",
                    "/api/player_goals",
                    body=json.dumps({"account_id": 86080912, "metric": "non_teamfight_deaths_after_10m", "target": 1.5}),
                    headers={"Content-Type": "application/json", "X-Team-Token": "secret-r34-token"},
                )
                r200 = conn2.getresponse()
                data = json.loads(r200.read().decode("utf-8"))
                self.assertEqual(r200.status, 200)
                self.assertTrue(data.get("ok"))
                ptg = data.get("personal_trends_and_goals") or {}
                p_main = (ptg.get("players") or {}).get("86080912") or {}
                self.assertIsNotNone(p_main.get("weekly_goal"))
                self.assertEqual(p_main["weekly_goal"]["target"], 1.5)
                conn2.close()
            finally:
                httpd.shutdown()
                httpd.server_close()

    def test_4_frontend_renders_svg_sparklines_goal_form_and_recent_7_label(self):
        """R3-4: 前端使用 SVG <polyline 折线图展示 4 条趋势曲线，提供设置目标入口，并将「每周」改为「最近 7 局」。"""
        app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("每周目标进度", app_js)
        self.assertIn("最近 7 局", app_js)
        self.assertIn("/api/player_goals", app_js)
        self.assertIn("f4-sparkline", app_js)
        self.assertIn("<polyline", app_js)
        self.assertIn("未设目标", app_js)


if __name__ == "__main__":
    unittest.main()
