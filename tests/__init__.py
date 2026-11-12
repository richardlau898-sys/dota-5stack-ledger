# -*- coding: utf-8 -*-
"""
T3-3 · 测试包全局隔离初始化
1. 自动将环境变量 DOTA_TMP_DIR 指向独立的临时目录（进程退出时清理），确保测试绝不读写生产缓存 /tmp/dota_reports。
2. 自动安装离线外网阻断卫士（除非显式设置 DOTA_ALLOW_TEST_NETWORK=1）。
"""
import atexit
import importlib.util
import os
import shutil
import tempfile
from pathlib import Path

_PROD_TMP_DIR = Path("/tmp/dota_reports").resolve()
_cur_tmp = (os.environ.get("DOTA_TMP_DIR") or "").strip()
if not _cur_tmp or Path(_cur_tmp).resolve() == _PROD_TMP_DIR:
    _isolated_tmp_dir = tempfile.mkdtemp(prefix="dota_test_tmp_")
    os.environ["DOTA_TMP_DIR"] = _isolated_tmp_dir
    atexit.register(shutil.rmtree, _isolated_tmp_dir, True)

_site_guard_path = Path(__file__).resolve().parent.parent / "tools" / "no_network_site" / "sitecustomize.py"
if _site_guard_path.exists() and os.environ.get("DOTA_ALLOW_TEST_NETWORK") != "1":
    _spec = importlib.util.spec_from_file_location("_dota_no_network_site", _site_guard_path)
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
