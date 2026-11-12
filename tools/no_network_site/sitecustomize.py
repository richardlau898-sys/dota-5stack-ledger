# -*- coding: utf-8 -*-
"""
T3-3 · 离线测试外网阻断卫士 (sitecustomize.py)
当 PYTHONPATH 包含 tools/no_network_site（或由 tests/__init__.py 导入安装）且未显式设置
DOTA_ALLOW_TEST_NETWORK=1 时，拦截所有非本机回环（non-loopback）的 socket 连接与外网 DNS 解析，
直接抛出 ExternalNetworkBlockedError（继承 BaseException，防止被业务层 except Exception 吞没）。
允许 127.0.0.1 / ::1 / localhost 本地回环与 AF_UNIX 进程内通信。
"""
import os
import socket
from typing import Any

_INSTALLED = False
_ORIG_GETADDRINFO = socket.getaddrinfo
_ORIG_CREATE_CONNECTION = socket.create_connection
_ORIG_CONNECT = socket.socket.connect
_ORIG_CONNECT_EX = socket.socket.connect_ex
_ORIG_SENDTO = socket.socket.sendto


class ExternalNetworkBlockedError(BaseException):
    """Raised when offline unit tests attempt an external network connection."""


def _is_loopback_host(host: Any) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii", errors="ignore")
        except Exception:
            return False
    h = str(host).strip().lower().strip("[]")
    if h in ("", "localhost", "127.0.0.1", "::1", "0:0:0:0:0:0:0:1", "0.0.0.0", "::"):
        return True
    if h.startswith("127.") or h.startswith("::ffff:127."):
        return True
    return False


def _check_socket_address(sock_family: int, address: Any) -> None:
    af_unix = getattr(socket, "AF_UNIX", None)
    if af_unix is not None and sock_family == af_unix:
        return
    if isinstance(address, (str, bytes)):
        return
    if isinstance(address, tuple) and len(address) >= 1:
        host = address[0]
        if not _is_loopback_host(host):
            raise ExternalNetworkBlockedError(
                f"Blocked external network connection during offline tests: {address!r}"
            )


def install_no_network_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    if os.environ.get("DOTA_ALLOW_TEST_NETWORK") == "1":
        return

    def guarded_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any):
        if os.environ.get("DOTA_ALLOW_TEST_NETWORK") != "1" and not _is_loopback_host(host):
            raise ExternalNetworkBlockedError(
                f"Blocked external DNS/network lookup during offline tests: {host!r}:{port!r}"
            )
        return _ORIG_GETADDRINFO(host, port, *args, **kwargs)

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any):
        if os.environ.get("DOTA_ALLOW_TEST_NETWORK") != "1":
            _check_socket_address(socket.AF_INET, address)
        return _ORIG_CREATE_CONNECTION(address, *args, **kwargs)

    def guarded_connect(self: socket.socket, address: Any):
        if os.environ.get("DOTA_ALLOW_TEST_NETWORK") != "1":
            _check_socket_address(self.family, address)
        return _ORIG_CONNECT(self, address)

    def guarded_connect_ex(self: socket.socket, address: Any) -> int:
        if os.environ.get("DOTA_ALLOW_TEST_NETWORK") != "1":
            _check_socket_address(self.family, address)
        return _ORIG_CONNECT_EX(self, address)

    def guarded_sendto(self: socket.socket, data: Any, *args: Any):
        if os.environ.get("DOTA_ALLOW_TEST_NETWORK") != "1" and args:
            addr = args[-1]
            _check_socket_address(self.family, addr)
        return _ORIG_SENDTO(self, data, *args)

    socket.getaddrinfo = guarded_getaddrinfo  # type: ignore[assignment]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    socket.socket.connect = guarded_connect  # type: ignore[assignment]
    socket.socket.connect_ex = guarded_connect_ex  # type: ignore[assignment]
    socket.socket.sendto = guarded_sendto  # type: ignore[assignment]
    _INSTALLED = True


install_no_network_guard()
