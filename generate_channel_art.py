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
import html
import os
import random

from playwright.sync_api import sync_playwright

from config import CHROMIUM_PATH

# ブランドカラー(2026年11月、新しいチャンネルで作り直したときのデザイン)。
# サムネイル一覧の小さなアイコンでも目立つよう、濃い紫の背景に黄色の吹き出しを置く。
BG_COLOR = "#1A0B3B"
BG_COLOR_2 = "#3B1580"
ACCENT_COLOR = "#FFE14D"   # 吹き出し・タイトル(黄色)
ACCENT_COLOR_2 = "#FF3D7F"  # 差し色(ピンク)
FG_COLOR = "#FFFFFF"

ICON_SIZE = 800
BANNER_SIZE = (2560, 1440)
BANNER_SAFE_AREA = (1546, 423)  # YouTube公式の「どのデバイスでも見切れない」領域

# 読めそうで読めない単語(土台の文字に結合文字を重ねたもの)。動画と同じ雰囲気を出す
Z = "\u0337\u0353\u0300\u0352\u0315"
ICON_GLYPH = "A\u0337\u0353\u031a\u0352\u0316\u0300"
BANNER_WORD = "\u1e5b\u0336\u0356u\u0489O\u0334\u0326i\u0338\u0347\u0300e\u0335\u0352e\u0317\u0303"
BG_WORDS = ["Q\u0337\u0353\u0300", "x\u0489\u0348", "\u00d8\u0336\u0326", "\u0466\u0338",
            "z\u0334\u0331\u0352", "\u00df\u0335\u0300", "\u01b7\u0337\u0353", "\u0283\u0338\u0352",
            "?!", "\u0298", "\u0e51"]

ICON_HTML = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:{size}px; height:{size}px; overflow:hidden;
         background: radial-gradient(circle at 50% 40%, {bg2} 0%, {bg} 72%);
         font-family: 'Noto Sans', sans-serif; }}
  /* YouTubeはアイコンを円形にクロップするので、要素は中央の円(直径800)の内側に収める */
  .bubble {{ position:absolute; left:130px; top:150px; width:540px; height:420px;
             background:{accent}; border-radius:120px;
             box-shadow: 0 0 80px rgba(255,225,77,0.45); }}
  .tail {{ position:absolute; left:210px; top:530px; width:0; height:0;
           border-left:40px solid transparent; border-right:90px solid transparent;
           border-top:120px solid {accent}; transform:skewX(-18deg); }}
  .glyph {{ position:absolute; left:130px; top:150px; width:540px; height:420px;
            display:flex; align-items:center; justify-content:center;
            font-size:300px; font-weight:700; color:#1A0B3B; line-height:1; }}
  .q {{ position:absolute; right:150px; top:110px; font-size:150px; font-weight:700;
        color:{accent2}; transform:rotate(14deg);
        text-shadow: 0 0 6px #1A0B3B, 0 0 6px #1A0B3B, 0 8px 0 #1A0B3B; }}
</style></head><body>
  <div class="tail"></div><div class="bubble"></div>
  <div class="glyph">{glyph}</div>
  <div class="q">?!</div>
</body></html>
"""

BANNER_HTML = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:{w}px; height:{h}px; overflow:hidden;
         background: radial-gradient(ellipse at 50% 50%, {bg2} 0%, {bg} 65%);
         font-family: 'Noto Sans', sans-serif; }}
  .bg {{ position:absolute; color:rgba(255,255,255,0.07); font-weight:700; }}
  .safe {{ position:absolute; left:{safe_left}px; top:{safe_top}px; width:{safe_w}px; height:{safe_h}px;
           display:flex; flex-direction:column; align-items:center; justify-content:center; gap:14px; }}
  .title {{ font-size:150px; font-weight:700; color:{accent}; letter-spacing:4px; line-height:1;
            -webkit-text-stroke: 6px #12062B; paint-order: stroke fill;
            text-shadow: 0 10px 0 #12062B, 0 0 60px rgba(255,225,77,0.35); }}
  .row {{ display:flex; align-items:center; gap:30px; }}
  .word {{ background:#FFFFFF; color:#1A0B3B; font-size:60px; font-weight:700; padding:14px 40px 26px; line-height:1.2;
           border-radius:60px; }}
  .tag {{ font-size:46px; font-weight:700; color:#FFFFFF; }}
  .cta {{ background:{accent2}; color:#FFFFFF; font-size:36px; font-weight:700; letter-spacing:3px;
          padding:8px 34px; border-radius:40px; }}
</style></head><body>
  {bg_words}
  <div class="safe">
    <div class="title">CAN YOU SAY THIS?</div>
    <div class="row"><div class="word">{word}</div><div class="tag">Impossible words. Weird voices.</div></div>
    <div class="cta">TRY SAYING IT OUT LOUD</div>
  </div>
</body></html>
"""


def _scatter_words(w, h, count=70, seed=3):
    """背景に、読めない単語を薄く散らす(中央のセーフエリアは避ける)。"""
    rng = random.Random(seed)
    sw, sh = BANNER_SAFE_AREA
    x0, y0 = (w - sw) // 2 - 60, (h - sh) // 2 - 60
    spans = []
    while len(spans) < count:
        x, y = rng.randrange(0, w - 120), rng.randrange(0, h - 120)
        if x0 - 100 < x < x0 + sw + 120 and y0 - 80 < y < y0 + sh + 120:
            continue
        size = rng.randrange(60, 150)
        rot = rng.randrange(-25, 26)
        spans.append(f'<div class="bg" style="left:{x}px;top:{y}px;font-size:{size}px;'
                     f'transform:rotate({rot}deg)">{html.escape(rng.choice(BG_WORDS))}</div>')
    return "".join(spans)


def _get_browser(pw):
    # CHROMIUM_PATHは元の開発環境にだけ存在するブラウザの実体パス。
    # 他の環境には無いので、その場合はPlaywright自身が解決するデフォルトの
    # バンドル済みChromiumにフォールバックする。
    executable_path = CHROMIUM_PATH if os.path.isfile(CHROMIUM_PATH) else None
    return pw.chromium.launch(executable_path=executable_path)


def _render_html(html_content, size, out_path):
    with sync_playwright() as pw:
        browser = _get_browser(pw)
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
        size=ICON_SIZE, bg=BG_COLOR, bg2=BG_COLOR_2, accent=ACCENT_COLOR, accent2=ACCENT_COLOR_2,
        glyph=html.escape(ICON_GLYPH),
    )
    _render_html(html_content, (ICON_SIZE, ICON_SIZE), out_path)


def build_banner(out_path):
    w, h = BANNER_SIZE
    safe_w, safe_h = BANNER_SAFE_AREA
    html_content = BANNER_HTML.format(
        w=w, h=h, bg=BG_COLOR, bg2=BG_COLOR_2, accent=ACCENT_COLOR, accent2=ACCENT_COLOR_2,
        safe_left=(w - safe_w) // 2, safe_top=(h - safe_h) // 2, safe_w=safe_w, safe_h=safe_h,
        word=html.escape(BANNER_WORD), bg_words=_scatter_words(w, h),
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
