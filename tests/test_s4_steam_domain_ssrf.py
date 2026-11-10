import io
import unittest
from unittest.mock import patch

import server


class _FakeXmlResp:
    def __init__(self, xml_str: str):
        self._buf = io.BytesIO(xml_str.encode("utf-8"))

    def read(self) -> bytes:
        return self._buf.read()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestS4SteamDomainSsrf(unittest.TestCase):
    """S4 · 玩家搜索只允许 Steam 域名"""

    def test_reject_internal_ip_http_url(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            with self.assertRaises(ValueError):
                server.resolve_player_input("http://169.254.169.254/")
            mock_urlopen.assert_not_called()

    def test_reject_spoofed_subdomain_hostname(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            with self.assertRaises(ValueError):
                server.resolve_player_input("https://steamcommunity.com.evil.example/id/x")
            mock_urlopen.assert_not_called()

    def test_accept_valid_steamcommunity_https_url_and_short_name(self):
        xml_payload = "<profile><steamID64>76561198046346640</steamID64></profile>"
        with patch("urllib.request.urlopen", return_value=_FakeXmlResp(xml_payload)) as mock_urlopen:
            aid = server.resolve_player_input("https://steamcommunity.com/id/richardlau898/")
            self.assertEqual(aid, 86080912)
            req_obj = mock_urlopen.call_args[0][0]
            self.assertEqual(req_obj.full_url, "https://steamcommunity.com/id/richardlau898/?xml=1")

        with patch("urllib.request.urlopen", return_value=_FakeXmlResp(xml_payload)) as mock_urlopen:
            aid2 = server.resolve_player_input("richardlau898")
            self.assertEqual(aid2, 86080912)
            req_obj2 = mock_urlopen.call_args[0][0]
            self.assertEqual(req_obj2.full_url, "https://steamcommunity.com/id/richardlau898/?xml=1")

    def test_accept_pure_numeric_id_without_network(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            self.assertEqual(server.resolve_player_input("86080912"), 86080912)
            self.assertEqual(server.resolve_player_input("76561198046346640"), 86080912)
            mock_urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
