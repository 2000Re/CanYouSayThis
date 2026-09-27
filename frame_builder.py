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

from config import CHROMIUM_PATH, FRAME_CSS_FONT_STACK, FRAME_SIZE, MODE_LABELS, THUMBNAIL_SIZE

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
<p class="sub">{sub_label}</p>
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

# "絵だけ"のミニマルなサムネイル画像用のテンプレート(build_thumbnail()参照)。
# FRAME_HTML_TEMPLATEと違い、キッカー("How to Pronounce")・サブラベル
# (モード/注記)・スピーカーアイコンは一切載せない。YouTube検索/一覧の
# サムネイルはタイトルテキストが横に別途表示されるため、サムネイル画像側に
# 同じ文言を重複させても却って窮屈になるだけ、という競合チャンネル
# (Sound Effect Master)の実例を踏まえた設計(README「ハマった罠」参照)。
THUMBNAIL_HTML_TEMPLATE = """
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:{width}px; height:{height}px; background:white;
         font-family: {font_stack};
         display:flex; align-items:center; justify-content:center; }}
  h1.word {{ font-size:{word_font_size}px; font-weight:900; margin:30px 40px 0; text-align:center;
             word-break:break-word; max-width:{word_max_width}px; line-height:1.05; color:black; }}
</style></head>
<body>
<h1 class="word">{word}</h1>
</body></html>
"""

_THUMBNAIL_MAX_WIDTH_MARGIN = 120  # フレーム幅からこの分を引いたものが単語のmax-width


def _sub_label(mode, is_native_script):
    """フレーム下部の小さいサブテキスト([Mode / ...])を組み立てる。

    is_native_script=True(ロシア語・タイ語・アラビア語・ヘブライ語のように
    実在の文字体系からランダムに文字を組み合わせて生成した回)の場合、
    「実在の単語ではない」旨を"Not a real word!"としてここに表示する。

    説明欄にも同じ趣旨の注記があるが(generate.py _youtube_metadata()の
    is_native_script分岐)、Shorts視聴者の多くは説明欄を開かないため、
    実際にその言語の話者から「発音が間違っている」という誤解のコメントが
    付いた(README「ハマった罠」参照)。動画フレーム自体は視聴時に必ず
    目に入るため、確実に伝わる側にも同じ注記を焼き込む。"""
    label = MODE_LABELS.get(mode, mode)
    note = "Not a real word!" if is_native_script else "Unpronounceable word"
    return f"[{label} / {note}]"


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


def _thumbnail_word_font_size(word_label, width):
    """サムネイル(絵だけ・キッカーやサブラベル無し)用のフォントサイズ。
    _word_font_size()と違い、競合する要素(キッカー・サブラベル・アイコン)
    が無く画面の全高を単語だけに使えるため、同じ文字数でも一回り大きくする。"""
    n = len(word_label)
    if n <= 6:
        base = 320
    elif n <= 9:
        base = 260
    elif n <= 12:
        base = 210
    else:
        base = 170
    return round(base * width / _BASELINE_WIDTH)

_playwright_ctx = {"pw": None, "browser": None}


def _get_browser():
    if _playwright_ctx["browser"] is None:
        pw = sync_playwright().start()
        try:
            # CHROMIUM_PATHは元の開発環境にだけ存在するブラウザの実体パス。
            # 他の環境(CI含む)には無いので、その場合はPlaywright自身が
            # 解決するデフォルトのバンドル済みChromiumにフォールバックする。
            executable_path = CHROMIUM_PATH if os.path.exists(CHROMIUM_PATH) else None
            browser = pw.chromium.launch(executable_path=executable_path)
        except Exception:
            # launch()が失敗すると、start()済みのドライバープロセスが
            # 誰にも参照されず残ってしまう(close_browser()はbrowserが
            # Noneの間は何もしないため)。ここで即座に後片付けしないと、
            # generate.pyが動画ごとの例外を握りつぶして次に進む作りのため、
            # 起動失敗のたびにプロセスがリークし続ける。
            pw.stop()
            raise
        _playwright_ctx["pw"] = pw
        _playwright_ctx["browser"] = browser
    return _playwright_ctx["browser"]


def close_browser():
    if _playwright_ctx["browser"] is not None:
        _playwright_ctx["browser"].close()
        _playwright_ctx["pw"].stop()
        _playwright_ctx["browser"] = None
        _playwright_ctx["pw"] = None


