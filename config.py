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

# 動画フレームに表示するラベル(海外視聴者向けなので英語表記に統一)。
# --mode randomはこのdictのキーからランダムに1つ選ぶため(generate.py
# _resolve_mode()参照)、新しいモードを追加する場合はここに登録すれば
# 自動的にrandomの抽選対象にも入る。
MODE_LABELS = {
    "tts": "Text-to-Speech",
    "glitch": "Synthesized Glitch Audio",
    "tts_extreme": "Distorted Text-to-Speech",
    "morse": "Morse Code",
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
#
# (3) 上記2つは音声(espeak-ng)側の罠だが、表示側にも罠があった。
#     Combining Diacritical Marks for Symbols(U+20D0-U+20F0)は音声的には
#     無音確認済みでも、Chromium+Notoフォントで実際に土台文字へ結合させて
#     描画すると軒並み豆腐(□)になり、正しく結合しない(ENCLOSING系を除外
#     した残りの約26種で確認済み)。動画フレームは長らく readable_label()
#     (結合文字を全部落とした簡易ラベル)しか表示しておらず、この問題が
#     隠れて気づかれていなかった。フレームに実際の結合文字を描画する
#     ようになったタイミングで発覚したため、このブロック自体を候補から
#     除外している。
#
# (4) 残った4ブロック(計200コードポイント)についても、Playwrightで実際に
#     「土台文字+マーク」の描画幅を「土台文字単体」と比較する形で全数検証
#     したところ、U+1DFA(COMBINING DOT BELOW LEFT)だけが結合できない
#     (土台文字1文字ぶんまるごと幅が伸びる=豆腐/非結合)ことが判明した。
#     ブロックの残り99%は正常なので、ブロックごと除外するのではなくこの
#     1点だけを除外している。
_BROKEN_RENDERING_MARKS = {0x1DFA}

SAFE_COMBINING_BLOCKS = [
    list(range(0x0300, 0x0370)),  # Combining Diacritical Marks
    list(range(0x0483, 0x048A)),  # Cyrillic combining
    list(range(0x0591, 0x05B0)),  # Hebrew accents(母音記号 05B0-05BDは除外済み)
    # Combining Diacritical Marks Supplement(U+1DFAのみ描画不良のため除外)
    [cp for cp in list(range(0x1DC0, 0x1DE7)) + list(range(0x1DF5, 0x1E00))
     if cp not in _BROKEN_RENDERING_MARKS],
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

# --- YouTubeアップロード履歴 -------------------------------------------------

UPLOAD_HISTORY_PATH = "upload_history.json"  # generate.py --upload の成功履歴

# --- compile_shorts.py: Shorts結合動画 ---------------------------------------
#
# Shorts(縦型9:16、3分以内)は本数を連結しても合計尺が短いままだと縦型ゆえに
# YouTubeにShorts判定されてしまう(判定は投稿者の意図ではなく、アスペクト比
# +尺のみで決まる仕様のため)。そのため結合時は各クリップを横型(16:9)
# キャンバスにピラーボックス(左右に無地の帯)で配置し直し、確実に「通常動画」
# として扱われるようにする。

COMPILATION_STATE_PATH = "compilation_state.json"
COMPILATION_BATCH_SIZE = 10  # この件数たまるごとに結合動画を1本作る
COMPILATION_DOWNLOAD_DIR = "compilation_downloads"
COMPILATION_OUTPUT_DIR = "compilation_output"
COMPILATION_VIDEO_WIDTH = 1920
COMPILATION_VIDEO_HEIGHT = 1080
COMPILATION_BG_COLOR = (11, 13, 18)  # generate_channel_art.BG_COLOR(#0B0D12)と統一
# GitHub ActionsのIPがYouTube側に「Sign in to confirm you're not a bot」で
# ボット判定される問題(player_client変更・cookie認証のいずれでも解決しない)
# を根本的に回避するため、動画本体はYouTubeからyt-dlpで再ダウンロードせず、
# generate.pyが生成した時点でGitHub Actionsアーティファクトとして保存済みの
# ものをGitHub Actions APIから取得する方式にしている(README「ハマった罠」の
# 8番を参照)。
#
# アーティファクトの取得先(該当runのID)が見つからない/保持期限切れ等の
# 「恒久的に取得不可能」なケースと、一時的なネットワーク不調を区別するための
# リトライ回数。前者はcompilation_state.jsonのskipped_video_idsに記録し、
# 結合対象から永久に除外する(次回以降取得を再試行しない)。
COMPILATION_DOWNLOAD_MAX_RETRIES = 2
COMPILATION_DOWNLOAD_RETRY_BACKOFF_SECONDS = 5
COMPILATION_GITHUB_API_TIMEOUT_SECONDS = 20
# GitHub Actionsアーティファクトのデフォルト保持期間は90日(組織/リポジトリの
# 設定で変更されていなければ)。COMPILATION_BATCH_SIZE(10件)たまるまでの
# 実運用上の日数は十分この範囲に収まる想定。
COMPILATION_ARTIFACT_NAME = "generated-videos"

# --- YouTube Data API クォータ ------------------------------------------------
#
# youtube_upload.py / compile_shorts.py の両方から参照し、実行ログに
# 「今回の実行でどれだけ消費し、残りがどれくらいか」を概算表示するために使う。
DAILY_QUOTA_UNITS = 10000  # 日次クォータの目安(GCPコンソールのデフォルト)
DAILY_UPLOAD_LIMIT = 100   # videos.insertとは別枠の「1日あたりの動画投稿数」上限

# --- YouTubeリフレッシュトークンの有効期限監視 --------------------------------
#
# OAuth同意画面の公開ステータスが「テスト」のままだと、リフレッシュトークンは
# 発行から7日で失効する(スコープにname/email/profile以外を含むアプリのため)。
# get_youtube_refresh_token.py実行時の日付を任意のSecret
# (YOUTUBE_REFRESH_TOKEN_ISSUED_AT)として登録しておくと、
# youtube_upload.get_youtube_client() がこの日数を目安に警告を出す。
TOKEN_EXPIRY_DAYS = 7          # テストステータスでの既知の失効日数
TOKEN_WARNING_AFTER_DAYS = 5   # この日数を過ぎたら「そろそろ」の警告を出す
