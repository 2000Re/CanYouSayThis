"""
全モジュール共通の設定・定数。

ここに定義している値(特に SAFE_COMBINING_BLOCKS と DECORATIVE_SYMBOLS)は
「espeak-ng に実際に1文字ずつ読ませて無音になることを確認した」実測結果で
あり、当てずっぽうのUnicodeブロック指定ではない。詳しくは README.md の
「ハマった罠」の節を参照。
"""

import unicodedata

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
}

# --voice random が「実在の文字体系」の言語を選んだ場合、単語自体をその
# 言語の文字からランダムに組み立てる(word_generator.random_script_word() /
# random_abugida_word())。BASE_CHARSを流用したZalgo単語と違い、装飾記号・
# Zalgoの結合文字(いずれも英語音声での無音確認しか取れていない)は使わず、
# 実機でChromium+Notoフォントによる描画とespeak-ngでの音声合成の両方が
# 正常に動くことを確認済みの言語のみ対応している。
RUSSIAN_LETTERS = list("абвгдежзийклмнопрстуфхцчшщъыьэюя")
GEORGIAN_LETTERS = list("აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰ")


def _assigned_chars(ranges):
    """Unicodeのコードポイント範囲(閉区間のタプルのリスト)から、未割り当て
    (unicodedata.category() == 'Cn')のコードポイントを除いた文字のリストを
    作る。手打ちで文字を列挙するのが非現実的な言語(文字数が多い/範囲が
    広い)向け。未割り当てコードポイントはフォントが対応しておらず「豆腐」の
    原因になるため、SAFE_COMBINING_BLOCKSと同じ理由で除外している。"""
    out = []
    for start, end in ranges:
        for cp in range(start, end + 1):
            if unicodedata.category(chr(cp)) != "Cn":
                out.append(chr(cp))
    return out


# タイ文字・ミャンマー文字・シンハラ文字・タミル文字・テルグ文字・ベンガル
# 文字は、子音字+母音記号(前後左右に付く、単体では使わない)で音節を作る
# 「アブギダ」と呼ばれる文字体系なので、子音・母音記号を別々のリストに分けて
# いる(word_generator.random_abugida_word()参照)。
THAI_CONSONANTS = list("กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ")
THAI_VOWEL_MARKS = list("ะาิีึืุูเแโใไ")

# アラビア文字・ヘブライ文字・アルメニア文字・アムハラ文字(エチオピア)・
# チェロキー文字は、母音記号が任意(アラビア語・ヘブライ語)だったり、文字
# 自体が既に完結した音節(アムハラ文字・チェロキー文字)だったりするため、
# random_script_word()(文字をランダムに並べるだけ、同じ文字の連打あり)で
# 十分自然な見た目になる。
ARABIC_LETTERS = _assigned_chars([(0x0621, 0x064A)])
HEBREW_LETTERS = _assigned_chars([(0x05D0, 0x05EA)])
ARMENIAN_LETTERS = _assigned_chars([(0x0561, 0x0586)])
AMHARIC_SYLLABLES = _assigned_chars(
    [(0x1200, 0x1248), (0x1250, 0x1256), (0x1260, 0x1288), (0x1290, 0x12B0), (0x12C0, 0x12C0)]
)
CHEROKEE_SYLLABLES = _assigned_chars([(0x13A0, 0x13F5)])

# ミャンマー文字・シンハラ文字・タミル文字・テルグ文字・ベンガル文字も
# タイ文字と同じアブギダ(子音字+母音記号)なので、子音・母音記号を分けて
# 定義する。
MYANMAR_CONSONANTS = _assigned_chars([(0x1000, 0x1020)])
MYANMAR_VOWEL_MARKS = _assigned_chars([(0x102B, 0x1030), (0x1032, 0x1037)])
SINHALA_CONSONANTS = _assigned_chars([(0x0D9A, 0x0DC6)])
SINHALA_VOWEL_MARKS = _assigned_chars([(0x0DCF, 0x0DDF)])
TAMIL_CONSONANTS = _assigned_chars([(0x0B95, 0x0BB9)])
TAMIL_VOWEL_MARKS = _assigned_chars([(0x0BBE, 0x0BCD)])
TELUGU_CONSONANTS = _assigned_chars([(0x0C15, 0x0C39)])
TELUGU_VOWEL_MARKS = _assigned_chars([(0x0C3E, 0x0C4C)])
BENGALI_CONSONANTS = _assigned_chars([(0x0995, 0x09B9)])
BENGALI_VOWEL_MARKS = _assigned_chars([(0x09BE, 0x09CC)])

