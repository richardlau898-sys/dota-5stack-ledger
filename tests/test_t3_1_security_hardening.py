# -*- coding: utf-8 -*-
r"""
T3-1 · 任意文件读取、错误外泄、未登录访问 Steam 单元测试
验收要求：
1. task_id 只接受 ^llm-\d+-(radiant|dire)-\d+$（含长度上限），其余一律返回 400；
   用 ../、%2e%2e%2f、绝对路径、超长字符串请求状态接口全部 400，且文件打开钩子断言未读取 tasks 目录外的任何文件；
   状态接口只返回状态、进度和错误码，不返回完整报告（report / structured）。
2. 错误改为严格白名单（固定中文提示 + error_code），LLM 失败归为超时（LLM_TIMEOUT）、鉴权失败（LLM_AUTH_FAILED）、上游错误（LLM_UPSTREAM_ERROR）三类；
   mock LLM 抛出 URLError / HTTPError 401 / TimeoutError，断言响应体绝不含 urlopen、HTTP Error、Errno。
3. 不带口令时账号只接受纯数字 ID；不带口令请求 Steam 短名或链接返回 401，对外请求数为 0。
"""
import builtins
import io
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import ai_coach_engine
import cloud_store
import server


class _TestableHandler(server.DotaAnalystHandler):
    def __init__(self, method: str, path: str, body: dict = None, headers: dict = None):
        self.command = method
        self.path = path
        self.request_version = "HTTP/1.1"
        raw_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
        hdrs = dict(headers or {})
        if body is not None:
            hdrs.setdefault("Content-Length", str(len(raw_bytes)))
            hdrs.setdefault("Content-Type", "application/json")
        self.headers = hdrs
        self.rfile = io.BytesIO(raw_bytes)
        self.wfile = io.BytesIO()
        self.resp_status = None
        self.resp_headers = {}

    def address_string(self) -> str:
        return "127.0.0.1"

    def send_response(self, code, message=None):
        self.resp_status = code

    def send_header(self, keyword, value):
        self.resp_headers[keyword] = value

    def end_headers(self):
        pass


@contextmanager
def _record_opened_files():
    opened_paths = []
    orig_builtin_open = builtins.open
    orig_path_open = Path.open
    orig_read_text = Path.read_text
    orig_read_bytes = Path.read_bytes

    def wrapped_builtin_open(file, *args, **kwargs):
        if isinstance(file, (str, os.PathLike)):
            opened_paths.append(Path(file).resolve())
        return orig_builtin_open(file, *args, **kwargs)

    def wrapped_path_open(self_path, *args, **kwargs):
        opened_paths.append(Path(self_path).resolve())
        return orig_path_open(self_path, *args, **kwargs)

    def wrapped_read_text(self_path, *args, **kwargs):
        opened_paths.append(Path(self_path).resolve())
        return orig_read_text(self_path, *args, **kwargs)

    def wrapped_read_bytes(self_path, *args, **kwargs):
        opened_paths.append(Path(self_path).resolve())
        return orig_read_bytes(self_path, *args, **kwargs)

    builtins.open = wrapped_builtin_open
    Path.open = wrapped_path_open
    Path.read_text = wrapped_read_text
    Path.read_bytes = wrapped_read_bytes
    try:
        yield opened_paths
    finally:
        builtins.open = orig_builtin_open
        Path.open = orig_path_open
        Path.read_text = orig_read_text
        Path.read_bytes = orig_read_bytes


