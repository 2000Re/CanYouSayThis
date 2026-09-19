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
# --mode randomはこのdictのキーからMODE_WEIGHTSの重みでランダムに1つ選ぶ
# ため(generate.py _resolve_mode()参照)、新しいモードを追加する場合は
# ここに登録すれば自動的にrandomの抽選対象にも入る(MODE_WEIGHTSに追加が
# 無ければ他のモードと同じ重みがデフォルトで使われる)。
MODE_LABELS = {
    "tts": "Text-to-Speech",
    "glitch": "Synthesized Glitch Audio",
    "tts_extreme": "Distorted Text-to-Speech",
}

# --mode random で各モードが選ばれる相対的な重み(generate.py
# _resolve_mode()参照)。glitchは実際に単語を読み上げるtts/tts_extremeと
# 違い合成音のみで「発音してみて」というコンセプトへの説得力が弱いという
# 判断から、均等抽選(各1/3)よりも比率を下げている。完全に無くすのではなく
# 一旦下げる方針(効果を見て再調整する可能性あり)。
MODE_WEIGHTS = {
    "tts": 2,
    "tts_extreme": 2,
    "glitch": 1,
}

# --voice random が「実在の文字体系」の言語を選んだ場合、単語自体をその
# 言語の文字からランダムに組み立てる(word_generator.random_script_word() /
# random_abugida_word())。BASE_CHARSを流用したZalgo単語と違い、装飾記号・
# Zalgoの結合文字(いずれも英語音声での無音確認しか取れていない)は使わず、
# 実機でChromium+Notoフォントによる描画とespeak-ngでの音声合成の両方が
# 正常に動くことを確認済みの言語のみ対応している。
RUSSIAN_LETTERS = list("абвгдежзийклмнопрстуфхцчшщъыьэюя")


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


# タイ文字は、子音字+母音記号(前後左右に付く、単体では使わない)で音節を
# 作る「アブギダ」と呼ばれる文字体系なので、子音・母音記号を別々のリストに
# 分けている(word_generator.random_abugida_word()参照)。
THAI_CONSONANTS = list("กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ")
THAI_VOWEL_MARKS = list("ะาิีึืุูเแโใไ")

# アラビア文字・ヘブライ文字は、母音記号が任意なため、random_script_word()
# (文字をランダムに並べるだけ、同じ文字の連打あり)で十分自然な見た目になる。
ARABIC_LETTERS = _assigned_chars([(0x0621, 0x064A)])
HEBREW_LETTERS = _assigned_chars([(0x05D0, 0x05EA)])

