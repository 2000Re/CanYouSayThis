"""youtube_quick_stats.py の純粋関数(_entries_in_last_hours)に対する
ユニットテスト。Google APIの実呼び出しは行わない。"""

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from youtube_quick_stats import _entries_in_last_hours

NOW = datetime.datetime(2026, 9, 22, 12, 0, 0, tzinfo=datetime.timezone.utc)


def test_entries_in_last_hours_includes_recent_entry():
    history = [{"video_id": "a", "uploaded_at": "2026-09-22T10:00:00+00:00"}]
    result = _entries_in_last_hours(history, hours=24, now=NOW)
    assert [e["video_id"] for e in result] == ["a"]


def test_entries_in_last_hours_excludes_old_entry():
    history = [{"video_id": "a", "uploaded_at": "2026-09-20T10:00:00+00:00"}]
    result = _entries_in_last_hours(history, hours=24, now=NOW)
    assert result == []


def test_entries_in_last_hours_is_inclusive_of_cutoff():
    cutoff_str = (NOW - datetime.timedelta(hours=24)).isoformat()
    history = [{"video_id": "a", "uploaded_at": cutoff_str}]
    result = _entries_in_last_hours(history, hours=24, now=NOW)
    assert [e["video_id"] for e in result] == ["a"]


def test_entries_in_last_hours_skips_entries_without_uploaded_at():
    history = [{"video_id": "a", "uploaded_at": None}, {"video_id": "b"}]
    result = _entries_in_last_hours(history, hours=24, now=NOW)
    assert result == []


def test_entries_in_last_hours_skips_malformed_dates():
    history = [{"video_id": "a", "uploaded_at": "not-a-date"}]
    result = _entries_in_last_hours(history, hours=24, now=NOW)
    assert result == []
