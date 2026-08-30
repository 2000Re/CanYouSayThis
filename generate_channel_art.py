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

from config import CHROMIUM_PATH, FRAME_CSS_FONT_STACK

# ブランドカラー(動画フレームは白背景なので、チャンネル アイコン/バナーは
# サムネイル一覧やチャンネルページで目立つよう濃色ベースにしている)。
# BG_COLOR_2 はグラデーションの明るい側(中心)。ACCENT_COLOR_2 は
# ACCENT_COLORとのグラデーションでロゴ/タイトルに深みを出すための差し色。
BG_COLOR = "#0B0D12"
BG_COLOR_2 = "#1B2333"
ACCENT_COLOR = "#39FF88"   # メインアクセント
ACCENT_COLOR_2 = "#22D3EE"  # グラデーション用の差し色2(シアン)
FG_COLOR = "#FFFFFF"

ICON_SIZE = 800
BANNER_SIZE = (2560, 1440)
BANNER_SAFE_AREA = (1546, 423)  # YouTube公式の「どのデバイスでも見切れない」領域

# 背景に薄く散らす「発音不能っぽい」記号(config.DECORATIVE_SYMBOLSと同じ、
# 実測でフォント対応済みのものだけを使う)
from config import DECORATIVE_SYMBOLS  # noqa: E402

ICON_HTML = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:{size}px; height:{size}px;
         background: radial-gradient(circle at 50% 42%, {bg2} 0%, {bg} 70%);
         font-family: {font_stack};
         display:flex; align-items:center; justify-content:center; }}
  /* YouTubeはアイコンを円形にクロップして表示するため、要素は全て
     この正方形コンテナ(内接円の安全範囲)にまとめて中央寄せする */
  .stage {{ position:relative; width:{size}px; height:{size}px;
            display:flex; align-items:center; justify-content:center; }}
  .ring {{ position:absolute; top:50%; left:50%; width:680px; height:680px;
           margin:-340px 0 0 -340px; border-radius:50%;
           border:2px solid rgba(57,255,136,0.18); }}
  /* 動画本編と同じ「安全な結合文字」を積んだZalgo風の巨大な1文字。
     チャンネルの中身(発音不能な単語)そのものをアイコンの顔にしている。
     結合文字を積める高さにはブラウザ側の上限があるため、それだけでは
     地味になりがちなので、赤/青にずらした半透明コピーを重ねて色収差
     (デジタルに壊れた/グリッチした)風の見た目を追加している */
  .glyph-layer {{ position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
                  font-size:{glyph_size}px; font-weight:900; line-height:1; white-space:nowrap; }}
  .glyph-r {{ color:rgba(255,45,110,0.65); transform:translate(calc(-50% - 7px), calc(-50% + 3px)); filter: blur(0.6px); }}
  .glyph-b {{ color:rgba(45,180,255,0.65); transform:translate(calc(-50% + 7px), calc(-50% - 3px)); filter: blur(0.6px); }}
  .glyph {{ background: linear-gradient(160deg, {accent} 0%, {accent2} 100%);
            -webkit-background-clip:text; background-clip:text; color:transparent;
            filter: drop-shadow(0 0 46px rgba(57,255,136,0.45))
                    drop-shadow(0 0 90px rgba(34,211,238,0.25)); }}
</style></head>
<body>
<div class="stage">
  <div class="ring"></div>
  <div class="glyph-layer glyph-r">{glyph}</div>
  <div class="glyph-layer glyph-b">{glyph}</div>
  <div class="glyph-layer glyph">{glyph}</div>
</div>
</body></html>
"""

BANNER_HTML = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:{w}px; height:{h}px;
         background: radial-gradient(ellipse at 50% 40%, {bg2} 0%, {bg} 65%);
         font-family: {font_stack}; position:relative; overflow:hidden; }}
  /* 記号はPython側でランダムな位置・サイズ・不透明度・回転を計算し、
     individual spanのinline styleとして埋め込む(CSS Gridの均一な
     タイル敷きだと壁紙のような単調さが出るため、ばらけた配置にしている) */
  .bg-symbols {{ position:absolute; inset:0; overflow:hidden; }}
  .bg-symbols span {{ position:absolute; color:{fg}; }}
  /* 上下の縁をわずかに暗くして奥行きを出す */
  .vignette {{ position:absolute; inset:0;
               background: linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0) 20%,
                                            rgba(0,0,0,0) 80%, rgba(0,0,0,0.35) 100%); }}
  /* セーフエリアの後ろだけ軽く暗くして、パターンと文字が被っても可読性を保つ */
  .scrim {{ position:absolute; left:{scrim_left}px; top:0; width:{scrim_w}px; height:100%;
            background: radial-gradient(ellipse at center, rgba(0,0,0,0.65) 0%,
                                         rgba(0,0,0,0.15) 55%, rgba(0,0,0,0) 78%); }}
  .safe {{ position:absolute; left:{safe_left}px; top:{safe_top}px; width:{safe_w}px; height:{safe_h}px;
           display:flex; flex-direction:column; align-items:center; justify-content:center;
           text-align:center; }}
  .kicker-row {{ display:flex; align-items:center; gap:18px; }}
  .kicker-bar {{ width:44px; height:4px; border-radius:2px;
                 background: linear-gradient(90deg, {accent} 0%, {accent2} 100%); }}
  .kicker {{ font-size:40px; font-weight:700; letter-spacing:6px; text-transform:uppercase;
             color:{accent}; margin:0; white-space:nowrap; }}
  .title {{ font-size:110px; font-weight:900; margin:14px 0 0 0; line-height:1;
            background: linear-gradient(135deg, {fg} 0%, {fg} 55%, {accent2} 100%);
            -webkit-background-clip:text; background-clip:text; color:transparent;
            text-shadow: 0 0 46px rgba(57,255,136,0.25); }}
  .divider {{ width:220px; height:3px; margin:28px auto 0; border-radius:2px;
              background: linear-gradient(90deg, transparent, {accent2}, transparent); }}
  .tagline {{ font-size:32px; color:#B9BCC4; margin-top:26px; letter-spacing:1px; }}
</style></head>
<body>
<div class="bg-symbols">{bg_symbols}</div>
<div class="vignette"></div>
<div class="scrim"></div>
<div class="safe">
  <div class="kicker-row">
    <span class="kicker-bar"></span>
    <p class="kicker">Can You Say This?</p>
    <span class="kicker-bar"></span>
  </div>
  <p class="title">How to Pronounce</p>
  <div class="divider"></div>
  <p class="tagline">A new unpronounceable word, every day.</p>
</div>
</body></html>
"""