# --voice random(generate.py _resolve_voice()参照)が抽選する言語/性別の
# 候補。単語自体は母音中心のBASE_CHARSしか使わないので、言語ごとの発音規則の
# 違い(鼻母音・声調・アクセントなど)で聞こえ方が変わることを狙った機能。
#
# "female"は実機でespeak-ng(MBROLAエンジン)による音声合成が実際に成功する
# ことを確認できた言語のみ設定しており、それ以外はNone(male音声のみ抽選)。
# 除外理由:
#   - 中国語(zh): Debianのmbrola-cn1パッケージが同梱するespeak-ng用ボイス
#     定義が、存在しない音素変換ファイル(zh_phtrans。実際に存在するのは
#     cmn_phtrans)を参照しており、"voice does not exist"エラーで合成に
#     失敗する(パッケージ自体の不具合。実機で検証済み)。
#   - 広東語(yue)・フィンランド語(fi)・ベトナム語(vi)・ロシア語(ru)・
#     ジョージア語(ka)・タイ語(th): これらの言語に対応するMBROLA音声
#     データが存在しない(`apt-cache search mbrola`で該当なしを確認済み)。
#   - アイスランド語(is): MBROLA音声(ic1)はあるが男性のみで、女性音声は
#     存在しない。
#
# "script"は実在の文字体系を使う言語にのみ設定する(generate.py
# _native_script_for_voice()参照)。
#   - "cluster": random_script_word()に"chars"を渡す(文字をランダムに
#     並べるだけで自然な見た目になる文字体系向け)。
#   - "abugida": random_abugida_word()に"consonants"/"vowels"を渡す
#     (子音字+母音記号で音節を作る文字体系向け)。
# いずれも未設定(None)の言語は従来通りBASE_CHARSベースのZalgo単語を使う。
#
# GitHub Actions側では、maleのespeak-ngボイスコードは追加パッケージ無しで
# 動くが、femaleが設定されている言語のみ対応するmbrola-*パッケージの
# インストールが別途必要(generate.yml参照)。
VOICE_LANGUAGES = {
    "en":  {"label": "English",    "male": "en",    "female": "mb-us1", "script": None, "chars": None, "consonants": None, "vowels": None},
    "fr":  {"label": "French",     "male": "fr-fr", "female": "mb-fr4", "script": None, "chars": None, "consonants": None, "vowels": None},
    "de":  {"label": "German",     "male": "de",    "female": "mb-de1", "script": None, "chars": None, "consonants": None, "vowels": None},
    "hu":  {"label": "Hungarian",  "male": "hu",    "female": "mb-hu1", "script": None, "chars": None, "consonants": None, "vowels": None},
    "sv":  {"label": "Swedish",    "male": "sv",    "female": "mb-sw2", "script": None, "chars": None, "consonants": None, "vowels": None},
    "zh":  {"label": "Mandarin",   "male": "zh",    "female": None, "script": None, "chars": None, "consonants": None, "vowels": None},
    "yue": {"label": "Cantonese",  "male": "yue",   "female": None, "script": None, "chars": None, "consonants": None, "vowels": None},
    "fi":  {"label": "Finnish",    "male": "fi",    "female": None, "script": None, "chars": None, "consonants": None, "vowels": None},
    "is":  {"label": "Icelandic",  "male": "is",    "female": None, "script": None, "chars": None, "consonants": None, "vowels": None},
    "vi":  {"label": "Vietnamese", "male": "vi",    "female": None, "script": None, "chars": None, "consonants": None, "vowels": None},
    "ru":  {"label": "Russian",    "male": "ru",    "female": None, "script": "cluster", "chars": RUSSIAN_LETTERS, "consonants": None, "vowels": None},
    "ka":  {"label": "Georgian",   "male": "ka",    "female": None, "script": "cluster", "chars": GEORGIAN_LETTERS, "consonants": None, "vowels": None},
    "th":  {"label": "Thai",       "male": "th",    "female": None, "script": "abugida", "chars": None, "consonants": THAI_CONSONANTS, "vowels": THAI_VOWEL_MARKS},
    "ar":  {"label": "Arabic",     "male": "ar",    "female": None, "script": "cluster", "chars": ARABIC_LETTERS, "consonants": None, "vowels": None},
    "he":  {"label": "Hebrew",     "male": "he",    "female": None, "script": "cluster", "chars": HEBREW_LETTERS, "consonants": None, "vowels": None},
    "hy":  {"label": "Armenian",   "male": "hy",    "female": None, "script": "cluster", "chars": ARMENIAN_LETTERS, "consonants": None, "vowels": None},
    "am":  {"label": "Amharic",    "male": "am",    "female": None, "script": "cluster", "chars": AMHARIC_SYLLABLES, "consonants": None, "vowels": None},
    "chr": {"label": "Cherokee",   "male": "chr",   "female": None, "script": "cluster", "chars": CHEROKEE_SYLLABLES, "consonants": None, "vowels": None},
    "my":  {"label": "Myanmar",    "male": "my",    "female": None, "script": "abugida", "chars": None, "consonants": MYANMAR_CONSONANTS, "vowels": MYANMAR_VOWEL_MARKS},
    "si":  {"label": "Sinhala",    "male": "si",    "female": None, "script": "abugida", "chars": None, "consonants": SINHALA_CONSONANTS, "vowels": SINHALA_VOWEL_MARKS},
    "ta":  {"label": "Tamil",      "male": "ta",    "female": None, "script": "abugida", "chars": None, "consonants": TAMIL_CONSONANTS, "vowels": TAMIL_VOWEL_MARKS},
    "te":  {"label": "Telugu",     "male": "te",    "female": None, "script": "abugida", "chars": None, "consonants": TELUGU_CONSONANTS, "vowels": TELUGU_VOWEL_MARKS},
    "bn":  {"label": "Bengali",    "male": "bn",    "female": None, "script": "abugida", "chars": None, "consonants": BENGALI_CONSONANTS, "vowels": BENGALI_VOWEL_MARKS},
}

