"""
"How to Pronounce" フレーム画像生成。

PILの単一フォント描画だとZalgoの結合文字や記号ブロックが「豆腐(□)」に
なりやすいので、Chromium(Playwright)にHTMLを描かせてOSのフォント
フォールバック(fontconfig)に任せる。Noto系フォント一式が入っていれば
ほぼ全てのUnicodeブロックをカバーできる。
"""

import html
import os

from playwright.sync_api import sync_playwright

from config import CHROMIUM_PATH, FRAME_CSS_FONT_STACK, FRAME_SIZE, MODE_LABELS

# サムネイルとしての見栄えを優先し、「What」よりも肝心の単語そのものを
# どかんと大きく見せるレイアウト。"How to Pronounce" は上の小さいキッカー
# 扱いにして、単語をフレームの主役にしている。
# フォントサイズ等はすべて {width}/{height} を含むプレースホルダで渡し、
# build_frame() が横幅1280px基準からのスケール比で計算する(縦型Shorts
# サイズ(1080x1920)などフレーム幅が変わっても崩れないようにするため)。
FRAME_HTML_TEMPLATE = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:{width}px; height:{height}px; background:white;
         font-family: {font_stack};
         display:flex; flex-direction:column; align-items:center; justify-content:center; }}
  p.kicker {{ font-size:{kicker_font_size}px; font-weight:700; letter-spacing:4px; text-transform:uppercase;
              color:#333; margin:0 0 8px 0; }}
  h1.word {{ font-size:{word_font_size}px; font-weight:900; margin:{word_margin_top}px 30px; text-align:center;
             word-break:break-word; max-width:{word_max_width}px; line-height:1.05; color:black; }}
  p.sub {{ color:#777; font-size:{sub_font_size}px; margin-top:28px; }}
  .icon {{ margin-top:20px; }}
</style></head>
<body>
<p class="kicker">How to Pronounce</p>
<h1 class="word">{word}</h1>
<p class="sub">[{mode_label} / Unpronounceable word]</p>
<svg class="icon" width="{icon_size}" height="{icon_size}" viewBox="0 0 140 140">
  <polygon points="10,50 50,50 90,10 90,130 50,90 10,90" fill="black"/>
  <path d="M100,70 A30,30 0 0 0 100,30" stroke="black" stroke-width="6" fill="none"/>
  <path d="M100,95 A55,55 0 0 0 100,5" stroke="black" stroke-width="6" fill="none"/>
</svg>
</body></html>
"""

# 以下の基準値はすべて横幅1280px(旧デフォルトの16:9フレーム)を基準に
# 調整したもの。build_frame() でフレーム幅に応じて一律スケールする。
_BASELINE_WIDTH = 1280
_BASELINE_KICKER_FONT_SIZE = 36
_BASELINE_SUB_FONT_SIZE = 24
_BASELINE_ICON_SIZE = 90
_BASELINE_MAX_WIDTH_MARGIN = 80  # フレーム幅からこの分を引いたものが単語のmax-width
# 結合文字(Zalgoの見た目)は土台の文字の行の上へせり出して描画されるため、
# 詰めすぎるとキッカー("How to Pronounce")と衝突する。それを避けるための
# 単語上の余白(結合文字を含まない旧デザインの頃は margin-top:0 だった)。
_BASELINE_WORD_MARGIN_TOP = 130


def _word_font_size(word_label, width):
    """単語の長さに応じて「どかんと」感が出る最大サイズを選ぶ
    (フレーム幅からはみ出さない範囲で、短いほど大きく)"""
    n = len(word_label)
    if n <= 6:
        base = 220
    elif n <= 9:
        base = 180
    elif n <= 12:
        base = 150
    else:
        base = 120
    return round(base * width / _BASELINE_WIDTH)

_playwright_ctx = {"pw": None, "browser": None}


def _get_browser():
    if _playwright_ctx["browser"] is None:
        _playwright_ctx["pw"] = sync_playwright().start()
        # CHROMIUM_PATHは元の開発環境にだけ存在するブラウザの実体パス。
        # 他の環境(CI含む)には無いので、その場合はPlaywright自身が
        # 解決するデフォルトのバンドル済みChromiumにフォールバックする。
        executable_path = CHROMIUM_PATH if os.path.exists(CHROMIUM_PATH) else None
        _playwright_ctx["browser"] = _playwright_ctx["pw"].chromium.launch(
            executable_path=executable_path
        )
    return _playwright_ctx["browser"]


def close_browser():
    if _playwright_ctx["browser"] is not None:
        _playwright_ctx["browser"].close()
        _playwright_ctx["pw"].stop()
        _playwright_ctx["browser"] = None
        _playwright_ctx["pw"] = None


def build_frame(word_label, frame_path, mode="tts", size=FRAME_SIZE, display_word=None):
    """word_label: フォントサイズ算出の基準にする、結合文字を含まないラベル
    (word_generator.readable_label()の出力)。文字数がそのまま見た目の
    サイズに対応するので、サイジングは常にこちらの長さで行う。

    display_word: 実際に画面へ描画する文字列。結合文字(Zalgoの見た目)を
    保持した word_generator.zalgo_display_word() の出力を渡すことで、
    フレームに実際のZalgo感を出す。省略時は word_label をそのまま描画する
    (後方互換用)。"""
    display_word = word_label if display_word is None else display_word
    width, height = size
    scale = width / _BASELINE_WIDTH
    html_content = FRAME_HTML_TEMPLATE.format(
        font_stack=FRAME_CSS_FONT_STACK,
        word=html.escape(display_word),
        mode_label=MODE_LABELS.get(mode, mode),
        word_font_size=_word_font_size(word_label, width),
        width=width,
        height=height,
        word_max_width=width - _BASELINE_MAX_WIDTH_MARGIN,
        kicker_font_size=round(_BASELINE_KICKER_FONT_SIZE * scale),
        sub_font_size=round(_BASELINE_SUB_FONT_SIZE * scale),
        icon_size=round(_BASELINE_ICON_SIZE * scale),
        word_margin_top=round(_BASELINE_WORD_MARGIN_TOP * scale),
    )
    html_path = frame_path + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    browser = _get_browser()
    page = browser.new_page(viewport={"width": size[0], "height": size[1]})
    page.goto(f"file://{os.path.abspath(html_path)}")
    page.screenshot(path=frame_path)
    page.close()
    os.remove(html_path)
