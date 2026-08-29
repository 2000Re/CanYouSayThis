"""
"How to Pronounce" フレーム画像生成。

PILの単一フォント描画だとZalgoの結合文字や記号ブロックが「豆腐(□)」に
なりやすいので、Chromium(Playwright同梱)にHTMLを描かせてOSのフォント
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
FRAME_HTML_TEMPLATE = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:1280px; height:720px; background:white;
         font-family: {font_stack};
         display:flex; flex-direction:column; align-items:center; justify-content:center; }}
  p.kicker {{ font-size:36px; font-weight:700; letter-spacing:4px; text-transform:uppercase;
              color:#333; margin:0 0 8px 0; }}
  h1.word {{ font-size:{word_font_size}px; font-weight:900; margin:0 30px; text-align:center;
             word-break:break-word; max-width:1200px; line-height:1.05; color:black; }}
  p.sub {{ color:#777; font-size:24px; margin-top:28px; }}
  .icon {{ margin-top:20px; }}
</style></head>
<body>
<p class="kicker">How to Pronounce</p>
<h1 class="word">{word}</h1>
<p class="sub">[{mode_label} / Unpronounceable word]</p>
<svg class="icon" width="90" height="90" viewBox="0 0 140 140">
  <polygon points="10,50 50,50 90,10 90,130 50,90 10,90" fill="black"/>
  <path d="M100,70 A30,30 0 0 0 100,30" stroke="black" stroke-width="6" fill="none"/>
  <path d="M100,95 A55,55 0 0 0 100,5" stroke="black" stroke-width="6" fill="none"/>
</svg>
</body></html>
"""


def _word_font_size(word_label):
    """単語の長さに応じて「どかんと」感が出る最大サイズを選ぶ
    (フレーム幅1280pxからはみ出さない範囲で、短いほど大きく)"""
    n = len(word_label)
    if n <= 6:
        return 220
    if n <= 9:
        return 180
    if n <= 12:
        return 150
    return 120

_playwright_ctx = {"pw": None, "browser": None}


def _get_browser():
    if _playwright_ctx["browser"] is None:
        _playwright_ctx["pw"] = sync_playwright().start()
        _playwright_ctx["browser"] = _playwright_ctx["pw"].chromium.launch(
            executable_path=CHROMIUM_PATH
        )
    return _playwright_ctx["browser"]


def close_browser():
    if _playwright_ctx["browser"] is not None:
        _playwright_ctx["browser"].close()
        _playwright_ctx["pw"].stop()
        _playwright_ctx["browser"] = None
        _playwright_ctx["pw"] = None


def build_frame(word_label, frame_path, mode="tts", size=FRAME_SIZE):
    html_content = FRAME_HTML_TEMPLATE.format(
        font_stack=FRAME_CSS_FONT_STACK,
        word=html.escape(word_label),
        mode_label=MODE_LABELS.get(mode, mode),
        word_font_size=_word_font_size(word_label),
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
