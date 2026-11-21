#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
英雄攻略页的数据读取 (hero_builds_store.py)

数据由 GitHub Actions 定时生成（.github/workflows/hero_builds.yml），
以单个 gzip JSON 文件发布在本仓库的 Release "hero-builds-data" 下。
网站只读取这个文件：每个服务器实例最多每 30 分钟取一次，取不到时继续用上一次的数据。
"""
import gzip
import json
import os
import threading
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple

DEFAULT_BUNDLE_URL = (
    "https://github.com/richardlau898-sys/dota-5stack-ledger/releases/download/"
    "hero-builds-data/hero_builds.json.gz"
)
REFRESH_SECONDS = 30 * 60
FETCH_TIMEOUT = 12
MAX_BUNDLE_BYTES = 20 * 1024 * 1024

_lock = threading.Lock()
_state: Dict[str, Any] = {"bundle": None, "fetched_at": 0.0, "last_attempt": 0.0}


class HeroBuildsUnavailable(Exception):
    """攻略数据还没有生成，或暂时取不到。"""


def bundle_url() -> str:
    return (os.environ.get("HERO_BUILDS_BUNDLE_URL") or DEFAULT_BUNDLE_URL).strip()


def _download() -> Dict[str, Any]:
    req = urllib.request.Request(bundle_url(), headers={"User-Agent": "dota-ledger-hero-builds/1.0"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        raw = resp.read(MAX_BUNDLE_BYTES + 1)
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ValueError("hero builds bundle too large")
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("index"), dict) or not isinstance(data.get("heroes"), dict):
        raise ValueError("hero builds bundle has an unexpected shape")
    return data


def get_bundle(now: Optional[float] = None) -> Tuple[Dict[str, Any], bool]:
    """返回 (bundle, is_stale)。没有任何可用数据时抛出 HeroBuildsUnavailable。"""
    now = time.time() if now is None else now
    with _lock:
        cached = _state["bundle"]
        fresh = cached is not None and now - _state["fetched_at"] < REFRESH_SECONDS
        # 失败后 60 秒内不重复请求，避免每个访客都触发一次下载。
        recently_failed = now - _state["last_attempt"] < 60 and not fresh
        if fresh:
            return cached, False
        if recently_failed:
            if cached is not None:
                return cached, True
            raise HeroBuildsUnavailable()
        _state["last_attempt"] = now
    try:
        data = _download()
    except Exception as exc:  # 网络或格式问题：有旧数据就用旧数据
        import sys
        sys.stderr.write(f"[hero_builds] bundle fetch failed: {type(exc).__name__}\n")
        with _lock:
            if _state["bundle"] is not None:
                return _state["bundle"], True
        raise HeroBuildsUnavailable() from None
    with _lock:
        _state["bundle"] = data
        _state["fetched_at"] = now
    return data, False


def reset_cache_for_tests() -> None:
    with _lock:
        _state.update({"bundle": None, "fetched_at": 0.0, "last_attempt": 0.0})
