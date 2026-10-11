"""youtube_regular_video_impressions.py の純粋関数(list_regular_video_ids
のフィルタリング相当、fetch_video_impressions)に対するユニットテスト。
Google APIの実呼び出しは行わず、get_analytics_client()/get_youtube_client()
をモックに差し替える。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import youtube_regular_video_impressions
from youtube_regular_video_impressions import fetch_video_impressions, list_regular_video_ids


def test_fetch_video_impressions_parses_rows_and_converts_ctr_to_percent(monkeypatch):
    analytics = MagicMock()
    analytics.reports.return_value.query.return_value.execute.return_value = {
        "rows": [["v1", 10, 200, 0.05], ["v2", 3, 50, 0.06]]
    }
    monkeypatch.setattr(
        youtube_regular_video_impressions, "get_analytics_client", lambda: analytics
    )

    result = fetch_video_impressions(["v1", "v2"], "2026-09-01", "2026-09-23")

    assert result == {
        "v1": {"views": 10, "impressions": 200, "impression_click_through_rate": 5.0},
        "v2": {"views": 3, "impressions": 50, "impression_click_through_rate": 6.0},
    }
    kwargs = analytics.reports.return_value.query.call_args.kwargs
    assert kwargs["ids"] == "channel==MINE"
    assert kwargs["metrics"] == "views,impressions,impressionClickThroughRate"
    assert kwargs["dimensions"] == "video"
    assert kwargs["filters"] == "video==v1,v2"


def test_fetch_video_impressions_omits_videos_with_no_data(monkeypatch):
    analytics = MagicMock()
    analytics.reports.return_value.query.return_value.execute.return_value = {
        "rows": [["v1", 10, 200, 0.05]]
    }
    monkeypatch.setattr(
        youtube_regular_video_impressions, "get_analytics_client", lambda: analytics
    )

    result = fetch_video_impressions(["v1", "v2"], "2026-09-01", "2026-09-23")

    assert "v1" in result
    assert "v2" not in result


def test_fetch_video_impressions_handles_empty_rows(monkeypatch):
    analytics = MagicMock()
    analytics.reports.return_value.query.return_value.execute.return_value = {}
    monkeypatch.setattr(
        youtube_regular_video_impressions, "get_analytics_client", lambda: analytics
    )

    assert fetch_video_impressions(["v1"], "2026-09-01", "2026-09-23") == {}


def _playlist_items_page(video_titles, next_page_token=None):
    resp = {
        "items": [
            {"snippet": {"title": title, "resourceId": {"videoId": video_id}}}
            for video_id, title in video_titles
        ]
    }
    if next_page_token:
        resp["nextPageToken"] = next_page_token
    return resp


def test_list_regular_video_ids_excludes_shorts_by_title(monkeypatch):
    youtube = MagicMock()
    youtube.channels.return_value.list.return_value.execute.return_value = {
        "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUxxxx"}}}]
    }
    youtube.playlistItems.return_value.list.return_value.execute.return_value = (
        _playlist_items_page([
            ("v1", 'How to Pronounce "abc" #Shorts'),
            ("v2", 'How to Pronounce "abc"'),
            ("v3", 'Can You Say "xyz" in French? #Shorts'),
        ])
    )
    # list_regular_video_ids()は関数内でyoutube_uploadからget_youtube_clientを
    # 遅延importするため、youtube_upload側をモックする。
    import youtube_upload
    monkeypatch.setattr(youtube_upload, "get_youtube_client", lambda: youtube)

    result = list_regular_video_ids()

    assert result == [("v2", 'How to Pronounce "abc"')]


def test_list_regular_video_ids_paginates_through_all_pages(monkeypatch):
    youtube = MagicMock()
    youtube.channels.return_value.list.return_value.execute.return_value = {
        "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUxxxx"}}}]
    }
    pages = [
        _playlist_items_page([("v1", "no shorts tag")], next_page_token="PAGE2"),
        _playlist_items_page([("v2", "also no shorts tag")]),
    ]
    youtube.playlistItems.return_value.list.return_value.execute.side_effect = pages

    import youtube_upload
    monkeypatch.setattr(youtube_upload, "get_youtube_client", lambda: youtube)

    result = list_regular_video_ids()

    assert result == [("v1", "no shorts tag"), ("v2", "also no shorts tag")]
