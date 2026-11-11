# -*- coding: utf-8 -*-
"""
R1-3 · 让 CI 变绿，并且以后保持 单元测试
验证：
1. 报告不再存服务器时区的时间字符串 start_time_str，只存 Unix 时间戳 start_time。
2. 在 TZ=UTC 和 TZ=Asia/Shanghai 下，全部 22 个样本生成的报告 JSON 完全一致。
3. server.fetch_recent_matches_formatted 不返回服务器时区时间字符串，且测试使用临时目录不往仓库写文件。
4. 跑完测试后 git status 干净（reports/ 下无新增临时文件）。
"""
import hashlib
import io
import json
import os
import subprocess
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import dota_analyst
import draft_and_phase_coach
import server
from tests.helpers import load_all_raw_matches

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestR13CiTimezoneAndTempdir(unittest.TestCase):
    def test_1_report_stores_only_unix_start_time_no_server_timezone_string(self):
        roster = dota_analyst.load_roster()
        raw_matches = load_all_raw_matches()
        self.assertGreaterEqual(len(raw_matches), 10)
        for mid, raw in raw_matches.items():
            rep = dota_analyst.analyze_match_data(raw, roster)
            self.assertNotIn(
                "start_time_str",
                rep,
                f"Match {mid} report must not store server-timezone start_time_str",
            )
            self.assertEqual(rep.get("start_time"), int(raw["start_time"]))

            summary_part = dota_analyst.extract_report_part(rep, "summary")
            self.assertNotIn("start_time_str", summary_part)
            self.assertEqual(summary_part.get("start_time"), int(raw["start_time"]))

    def test_2_all_sample_reports_identical_between_utc_and_shanghai(self):
        roster = dota_analyst.load_roster()
        raw_matches = load_all_raw_matches()
        orig_tz = os.environ.get("TZ")
        try:
            for mid, raw in raw_matches.items():
                os.environ["TZ"] = "UTC"
                if hasattr(time, "tzset"):
                    time.tzset()
                rep_utc = dota_analyst.analyze_match_data(raw, roster)
                sha_utc = hashlib.sha256(
                    json.dumps(rep_utc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                ).hexdigest()

                os.environ["TZ"] = "Asia/Shanghai"
                if hasattr(time, "tzset"):
                    time.tzset()
                rep_sh = dota_analyst.analyze_match_data(raw, roster)
                sha_sh = hashlib.sha256(
                    json.dumps(rep_sh, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                ).hexdigest()

                self.assertEqual(
                    sha_utc,
                    sha_sh,
                    f"Match {mid} produced different report JSON across TZ=UTC and TZ=Asia/Shanghai",
                )
        finally:
            if orig_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = orig_tz
            if hasattr(time, "tzset"):
                time.tzset()

    def test_3_cmd_recent_and_recent_matches_timezone_independent_and_tempdir_only(self):
        fake_recent = [
            {
                "match_id": 8604323503,
                "player_slot": 0,
                "radiant_win": True,
                "start_time": 1762770000,
                "duration": 2400,
                "hero_id": 1,
                "kills": 10,
                "deaths": 2,
                "assists": 8,
                "party_size": 5,
                "version": 22,
            }
        ]
        before_files = set((REPO_ROOT / "reports").glob("*"))
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            server._RECENT_MATCHES_CACHE.clear()
            with patch.object(server, "REPORTS_DIR", tmp_path), \
                 patch.object(server, "TMP_REPORTS_DIR", tmp_path / "tmp"), \
                 patch.object(server, "api_get", return_value=fake_recent):
                items = server.fetch_recent_matches_formatted(125383759, limit=1)
        after_files = set((REPO_ROOT / "reports").glob("*"))
        self.assertEqual(before_files, after_files, "Test must not write into repo reports/")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get("start_time"), 1762770000)
        self.assertNotIn("start_time_str", items[0])

        # Verify cmd_recent produces identical output across timezones
        orig_tz = os.environ.get("TZ")
        try:
            class _Args:
                account_id = "86080912"
                limit = 1

            with patch.object(dota_analyst, "api_get", return_value=fake_recent):
                os.environ["TZ"] = "UTC"
                if hasattr(time, "tzset"):
                    time.tzset()
                buf_utc = io.StringIO()
                with redirect_stdout(buf_utc):
                    dota_analyst.cmd_recent(_Args())

                os.environ["TZ"] = "Asia/Shanghai"
                if hasattr(time, "tzset"):
                    time.tzset()
                buf_sh = io.StringIO()
                with redirect_stdout(buf_sh):
                    dota_analyst.cmd_recent(_Args())

            self.assertEqual(buf_utc.getvalue(), buf_sh.getvalue())
        finally:
            if orig_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = orig_tz
            if hasattr(time, "tzset"):
                time.tzset()


if __name__ == "__main__":
    unittest.main()
