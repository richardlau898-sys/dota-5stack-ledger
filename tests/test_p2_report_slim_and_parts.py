import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from tests.helpers import build_all_sample_reports

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


class TestP2ReportSlimAndParts(unittest.TestCase):
    """P2 · 报告瘦身和分段加载：按列快照、只存key不存CDN图片地址、无缩进落盘、?part=summary|timeline|microscope、<150KB摘要与<1MB全量"""

    @classmethod
    def setUpClass(cls):
        cls.sample_reports = build_all_sample_reports(force_rebuild=True)

    def test_1_minute_snapshots_is_columnar(self):
        """逐分钟快照改为按列的数组结构 (format == 'columnar_v1')"""
        rep = self.sample_reports[9058105598]
        ms = (rep.get("deep_forensics") or {}).get("minute_snapshots")
        self.assertIsInstance(ms, dict, "minute_snapshots must be a columnar dict")
        self.assertEqual(ms.get("format"), "columnar_v1")
        self.assertIsInstance(ms.get("minutes"), list)
        self.assertIsInstance(ms.get("radiant_gold_adv"), list)
        self.assertIsInstance(ms.get("players"), list)
        self.assertEqual(len(ms["players"]), 10)
        p0 = ms["players"][0]
        self.assertIsInstance(p0.get("networth"), list)
        self.assertIsInstance(p0.get("lh"), list)
        self.assertIsInstance(p0.get("recent_purchases"), list)

    def test_2_no_steam_cdn_urls_in_report_json(self):
        """报告里只存英雄和物品的 key，不含 cdn.cloudflare.steamstatic.com 图片 URL"""
        rep = self.sample_reports[9058105598]
        serialized = json.dumps(rep, ensure_ascii=False, separators=(",", ":"))
        self.assertNotIn(
            "cdn.cloudflare.steamstatic.com",
            serialized,
            "Report JSON must store hero/item keys only, not repeated Steam CDN URLs",
        )

    def test_3_largest_full_report_under_1mb(self):
        """所有样本比赛（包括 71 分钟的 9058105598）完整报告体积均小于 1MB"""
        max_bytes = 0
        max_mid = None
        for mid, rep in self.sample_reports.items():
            b = len(json.dumps(rep, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            if b > max_bytes:
                max_bytes = b
                max_mid = mid
        self.assertLess(
            max_bytes,
            1024 * 1024,
            f"Largest match report {max_mid} is {max_bytes:,} bytes (>= 1MB)",
        )

    def test_4_part_summary_timeline_microscope_and_summary_under_150kb(self):
        """/api/match/<id>?part=summary|timeline|microscope 正常工作，且 summary 小于 150KB"""
        rep = self.sample_reports[9058105598]
        with patch.object(server, "get_or_build_match_report", return_value=rep):
            sum_res = _call_get_endpoint("/api/match/9058105598?part=summary")
            tl_res = _call_get_endpoint("/api/match/9058105598?part=timeline")
            mic_res = _call_get_endpoint("/api/match/9058105598?part=microscope")

        self.assertTrue(sum_res.get("ok"))
        self.assertEqual(sum_res.get("part"), "summary")
        sum_bytes = len(json.dumps(sum_res["report"], ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        self.assertLess(
            sum_bytes,
            150 * 1024,
            f"?part=summary for 9058105598 is {sum_bytes:,} bytes (>= 150KB)",
        )

        self.assertTrue(tl_res.get("ok"))
        self.assertEqual(tl_res.get("part"), "timeline")
        self.assertIn("minute_snapshots", tl_res["report"].get("deep_forensics", {}))

        self.assertTrue(mic_res.get("ok"))
        self.assertEqual(mic_res.get("part"), "microscope")
        self.assertIn("phases_data", mic_res["report"])


if __name__ == "__main__":
    unittest.main()
