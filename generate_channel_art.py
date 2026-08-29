#!/usr/bin/env python3
"""
YouTubeチャンネル用アセット(アイコン・バナー)の生成。

動画フレームと同じく、フォントの豆腐対策としてChromium(Playwright)で
HTMLを描画してスクリーンショットする方式を使う。

出力:
    assets/icon.png    800x800   チャンネルアイコン(YouTubeは円形にクロップ
                                  して表示するので、重要な要素は中央の円内に
                                  収めてある)
    assets/banner.png  2560x1440 チャンネルバナー。YouTubeの「セーフエリア」
                                  (どのデバイスでも見切れない中央1546x423の
                                  領域)にタイトル・タグラインを収めてある

使い方:
    python3 generate_channel_art.py
    python3 generate_channel_art.py --outdir ./assets
"""

import argparse
import os

from playwright.sync_api import sync_playwright

from config import CHROMIUM_PATH, FRAME_CSS_FONT_STACK

# ブランドカラー(動画フレームは白背景なので、チャンネル アイコン/バナーは
# サムネイル一覧やチャンネルページで目立つよう濃色ベースにしている)
BG_COLOR = "#101114"
ACCENT_COLOR = "#39FF88"  # 差し色(スピーカーの音波・アクセント文字)
FG_COLOR = "#FFFFFF"

ICON_SIZE = 800
BANNER_SIZE = (2560, 1440)
BANNER_SAFE_AREA = (1546, 423)  # YouTube公式の「どのデバイスでも見切れない」領域

# 背景に薄く散らす「発音不能っぽい」記号(config.DECORATIVE_SYMBOLSと同じ、
# 実測でフォント対応済みのものだけを使う)
from config import DECORATIVE_SYMBOLS  # noqa: E402

ICON_HTML = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:{size}px; height:{size}px; background:{bg};
         font-family: {font_stack};
         display:flex; align-items:center; justify-content:center; }}
  /* YouTubeはアイコンを円形にクロップして表示するため、要素は全て
     この正方形コンテナ(内接円の安全範囲)にまとめて中央寄せする */
  .mark {{ position:relative; width:560px; height:560px; }}
  .speaker {{ position:absolute; left:0; top:70px; }}
  .qmark {{ position:absolute; right:0; top:0; font-size:150px; font-weight:900;
            color:{accent}; line-height:1; transform:rotate(8deg); }}
</style></head>
<body>
<div class="mark">
  <svg class="speaker" width="380" height="380" viewBox="0 0 140 140">
    <polygon points="10,50 50,50 90,10 90,130 50,90 10,90" fill="{fg}"/>
    <path d="M100,70 A30,30 0 0 0 100,30" stroke="{accent}" stroke-width="9" fill="none" stroke-linecap="round"/>
    <path d="M100,95 A55,55 0 0 0 100,5" stroke="{accent}" stroke-width="9" fill="none" stroke-linecap="round"/>
  </svg>
  <div class="qmark">?!</div>
</div>
</body></html>
"""

BANNER_HTML = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:{w}px; height:{h}px; background:{bg};
         font-family: {font_stack}; position:relative; overflow:hidden; }}
  /* CSS Gridで隙間なく敷き詰める(flexのwrapだと最終行/最終列で余白が
     余って右端・下端が途切れて見えるためGridに変更) */
  .bg-symbols {{ position:absolute; inset:0; display:grid;
                 grid-template-columns: repeat(auto-fill, 130px);
                 grid-auto-rows: 130px; justify-content:center; align-content:center;
                 opacity:0.12; color:{fg}; font-size:54px; }}
  .bg-symbols span {{ display:flex; align-items:center; justify-content:center; }}
  /* セーフエリアの後ろだけ軽く暗くして、パターンと文字が被っても可読性を保つ */
  .scrim {{ position:absolute; left:{scrim_left}px; top:0; width:{scrim_w}px; height:100%;
            background: radial-gradient(ellipse at center, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 70%); }}
  .safe {{ position:absolute; left:{safe_left}px; top:{safe_top}px; width:{safe_w}px; height:{safe_h}px;
           display:flex; flex-direction:column; align-items:center; justify-content:center;
           text-align:center; }}
  .kicker {{ font-size:40px; font-weight:700; letter-spacing:6px; text-transform:uppercase; color:{accent}; margin:0; }}
  .title {{ font-size:110px; font-weight:900; color:{fg}; margin:14px 0 0 0; line-height:1; }}
  .tagline {{ font-size:32px; color:#B9BCC4; margin-top:22px; }}
</style></head>
<body>
<div class="bg-symbols">{bg_symbols}</div>
<div class="scrim"></div>
<div class="safe">
  <p class="kicker">Can You Say This?</p>
  <p class="title">How to Pronounce</p>
  <p class="tagline">A new unpronounceable word, every day.</p>
</div>
</body></html>
"""


def _render_html(html_content, size, out_path):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM_PATH)
        page = browser.new_page(viewport={"width": size[0], "height": size[1]})
        html_path = out_path + ".html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        page.goto(f"file://{os.path.abspath(html_path)}")
        page.screenshot(path=out_path)
        browser.close()
    os.remove(html_path)


def build_icon(out_path):
    html_content = ICON_HTML.format(
        size=ICON_SIZE, bg=BG_COLOR, fg=FG_COLOR, accent=ACCENT_COLOR,
        font_stack=FRAME_CSS_FONT_STACK,
    )
    _render_html(html_content, (ICON_SIZE, ICON_SIZE), out_path)


def build_banner(out_path):
    w, h = BANNER_SIZE
    safe_w, safe_h = BANNER_SAFE_AREA
    safe_left = (w - safe_w) // 2
    safe_top = (h - safe_h) // 2

    # グリッドセル(130px角)で全面を隙間なく埋めるのに十分な個数を用意する
    # (足りない分はタイルが途中で切れて見え、多い分はoverflow:hiddenで
    # 単純に切り捨てられるので、多めに用意する方が安全)
    cols = -(-w // 130)  # ceil
    rows = -(-h // 130)
    needed = cols * rows
    reps = -(-needed // len(DECORATIVE_SYMBOLS)) + 1
    symbols_list = (DECORATIVE_SYMBOLS * reps)[:needed]
    bg_symbols = "".join(f"<span>{s}</span>" for s in symbols_list)

    scrim_w = safe_w + 500
    scrim_left = (w - scrim_w) // 2

    html_content = BANNER_HTML.format(
        w=w, h=h, bg=BG_COLOR, fg=FG_COLOR, accent=ACCENT_COLOR,
        font_stack=FRAME_CSS_FONT_STACK,
        safe_left=safe_left, safe_top=safe_top, safe_w=safe_w, safe_h=safe_h,
        scrim_left=scrim_left, scrim_w=scrim_w,
        bg_symbols=bg_symbols,
    )
    _render_html(html_content, (w, h), out_path)


def main():
    ap = argparse.ArgumentParser(description="YouTubeチャンネル用アイコン・バナーの生成")
    ap.add_argument("--outdir", type=str, default="./assets", help="出力ディレクトリ")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    icon_path = os.path.join(args.outdir, "icon.png")
    banner_path = os.path.join(args.outdir, "banner.png")

    build_icon(icon_path)
    print(f"icon:   {icon_path} ({ICON_SIZE}x{ICON_SIZE})")

    build_banner(banner_path)
    print(f"banner: {banner_path} ({BANNER_SIZE[0]}x{BANNER_SIZE[1]}, "
          f"safe area {BANNER_SAFE_AREA[0]}x{BANNER_SAFE_AREA[1]})")


if __name__ == "__main__":
    main()
