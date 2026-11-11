# -*- coding: utf-8 -*-
import io
import json
import os
import unittest
from unittest.mock import patch

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


class TestR12NoErrorLeak(unittest.TestCase):
    """R1-2 · 错误详情不返回给客户端"""

    def _assert_clean_chinese_error(self, raw_body: str):
        self.assertNotIn("invalid literal", raw_body)
        self.assertNotIn("Traceback", raw_body)
        self.assertNotIn("/Users/", raw_body)
        self.assertNotIn("/etc/", raw_body)
        self.assertNotIn("server.py", raw_body)
        data = json.loads(raw_body)
        self.assertFalse(data.get("ok"))
        err = data.get("error") or ""
        self.assertTrue(len(err) > 0)
        # Must contain Chinese characters
        self.assertTrue(any("\u4e00" <= ch <= "\u9fff" for ch in err), f"Expected Chinese prompt, got: {err!r}")

    def test_get_invalid_match_id_hides_value_error_details(self):
        h = _TestableHandler("GET", "/api/match/abc_invalid_/Users/alice/server.py")
        h.do_GET()
        self.assertEqual(h.resp_status, 400)
        body = h.wfile.getvalue().decode("utf-8")
        self._assert_clean_chinese_error(body)

    def test_post_invalid_match_id_hides_value_error_details(self):
        with patch.dict(os.environ, {"TEAM_TOKEN": "test-r1-2-secret-token"}, clear=False):
            h = _TestableHandler(
                "POST",
                "/api/request_parse",
                body={"match_id": "bad_id_/etc/passwd"},
                headers={"X-Team-Token": "test-r1-2-secret-token"},
            )
            h.do_POST()
        self.assertEqual(h.resp_status, 400)
        body = h.wfile.getvalue().decode("utf-8")
        self._assert_clean_chinese_error(body)

    def test_llm_review_task_and_status_never_return_raw_exception(self):
        raw_exc_msg = (
            'Traceback (most recent call last):\n'
            '  File "/Users/alice/app/server.py", line 727, in _execute_llm_review_task\n'
            "ValueError: invalid literal for int() with base 10: 'xyz'"
        )
        saved_tasks = {}

        def fake_save(task_id, state):
            saved_tasks[task_id] = dict(state)
            return True

        def fake_load(task_id):
            return saved_tasks.get(task_id)

        with patch.object(server, "cloud_save_llm_task", side_effect=fake_save), patch.object(
            server, "cloud_load_llm_task", side_effect=fake_load
        ), patch.object(server, "call_llm_coach_review", side_effect=RuntimeError(raw_exc_msg)):
            res_state = server._execute_llm_review_task("task-exc-1", 9083213997, "radiant", {"match_id": 9083213997})
            self.assertEqual(res_state.get("status"), "failed")
            self.assertNotIn("invalid literal", str(res_state.get("error") or ""))
            self.assertNotIn("Traceback", str(res_state.get("error") or ""))
            self.assertNotIn("/Users/", str(res_state.get("error") or ""))

            # Even if an old task in storage has raw traceback in "error", /api/llm_review_status strips it
            saved_tasks["task-legacy-leak"] = {
                "task_id": "task-legacy-leak",
                "match_id": 9083213997,
                "side": "radiant",
                "status": "failed",
                "error": raw_exc_msg,
            }
            for tid in ("task-exc-1", "task-legacy-leak"):
                h = _TestableHandler("GET", f"/api/llm_review_status?task_id={tid}")
                h.do_GET()
                self.assertEqual(h.resp_status, 200)
                body = h.wfile.getvalue().decode("utf-8")
                self.assertNotIn("invalid literal", body)
                self.assertNotIn("Traceback", body)
                self.assertNotIn("/Users/", body)
                self.assertNotIn("server.py", body)
                payload = json.loads(body)
                self.assertEqual(payload.get("status"), "failed")
                self.assertTrue(any("\u4e00" <= ch <= "\u9fff" for ch in (payload.get("error") or "")))

    def test_not_found_routes_do_not_echo_file_paths(self):
        h_get = _TestableHandler("GET", "/Users/alice/missing_secret.py")
        h_get.do_GET()
        self.assertEqual(h_get.resp_status, 404)
        self._assert_clean_chinese_error(h_get.wfile.getvalue().decode("utf-8"))

        with patch.dict(os.environ, {"TEAM_TOKEN": "test-r1-2-secret-token"}, clear=False):
            h_post = _TestableHandler(
                "POST",
                "/api/Users/alice/server.py",
                body={},
                headers={"X-Team-Token": "test-r1-2-secret-token"},
            )
            h_post.do_POST()
        self.assertEqual(h_post.resp_status, 404)
        self._assert_clean_chinese_error(h_post.wfile.getvalue().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
