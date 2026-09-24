"""youtube_traffic_source.py の純粋関数(_breakdown_with_labels)および
fetch_traffic_source_breakdown()のリクエスト組み立てに対するユニットテスト。
Google APIの実呼び出しは行わず、get_analytics_client()をモックに差し替える。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import youtube_traffic_source
from youtube_traffic_source import _breakdown_with_labels, fetch_search_queries, fetch_traffic_source_breakdown


def test_fetch_traffic_source_breakdown_parses_rows(monkeypatch):
    analytics = MagicMock()
    analytics.reports.return_value.query.return_value.execute.return_value = {
        "rows": [["RELATED_VIDEO", 900], ["YT_SEARCH", 100]]
    }
    monkeypatch.setattr(youtube_traffic_source, "get_analytics_client", lambda: analytics)

    result = fetch_traffic_source_breakdown("v1", "2026-09-01", "2026-09-23")

    assert result == [("RELATED_VIDEO", 900), ("YT_SEARCH", 100)]
    kwargs = analytics.reports.return_value.query.call_args.kwargs
    assert kwargs["ids"] == "channel==MINE"
    assert kwargs["metrics"] == "views"
    assert kwargs["dimensions"] == "insightTrafficSourceType"
    assert kwargs["filters"] == "video==v1"


def test_fetch_traffic_source_breakdown_handles_no_rows(monkeypatch):
    analytics = MagicMock()
    analytics.reports.return_value.query.return_value.execute.return_value = {}
    monkeypatch.setattr(youtube_traffic_source, "get_analytics_client", lambda: analytics)

    assert fetch_traffic_source_breakdown("v1", "2026-09-01", "2026-09-23") == []


def test_breakdown_with_labels_sorts_by_views_descending():
    breakdown = [("YT_SEARCH", 100), ("RELATED_VIDEO", 900), ("EXT_URL", 50)]
    result = _breakdown_with_labels(breakdown)
    assert [source_type for _, source_type, _, _ in result] == [
        "RELATED_VIDEO", "YT_SEARCH", "EXT_URL",
    ]


def test_breakdown_with_labels_computes_percentages():
    breakdown = [("RELATED_VIDEO", 75), ("YT_SEARCH", 25)]
    result = _breakdown_with_labels(breakdown)
    assert result[0][2:] == (75, 75.0)
    assert result[1][2:] == (25, 25.0)


def test_breakdown_with_labels_maps_known_source_to_japanese_label():
    result = _breakdown_with_labels([("RELATED_VIDEO", 10)])
    assert result[0][0] == "関連動画のおすすめ"


def test_breakdown_with_labels_falls_back_to_raw_code_for_unknown_source():
    # Google側で将来値が追加された場合でも落ちない(未知コードはそのまま表示)。
    result = _breakdown_with_labels([("SOME_NEW_SOURCE_TYPE", 10)])
    assert result[0][0] == "SOME_NEW_SOURCE_TYPE"


def test_breakdown_with_labels_handles_empty_input():
    assert _breakdown_with_labels([]) == []


def test_breakdown_with_labels_zero_total_views_gives_zero_percent():
    result = _breakdown_with_labels([("RELATED_VIDEO", 0)])
    assert result[0][3] == 0.0


def test_fetch_search_queries_parses_and_sorts_rows(monkeypatch):
    analytics = MagicMock()
    analytics.reports.return_value.query.return_value.execute.return_value = {
        "rows": [["how to pronounce zalgo", 5], ["unpronounceable word", 20]]
    }
    monkeypatch.setattr(youtube_traffic_source, "get_analytics_client", lambda: analytics)

    result = fetch_search_queries("v1", "2026-09-01", "2026-09-23")

    assert result == [("unpronounceable word", 20), ("how to pronounce zalgo", 5)]
    kwargs = analytics.reports.return_value.query.call_args.kwargs
    assert kwargs["ids"] == "channel==MINE"
    assert kwargs["metrics"] == "views"
    assert kwargs["dimensions"] == "insightTrafficSourceDetail"
    assert kwargs["filters"] == "video==v1;insightTrafficSourceType==YT_SEARCH"


def test_fetch_search_queries_handles_no_rows(monkeypatch):
    analytics = MagicMock()
    analytics.reports.return_value.query.return_value.execute.return_value = {}
    monkeypatch.setattr(youtube_traffic_source, "get_analytics_client", lambda: analytics)

    assert fetch_search_queries("v1", "2026-09-01", "2026-09-23") == []
