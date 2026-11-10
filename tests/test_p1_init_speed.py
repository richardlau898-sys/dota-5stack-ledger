import io
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import draft_and_phase_coach
import server

ROOT_DIR = Path(__file__).resolve().parent.parent


def _call_get_endpoint(path_str: str) -> dict:
    handler = server.DotaAnalystHandler.__new__(server.DotaAnalystHandler)
    handler.path = path_str
    handler.headers = {}
    handler.wfile = io.BytesIO()
    handler.send_response = lambda code: None
    handler.send_header = lambda k, v: None
    handler.end_headers = lambda: None
    handler.address_string = lambda: "127.0.0.1"
    handler.do_GET()
    return json.loads(handler.wfile.getvalue().decode("utf-8"))


class TestP1InitSpeed(unittest.TestCase):
    """P1 · /api/init 提速：总账入库时预计算并缓存、响应只留 latest_match_report、/api/match 不带总账、非报告部分 <300KB 且 <1s"""

    def test_1_init_has_single_report_field_and_fast_small_payload(self):
        """热启动下 /api/init 不包含重复的 latest_report，非报告部分 < 300KB 且耗时 < 1 秒"""
        with patch.object(server, "fetch_recent_matches_formatted", return_value=[]):
            # Warm up persisted ledger cache once
            _call_get_endpoint("/api/init")

            t0 = time.perf_counter()
            data = _call_get_endpoint("/api/init")
            elapsed = time.perf_counter() - t0

        self.assertTrue(data.get("ok"))
        self.assertIn("latest_match_report", data)
        self.assertNotIn("latest_report", data, "/api/init must not duplicate report in latest_report")

        without_report = {k: v for k, v in data.items() if k != "latest_match_report"}
        payload_bytes = len(json.dumps(without_report, ensure_ascii=False).encode("utf-8"))
        self.assertLess(
            payload_bytes,
            300 * 1024,
            f"/api/init non-report payload is {payload_bytes} bytes (>= 300KB)",
        )
        self.assertLess(
            elapsed,
            1.0,
            f"/api/init warm start took {elapsed:.3f}s (>= 1.0s)",
        )

    def test_2_match_endpoint_does_not_return_squad_ledger(self):
        """GET /api/match/<id> 不再计算或附带 squad_ledger"""
        fake_rep = {"match_id": 9046276667, "is_parsed": True}
        with patch.object(server, "get_or_build_match_report", return_value=fake_rep), \
             patch.object(server, "build_squad_history_ledger", side_effect=AssertionError("Must not call build_squad_history_ledger in /api/match")):
            data = _call_get_endpoint("/api/match/9046276667")

        self.assertTrue(data.get("ok"))
        self.assertNotIn("squad_ledger", data, "/api/match response must not contain squad_ledger")

    def test_3_persisted_squad_ledger_avoids_reparsing_match_files_on_request(self):
        """总账在入库时预计算存盘，请求时直接读取，不再每次遍历解析全部 match_*.json"""
        self.assertTrue(
            hasattr(draft_and_phase_coach, "load_or_build_squad_ledger"),
            "draft_and_phase_coach must provide load_or_build_squad_ledger",
        )
        self.assertTrue(
            hasattr(draft_and_phase_coach, "refresh_persisted_squad_ledger"),
            "draft_and_phase_coach must provide refresh_persisted_squad_ledger",
        )
        roster = server.load_roster()
        draft_and_phase_coach.refresh_persisted_squad_ledger(server.REPORTS_DIR, roster, [])
        with patch.object(
            draft_and_phase_coach,
            "build_squad_history_ledger",
            side_effect=AssertionError("Should read persisted ledger cache instead of rebuilding"),
        ):
            ledger = draft_and_phase_coach.load_or_build_squad_ledger(server.REPORTS_DIR, roster, [])
            self.assertIn("squad_members_rank", ledger)
            self.assertIn("lane_duo_chemistry", ledger)


if __name__ == "__main__":
    unittest.main()