# チャンネルアイコンは動画と違って「毎回違う見た目」だと困るため、ランダム
# 選択ではなく、上方向・下方向のマークを手動でキュレーションして組み合わせて
# いる(ランダムだと同じ位置に重なるマークばかり選ばれ、間延びした見た目に
# なりがちなため)。いずれもCombining Diacritical Marksブロック(U+0300-036F)。
# 他のブロック(結合文字シンボル用など)は矢印や図形のような見た目のものが
# 混ざり、1文字を巨大に見せるアイコン用途には向かないため使っていない。
_ICON_GLYPH_BASE = "A"
# 同じマークを繰り返しても(フォント側が重複をほぼ同位置にまとめてしまうため)
# タワー感は出ない。積み重なった高さを出すには「種類の異なる」マークを
# 複数使う必要がある。マークのタワーの高さはフォントサイズに比例して伸びる
# ので、glyph_size(ICON_HTML側)と合わせてキャンバス内に収まるよう調整済み。
_ICON_GLYPH_ABOVE = [0x0300, 0x0301, 0x0303, 0x030C]
_ICON_GLYPH_BELOW = [0x0316, 0x031E, 0x032D]
_ICON_GLYPH_MARKS = _ICON_GLYPH_ABOVE + _ICON_GLYPH_BELOW


def _icon_glyph():
    """手動で選んだ結合文字を1つの土台文字に積んだ、Zalgo風の巨大な
    アイコン用グリフを作る。"""
    return _ICON_GLYPH_BASE + "".join(chr(cp) for cp in _ICON_GLYPH_MARKS)


def _scatter_symbols(count=140):
    """記号をランダムな位置・サイズ・不透明度・回転で散らした<span>群を作る。
    均一グリッドで敷き詰めるより「壁紙感」が薄れ、星座のような疎らな見た目になる。"""
    spans = []
    for _ in range(count):
        sym = random.choice(DECORATIVE_SYMBOLS)
        left = random.uniform(0, 100)
        top = random.uniform(0, 100)
        size = random.randint(26, 60)
        opacity = round(random.uniform(0.05, 0.16), 2)
        rotate = random.randint(-25, 25)
        spans.append(
            f'<span style="left:{left:.2f}%; top:{top:.2f}%; font-size:{size}px; '
            f'opacity:{opacity}; transform:translate(-50%,-50%) rotate({rotate}deg);">{sym}</span>'
        )
    return "".join(spans)


def _get_browser(pw):
    # CHROMIUM_PATHは元の開発環境にだけ存在するブラウザの実体パス。
    # 他の環境には無いので、その場合はPlaywright自身が解決するデフォルトの
    # バンドル済みChromiumにフォールバックする。
    executable_path = CHROMIUM_PATH if os.path.exists(CHROMIUM_PATH) else None
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
        size=ICON_SIZE, bg=BG_COLOR, bg2=BG_COLOR_2, fg=FG_COLOR,
        accent=ACCENT_COLOR, accent2=ACCENT_COLOR_2,
        glyph_size=215, glyph=html.escape(_icon_glyph()),
        font_stack=FRAME_CSS_FONT_STACK,
    )
    _render_html(html_content, (ICON_SIZE, ICON_SIZE), out_path)


def build_banner(out_path):
    w, h = BANNER_SIZE
    safe_w, safe_h = BANNER_SAFE_AREA
    safe_left = (w - safe_w) // 2
    safe_top = (h - safe_h) // 2

    bg_symbols = _scatter_symbols()

    scrim_w = safe_w + 500
    scrim_left = (w - scrim_w) // 2

    html_content = BANNER_HTML.format(
        w=w, h=h, bg=BG_COLOR, bg2=BG_COLOR_2, fg=FG_COLOR,
        accent=ACCENT_COLOR, accent2=ACCENT_COLOR_2,
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
