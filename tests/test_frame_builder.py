"""frame_builder.py の_get_browser()・_sub_label()に対するユニットテスト。
実際のChromium/Playwrightは起動せず、_get_browser()はsync_playwrightを
モックして起動失敗時の後片付けだけを検証する(軽いテストのみ)。"""

import os
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


def test_random_cta_text_returns_one_of_the_known_phrases():
    assert frame_builder._random_cta_text() in frame_builder._CTA_TEXTS


def test_random_cta_text_varies_across_calls():
    # _COMMENT_TEMPLATES(generate.py)と同じ「テンプレ感」回避の方針が
    # ここでも機能していることの回帰防止(固定1パターンに戻っていないか)。
    seen = {frame_builder._random_cta_text() for _ in range(50)}
    assert len(seen) > 1


def test_thumbnail_word_font_size_shrinks_as_length_grows():
    # 文字数が増えるほど基準サイズが小さくなること(_word_font_size()と
    # 同じ傾向)の確認。
    short = frame_builder._thumbnail_word_font_size("abcdef", 1280)
    long = frame_builder._thumbnail_word_font_size("abcdefghijklmnop", 1280)
    assert short > long


def test_thumbnail_word_font_size_is_larger_than_frame_font_size():
    # サムネイルはキッカー・サブラベル・アイコンが無く全高を単語だけに
    # 使えるため、同じ文字数でも動画フレーム用(_word_font_size)より
    # 大きいサイズになることの確認。
    word_label = "abcdef"
    assert frame_builder._thumbnail_word_font_size(word_label, 1280) > \
        frame_builder._word_font_size(word_label, 1280)


def test_thumbnail_word_font_size_scales_with_width():
    base = frame_builder._thumbnail_word_font_size("abcdef", 1280)
    scaled = frame_builder._thumbnail_word_font_size("abcdef", 640)
    assert scaled == round(base / 2)


def test_word_font_size_keeps_shrinking_for_long_sentences():
    # --wordで文章丸ごとのリクエスト(animaleseモード等)が来た場合、
    # 12文字を超える長さでも単調に縮小し続けること(README「ハマった罠」
    # 63番)。以前は13文字以上が一律同じ最小サイズだった。各段階の境界を
    # またぐ代表値を1つずつ取る(13→n<=20、21→n<=35、36→n<=50、
    # 51→n<=65、66→それ以上)。
    sizes = [
        frame_builder._word_font_size("a" * n, 1280)
        for n in (13, 21, 36, 51, 66)
    ]
    assert sizes == sorted(sizes, reverse=True)
    assert len(set(sizes)) == len(sizes)


def test_thumbnail_word_font_size_keeps_shrinking_for_long_sentences():
    sizes = [
        frame_builder._thumbnail_word_font_size("a" * n, 1280)
        for n in (13, 21, 36, 51, 66)
    ]
    assert sizes == sorted(sizes, reverse=True)
    assert len(set(sizes)) == len(sizes)


def test_shrink_word_to_fit_evaluates_with_expected_args():
    # 実際のブラウザは起動せず、page.evaluate()に正しい引数(フレーム幅・
    # 高さ・最小フォントサイズ・縮小係数)が渡ることだけを確認する。
    page = MagicMock()

    frame_builder._shrink_word_to_fit(page, 1280, 720, min_font_size=50, shrink_factor=0.9)

    args, _ = page.evaluate.call_args
    js_code, eval_args = args
    assert "scrollWidth" in js_code
    assert "scrollHeight" in js_code
    assert eval_args == [1280, 720, 50, 0.9]


_VALID_PNG_BYTES = frame_builder._PNG_SIGNATURE + b"\x00" * frame_builder._THUMBNAIL_MIN_VALID_SIZE_BYTES


def test_is_valid_png_true_for_real_looking_png(tmp_path):
    path = tmp_path / "ok.png"
    path.write_bytes(_VALID_PNG_BYTES)
    assert frame_builder._is_valid_png(str(path)) is True


def test_is_valid_png_false_for_missing_file(tmp_path):
    assert frame_builder._is_valid_png(str(tmp_path / "missing.png")) is False


def test_is_valid_png_false_for_too_small_file(tmp_path):
    path = tmp_path / "tiny.png"
    path.write_bytes(frame_builder._PNG_SIGNATURE)  # シグネチャだけで中身が無い
    assert frame_builder._is_valid_png(str(path)) is False


def test_is_valid_png_false_for_wrong_signature(tmp_path):
    path = tmp_path / "notpng.png"
    path.write_bytes(b"not a png" + b"\x00" * frame_builder._THUMBNAIL_MIN_VALID_SIZE_BYTES)
    assert frame_builder._is_valid_png(str(path)) is False


def _mock_browser_with_screenshot_sequence(contents):
    """page.screenshot(path=...)が呼ばれるたびにcontentsを順番に書き込む
    モックbrowserを返す(壊れた画像→正常な画像、のような再試行シナリオの
    再現用)。"""
    contents_iter = iter(contents)

    def fake_screenshot(path):
        with open(path, "wb") as f:
            f.write(next(contents_iter))

    page = MagicMock()
    page.screenshot.side_effect = fake_screenshot
    browser = MagicMock()
    browser.new_page.return_value = page
    return browser, page


def test_build_thumbnail_retries_once_after_corrupt_screenshot(tmp_path, monkeypatch):
    browser, page = _mock_browser_with_screenshot_sequence([b"\x00" * 10, _VALID_PNG_BYTES])
    monkeypatch.setattr(frame_builder, "_get_browser", lambda: browser)

    out_path = tmp_path / "thumb.png"
    frame_builder.build_thumbnail("abc", str(out_path))

    assert page.screenshot.call_count == 2
    assert frame_builder._is_valid_png(str(out_path))
    # 一時HTMLファイルは成功後も残らない
    assert not os.path.exists(str(out_path) + ".html")


def test_build_thumbnail_succeeds_immediately_when_first_screenshot_is_valid(tmp_path, monkeypatch):
    browser, page = _mock_browser_with_screenshot_sequence([_VALID_PNG_BYTES])
    monkeypatch.setattr(frame_builder, "_get_browser", lambda: browser)

    frame_builder.build_thumbnail("abc", str(tmp_path / "thumb.png"))

    assert page.screenshot.call_count == 1


def test_build_thumbnail_raises_after_max_attempts_all_corrupt(tmp_path, monkeypatch):
    browser, page = _mock_browser_with_screenshot_sequence([b"\x00" * 10] * 3)
    monkeypatch.setattr(frame_builder, "_get_browser", lambda: browser)

    out_path = tmp_path / "thumb.png"
    with pytest.raises(RuntimeError):
        frame_builder.build_thumbnail("abc", str(out_path), max_attempts=3)

    assert page.screenshot.call_count == 3
    # 失敗してもHTMLの後片付けはされる(finally節)
    assert not os.path.exists(str(out_path) + ".html")
