"""youtube_fix_localization.py の純粋関数(_rewrap_title_label)および
fix_video_localization()のリクエスト組み立てに対するユニットテスト。
Google APIの実呼び出しは行わず、get_youtube_client()をモックに差し替える。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import youtube_fix_localization
from youtube_fix_localization import _rewrap_title_label, fix_video_localization


def test_rewrap_title_label_wraps_label_with_bidi_isolate():
    title = "「קקעמדחפ」の発音は?(ヘブライ語) #Shorts"
    result = _rewrap_title_label(title)
    assert result == "「⁨קקעמדחפ⁩」の発音は?(ヘブライ語) #Shorts"


def test_rewrap_title_label_returns_none_when_already_wrapped():
    title = "「⁨קקעמדחפ⁩」の発音は?(ヘブライ語) #Shorts"
    assert _rewrap_title_label(title) is None


def test_rewrap_title_label_returns_none_when_no_brackets():
    assert _rewrap_title_label("何も囲まれていないタイトル #Shorts") is None


def test_rewrap_title_label_works_without_language_name():
    title = "「voOn」の発音は? #Shorts"
    result = _rewrap_title_label(title)
    assert result == "「⁨voOn⁩」の発音は? #Shorts"


def test_fix_video_localization_updates_when_needed(monkeypatch):
    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"localizations": {"ja": {
            "title": "「קקעמדחפ」の発音は?(ヘブライ語) #Shorts",
            "description": "desc",
        }}}]
    }
    monkeypatch.setattr(youtube_fix_localization, "get_youtube_client", lambda: youtube)

    result = fix_video_localization("v1")

    assert result is True
    update_kwargs = youtube.videos.return_value.update.call_args.kwargs
    assert update_kwargs["part"] == "localizations"
    assert update_kwargs["body"]["id"] == "v1"
    fixed_ja = update_kwargs["body"]["localizations"]["ja"]
    assert fixed_ja["title"] == "「⁨קקעמדחפ⁩」の発音は?(ヘブライ語) #Shorts"
    assert fixed_ja["description"] == "desc"


def test_fix_video_localization_skips_when_already_fixed(monkeypatch):
    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"localizations": {"ja": {
            "title": "「⁨voOn⁩」の発音は? #Shorts",
            "description": "desc",
        }}}]
    }
    monkeypatch.setattr(youtube_fix_localization, "get_youtube_client", lambda: youtube)

    result = fix_video_localization("v1")

    assert result is False
    youtube.videos.return_value.update.assert_not_called()


def test_fix_video_localization_skips_when_no_japanese_localization(monkeypatch):
    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"localizations": {}}]
    }
    monkeypatch.setattr(youtube_fix_localization, "get_youtube_client", lambda: youtube)

    result = fix_video_localization("v1")

    assert result is False
    youtube.videos.return_value.update.assert_not_called()


def test_fix_video_localization_handles_missing_video(monkeypatch):
    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {"items": []}
    monkeypatch.setattr(youtube_fix_localization, "get_youtube_client", lambda: youtube)

    result = fix_video_localization("v1")

    assert result is False
    youtube.videos.return_value.update.assert_not_called()
