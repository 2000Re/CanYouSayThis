"""youtube_fix_localization.py の純粋関数(_rebuild_title)および
fix_video_localization()のリクエスト組み立てに対するユニットテスト。
Google APIの実呼び出しは行わず、get_youtube_client()をモックに差し替える。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import youtube_fix_localization
from youtube_fix_localization import _rebuild_title, fix_video_localization


def test_rebuild_title_moves_language_name_to_front():
    title = "「קקעמדחפ」の発音は?(ヘブライ語) #Shorts"
    result = _rebuild_title(title)
    assert result == "ヘブライ語で「⁨קקעמדחפ⁩」はどう発音する? #Shorts"


def test_rebuild_title_rewraps_already_isolated_label_too():
    # bidi isolate文字で囲むだけの旧対策が適用済みのタイトルも、語順自体は
    # 旧形式のままなので新形式へ組み立て直す対象になる。
    title = "「⁨קקעמדחפ⁩」の発音は?(ヘブライ語) #Shorts"
    result = _rebuild_title(title)
    assert result == "ヘブライ語で「⁨קקעמדחפ⁩」はどう発音する? #Shorts"


def test_rebuild_title_returns_none_when_no_brackets():
    assert _rebuild_title("何も囲まれていないタイトル #Shorts") is None


def test_rebuild_title_works_without_language_name():
    title = "「voOn」の発音は? #Shorts"
    result = _rebuild_title(title)
    assert result == "「⁨voOn⁩」の発音は? #Shorts"


def test_rebuild_title_returns_none_when_already_new_format():
    title = "ヘブライ語で「⁨קקעמדחפ⁩」はどう発音する? #Shorts"
    assert _rebuild_title(title) is None


def test_rebuild_title_returns_none_when_no_change_needed():
    # 言語名が無く、既にisolate済みの場合は組み立て直しても変化が無い。
    title = "「⁨voOn⁩」の発音は? #Shorts"
    assert _rebuild_title(title) is None


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
    assert fixed_ja["title"] == "ヘブライ語で「⁨קקעמדחפ⁩」はどう発音する? #Shorts"
    assert fixed_ja["description"] == "desc"


def test_fix_video_localization_skips_when_already_fixed(monkeypatch):
    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"localizations": {"ja": {
            "title": "ヘブライ語で「⁨קקעמדחפ⁩」はどう発音する? #Shorts",
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
