"""
全モジュール共通の設定・定数。

ここに定義している値(特に SAFE_COMBINING_BLOCKS と DECORATIVE_SYMBOLS)は
「espeak-ng に実際に1文字ずつ読ませて無音になることを確認した」実測結果で
あり、当てずっぽうのUnicodeブロック指定ではない。詳しくは README.md の
「ハマった罠」の節を参照。
"""

# --- 動画共通設定 -----------------------------------------------------------

CHROMIUM_PATH = "/opt/pw-browsers/chromium"  # Playwright同梱のChromium
FRAME_SIZE = (1080, 1920)  # YouTube Shorts / TikTok / Reels向けの縦型9:16

# 動画フレームに表示するラベル(海外視聴者向けなので英語表記に統一)
MODE_LABELS = {
    "tts": "Text-to-Speech",
    "glitch": "Synthesized Glitch Audio",
}

# --- 単語ジェネレータ設定 ----------------------------------------------------

# 土台になる文字(TTSが実際に音を出す部分。母音を中心にした「本物の文字」だけ
# にする。括弧やコロンのような記号を土台にすると、espeak-ngは重ねた結合文字
# を「アキュート」のように名前で読み上げてしまい、単語というより説明文にな
# ってしまうため NG)
BASE_CHARS = list("aeiouAEIOU") + list("vVvvOoOo") + list("nmrl")

# 単語の区切りとして飾り的に挟む記号(結合文字は乗せず単体で使う)
SEPARATOR_SYMBOLS = ["(", ")", ":", "-"]

# 積み重ねる結合文字の候補。
#
# 重要な罠が2つあった:
#   (1) 「Combining Diacritical Marksのブロックだから安全」という判断は誤り。
#       同じブロック内でもヘブライ語の母音記号(U+05B0-U+05BD)などは
#       espeak-ngが "Hebrew A" のように律儀に読み上げてしまう。
#   (2) 個々のコードポイントが無音確認済みでも、"異なるブロックの結合文字"
#       を同じ1文字の上に混ぜて乗せると、espeak-ngが一部のマークを
#       「載せ忘れた」扱いにして単独の記号として読み上げてしまうことがある
#       (例: acute accentを名指しで読み上げる)。同じブロック内のマーク同士
#       なら何個重ねても無音のままなのを確認済み。
#
# そのため、(a) 実際にespeak-ngへ1文字ずつ通して無音を個別確認したコード
# ポイントのみを候補にし、(b) 1つの土台文字に乗せるマークは必ず「同じブロ
# ックの中だけ」から選ぶ、という2段構えにしている。
# U+20D0-20F0の中でも「土台の文字を覆い隠す大きな図形」として描画される
# ENCLOSING系(丸・四角・ひし形・スクリーン・キーキャップ・三角)のコード
# ポイント。詳細は SAFE_COMBINING_BLOCKS のコメント参照。
_ENCLOSING_COMBINING_MARKS = {0x20DD, 0x20DE, 0x20DF, 0x20E0, 0x20E2, 0x20E3, 0x20E4}

SAFE_COMBINING_BLOCKS = [
    list(range(0x0300, 0x0370)),  # Combining Diacritical Marks
    list(range(0x0483, 0x048A)),  # Cyrillic combining
    list(range(0x0591, 0x05B0)),  # Hebrew accents(母音記号 05B0-05BDは除外済み)
    list(range(0x1DC0, 0x1DE7)) + list(range(0x1DF5, 0x1E00)),  # Combining Diacritical Marks Supplement
    # Combining Diacritical Marks for Symbols。
    # 0x20F1以降はUnicode未割り当てでフォントが無く「豆腐」になるため除外。
    # さらに「ENCLOSING(囲み)」系(丸・四角・ひし形・キーキャップ・三角など)
    # は土台の文字を覆い隠す大きな図形として描画され、小さな飾りが重なる
    # Zalgo的な見た目ではなく「表示崩れ」に見えてしまうため除外している。
    [cp for cp in range(0x20D0, 0x20F1) if cp not in _ENCLOSING_COMBINING_MARKS],
]

# 装飾記号。実際にespeak-ngへ1文字ずつ通し、「何も読み上げない(無音)」こと
# を確認済みの文字だけを採用。ここに含めなかった文字(例: ꐑ ྀ ๅ ๆ ั ඕ ළ ؖ
# ৣ ৢ ꙰ ꙮ など)は、espeak-ngがブロック名や文字名を律儀に読み上げてしまい
# 「発音」ではなく「解説」になってしまうため意図的に除外している。
DECORATIVE_SYMBOLS = list("☼✧◉❁❍⊁⊀◞◟๑٭؞֍֎")

# フレーム画像(HTML)で使うフォントスタック。Zalgoの結合文字や記号ブロックは
# 1つのフォントに全部入っていないことが多いので、複数のNoto系フォントを並べ
# てブラウザのfontconfigフォールバックに解決を任せる。
FRAME_CSS_FONT_STACK = (
    "'Noto Sans','Noto Sans CJK JP','Noto Sans Symbols','Noto Sans Symbols2',"
    "'Noto Sans Thai','Noto Sans Devanagari','Noto Sans Hebrew','Noto Sans Arabic',"
    "'Noto Sans Bengali','Noto Sans Sinhala','Noto Sans Tibetan','Noto Sans Yi',"
    "'Noto Sans Cherokee','Noto Sans Mongolian','DejaVu Sans',sans-serif"
)

# --- デフォルトのCLIパラメータ -----------------------------------------------

DEFAULT_MODE = "tts"
DEFAULT_VOICE = "en"
DEFAULT_SPEED = 150
DEFAULT_UNIT_DURATION = 2.0   # [glitchモード] 「答え」1回分の長さ(秒)
DEFAULT_REPEAT = 2            # 「答え」を何回繰り返すか
DEFAULT_REPEAT_GAP = 0.4      # 繰り返し間の無音の長さ(秒)
DEFAULT_FADE = 0.4            # 末尾のフェードアウトの長さ(秒)
