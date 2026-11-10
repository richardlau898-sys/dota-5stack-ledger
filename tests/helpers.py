import json
import pathlib
import urllib.request
from typing import Any, Dict, Iterator, List, Tuple
from unittest.mock import patch

import dota_analyst

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT_DIR / "reports"
FIXTURES_DIR = ROOT_DIR / "tests" / "fixtures"

_RAW_CACHE: Dict[int, Dict[str, Any]] = {}
_REPORT_CACHE: Dict[int, Dict[str, Any]] = {}


def _forbid_network(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError(f"Offline test attempted network call: args={args} kwargs={kwargs}")


def load_all_raw_matches() -> Dict[int, Dict[str, Any]]:
    if _RAW_CACHE:
        return _RAW_CACHE
    paths: List[pathlib.Path] = []
    if FIXTURES_DIR.exists():
        paths.extend(sorted(FIXTURES_DIR.glob("raw_*.json")))
    if REPORTS_DIR.exists():
        paths.extend(sorted(REPORTS_DIR.glob("raw_*.json")))
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("match_id"):
            mid = int(data["match_id"])
            if mid not in _RAW_CACHE:
                _RAW_CACHE[mid] = data
    return _RAW_CACHE


def build_all_sample_reports(force_rebuild: bool = False) -> Dict[int, Dict[str, Any]]:
    if _REPORT_CACHE and not force_rebuild:
        return _REPORT_CACHE
    _REPORT_CACHE.clear()
    raw_matches = load_all_raw_matches()
    roster = dota_analyst.load_roster()
    main_aid = roster.get("main_account_id")
    with patch.object(urllib.request, "urlopen", side_effect=_forbid_network), \
         patch.object(dota_analyst, "load_cached_grok_coaching", return_value=None):
        for mid, raw_data in raw_matches.items():
            report = dota_analyst.analyze_match_data(
                raw_data,
                roster=roster,
                focus_account_id=main_aid,
            )
            _REPORT_CACHE[mid] = report
    return _REPORT_CACHE


def iter_report_strings(obj: Any, path: str = "") -> Iterator[Tuple[str, str]]:
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            sub_path = f"{path}.{k}" if path else str(k)
            yield from iter_report_strings(v, sub_path)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            sub_path = f"{path}[{i}]"
            yield from iter_report_strings(v, sub_path)
