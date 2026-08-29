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

FRAME_HTML_TEMPLATE = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:1280px; height:720px; background:white;
         font-family: {font_stack};
         display:flex; flex-direction:column; align-items:center; justify-content:flex-start; }}
  h1 {{ font-size:54px; font-weight:800; margin:60px 0 0 0; color:black; }}
  h2 {{ font-size:50px; font-weight:800; margin:20px 40px 0 40px; text-align:center;
        word-break:break-word; max-width:1150px; line-height:1.3; color:black; }}
  p.sub {{ color:#666; font-size:26px; margin-top:24px; }}
  .icon {{ margin-top:60px; }}
</style></head>
<body>
<h1>How to Pronounce</h1>
<h2>{word}</h2>
<p class="sub">[{mode_label} / 自動生成された発音不能ワード]</p>
<svg class="icon" width="140" height="140" viewBox="0 0 140 140">
  <polygon points="10,50 50,50 90,10 90,130 50,90 10,90" fill="black"/>
  <path d="M100,70 A30,30 0 0 0 100,30" stroke="black" stroke-width="6" fill="none"/>
  <path d="M100,95 A55,55 0 0 0 100,5" stroke="black" stroke-width="6" fill="none"/>
</svg>
</body></html>
"""

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