# --voice random(generate.py _resolve_voice()参照)が抽選する言語/性別の
# 候補。単語自体は母音中心のBASE_CHARSしか使わないので、言語ごとの発音規則の
# 違い(鼻母音・声調・アクセントなど)で聞こえ方が変わることを狙った機能。
#
# "female"には2種類の由来がある:
#   (1) MBROLA音声("mb-"で始まるコード): 実機でespeak-ng(MBROLAエンジン)
#       による音声合成が実際に成功することを確認できた8言語
#       (en/fr/de/hu/sv/tr/pt-br/pt)のみ。専用の音声データパッケージ
#       (mbrola-*、generate.yml参照)が必要な代わり、より自然な声質になる。
#   (2) espeak-ng内蔵の"+f3"フォルマントバリアント: MBROLA音声データが存在
#       しない/壊れている言語向けに、任意のmaleボイスコードへ"+f3"を付ける
#       だけで使える組み込みの女性寄りフォルマント変換(tts_synth.pyの
#       EXTREME_VOICE_VARIANTSで使っている「ボイス+バリアント名」と同じ
#       仕組み)。追加パッケージ不要で全言語をカバーできるため、(1)が使えない
#       残り12言語すべてに採用している。実機でf0(基本周波数)を測定し、
#       素の声(約108Hz)から約194Hzへ明確に上がる(MBROLA版の約235Hzに
#       近い自然な範囲)ことを確認済み。(1)と違い、この"+f3"自体が既に
#       十分な高さなのでFEMALE_VOICE_PITCHは重ねて適用しない
#       (generate.py generate_one()参照。実機で両方重ねると約258Hzまで
#       上がりすぎることを確認したため)。
#       なお中国語(標準語)は、male/female問わずコードとして"zh"ではなく
#       "cmn"(espeak-ng内部の本来のコード)を使っている。"zh"はエイリアス
#       としてボイス単体では動くが、"+バリアント名"を付けると
#       "voice does not exist"エラーになる(全23言語×男女×
#       EXTREME_VOICE_VARIANTS全種の総当たりで実機検証し、壊れているのは
#       "zh"のみと確認済み)。tts_extremeモードでランダムに選ばれた声へ
#       バリアントを付与する際にこの問題を踏むため、maleも"cmn"に統一して
#       いる。これにより、mbrola-cn1パッケージの不具合(後述のハマった罠
#       11番)を経由せずに中国語の女性ボイスにも対応できている。
#
# "script"は実在の文字体系を使う言語にのみ設定する(generate.py
# _native_script_for_voice()参照)。
#   - "cluster": random_script_word()に"chars"を渡す(文字をランダムに
#     並べるだけで自然な見た目になる文字体系向け)。
#   - "abugida": random_abugida_word()に"consonants"/"vowels"を渡す
#     (子音字+母音記号で音節を作る文字体系向け)。
# いずれも未設定(None)の言語は従来通りBASE_CHARSベースのZalgo単語を使う。
#
# GitHub Actions側では、maleのespeak-ngボイスコードも"+f3"バリアントも
# espeak-ng本体だけで追加パッケージ無しに動くが、MBROLA由来のfemaleが
# 設定されている8言語(en/fr/de/hu/sv/tr/pt-br/pt)のみ対応するmbrola-*
# パッケージのインストールが別途必要(generate.yml参照)。
# "hashtag_word"は、その言語の話者がYouTube内で自国語のまま検索した際に
# 見つけてもらえるよう、動画説明文の末尾に追加する「発音」の意味の現地語
# ハッシュタグ(generate.py _youtube_metadata()参照)。英語は既に
# #Pronunciationがあるため不要(None)。
VOICE_LANGUAGES = {
    "en":  {"label": "English",    "male": "en",    "female": "mb-us1", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": None},
    "fr":  {"label": "French",     "male": "fr-fr", "female": "mb-fr4", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Prononciation"},
    "de":  {"label": "German",     "male": "de",    "female": "mb-de1", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Aussprache"},
    "hu":  {"label": "Hungarian",  "male": "hu",    "female": "mb-hu1", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Kiejtés"},
    "sv":  {"label": "Swedish",    "male": "sv",    "female": "mb-sw2", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Uttal"},
    "zh":  {"label": "Mandarin",   "male": "cmn",   "female": "cmn+f3", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "发音"},
    "yue": {"label": "Cantonese",  "male": "yue",   "female": "yue+f3", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "發音"},
    "fi":  {"label": "Finnish",    "male": "fi",    "female": "fi+f3", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Ääntäminen"},
    "is":  {"label": "Icelandic",  "male": "is",    "female": "is+f3", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Framburður"},
    "vi":  {"label": "Vietnamese", "male": "vi",    "female": "vi+f3", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "PhátÂm"},
    "id":  {"label": "Indonesian", "male": "id",    "female": "id+f3", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Pengucapan"},
    "ms":  {"label": "Malay",      "male": "ms",    "female": "ms+f3", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Sebutan"},
    "tr":  {"label": "Turkish",    "male": "tr",    "female": "mb-tr2", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Telaffuz"},
    "pt-br": {"label": "Portuguese (Brazil)", "male": "pt-br", "female": "mb-br4", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Pronúncia"},
    "pt":  {"label": "Portuguese (Portugal)", "male": "pt", "female": "mb-pt1", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Pronúncia"},
    "ro":  {"label": "Romanian",   "male": "ro",    "female": "ro+f3", "script": None, "chars": None, "consonants": None, "vowels": None, "hashtag_word": "Pronunție"},
    "ru":  {"label": "Russian",    "male": "ru",    "female": "ru+f3", "script": "cluster", "chars": RUSSIAN_LETTERS, "consonants": None, "vowels": None, "hashtag_word": "Произношение"},
    "th":  {"label": "Thai",       "male": "th",    "female": "th+f3", "script": "abugida", "chars": None, "consonants": THAI_CONSONANTS, "vowels": THAI_VOWEL_MARKS, "hashtag_word": "การออกเสียง"},
    "ar":  {"label": "Arabic",     "male": "ar",    "female": "ar+f3", "script": "cluster", "chars": ARABIC_LETTERS, "consonants": None, "vowels": None, "hashtag_word": "نطق"},
    "he":  {"label": "Hebrew",     "male": "he",    "female": "he+f3", "script": "cluster", "chars": HEBREW_LETTERS, "consonants": None, "vowels": None, "hashtag_word": "הגייה"},
}

# --voice random で女性ボイスが選ばれた場合に使うespeak-ngのピッチ(-p、
# 0〜99、デフォルト50)。MBROLA由来の女性ボイス(femaleコードが"mb-"で
# 始まる5言語)は素のままだとやや低めに聞こえたため、この値で底上げする。
# "+f3"フォルマントバリアント由来の女性ボイスはそれ単体で既に十分な高さに
# なるため対象外(generate.py generate_one()参照)。tts_synth.synthesize_tts()も
# 参照。
FEMALE_VOICE_PITCH = 75

# --voice random で「実在の文字体系を使う言語」が選ばれる確率。
# 実在文字体系の言語(ロシア語・タイ語・アラビア語・ヘブライ語の4言語)は、
# 視聴地域データの裏付けが無い言語(アルメニア語・アムハラ語・グルジア語・
# チェロキー語・ミャンマー語・シンハラ語・タミル語・テルグ語・ベンガル語の
# 9言語)を削除したことで、ラテン文字(Zalgo)系の言語(16言語)に対して
# 少数派に戻っている(20言語中4)。それでも均等抽選(4/20=20%)よりやや
# 高めの0.3に据え置いているのは、これらの言語が持つ「見た目のインパクト」
# (視覚的なnoveltyがこのチャンネルの売りの一部)を一定の頻度で保つ狙い
# (generate.py _resolve_voice()参照)。
NATIVE_SCRIPT_VOICE_CHANCE = 0.3

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
    "'Noto Sans Tibetan','Noto Sans Yi','Noto Sans Mongolian',"
    "'DejaVu Sans',sans-serif"
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
