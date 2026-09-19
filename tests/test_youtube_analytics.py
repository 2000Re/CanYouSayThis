"""youtube_analytics.py の純粋関数(_chunk, _entries_in_range, _days_available,
summarize_by_mode)およびfetch_video_metrics()のリクエスト組み立てに対する
ユニットテスト。Google APIの実呼び出しは行わず、get_analytics_client()を
モックに差し替える。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import youtube_analytics
from youtube_analytics import (
    _chunk,
    _days_available,
    _entries_in_range,
    fetch_video_metrics,
    summarize_by_mode,
)


def test_chunk_splits_into_expected_sizes():
    chunks = list(_chunk(list(range(10)), 3))
    assert chunks == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]


def test_chunk_handles_empty_sequence():
    assert list(_chunk([], 5)) == []


def test_entries_in_range_filters_by_uploaded_at():
    history = [
        {"video_id": "a", "uploaded_at": "2026-09-01T00:00:00+00:00"},
        {"video_id": "b", "uploaded_at": "2026-09-10T00:00:00+00:00"},
        {"video_id": "c", "uploaded_at": "2026-09-20T00:00:00+00:00"},
    ]
    result = _entries_in_range(history, "2026-09-05", "2026-09-15")
    assert [e["video_id"] for e in result] == ["b"]


def test_entries_in_range_is_inclusive_of_boundaries():
    history = [
        {"video_id": "a", "uploaded_at": "2026-09-05T12:00:00+00:00"},
        {"video_id": "b", "uploaded_at": "2026-09-15T12:00:00+00:00"},
    ]
    result = _entries_in_range(history, "2026-09-05", "2026-09-15")
    assert {e["video_id"] for e in result} == {"a", "b"}


def test_entries_in_range_skips_entries_without_uploaded_at():
    # uploaded_at追加前の古いエントリはキー自体が無いことがある(README参照)
    history = [
        {"video_id": "a", "uploaded_at": None},
        {"video_id": "b"},
        {"video_id": "c", "uploaded_at": "2026-09-10T00:00:00+00:00"},
    ]
    result = _entries_in_range(history, "2026-09-01", "2026-09-30")
    assert [e["video_id"] for e in result] == ["c"]


def test_entries_in_range_skips_malformed_dates():
    history = [{"video_id": "a", "uploaded_at": "not-a-date"}]
    result = _entries_in_range(history, "2026-09-01", "2026-09-30")
    assert result == []


def test_days_available_counts_upload_day_as_day_one():
    assert _days_available("2026-09-19T00:00:00+00:00", "2026-09-19") == 1


def test_days_available_counts_inclusive_span():
    assert _days_available("2026-09-10T00:00:00+00:00", "2026-09-19") == 10


def test_fetch_video_metrics_queries_in_batches_and_parses_rows(monkeypatch):
    monkeypatch.setattr(youtube_analytics.config, "ANALYTICS_VIDEO_BATCH_SIZE", 2)

    responses = iter([
        {"rows": [["v1", 100, 50.0], ["v2", 200, 60.0]]},
        {"rows": [["v3", 300, 70.0]]},
    ])
    analytics = MagicMock()
    analytics.reports.return_value.query.return_value.execute.side_effect = (
        lambda: next(responses)
    )
    monkeypatch.setattr(youtube_analytics, "get_analytics_client", lambda: analytics)

    result = fetch_video_metrics(["v1", "v2", "v3"], "2026-09-01", "2026-09-19")

    assert result == {
        "v1": {"views": 100, "average_view_percentage": 50.0},
        "v2": {"views": 200, "average_view_percentage": 60.0},
        "v3": {"views": 300, "average_view_percentage": 70.0},
    }
    assert analytics.reports.return_value.query.call_count == 2
    first_call_kwargs = analytics.reports.return_value.query.call_args_list[0].kwargs
    assert first_call_kwargs["ids"] == "channel==MINE"
    assert first_call_kwargs["metrics"] == "views,averageViewPercentage"
    assert first_call_kwargs["dimensions"] == "video"
    assert first_call_kwargs["filters"] == "video==v1,v2"


def test_fetch_video_metrics_omits_videos_with_no_data(monkeypatch):
    analytics = MagicMock()
    analytics.reports.return_value.query.return_value.execute.return_value = {
        "rows": [["v1", 100, 50.0]]
    }
    monkeypatch.setattr(youtube_analytics, "get_analytics_client", lambda: analytics)

    result = fetch_video_metrics(["v1", "v2"], "2026-09-01", "2026-09-19")
    assert "v1" in result
    assert "v2" not in result


@pytest.fixture
def sample_entries():
    return [
        {"video_id": "t1", "mode": "tts", "uploaded_at": "2026-09-10T00:00:00+00:00"},
        {"video_id": "t2", "mode": "tts", "uploaded_at": "2026-09-15T00:00:00+00:00"},
        {"video_id": "g1", "mode": "glitch", "uploaded_at": "2026-09-19T00:00:00+00:00"},
    ]


def test_summarize_by_mode_computes_totals_and_averages(sample_entries):
    metrics_by_id = {
        "t1": {"views": 100, "average_view_percentage": 40.0},   # 10日視聴可能 -> 10/day
        "t2": {"views": 50, "average_view_percentage": 60.0},    # 5日視聴可能 -> 10/day
        "g1": {"views": 10, "average_view_percentage": 20.0},    # 1日視聴可能 -> 10/day
    }
    summary = summarize_by_mode(metrics_by_id, sample_entries, "2026-09-19")

    assert summary["tts"]["videos"] == 2
    assert summary["tts"]["total_views"] == 150
    assert summary["tts"]["avg_views"] == pytest.approx(75.0)
    # 再生数重み付き視聴維持率: (100*40 + 50*60) / 150 = 46.666...
    assert summary["tts"]["avg_view_percentage"] == pytest.approx((100 * 40 + 50 * 60) / 150)
    # 1日あたり再生数: t1=100/10=10, t2=50/5=10 -> 平均10
    assert summary["tts"]["avg_views_per_day"] == pytest.approx(10.0)

    assert summary["glitch"]["videos"] == 1
    assert summary["glitch"]["total_views"] == 10
    assert summary["glitch"]["avg_views_per_day"] == pytest.approx(10.0)


def test_summarize_by_mode_treats_missing_metrics_as_zero_views(sample_entries):
    # t2, g1に対応するAnalyticsデータが無い(期間内に再生が無かった/未反映)場合
    summary = summarize_by_mode(
        {"t1": {"views": 100, "average_view_percentage": 40.0}}, sample_entries, "2026-09-19"
    )
    assert summary["tts"]["videos"] == 2
    assert summary["tts"]["total_views"] == 100
    assert summary["glitch"]["total_views"] == 0
    assert summary["glitch"]["avg_view_percentage"] == 0.0


def test_summarize_by_mode_skips_entries_missing_required_fields():
    entries = [
        {"video_id": "a", "mode": "tts", "uploaded_at": "2026-09-19T00:00:00+00:00"},
        {"video_id": None, "mode": "tts", "uploaded_at": "2026-09-19T00:00:00+00:00"},
        {"video_id": "b", "mode": None, "uploaded_at": "2026-09-19T00:00:00+00:00"},
        {"video_id": "c", "mode": "tts", "uploaded_at": None},
    ]
    summary = summarize_by_mode({}, entries, "2026-09-19")
    assert summary["tts"]["videos"] == 1