class TestT31SecurityHardening(unittest.TestCase):
    def test_1_llm_review_status_traversal_rejected_400_zero_outside_reads_and_minimal_fields(self):
        """../、%2e%2e%2f、绝对路径、超长字符串均返回 400 且不打开 tasks 目录外文件；正常状态响应不含完整报告"""
        with tempfile.TemporaryDirectory() as outer_tmp:
            outer_root = Path(outer_tmp).resolve()
            tmp_reports = outer_root / "dota_tmp"
            tasks_dir = tmp_reports / "tasks"
            tasks_dir.mkdir(parents=True, exist_ok=True)
            empty_reports = outer_root / "empty_reports"
            empty_reports.mkdir(parents=True, exist_ok=True)

            # Sensitive JSON files placed outside tasks/
            secret_sibling = tmp_reports / "secret_sibling.json"
            secret_sibling.write_text('{"top_secret": "SIBLING_LEAK_MARKER"}', encoding="utf-8")
            secret_parent = outer_root / "secret_parent.json"
            secret_parent.write_text('{"top_secret": "PARENT_LEAK_MARKER"}', encoding="utf-8")

            valid_tid = "llm-9083213997-radiant-1794500000001"
            (tasks_dir / f"{valid_tid}.json").write_text(
                json.dumps(
                    {
                        "task_id": valid_tid,
                        "match_id": 9083213997,
                        "side": "radiant",
                        "status": "completed",
                        "progress": 100,
                        "structured": {"verdict": "MUST_NOT_RETURN_IN_STATUS"},
                        "report": {"match_id": 9083213997, "full_blob": "MUST_NOT_RETURN_FULL_REPORT"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            malicious_task_ids = [
                "../secret_sibling",
                "../../secret_parent",
                "%2e%2e%2fsecret_sibling",
                "%2e%2e%2f%2e%2e%2fsecret_parent",
                "/etc/passwd",
                str(secret_parent.with_suffix("")),
                "llm-" + ("9" * 200) + "-radiant-1",
                "x" * 512,
                "llm-9083213997-neutral-12345",
            ]

            cloud_store._LLM_TASKS_MEM.clear()
            with patch.object(cloud_store, "TMP_REPORTS_DIR", tmp_reports), \
                 patch.object(server, "TMP_REPORTS_DIR", tmp_reports), \
                 patch.object(server, "REPORTS_DIR", empty_reports), \
                 patch.object(cloud_store, "get_cloud_config", return_value={"supabase_url": "", "supabase_key": "", "supabase_bucket": "dota-reports"}):
                for bad_tid in malicious_task_ids:
                    with _record_opened_files() as opened:
                        qs_val = bad_tid if "%" in bad_tid else urllib.parse.quote(bad_tid, safe="/")
                        h = _TestableHandler("GET", f"/api/llm_review_status?task_id={qs_val}")
                        h.do_GET()
                    body_txt = h.wfile.getvalue().decode("utf-8")
                    self.assertEqual(
                        h.resp_status,
                        400,
                        f"Expected 400 for malicious task_id={bad_tid!r}, got {h.resp_status}: {body_txt}",
                    )
                    self.assertNotIn("SIBLING_LEAK_MARKER", body_txt)
                    self.assertNotIn("PARENT_LEAK_MARKER", body_txt)
                    outside_reads = [
                        p for p in opened if p != tasks_dir.resolve() and tasks_dir.resolve() not in p.parents
                    ]
                    self.assertEqual(
                        outside_reads,
                        [],
                        f"Malicious task_id={bad_tid!r} opened files outside tasks/: {outside_reads}",
                    )

                # Valid task_id returns ONLY status, progress, error_code (no report, no structured)
                with _record_opened_files() as valid_opened:
                    h_ok = _TestableHandler("GET", f"/api/llm_review_status?task_id={valid_tid}")
                    h_ok.do_GET()
                self.assertEqual(h_ok.resp_status, 200)
                ok_body = h_ok.wfile.getvalue().decode("utf-8")
                self.assertNotIn("MUST_NOT_RETURN_FULL_REPORT", ok_body)
                self.assertNotIn("MUST_NOT_RETURN_IN_STATUS", ok_body)
                ok_json = json.loads(ok_body)
                self.assertEqual(ok_json.get("status"), "completed")
                self.assertIn("progress", ok_json)
                self.assertIn("error_code", ok_json)
                self.assertNotIn("report", ok_json)
                self.assertNotIn("structured", ok_json)
                outside_valid = [
                    p for p in valid_opened if p != tasks_dir.resolve() and tasks_dir.resolve() not in p.parents
                ]
                self.assertEqual(outside_valid, [])

    def test_2_llm_error_whitelist_and_three_categories_no_leak(self):
        """mock LLM 抛出 URLError / HTTPError 401 / TimeoutError，响应不含 urlopen、HTTP Error、Errno，且精确归为三类错误码"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tpath = Path(tmpdir)
            fake_rep = {
                "match_id": 9083213997,
                "is_parsed": True,
                "focus_side": "radiant",
                "radiant_win": False,
                "user_won": False,
                "radiant_pos_1_to_5": [],
                "dire_pos_1_to_5": [],
                "deep_forensics": {},
            }
            (tpath / "match_9083213997.json").write_text(json.dumps(fake_rep), encoding="utf-8")

            http_401 = urllib.error.HTTPError(
                "https://api.x.ai/v1/chat/completions", 401, "Unauthorized", {}, io.BytesIO(b"")
            )
            cases = [
                (
                    urllib.error.URLError("[Errno 8] nodename nor servname provided, or not known"),
                    "LLM_UPSTREAM_ERROR",
                ),
                (
                    http_401,
                    "LLM_AUTH_FAILED",
                ),
                (
                    TimeoutError("The read operation timed out"),
                    "LLM_TIMEOUT",
                ),
            ]

            token = "t3_1_test_secret_token_value_12345"
            cloud_store._LLM_TASKS_MEM.clear()
            try:
                with patch.dict(os.environ, {"TEAM_TOKEN": token}, clear=False), \
                     patch.object(server, "REPORTS_DIR", tpath), \
                     patch.object(server, "TMP_REPORTS_DIR", tpath), \
                     patch.object(cloud_store, "TMP_REPORTS_DIR", tpath), \
                     patch.object(cloud_store, "get_cloud_config", return_value={"supabase_url": "", "supabase_key": "", "supabase_bucket": "dota-reports"}), \
                     patch.object(ai_coach_engine, "load_env_llm_config", return_value={"provider": "xai", "model_name": "grok-4.20-0309-non-reasoning", "api_key": "fake-key", "base_url": "https://api.x.ai/v1"}):
                    for exc_obj, expected_code in cases:
                        with patch.object(urllib.request, "urlopen", side_effect=exc_obj):
                            h_post = _TestableHandler(
                                "POST",
                                "/api/llm_review",
                                body={"match_id": 9083213997, "side": "radiant", "force": True, "sync": True},
                                headers={"X-Team-Token": token},
                            )
                            h_post.do_POST()
                            post_txt = h_post.wfile.getvalue().decode("utf-8")
                            for forbidden in ("urlopen", "HTTP Error", "Errno", "Unauthorized", "nodename", "timed out"):
                                self.assertNotIn(
                                    forbidden,
                                    post_txt,
                                    f"Leaked {forbidden!r} in /api/llm_review response: {post_txt}",
                                )
                            post_json = json.loads(post_txt)
                            self.assertEqual(post_json.get("error_code"), expected_code)
                            tid = post_json.get("task_id")
                            self.assertTrue(tid)

                            h_status = _TestableHandler("GET", f"/api/llm_review_status?task_id={tid}")
                            h_status.do_GET()
                            status_txt = h_status.wfile.getvalue().decode("utf-8")
                            for forbidden in ("urlopen", "HTTP Error", "Errno", "Unauthorized", "nodename", "timed out"):
                                self.assertNotIn(
                                    forbidden,
                                    status_txt,
                                    f"Leaked {forbidden!r} in /api/llm_review_status response: {status_txt}",
                                )
                            status_json = json.loads(status_txt)
                            self.assertEqual(status_json.get("error_code"), expected_code)
            finally:
                http_401.close()

    def test_3_unauthenticated_steam_short_name_returns_401_with_zero_outbound_requests(self):
        """不带口令请求 Steam 短名或链接：返回 401，对外请求数为 0"""
        outbound_calls = []

        def spy_urlopen(req, *args, **kwargs):
            outbound_calls.append(req)
            raise AssertionError("Unauthenticated request must NOT make any outbound HTTP call")

        with tempfile.TemporaryDirectory() as tmpdir:
            tpath = Path(tmpdir)
            for env_token in ("", "configured_team_secret_token_xyz"):
                env_patch = {"TEAM_TOKEN": env_token}
                with patch.dict(os.environ, env_patch, clear=False), \
                     patch.object(server, "REPORTS_DIR", tpath), \
                     patch.object(server, "TMP_REPORTS_DIR", tpath), \
                     patch.object(cloud_store, "TMP_REPORTS_DIR", tpath), \
                     patch.object(urllib.request, "urlopen", side_effect=spy_urlopen):
                    for url_path in (
                        "/api/player?query=richardlau898",
                        "/api/recent?account_id=richardlau898",
                        "/api/player?query=https%3A%2F%2Fsteamcommunity.com%2Fid%2Frichardlau898%2F",
                        "/api/match/9083213997?account_id=richardlau898",
                        "/api/match/9083213997?account_id=https%3A%2F%2Fsteamcommunity.com%2Fprofiles%2F76561198046346640",
                    ):
                        h = _TestableHandler("GET", url_path)
                        h.do_GET()
                        self.assertEqual(
                            h.resp_status,
                            401,
                            f"Expected 401 for unauthenticated {url_path} (TEAM_TOKEN={env_token!r}), got {h.resp_status}",
                        )
                        self.assertEqual(len(outbound_calls), 0)

                    # Pure numeric ID without token continues to work with 0 outbound requests
                    h_num = _TestableHandler("GET", "/api/player?query=86080912")
                    h_num.do_GET()
                    self.assertEqual(h_num.resp_status, 200)
                    self.assertEqual(len(outbound_calls), 0)


if __name__ == "__main__":
    unittest.main()
