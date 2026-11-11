# -*- coding: utf-8 -*-
"""
R0-4 · 删除合成的英雄胜率数据
验证：
1. 删除 build_offline_hero_stats_from_constants_and_reports 与 ensure_hero_stats_cache 合成函数。
2. mock 下载失败时，refresh_constants 脚本退出码非 0 且没有写任何文件；--check 模式只检查不写文件。
3. 仓库提交的 .cache/hero_stats.json 来自真实 OpenDota /api/heroStats，记录了 downloaded_at，不含合成常数（如全员 1_pick==200）。
4. hero_stats.json 不存在时，load_hero_stats_by_id 返回空字典，BP 工具的 bracket_win_rate 为 None（界面显示“无数据”）。
"""
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import draft_and_phase_coach
from tools import refresh_constants

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestR04RealHeroStats(unittest.TestCase):
    def test_1_synthetic_functions_removed(self):
        self.assertFalse(
            hasattr(refresh_constants, "build_offline_hero_stats_from_constants_and_reports"),
            "必须删除合成函数 build_offline_hero_stats_from_constants_and_reports",
        )
        self.assertFalse(
            hasattr(refresh_constants, "ensure_hero_stats_cache"),
            "必须删除合成写盘函数 ensure_hero_stats_cache",
        )

    def test_2_mock_download_failure_exits_nonzero_and_writes_no_files(self):
        # 场景 A：任意网络错误导致下载失败 -> 退出码非 0，目录内无任何文件写入
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("simulated network failure"),
            ):
                rc = refresh_constants.main(["--cache-dir", str(tmp_path)])
            self.assertNotEqual(rc, 0, "下载失败时退出码必须非 0")
            self.assertEqual(list(tmp_path.iterdir()), [], "下载失败时不得写入任何文件")

        # 场景 B：前 5 个 constants 成功，但 /heroStats 失败 -> 同样退出码非 0 且不写任何文件
        def fail_on_hero_stats(req, timeout=20):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "heroStats" in url:
                raise urllib.error.URLError("heroStats endpoint failed")
            payload = {"1": {"id": 1, "name": "npc_dota_hero_antimage", "localized_name": "Anti-Mage"}}
            if url.endswith("/patch"):
                payload = [{"id": 59, "name": "7.39"}]
            resp = MagicMock()
            resp.read.return_value = json.dumps(payload).encode("utf-8")
            resp.__enter__.return_value = resp
            return resp

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with patch("urllib.request.urlopen", side_effect=fail_on_hero_stats):
                rc = refresh_constants.main(["--cache-dir", str(tmp_path)])
            self.assertNotEqual(rc, 0, "/heroStats 下载失败时退出码必须非 0")
            self.assertEqual(list(tmp_path.iterdir()), [], "/heroStats 下载失败时不得写入任何文件")

        # 场景 C：--check 模式绝不写 hero_stats.json 或任何其他文件
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            src_heroes = REPO_ROOT / ".cache" / "heroes_constants.json"
            (tmp_path / "heroes_constants.json").write_text(
                src_heroes.read_text(encoding="utf-8"), encoding="utf-8"
            )
            before_files = sorted(p.name for p in tmp_path.iterdir())
            rc_check = refresh_constants.main(["--check", "--cache-dir", str(tmp_path)])
            after_files = sorted(p.name for p in tmp_path.iterdir())
            self.assertEqual(rc_check, 0)
            self.assertEqual(before_files, after_files, "--check 模式不得写入任何文件")
            self.assertFalse((tmp_path / "hero_stats.json").exists())

    def test_3_committed_hero_stats_is_real_opendota_data_with_timestamp(self):
        hs_path = REPO_ROOT / ".cache" / "hero_stats.json"
        self.assertTrue(hs_path.exists(), "缺少真实下载的 .cache/hero_stats.json")
        payload = json.loads(hs_path.read_text(encoding="utf-8"))
        self.assertIsInstance(payload, dict, "hero_stats.json 应包含顶层元数据与 heroes 列表")
        self.assertIn("downloaded_at", payload, "hero_stats.json 必须记录下载时间 downloaded_at")
        self.assertTrue(str(payload["downloaded_at"]).endswith("Z"))
        heroes = payload.get("heroes")
        self.assertIsInstance(heroes, list)
        self.assertGreaterEqual(len(heroes), 120)

        distinct_1_picks = {int(h.get("1_pick") or 0) for h in heroes if isinstance(h, dict)}
        self.assertGreater(
            len(distinct_1_picks),
            50,
            f"检测到疑似合成数据（1_pick 取值集合过小: {distinct_1_picks}）",
        )

    def test_4_missing_hero_stats_returns_none_and_bp_shows_no_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = Path(tmpdir) / "hero_stats.json"
            hs_map = draft_and_phase_coach.load_hero_stats_by_id(hs_path=missing_path)
            self.assertEqual(hs_map, {}, "hero_stats.json 不存在时不得兜底生成或读其他文件")

            res = draft_and_phase_coach.compute_real_bp_matchup_stats(
                own_picks=[{"pos": 1, "hero_id": 8, "hero_short_zh": "主宰"}],
                enemy_picks=[{"pos": 2, "hero_id": 76, "hero_short_zh": "殁境神蚀者"}],
                squad_hero_pool={},
                against_heroes_data=[],
                hero_stats_by_id=hs_map,
            )
            self.assertEqual(len(res["own_hero_real_stats"]), 1)
            self.assertIsNone(res["own_hero_real_stats"][0]["bracket_win_rate"])
            self.assertIsNone(res["own_hero_real_stats"][0]["pub_win_rate"])

        app_js = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('h.bracket_win_rate != null ? `${h.bracket_win_rate}%` : "无数据"', app_js)


if __name__ == "__main__":
    unittest.main()
