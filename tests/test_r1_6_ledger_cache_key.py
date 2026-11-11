# -*- coding: utf-8 -*-
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import dota_analyst

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestR16LedgerCacheKey(unittest.TestCase):
    """R1-6 · 总账缓存键：跨进程确定性 SHA-256 签名"""

    def test_ledger_dir_signature_equal_across_subprocesses(self):
        roster = dota_analyst.load_roster()
        with tempfile.TemporaryDirectory() as tmpdir:
            tpath = Path(tmpdir)
            # 非空文件输入（Rule 16）
            (tpath / "match_9000000001.json").write_text('{"match_id": 9000000001}', encoding="utf-8")
            (tpath / "match_9000000002.json").write_text('{"match_id": 9000000002}', encoding="utf-8")

            code = (
                "import sys, dota_analyst, draft_and_phase_coach;"
                f"roster = dota_analyst.load_roster();"
                f"print(draft_and_phase_coach._ledger_dir_signature({str(tpath)!r}, roster))"
            )
            env1 = dict(os.environ, PYTHONHASHSEED="101", PYTHONPATH=str(REPO_ROOT))
            env2 = dict(os.environ, PYTHONHASHSEED="202", PYTHONPATH=str(REPO_ROOT))

            out1 = subprocess.check_output([sys.executable, "-c", code], env=env1, text=True).strip()
            out2 = subprocess.check_output([sys.executable, "-c", code], env=env2, text=True).strip()

            self.assertTrue(out1)
            self.assertEqual(out1, out2)
            # Hash suffix should be 64-char sha256 hex digest, not signed integer hash()
            suffix = out1.rsplit("|", 1)[-1]
            self.assertEqual(len(suffix), 64)
            int(suffix, 16)


if __name__ == "__main__":
    unittest.main()
