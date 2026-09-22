"""frame_builder.py の_get_browser()・_sub_label()に対するユニットテスト。
実際のChromium/Playwrightは起動せず、_get_browser()はsync_playwrightを
モックして起動失敗時の後片付けだけを検証する(軽いテストのみ)。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import frame_builder


@pytest.fixture(autouse=True)
def _reset_playwright_ctx():
    frame_builder._playwright_ctx["pw"] = None
    frame_builder._playwright_ctx["browser"] = None
    yield
    frame_builder._playwright_ctx["pw"] = None
    frame_builder._playwright_ctx["browser"] = None


def test_get_browser_stops_driver_when_launch_fails(monkeypatch):
    # chromium.launch()が失敗した場合、start()済みのドライバープロセスが
    # 誰にも参照されず残ってしまう回帰を防ぐテスト。
    mock_pw = MagicMock()
    mock_pw.chromium.launch.side_effect = RuntimeError("boom")
    monkeypatch.setattr(frame_builder, "sync_playwright", lambda: MagicMock(start=lambda: mock_pw))

    with pytest.raises(RuntimeError):
        frame_builder._get_browser()

    mock_pw.stop.assert_called_once()
    assert frame_builder._playwright_ctx["pw"] is None
    assert frame_builder._playwright_ctx["browser"] is None


def test_get_browser_returns_cached_browser_without_relaunching(monkeypatch):
    mock_pw = MagicMock()
    mock_browser = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser
    monkeypatch.setattr(frame_builder, "sync_playwright", lambda: MagicMock(start=lambda: mock_pw))

    first = frame_builder._get_browser()
    second = frame_builder._get_browser()

    assert first is mock_browser
    assert second is mock_browser
    mock_pw.chromium.launch.assert_called_once()


def test_sub_label_default_says_unpronounceable():
    assert frame_builder._sub_label("tts", is_native_script=False) == \
        "[Text-to-Speech / Unpronounceable word]"


def test_sub_label_native_script_says_not_a_real_word():
    # 実在の文字体系(ロシア語・タイ語・アラビア語・ヘブライ語)でランダム
    # 生成した回は、視聴者がその言語の話者だった場合に「実在の単語だが
    # 発音が違う」と誤解するコメントが付いたため、動画フレーム自体にも
    # 注記を焼き込む回帰防止(README「ハマった罠」参照)。
    assert frame_builder._sub_label("tts", is_native_script=True) == \
        "[Text-to-Speech / Not a real word!]"


def test_sub_label_unknown_mode_falls_back_to_raw_mode_name():
    assert frame_builder._sub_label("mystery", is_native_script=False) == \
        "[mystery / Unpronounceable word]"