# --voice random で女性ボイスが選ばれた場合に使うespeak-ngのピッチ(-p、
# 0〜99、デフォルト50)。女性ボイスをより高く聞こえるようにするための
# 底上げ値。tts_synth.synthesize_tts()参照。
FEMALE_VOICE_PITCH = 75

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
#
# 後半62文字はMiscellaneous Symbols / Dingbats / Geometric Shapesブロックから
# 機械的に検証して追加したもの:
#   (1) espeak-ngに1文字ずつ通し、RMS音量が0(完全な無音)であることを確認
#       (905候補中748件が該当。espeak-ngは大半の記号を「未知の文字」として
#       無視するだけで名前を読み上げないことが判明した)
#   (2) Chromium+FRAME_CSS_FONT_STACKで実際にレンダリングし、既知のtofu
#       (未割り当て領域PUA U+E000)のスクリーンショットとピクセル差分が
#       ほぼ0(=同じtofuグリフ)になるものを除外(該当0件。このブロック群は
#       フォントカバレッジが良好だった)
#   (3) 上記を通過した748件から目視でコンタクトシートを確認し、星・スパー
#       クル・花・雪の結晶・ダイヤ・円弧など元のセットと同系統の「意味を
#       持たない図形」だけを選定。矢印・チェス駒・トランプスート・星座/
#       惑星記号・宗教的な記号(卍・アンク等)・チェックマーク・指差しの
#       手・丸数字など、何らかの意味を連想させるものは除外している。
DECORATIVE_SYMBOLS = list(
    "☼✧◉❁❍⊁⊀◞◟๑٭؞֍֎"
    "✤✥✦✩✪✫✬✭✮✯✰✱✲✵✶✷✸✹✺✻✼✽✾✿❀❂❃❅❆❈❉❊❋❏❐❑❒❖◆◇◈◊○◌◍◎◐◑◒◓◔◕◖◗◘◙◚◛◜◝◠◡"
)

# フレーム画像(HTML)で使うフォントスタック。Zalgoの結合文字や記号ブロックは
# 1つのフォントに全部入っていないことが多いので、複数のNoto系フォントを並べ
# てブラウザのfontconfigフォールバックに解決を任せる。
FRAME_CSS_FONT_STACK = (
    "'Noto Sans','Noto Sans CJK JP','Noto Sans Symbols','Noto Sans Symbols2',"
    "'Noto Sans Thai','Noto Sans Devanagari','Noto Sans Hebrew','Noto Sans Arabic',"
    "'Noto Sans Bengali','Noto Sans Sinhala','Noto Sans Tibetan','Noto Sans Yi',"
    "'Noto Sans Cherokee','Noto Sans Mongolian','Noto Sans Georgian',"
    "'Noto Sans Armenian','Noto Sans Ethiopic','Noto Sans Myanmar',"
    "'Noto Sans Tamil','Noto Sans Telugu','DejaVu Sans',sans-serif"
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
