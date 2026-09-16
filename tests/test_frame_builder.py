"""frame_builder.py の_get_browser()に対するユニットテスト。実際の
Chromium/Playwrightは起動せず、sync_playwrightをモックして
起動失敗時の後片付けだけを検証する(軽いテストのみ)。"""

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
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


_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_mode_accent_colors_cover_every_mode():
    # モードごとのアクセントカラーが1つでも抜けていると、そのモードの動画
    # フレームだけDEFAULT_MODE_ACCENT_COLORにフォールバックして他モードと
    # 見分けがつかなくなってしまうため、全モード分揃っていることを保証する。
    for mode in config.MODE_LABELS:
        assert mode in config.MODE_ACCENT_COLORS, mode


def test_mode_accent_colors_are_valid_hex_colors():
    colors = list(config.MODE_ACCENT_COLORS.values()) + [config.DEFAULT_MODE_ACCENT_COLOR]
    for color in colors:
        assert _HEX_COLOR_RE.match(color), color


def test_frame_html_template_renders_mode_accent_color():
    html_content = frame_builder.FRAME_HTML_TEMPLATE.format(
        font_stack="sans-serif", word="test", mode_label="Text-to-Speech",
        word_font_size=100, width=1080, height=1920, word_max_width=1000,
        kicker_font_size=30, sub_font_size=20, icon_size=90, word_margin_top=100,
        background_color=frame_builder._BACKGROUND_COLOR,
        word_color=config.MODE_ACCENT_COLORS["tts"],
    )
    assert f"background:{frame_builder._BACKGROUND_COLOR}" in html_content
    assert f"color:{config.MODE_ACCENT_COLORS['tts']}" in html_content