def build_frame(word_label, frame_path, mode="tts", size=FRAME_SIZE, display_word=None,
                 is_native_script=False):
    """word_label: フォントサイズ算出の基準にする、結合文字を含まないラベル
    (word_generator.readable_label()の出力)。文字数がそのまま見た目の
    サイズに対応するので、サイジングは常にこちらの長さで行う。

    display_word: 実際に画面へ描画する文字列。結合文字(Zalgoの見た目)を
    保持した word_generator.zalgo_display_word() の出力を渡すことで、
    フレームに実際のZalgo感を出す。省略時は word_label をそのまま描画する
    (後方互換用)。

    is_native_script: Trueの場合、フレーム下部のサブテキストに「実在の
    単語ではない」旨を表示する(_sub_label()参照)。"""
    display_word = word_label if display_word is None else display_word
    width, height = size
    scale = width / _BASELINE_WIDTH
    html_content = FRAME_HTML_TEMPLATE.format(
        font_stack=FRAME_CSS_FONT_STACK,
        word=html.escape(display_word),
        sub_label=html.escape(_sub_label(mode, is_native_script)),
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


def build_thumbnail(word_label, thumbnail_path, size=THUMBNAIL_SIZE, display_word=None):
    """"絵だけ"のミニマルなカスタムサムネイル画像を生成する(--upload時、
    config.CUSTOM_THUMBNAIL_ENABLED有効時にyoutube_upload.upload_thumbnail()
    へ渡す用)。

    build_frame()と違い、キッカー("How to Pronounce")・サブラベル(モード/
    注記)・スピーカーアイコンは一切載せない。単語(display_word)だけを
    画面いっぱいに大きく表示する。動画本体のフレーム(縦型Shorts用)とは
    完全に独立しており、videos.thumbnails().set()で動画本体の縦横比とは
    無関係に設定できるため、動画がShorts(9:16)のままでもこの16:9サムネイル
    を使える(README「ハマった罠」参照)。

    word_label/display_wordの意味はbuild_frame()と同じ(前者はフォント
    サイズ算出用、後者は実際に描画する文字列)。"""
    display_word = word_label if display_word is None else display_word
    width, height = size
    html_content = THUMBNAIL_HTML_TEMPLATE.format(
        font_stack=FRAME_CSS_FONT_STACK,
        word=html.escape(display_word),
        width=width,
        height=height,
        word_font_size=_thumbnail_word_font_size(word_label, width),
        word_max_width=width - _THUMBNAIL_MAX_WIDTH_MARGIN,
    )
    html_path = thumbnail_path + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    browser = _get_browser()
    page = browser.new_page(viewport={"width": width, "height": height})
    page.goto(f"file://{os.path.abspath(html_path)}")
    _shrink_word_to_fit(page, width, height)
    page.screenshot(path=thumbnail_path)
    page.close()
    os.remove(html_path)


def _shrink_word_to_fit(page, max_width, max_height, min_font_size=48, shrink_factor=0.92):
    """h1.wordの実際の描画結果がフレームからはみ出す場合、font-sizeを段階的に
    縮めてはみ出さなくなるまで繰り返す(ブラウザ上で実測して調整する)。

    _thumbnail_word_font_size()は文字数だけを見た見積もりで、ラテン文字を
    基準にしている。楔形文字・エジプト/アナトリア象形文字(config.
    PICTOGRAPH_SCRIPTS、README「ハマった罠」27番参照)は1文字あたりの幅・
    高さがラテン文字よりずっと大きく複雑なため、同じ文字数の見積もりでは
    フレームから大きくはみ出す(実機で確認済み。README「ハマった罠」参照)。
    文字数ベースの見積もりを文字体系ごとに作り分けるのではなく、実際に
    ブラウザで描画したサイズ(scrollWidth/scrollHeight)を見て縮める方式に
    することで、どんな文字体系が来ても安全に収まるようにしている。"""
    page.evaluate(
        """
        ([maxWidth, maxHeight, minFontSize, shrinkFactor]) => {
            const el = document.querySelector('h1.word');
            let size = parseFloat(getComputedStyle(el).fontSize);
            while (
                (el.scrollWidth > maxWidth || el.scrollHeight > maxHeight)
                && size > minFontSize
            ) {
                size = Math.max(size * shrinkFactor, minFontSize);
                el.style.fontSize = size + 'px';
            }
        }
        """,
        [max_width, max_height, min_font_size, shrink_factor],
    )
