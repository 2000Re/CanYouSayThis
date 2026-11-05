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

from config import CHROMIUM_PATH

# ブランドカラー。旧チャンネルから使っている緑の「C」のアイコン(OAuth同意画面のロゴにも
# 登録済み)に合わせて、黒に近い背景と緑(#39FF88)でまとめる。
BG_COLOR = "#0B0D12"
BG_COLOR_2 = "#16301F"
ACCENT_COLOR = "#39FF88"   # メインの緑
ACCENT_COLOR_2 = "#1FCC66"  # 濃い緑(グラデーション・影)
FG_COLOR = "#FFFFFF"

ICON_SIZE = 800
BANNER_SIZE = (2560, 1440)
BANNER_SAFE_AREA = (1546, 423)  # YouTube公式の「どのデバイスでも見切れない」領域

# アイコン: 緑の円に大きな黒い「C」と「CAN YOU SAY THIS?」。
# YouTubeは円形に切り抜くので、緑の円を画面いっぱいにして、文字は円の内側に収める。
ICON_HTML = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:{size}px; height:{size}px; overflow:hidden; background:{bg};
         font-family: 'Noto Sans', sans-serif; }}
  .circle {{ position:absolute; left:0; top:0; width:{size}px; height:{size}px; border-radius:50%;
             background: radial-gradient(circle at 40% 32%, #6BFFAA 0%, {accent} 45%, {accent2} 100%); }}
  .c {{ position:absolute; left:0; top:70px; width:{size}px; text-align:center;
        font-size:440px; font-weight:700; line-height:1; color:#0B0D12;
        -webkit-text-stroke: 16px #0B0D12; }}
  .t {{ position:absolute; left:0; top:575px; width:{size}px; text-align:center;
        font-size:46px; font-weight:700; letter-spacing:2px; color:#0B0D12; }}
</style></head><body>
  <div class="circle"></div>
  <div class="c">C</div>
  <div class="t">CAN YOU SAY THIS?</div>
</body></html>
"""

BANNER_HTML = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:{w}px; height:{h}px; overflow:hidden;
         background: radial-gradient(ellipse at 50% 50%, {bg2} 0%, {bg} 62%);
         font-family: 'Noto Sans', sans-serif; }}
  .safe {{ position:absolute; left:{safe_left}px; top:{safe_top}px; width:{safe_w}px; height:{safe_h}px;
           display:flex; flex-direction:column; align-items:center; justify-content:center; gap:16px; }}
  .title {{ font-size:150px; font-weight:700; color:{accent}; letter-spacing:3px; line-height:1;
            text-shadow: 0 0 50px rgba(57,255,136,0.45); }}
  .tag {{ font-size:52px; font-weight:700; color:#FFFFFF; }}
  .cta {{ border:4px solid {accent}; color:{accent}; font-size:34px; font-weight:700; letter-spacing:4px;
          padding:6px 34px; border-radius:40px; }}
</style></head><body>
  <div class="safe">
    <div class="title">CAN YOU SAY THIS?</div>
    <div class="tag">Impossible words. Weird voices.</div>
    <div class="cta">TRY SAYING IT OUT LOUD</div>
  </div>
</body></html>
"""


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
    )
    _render_html(html_content, (ICON_SIZE, ICON_SIZE), out_path)


def build_banner(out_path):
    w, h = BANNER_SIZE
    safe_w, safe_h = BANNER_SAFE_AREA
    html_content = BANNER_HTML.format(
        w=w, h=h, bg=BG_COLOR, bg2=BG_COLOR_2, accent=ACCENT_COLOR, accent2=ACCENT_COLOR_2,
        safe_left=(w - safe_w) // 2, safe_top=(h - safe_h) // 2, safe_w=safe_w, safe_h=safe_h,
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
