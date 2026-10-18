"""youtube_fix_title_description.py の fix_video_title_description()に
対するユニットテスト。Google APIの実呼び出しは行わず、get_youtube_client()
と upload_history.load_upload_history() をモックに差し替える。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import youtube_fix_title_description
from youtube_fix_title_description import fix_video_title_description


def _symbol_heavy_entry():
    # 視聴者リクエスト(音楽記号+はさみ記号混在)で、タイトル表示が豆腐・
    # 意図しない絵文字になっていたことが発覚した実例(README「ハマった罠」
    # 79番)と同じ構成。
    word = "\U0001D1DA✂iv"  # 音楽記号+はさみ記号+通常の文字
    return {
        "word": word, "label": word, "video_id": "v1", "mode": "glitch",
        "voice_label": None, "lang_code": None, "title_template": "is_pronounceable",
    }


def test_fix_video_title_description_updates_when_symbols_present(monkeypatch):
    entry = _symbol_heavy_entry()
    monkeypatch.setattr(youtube_fix_title_description, "load_upload_history", lambda: [entry])

    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {
            "title": 'Is "?✂?iv" Pronounceable in R...',
            "description": "old description",
            "categoryId": "24",
        }}]
    }
    monkeypatch.setattr(youtube_fix_title_description, "get_youtube_client", lambda: youtube)

    result = fix_video_title_description("v1")

    assert result is True
    calls = youtube.videos.return_value.update.call_args_list
    snippet_call = next(c for c in calls if c.kwargs["part"] == "snippet")
    body = snippet_call.kwargs["body"]
    assert body["id"] == "v1"
    assert "✂" not in body["snippet"]["title"]
    assert "\U0001D1DA" not in body["snippet"]["title"]
    assert "iv" in body["snippet"]["title"]
    # categoryId等、titleとdescription以外のフィールドは保持する
    assert body["snippet"]["categoryId"] == "24"

    localizations_call = next(c for c in calls if c.kwargs["part"] == "localizations")
    assert localizations_call.kwargs["body"]["id"] == "v1"


def test_fix_video_title_description_preserves_playlist_link(monkeypatch):
    entry = _symbol_heavy_entry()
    monkeypatch.setattr(youtube_fix_title_description, "load_upload_history", lambda: [entry])

    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {
            "title": "old title",
            "description": "intro\n\nhttps://www.youtube.com/playlist?list=PLxyz123\n\nmore",
        }}]
    }
    monkeypatch.setattr(youtube_fix_title_description, "get_youtube_client", lambda: youtube)

    fix_video_title_description("v1")

    snippet_call = next(
        c for c in youtube.videos.return_value.update.call_args_list if c.kwargs["part"] == "snippet"
    )
    assert "playlist?list=PLxyz123" in snippet_call.kwargs["body"]["snippet"]["description"]


def test_fix_video_title_description_skips_when_no_upload_history_entry(monkeypatch):
    monkeypatch.setattr(youtube_fix_title_description, "load_upload_history", lambda: [])
    youtube = MagicMock()
    monkeypatch.setattr(youtube_fix_title_description, "get_youtube_client", lambda: youtube)

    result = fix_video_title_description("v1")

    assert result is False
    youtube.videos.assert_not_called()


def test_fix_video_title_description_skips_when_no_title_template_recorded(monkeypatch):
    # title_templateが記録されていない古いエントリ(README「ハマった罠」
    # 77番)は、元の言い回しを再現できないため対象外のまま。
    entry = _symbol_heavy_entry()
    entry["title_template"] = None
    monkeypatch.setattr(youtube_fix_title_description, "load_upload_history", lambda: [entry])
    youtube = MagicMock()
    monkeypatch.setattr(youtube_fix_title_description, "get_youtube_client", lambda: youtube)

    result = fix_video_title_description("v1")

    assert result is False
    youtube.videos.assert_not_called()


def test_fix_video_title_description_skips_when_already_correct(monkeypatch):
    entry = {
        "word": "voOn", "label": "voOn", "video_id": "v1", "mode": "tts",
        "voice_label": None, "lang_code": None, "title_template": "how_to_pronounce",
    }
    monkeypatch.setattr(youtube_fix_title_description, "load_upload_history", lambda: [entry])

    from generate import _youtube_metadata
    title, description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "voOn", "voOn", "tts", title_template="how_to_pronounce",
    )

    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"title": title, "description": description}}]
    }
    monkeypatch.setattr(youtube_fix_title_description, "get_youtube_client", lambda: youtube)

    result = fix_video_title_description("v1")

    assert result is False
    youtube.videos.return_value.update.assert_not_called()


def test_fix_video_title_description_handles_missing_video(monkeypatch):
    entry = _symbol_heavy_entry()
    monkeypatch.setattr(youtube_fix_title_description, "load_upload_history", lambda: [entry])
    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {"items": []}
    monkeypatch.setattr(youtube_fix_title_description, "get_youtube_client", lambda: youtube)

    result = fix_video_title_description("v1")

    assert result is False
    youtube.videos.return_value.update.assert_not_called()
