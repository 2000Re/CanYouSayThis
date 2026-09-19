"""youtube_upload.py の純粋関数(_token_age_warning, _quota_summary_lines)や
append_video_description()に対するユニットテスト。Google APIの実呼び出しは
行わず、get_youtube_client()をモックに差し替える。"""

import datetime
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import youtube_upload
from youtube_upload import QUOTA_COST_PER_CALL, _quota_summary_lines, _token_age_warning


def test_token_age_warning_none_when_unset():
    assert _token_age_warning(None) is None
    assert _token_age_warning("") is None


def test_token_age_warning_none_when_fresh():
    today = datetime.date(2026, 8, 31)
    assert _token_age_warning("2026-08-30", today=today) is None


def test_token_age_warning_fires_near_expiry():
    today = datetime.date(2026, 8, 31)
    # デフォルト warning_after_days=5, expiry_days=7 のとき、5日経過は警告対象
    message = _token_age_warning("2026-08-26", today=today)
    assert message is not None
    assert "再実行" in message


def test_token_age_warning_fires_after_expiry():
    today = datetime.date(2026, 8, 31)
    # 7日以上経過は「おそらく失効済み」の文面になる
    message = _token_age_warning("2026-08-20", today=today)
    assert message is not None
    assert "超えて" in message


def test_token_age_warning_none_on_bad_format():
    assert _token_age_warning("not-a-date") is None


def test_token_age_warning_respects_custom_thresholds():
    today = datetime.date(2026, 8, 31)
    # warning_after_days/expiry_daysを変えても正しく反映される
    assert _token_age_warning("2026-08-30", today=today,
                               warning_after_days=1, expiry_days=3) is not None
    assert _token_age_warning("2026-08-30", today=today,
                               warning_after_days=5, expiry_days=7) is None


def test_quota_summary_lines_reports_consumption_and_remaining():
    counts = {"videos.insert": 3}
    costs = {"videos.insert": 100}
    lines = _quota_summary_lines(counts, costs, daily_quota_units=10000, daily_upload_limit=100)
    text = "\n".join(lines)
    assert "300" in text
    assert "9700" in text
    assert "97" in text


def test_quota_cost_per_call_includes_playlist_items_insert():
    # playlistItems.insertは公式ドキュメントの一般的な書き込み操作コスト(50 units)
    assert QUOTA_COST_PER_CALL["playlistItems.insert"] == 50


def test_quota_cost_per_call_includes_channels_list():
    # channels.listは公式ドキュメントの一般的な読み取り操作コスト(1 unit)。
    # _verify_channel()が実際にAPIを叩くたび消費するが、以前はログの
    # クォータ集計に含まれていなかった。
    assert QUOTA_COST_PER_CALL["channels.list"] == 1


def test_quota_summary_lines_clamps_remaining_at_zero():
    # 消費量が上限を超えても残容量表示はマイナスにならない
    counts = {"videos.insert": 200}
    costs = {"videos.insert": 100}
    lines = _quota_summary_lines(counts, costs, daily_quota_units=10000, daily_upload_limit=100)
    text = "\n".join(lines)
    assert "残り目安: 0本" in text


def test_quota_cost_per_call_includes_videos_list_and_update():
    # append_video_description()が使うvideos.list(読み取り1 unit)/
    # videos.update(書き込み50 unit、公式ドキュメントの一般的なコスト)。
    assert QUOTA_COST_PER_CALL["videos.list"] == 1
    assert QUOTA_COST_PER_CALL["videos.update"] == 50


def _mock_youtube_client(existing_description):
    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"title": "t", "description": existing_description}}]
    }
    return youtube


def test_append_video_description_appends_to_existing_snippet(monkeypatch):
    youtube = _mock_youtube_client("original description")
    monkeypatch.setattr(youtube_upload, "get_youtube_client", lambda: youtube)
    monkeypatch.setattr(youtube_upload, "_api_call_counts",
                         {name: 0 for name in QUOTA_COST_PER_CALL})

    youtube_upload.append_video_description("abc123", "extra line")

    _, kwargs = youtube.videos.return_value.update.call_args
    assert kwargs["body"]["id"] == "abc123"
    snippet = kwargs["body"]["snippet"]
    # titleなど他のフィールドは失わずそのまま送り返す(丸ごと置き換え仕様のため)
    assert snippet["title"] == "t"
    assert snippet["description"] == "original description\n\nextra line"
    assert youtube_upload._api_call_counts["videos.list"] == 1
    assert youtube_upload._api_call_counts["videos.update"] == 1


def test_append_video_description_raises_when_video_not_found(monkeypatch):
    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {"items": []}
    monkeypatch.setattr(youtube_upload, "get_youtube_client", lambda: youtube)
    monkeypatch.setattr(youtube_upload, "_api_call_counts",
                         {name: 0 for name in QUOTA_COST_PER_CALL})

    with pytest.raises(RuntimeError):
        youtube_upload.append_video_description("missing", "extra line")


def _set_credential_env(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "client-id")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "refresh-token")


def test_load_credentials_defaults_to_upload_scopes(monkeypatch):
    _set_credential_env(monkeypatch)
    credentials = youtube_upload._load_credentials()
    assert credentials.scopes == youtube_upload.UPLOAD_SCOPES


def test_load_credentials_with_explicit_none_does_not_restrict_scopes(monkeypatch):
    # youtube_analytics.get_analytics_client()はscopes=Noneを渡す。リフレッシュ
    # トークンの実際の付与範囲と厳密に一致しない部分集合を指定するとGoogle側で
    # invalid_scopeエラーになるため、絞り込まずに済ませられることの回帰防止。
    _set_credential_env(monkeypatch)
    credentials = youtube_upload._load_credentials(scopes=None)
    assert credentials.scopes is None


def test_load_credentials_raises_when_env_vars_missing(monkeypatch):
    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        youtube_upload._load_credentials()
