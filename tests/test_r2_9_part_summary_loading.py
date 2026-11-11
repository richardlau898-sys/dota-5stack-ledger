import gzip
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import dota_analyst
import server


REPO_ROOT = Path(__file__).resolve().parent.parent


def _call_get_raw_bytes(path_str: str, headers: dict | None = None) -> tuple[bytes, dict]:
    handler = server.DotaAnalystHandler.__new__(server.DotaAnalystHandler)
    handler.path = path_str
    handler.headers = headers or {}
    handler.wfile = io.BytesIO()
    resp_headers = {}
    handler.send_response = lambda code: resp_headers.setdefault("_status", code)
    handler.send_header = lambda k, v: resp_headers.__setitem__(k, v)
    handler.end_headers = lambda: None
    handler.address_string = lambda: "127.0.0.1"
    handler.do_GET()
    return handler.wfile.getvalue(), resp_headers


class TestR29PartSummaryLoading(unittest.TestCase):
    def test_1_api_init_does_not_embed_report_and_uses_compact_json(self):
        """/api/init 不再内嵌 latest_match_report，且 HTTP JSON 响应使用紧凑格式 (separators=(',', ':'))"""
        with patch.object(server, "fetch_recent_matches_formatted", return_value=[]):
            raw_bytes, _ = _call_get_raw_bytes("/api/init")

        raw_str = raw_bytes.decode("utf-8")
        data = json.loads(raw_str)
        self.assertTrue(data.get("ok"))
        self.assertNotIn("latest_match_report", data, "/api/init must not embed full match report")
        self.assertNotIn("latest_report", data, "/api/init must not embed full match report")
        # Compact JSON must not have ': ' after top-level keys
        self.assertTrue(raw_str.startswith('{"ok":true,'), f"Response is not compact JSON: {raw_str[:80]!r}")

    def test_2_all_summaries_under_150kb_including_hydrated_coaching(self):
        """全部已保存报告与全部样本重生成报告的 part=summary 紧凑 JSON 均小于 150KB"""
        roster = dota_analyst.load_roster()
        over_limit = []

        for mf in sorted((REPO_ROOT / "reports").glob("match_*.json")):
            rep = json.loads(mf.read_text(encoding="utf-8"))
            mid = rep.get("match_id")
            hydrated = server._hydrate_grok_from_caches(rep, mid)
            dota_analyst.strip_report_cdn_urls_to_keys(hydrated)
            summ = dota_analyst.extract_report_part(hydrated, "summary")
            b_len = len(json.dumps(summ, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            if b_len >= 150 * 1024:
                over_limit.append((mf.name, b_len))

        for rf in sorted((REPO_ROOT / "reports").glob("raw_*.json")):
            raw = json.loads(rf.read_text(encoding="utf-8"))
            rep = dota_analyst.analyze_match_data(raw, roster)
            hydrated = server._hydrate_grok_from_caches(rep, rep.get("match_id"))
            dota_analyst.strip_report_cdn_urls_to_keys(hydrated)
            summ = dota_analyst.extract_report_part(hydrated, "summary")
            b_len = len(json.dumps(summ, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            if b_len >= 150 * 1024:
                over_limit.append((rf.name, b_len))

        self.assertEqual(
            over_limit,
            [],
            f"Found summary payloads >= 150KB (153,600 bytes): {over_limit}",
        )

    def test_3_frontend_initial_load_requests_part_summary_and_gzip_supported(self):
        """前端 loadMatchReport 默认请求 part=summary；服务端对浏览器 Accept-Encoding: gzip 支持压缩返回"""
        app_js = (REPO_ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("data.latest_match_report", app_js)
        self.assertIn("part=summary", app_js)

        with patch.object(server, "fetch_recent_matches_formatted", return_value=[]):
            gz_bytes, hdrs = _call_get_raw_bytes("/api/init", headers={"Accept-Encoding": "gzip, deflate, br"})
        self.assertEqual(hdrs.get("Content-Encoding"), "gzip")
        decoded = json.loads(gzip.decompress(gz_bytes).decode("utf-8"))
        self.assertTrue(decoded.get("ok"))


if __name__ == "__main__":
    unittest.main()
