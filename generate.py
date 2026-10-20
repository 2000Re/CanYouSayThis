#!/usr/bin/env python3
"""
How-to-Pronounce ネタ動画 自動生成パイプライン(メインCLI)
=================================================

1. Zalgo風「発音不能な単語」をランダム生成          -> word_generator.py
   (--upload時は、upload_history.jsonに既に記録済みの単語と被らないものを
   選ぶ。チャンネルへの重複投稿を避けるため)
2. 音声を作る(14方式から選択):     -> tts_synth.py / glitch_synth.py / morse_synth.py /
                                       animalese_synth.py
     --mode tts          : espeak-ng に単語そのものを読ませ、出てきた音を採用
                            (デフォルト。単語の文字列がそのまま音に反映され
                            るので「本当にその単語を読ませている」感が出せる)
     --mode tts_extreme  : espeak-ngの奇妙な声バリエーション+極端なピッチ・
                            速度で読ませ、さらにffmpegでピッチシフト・
                            ビットクラッシュ等をランダムにかけて歪ませる
                            (ttsと同じく単語自体は読ませているが、声質が
                            毎回激しく変わる)
     --mode glitch       : チャープ音・ノイズバースト・ビットクラッシュを
                            合成(単語の音とは無関係な効果音を当てる)
     --mode reverse      : espeak-ngに読ませた音声をそのまま逆再生する
     --mode robot_voice  : espeak-ngに読ませた音声に搬送波とのリング変調
                            (ffmpegのamultiply)をかけ、ロボット風の声にする
     --mode chorus       : 同じ単語を複数言語のボイスで同時に読み上げて重ねる
     --mode morse        : 単語の文字をモールス信号のビープ音に変換する
                            (espeak-ngは使わず、文字パターンから決定論的に
                            音を組み立てる)
     --mode animalese    : 「どうぶつの森」のキャラクターボイス風に、文字
                            ごとの短い録音済み音声をピッチシフトしながら
                            つなげる(espeak-ngは使わない。視聴者コメントで
                            紹介されたequalo-official/animalese-generator
                            を移植。animalese_synth.py参照)。声の高さは
                            --pitchで直接指定できる(省略時は1本ごとに
                            ランダム)
     --mode random       : 1本ごとに上記いずれかの方式からランダムに選ぶ
                            (--countで複数本まとめて作る際や、自動実行の
                            日々の投稿に単調さが出ないようにする用途)
3. 「答え」を --repeat 回(デフォルト2回)繰り返す      -> audio_utils.py
4. 無音パディングはしない。中身の実際の長さの末尾だけ短くフェードアウトし、
   動画の尺はその音声の長さにそのまま合わせる(固定尺に引き伸ばさない)
5. "How to Pronounce <word>" 形式のミニマルな静止画フレームを生成 -> frame_builder.py
6. 音声+フレームを合成して mp4 を書き出す(尺は音声の長さに追従)  -> video_builder.py
7. --upload 指定時は、書き出したmp4をそのままYouTubeにアップロードする -> youtube_upload.py
   (アップロード成功時は upload_history.json にも記録し、repost_shorts.py が
    横型の通常動画への変換対象として使えるようにする。--mode random で作った
    回も、実際に使われた方式が記録される)

--count で複数本生成する場合、1本の失敗(クォータ超過・一時的なネットワーク
エラー等)で残りの本数まで巻き添えで止めることはしない。失敗した回は記録
して次に進み、最後に失敗一覧を表示したうえで異常終了(exit code 1)する。

必要なもの:
    apt-get install -y espeak-ng ffmpeg
    apt-get install -y fonts-noto-core fonts-noto-extra fonts-noto-ui-core fonts-noto-ui-extra
    pip install -r requirements.txt
    playwright install chromium   # 同梱のChromiumが無い環境の場合のみ

    --upload を使う場合はさらに環境変数
    YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN が必要
    (取得方法は get_youtube_refresh_token.py を参照)

使い方:
    python3 generate.py --count 5 --outdir ./out
    python3 generate.py --count 5 --mode glitch --outdir ./out_glitch
    python3 generate.py --count 5 --mode tts_extreme --outdir ./out_extreme
    python3 generate.py --count 5 --mode random --outdir ./out_mixed
    python3 generate.py --count 3 --upload --privacy-status unlisted

出力:
    ./out/001_word.txt   (生成した単語そのもの)
    ./out/001.mp3        (音声。modeにより中身が変わる)
    ./out/001.mp4        (完成動画)

詳しい経緯・ハマった罠は README.md を参照。
"""

import argparse
import os
import random
import sys
import unicodedata

import config
from animalese_synth import synthesize_animalese
from audio_utils import _is_silent_audio, _stretch_to_min_duration, finalize_audio, repeat_audio, wav_to_mp3
from frame_builder import build_frame, close_browser
from glitch_synth import synthesize_glitch_chunk
from jst_time import jst_timestamp
from morse_synth import synthesize_morse
from tts_synth import (
    strip_unspeakable_foreign_script,
    synthesize_tts,
    synthesize_tts_8d_audio,
    synthesize_tts_chorus,
    synthesize_tts_echo_cave,
    synthesize_tts_extreme,
    synthesize_tts_nightcore,
    synthesize_tts_reverse,
    synthesize_tts_robot,
    synthesize_tts_slowed_reverb,
    synthesize_tts_telephone,
    synthesize_tts_underwater,
)
from video_builder import build_video
from word_generator import (
    cap_combining_marks,
    expand_unknown_chars_to_names,
    random_abugida_word,
    random_pictograph_word,
    random_script_word,
    random_zalgo_word,
    readable_label,
    zalgo_display_word,
)

# 単一の言語・ボイスで実際に「発音」を読み上げるモード(chorusのように複数
# 言語を同時に使ったり、glitch/morseのように単語の内容と無関係/文字パターン
# 由来だったりするモードは含まない)。この集合に入っているモードのみ、
# YouTube側のdefault_audio_language・upload_history.jsonのvoice_label/
# lang_codeへ実際のボイス言語を記録する(generate_one()参照)。
_SINGLE_VOICE_MODES = (
    "tts", "tts_extreme", "reverse", "robot_voice",
    "telephone", "slowed_reverb", "nightcore", "underwater", "8d_audio", "echo_cave",
)


def _single_voice_metadata(actual_mode, voice_label, lang_code):
    """actual_modeが_SINGLE_VOICE_MODESに含まれない(glitch/chorus/morse等)
    場合は、対応する単一の音声言語が存在しないため、voice_label/lang_codeを
    (None, None)に戻して返す。

    以前はgenerate_one()がここでNoneに戻さずvoice_label/lang_codeを
    _youtube_metadata()にそのまま渡していたため、たまたま解決されたボイスの
    lang_labelがタイトル・タグに「in X語」として紛れ込む一方、
    upload_history.jsonにはNoneで記録される不整合があった。この不整合の
    せいで、後からtitle_templateを使ってタイトルを再構築する
    youtube_fix_title_description.pyが元のタイトルにあった「in X語」を
    復元できず欠落させてしまう実害が実際に発生した(README「ハマった罠」
    参照)。_youtube_metadata()への入力とupload_history.jsonへの記録を
    常に同じ値にすることで、この種の不整合が再発しないようにする。"""
    if actual_mode in _SINGLE_VOICE_MODES:
        return voice_label, lang_code
    return None, None


def _lang_suffixed(base, lang_label):
    """base(末尾に"?"を付けない状態の文)に、lang_labelがあれば
    " in {lang_label}?" を付けて返す(無ければbaseのまま、"?"も付けない)。
    how_to_pronounce等、質問形で終わるタイトルテンプレートの共通処理。"""
    return base + (f" in {lang_label}?" if lang_label else "")


# タイトルの言い回しパターン(config.TITLE_TEMPLATE_WEIGHTS参照)。各関数は
# (label, lang_label) -> タイトル文字列(末尾の" #Shorts"を除く)を返す。
# 文の形によって疑問形か否か・lang_labelの挿入位置が異なるため、共通の
# フォーマット文字列1つではなくテンプレートごとに関数を分けている。
_TITLE_TEMPLATES = {
    "how_to_pronounce": lambda label, lang_label: _lang_suffixed(f'How to Pronounce "{label}"', lang_label),
    "can_you_say": lambda label, lang_label: _lang_suffixed(f'Can You Say "{label}"', lang_label),
    "can_you_pronounce": lambda label, lang_label: _lang_suffixed(f'Can You Pronounce "{label}"', lang_label),
    "try_to_say": lambda label, lang_label: f'Try to Say "{label}"' + (f" in {lang_label}" if lang_label else ""),
    "is_pronounceable": lambda label, lang_label: (
        f'Is "{label}" Pronounceable' + (f" in {lang_label}" if lang_label else "") + "?"
    ),
    # 2026-10-13、ユーザーとの相談で追加した6パターン(config.
    # TITLE_TEMPLATE_WEIGHTS参照)。
    "say_out_loud": lambda label, lang_label: (
        f'Say "{label}"' + (f" in {lang_label}" if lang_label else "") + " Out Loud"
    ),
    "pronunciation_challenge": lambda label, lang_label: (
        f'"{label}" Pronunciation Challenge' + (f" in {lang_label}" if lang_label else "")
    ),
    "nobody_can_pronounce": lambda label, lang_label: (
        f'Nobody Can Pronounce "{label}"' + (f" in {lang_label}" if lang_label else "")
    ),
    "what_does_it_sound_like": lambda label, lang_label: (
        f'What Does "{label}" Sound Like' + (f" in {lang_label}" if lang_label else "") + "?"
    ),
    "attempt_to_pronounce": lambda label, lang_label: (
        f'Attempt to Pronounce "{label}"' + (f" in {lang_label}" if lang_label else "")
    ),
    "impossible_to_say": lambda label, lang_label: (
        f'"{label}" — Impossible to Say' + (f" in {lang_label}" if lang_label else "") + "?"
    ),
}


# 運営者コメント自動投稿用の文面。固定1パターンだと複数本見る視聴者には
# 「ボットの定型文」に見えやすいとの判断から、8パターンをランダムに
# ローテーションする(2026-10-13、ユーザーとの相談で選定。元々の固定文面
# だった1番も含む)。字幕用のcaption_text(_youtube_metadata()参照)とは
# 別物で、こちらはコメント欄にしか使わない。repost_shorts.py側も同じ関数を
# 使う(build_repost_metadata()参照、元ShortsのコメントとDocument変換後の
# 通常動画のコメントが同じ文面に揃う必要は無いため、変換のたびに独立して
# 抽選する)。
_COMMENT_TEMPLATES = [
    lambda label, lang_label: (
        f'How to pronounce "{label}"' + (f" in {lang_label}" if lang_label else "")
        + "? Not a real word — just a joke, give it a try! \U0001F604"
    ),
    lambda label, lang_label: (
        f'Think you can say "{label}"' + (f" in {lang_label}" if lang_label else "")
        + "? Not a real word — just a fun challenge! \U0001F604"
    ),
    lambda label, lang_label: (
        f'"{label}"' + (f" in {lang_label}" if lang_label else "")
        + " — not a real word, just a pronunciation joke. Can you say it? \U0001F606"
    ),
    lambda label, lang_label: (
        f'Can anyone actually pronounce "{label}"' + (f" in {lang_label}" if lang_label else "")
        + "? (Not real — just for fun!) \U0001F604"
    ),
    lambda label, lang_label: (
        f'Give "{label}"' + (f" in {lang_label}" if lang_label else "")
        + " a try! Just a made-up word for laughs, not real. \U0001F601"
    ),
    lambda label, lang_label: (
        f'"{label}"' + (f" in {lang_label}" if lang_label else "")
        + "? Good luck \U0001F605 (Not a real word, just a joke!)"
    ),
    lambda label, lang_label: (
        f'Bet you can\'t say "{label}"' + (f" in {lang_label}" if lang_label else "")
        + " on the first try \U0001F604 (Not real — just for fun)"
    ),
    lambda label, lang_label: (
        f'Just a nonsense word for fun: "{label}"' + (f" in {lang_label}" if lang_label else "")
        + ". Can you say it without laughing? \U0001F604"
    ),
]


def _random_comment_text(label, lang_label):
    return random.choice(_COMMENT_TEMPLATES)(label, lang_label)


# 761文字という極端に長い--wordリクエストが来たことがきっかけで追加した
# 文字数上限の案内(README「ハマった罠」68番)。_youtube_metadata()
# (通常のShorts投稿)・repost_shorts.py build_repost_metadata()(Shortsを
# 通常動画に変換して再投稿する際のコメント)の両方で共通して使う定数化
# したもの。以前はrepost_shorts.py側にこの注記が無く、再投稿されたコメント
# にだけ付かないという不整合があった(運営者からの指摘で発覚、README
# 「ハマった罠」76番)。
_REQUEST_LENGTH_NOTICE = " Requests: 80 characters max, please! \U0001F4AC"

# readable_label()が残す「結合文字を除いた土台の文字」には、音楽記号・
# チェス駒記号・はさみ記号等のSymbol系文字も含まれうる(視聴者リクエストの
# バムン文字+チェスのクイーン記号+音楽記号混在の単語で発覚)。これらは
# YouTube自身のタイトル表示フォントが対応しておらず「❓」(豆腐)になるか、
# はさみ記号(✂)のように意図せず絵文字として表示されてしまう
# (README「ハマった罠」79番)。動画フレーム(サムネイル)は別経路
# (frame_label/zalgo_display_word())でこの処理を通さないため、崩れた
# 単語の見た目自体には影響しない。
_SYMBOL_CATEGORIES = ("Sm", "Sc", "Sk", "So")

# タイトル等から除去する記号(許可リスト方式からブロックリスト方式への
# 反転、README「ハマった罠」92番)。以前はSymbol系Unicodeカテゴリ
# (Sm/Sc/Sk/So)を原則すべて除去し、星・花びら・Block Elements・顔文字の
# 目印(`´)等を個別に許可リストへ追加する方式だった(83・86・88番)が、
# 視聴者リクエストの顔文字で新しい記号が来るたびに不一致が起き、その都度
# 許可リストへの追加が必要でスケールしなかった(92番)。そこで原則は表示し、
# 「絵文字として誤解される」「宗教的な意味を持つ」等、実際に問題が確認された
# 記号だけを個別に除去する方式に反転した。
#
# はさみ✂は視聴者リクエストの音楽記号混在単語で実際に絵文字として誤表示
# された(README「ハマった罠」79番の原因)。きらめき✨U+2728・✧U+2747・
# ✦U+2748・雪の結晶❄U+2744-2746は、同じDingbatsブロックの星・花びら系
# 記号と違い現実の物を強く連想させ絵文字として誤解されやすい。ダビデの星
# ✡U+2721は宗教的な意味を持つ。これらはいずれも引き続き除去する。
#
# "<"・">"(山括弧、U+003C/U+003E、Sm)はYouTube Data API側がHTMLタグと
# 誤認するらしく、タイトルに含めるとvideos.insert/updateが
# "The request metadata specifies an invalid or empty video title."
# (invalidTitle)で失敗する実機事故が発生した(視聴者リクエストの単語
# -%@><_><@%-、README「ハマった罠」94番)。見た目の問題ではなく
# アップロード自体が失敗するため、ブロックリスト方式の例外として除去する。
_BLOCKED_SYMBOLS = frozenset(
    chr(cp)
    for cp in (
        [0x2702]  # はさみ✂
        + [0x2728, 0x2747, 0x2748]  # きらめき✨✧✦
        + list(range(0x2744, 0x2747))  # 雪の結晶❄❅❆
        + [0x2721]  # ダビデの星✡(宗教的)
        + [0x3C, 0x3E]  # 山括弧<>(YouTube側がHTMLタグと誤認しアップロードが失敗する)
    )
)

# 説明欄の「Word: {word}」行は、タイトルで切り詰め・除去された記号も
# 視聴者が確認できるよう、label(_sanitize_label_for_display()適用済み)
# ではなく生のwordをそのまま埋め込む設計(README「ハマった罠」65番等)。
# そのため_BLOCKED_SYMBOLS(はさみ等、タイトルでの見た目上の問題を理由に
# 除去)はここでは適用しない方が設計意図に合う。しかし山括弧<>は見た目の
# 問題ではなくYouTube Data API自体が説明欄でも"invalidDescription"で
# アップロードを拒否することが実機で確認された(視聴者リクエストの単語
# -%@><_><@%-、README「ハマった罠」95番)。_BLOCKED_SYMBOLSとは別に、
# API自体が拒否する文字だけに絞った最小限の除去をここに適用する。
_API_UNSAFE_SYMBOLS = frozenset({"<", ">"})


def _strip_api_unsafe_symbols(text):
    """YouTube Data APIがHTMLタグと誤認して拒否する文字(_API_UNSAFE_
    SYMBOLS)だけを取り除く。_sanitize_label_for_display()と違い"this
    word"へのフォールバックは行わない(タイトル単体ではなく、常に他の
    文章の一部に埋め込まれる説明欄向けのため、除去した結果空になっても
    そのまま許容する)。"""
    return "".join(ch for ch in text if ch not in _API_UNSAFE_SYMBOLS)


def _sanitize_label_for_display(label):
    """タイトル・字幕・コメントに使うlabelから、_BLOCKED_SYMBOLS(絵文字として
    誤解されたり宗教的な意味を持つことが確認済みの記号)だけを取り除く。
    それ以外のSymbol系Unicode文字(音楽記号・顔文字の記号・数学記号等)は
    原則そのまま残す(README「ハマった罠」92番、ブロックリスト方式)。
    句読点・結合文字もそのまま残す(꧁꧂のような装飾目的の句読点文字まで
    巻き込んで消してしまっていた実装上の不具合の修正、README「ハマった罠」
    80番参照、は引き続き維持)。取り除いた結果、文字(Letter)・数字
    (Number)・Symbol文字が1つも残らない場合(全て取り除かれて空になった
    場合だけでなく、readable_label()が付与する省略記号"..."のような句読点
    だけが残った場合も含む。README「ハマった罠」82番参照)は、"this word"を
    返す(README「ハマった罠」96番)。全テンプレートが`"{label}"`の形で
    引用符内に埋め込むため、"???"のような記号の代わりにこの文字列を
    使うと、How to Pronounce "this word"?・Bet you can't say "this word"
    on the first try 😄のように、どのテンプレートでも不自然にならず
    組み込める。"""
    kept = "".join(ch for ch in label if ch not in _BLOCKED_SYMBOLS).strip()
    if not any(
        unicodedata.category(ch)[0] in ("L", "N") or unicodedata.category(ch) in _SYMBOL_CATEGORIES
        for ch in kept
    ):
        return "this word"
    return kept


def _is_symbol_only_word(word):
    """wordに文字(Letter)・数字(Number)が1つも含まれず、かつSymbol系
    Unicodeカテゴリ(_SYMBOL_CATEGORIES)の文字を1つ以上含む「記号だけの
    単語」(動画_-wkmpnDXWM・████が実例)かどうかを判定する。結合文字は
    判定対象外。꙰のような囲み結合文字(Meカテゴリ、combining()が0を返す
    ため土台文字として扱われる)や꥟のような句読点(Po)はSymbolでも
    Letter/Numberでもないため、含まれていても判定に影響しない(sanitizeで
    元々取り除かれない文字のため)。_BLOCKED_SYMBOLSによる除去は考慮しない
    (はさみ等のブロック対象記号が混ざっていても対象のまま。表示上の除去は
    _sanitize_label_for_display()側の別の話で、ここでは「タイトルの
    切り詰め幅をどちらにするか」だけを判定する)。

    末尾に区切り記号として星が1つ付いているだけの通常のZalgo単語
    (大半が文字で構成されている)まで対象になってしまっていた実装上の
    不具合を修正(README「ハマった罠」85番)。該当する場合、通常の
    readable_label()の12文字切り詰めではなく、説明欄の「Word:」行と同じ
    内容が見えるようもう少し長く表示する(運営者から「タイトルも説明欄と
    同じにしたい」との要望、README「ハマった罠」84番。ただしYouTubeタイトル
    100文字制限の安全マージンとして確立済みの_TITLE_SENTENCE_SNIPPET_CHARS
    (20文字)は超えない)。"""
    base_chars = [ch for ch in word if not unicodedata.combining(ch)]
    if not any(unicodedata.category(ch) in _SYMBOL_CATEGORIES for ch in base_chars):
        return False
    return not any(unicodedata.category(ch)[0] in ("L", "N") for ch in base_chars)


# 楔形文字・エジプト/アナトリア象形文字・線文字B(config.PICTOGRAPH_SCRIPTS)の
# 単語は、動画のフレーム画像(このプロジェクト自身のChromium+Notoフォントで
# 描画)では問題無く表示されるが、タイトル・説明欄・字幕・コメントの
# プレーンテキストはYouTube自身のウェブサイト/アプリ側のフォントで表示
# されるため、これらの歴史的文字体系のフォントが無く「豆腐」(表示不能の
# 四角)になってしまう(2026-10-14、実機のタイトル表示で確認)。動画フレーム
# 側の見た目は変えず、タイトル/説明欄/字幕/コメントにだけ生の文字を埋め込ま
# ないようにする。
_PICTOGRAPH_SCRIPT_CHARS = frozenset(ch for script in config.PICTOGRAPH_SCRIPTS for ch in script)


def _is_pictograph_word(word):
    """wordが_pictograph_word_generator()が生成した(楔形文字等の)単語か
    どうかを、生成に使った関数を覚えておく代わりに単語の中身から判定する。"""
    return any(ch in _PICTOGRAPH_SCRIPT_CHARS for ch in word)


def _speakable_word(word):
    """TTSに渡す直前にだけ楔形文字・エジプト/アナトリア象形文字・線文字B
    表意文字を取り除いた文字列を返す(動画フレーム側の見た目・label・
    upload_history.json記録用のwordそのものは変えない。呼び出し側で
    別々に扱う)。

    これらの文字はespeak-ngに読ませるとコードポイントを桁ごとに延々と
    読み上げてしまう(README「ハマった罠」参照)ため、morse_synth.pyが
    対応表に無い文字を無視するのと同じ考え方で、TTS系モード
    (tts/tts_extreme/reverse/robot_voice/chorus/telephone/slowed_reverb/
    nightcore/underwater/8d_audio/echo_cave)に渡す単語からだけ取り除く。
    全文字が取り除かれて空文字列になった場合はespeak-ngにほぼ無音の
    音声を作らせることになるが、エラーにはならず
    _stretch_to_min_duration()で最低尺まで引き伸ばされる(glitchモード
    専用だったPICTOGRAPH_VISUAL_CHANCEや--word直接指定時と同様、実害は
    無い)。"""
    return "".join(ch for ch in word if ch not in _PICTOGRAPH_SCRIPT_CHARS)


def _speak_symbols_by_name(word):
    """TTSに渡す直前に、Symbol系Unicodeカテゴリ(Sm/Sc/Sk/So。はさみ✂・
    音楽記号・顔文字の目印の`´等、_sanitize_label_for_display()が参照する
    のと同じ_SYMBOL_CATEGORIES)の文字を、word_generator.expand_unknown_
    chars_to_names()でUnicode正式名称の読み上げに変換する(例:
    "✂"→" BLACK SCISSORS "、"´"→" ACUTE ACCENT ")。

    これらの文字はespeak-ngにそのまま渡しても発音されず、無視されるか
    単語全体が実質無音になる。視聴者リクエストの顔文字(Ψ( ` 皿 ´ )Ψ等)
    のように単語の大半がSymbol文字の場合、無音を避けるためglitchモード
    以外の選択肢が実質無くなってしまっていた。技術的な正式名称を読ませる
    ことで、無音を避けつつ「もっともらしいのに変な読み方」というこの
    チャンネルの趣旨に沿った形で音声化できる(README「ハマった罠」89番)。

    結合文字(Zalgoの見た目)はSymbolカテゴリに含まれないため対象外
    (従来通りそのままTTSに渡る)。楔形文字等(_speakable_word()が別途
    取り除く対象)もLetterカテゴリのため対象外、こちらの挙動は変えない。"""
    return expand_unknown_chars_to_names(
        word, lambda ch: unicodedata.category(ch) not in _SYMBOL_CATEGORIES
    )


_PICTOGRAPH_TITLE = "Can You Read These Ancient Symbols?"
_PICTOGRAPH_DESCRIPTION_LINE = "A sequence of ancient pictographic symbols"
_PICTOGRAPH_CAPTION_TEXT = (
    "Can you read these ancient symbols? Not a real word — just a visual puzzle! \U0001F440"
)
_PICTOGRAPH_COMMENT_TEMPLATES = [
    "These ancient-looking symbols are just for fun — can you make sense of them? \U0001F440",
    "Not a real word, just a pattern of ancient symbols! Can you read it? \U0001F604",
]

# 動画フレーム(サムネイル含む)表示専用の文字数上限。readable_label()の
# デフォルト(12文字)はYouTubeタイトルの100文字制限を守るためのもので、
# フレーム画像自体にはそのような技術的上限が無い(frame_builder.py側の
# _word_font_size()がフォントサイズを文字数に応じて縮小するだけで済む)。
# そのため、長い文章の--wordリクエスト(animaleseモード等)でも
# フレーム上で「Welcome to m...」のように途中で切れないよう、こちらは
# 別枠でより大きい値にしている(README「ハマった罠」63番参照)。
_FRAME_MAX_BASE_CHARS = 80

# 完成した音声が実質無音(_is_silent_audio()参照)だった場合に、ランダム
# 生成の単語を選び直して再合成を試みる最大回数(1回目を含む)。
# build_thumbnail()の壊れたPNG再試行(max_attempts)と同じ考え方の安全網
# (README「ハマった罠」69・70番参照)。
_SILENCE_RETRY_ATTEMPTS = 3

# タイトル用「文章スニペット」の文字数上限。YouTubeタイトルの100文字制限
# のworst case(最長の言語名+最長のタイトルテンプレート+ジャンルサフィ
# ックス+" #Shorts")でも安全な23文字以内で、readable_label()の既定値
# (12文字)より少し余裕を持たせている(_sentence_title_snippet()参照、
# README「ハマった罠」65番)。
_TITLE_SENTENCE_SNIPPET_CHARS = 20


def _sentence_title_snippet(word):
    """wordが複数単語からなる「文章」(--wordでの視聴者リクエスト等、
    スペースを含む長い入力。animaleseモードの文章丸ごとリクエストが典型例)
    で、通常のreadable_label()(12文字)のまま使うと単語の途中で切れて
    「Welcome to m...」のように意味が通じなくなる場合、単語の区切り
    (スペース)より手前までの範囲をタイトル用に切り出す。

    通常の自動生成された単語(zalgo単語等)はスペースを含まない1語構成
    のため、常にNoneを返す(呼び出し側はreadable_label()の結果(label)
    をそのまま使う)。切り詰めが発生しないほど短い文章もNoneを返す
    (readable_label()の結果で十分なため)。

    動画フレーム側は別枠の_FRAME_MAX_BASE_CHARS(80文字)で既に全文
    表示されている(README「ハマった罠」63番)ため、ここで対処するのは
    タイトル・字幕・コメント・ローカライズタイトルだけの問題であること
    に注意(README「ハマった罠」65番)。"""
    stripped = readable_label(word, max_base_chars=len(word) + 1)
    if " " not in stripped or len(stripped) <= _TITLE_SENTENCE_SNIPPET_CHARS:
        return None
    cutoff = stripped.rfind(" ", 0, _TITLE_SENTENCE_SNIPPET_CHARS + 1)
    if cutoff <= 0:
        return None
    return stripped[:cutoff] + "..."


def _random_pictograph_comment_text():
    return random.choice(_PICTOGRAPH_COMMENT_TEMPLATES)


def _mode_genre_suffix(mode):
    """modeがconfig.TITLE_GENRE_MODESに含まれる場合、タイトル末尾に付ける
    " (ジャンル名)" を返す(該当しなければ空文字列)。

    nightcore/8d_audio/slowed_reverbは実際にYouTube上で検索されるジャンル
    名(音楽系のトレンド)のため、タイトルに含めると検索流入が見込める。
    glitch/reverse等の他モードは音声加工の技術名であって視聴者が検索する
    言葉ではないため対象外(「ハマった罠」45番)。repost_shorts.pyの
    build_repost_metadata()も通常動画のタイトルに同じ接尾辞を付けるため
    ここから流用する。"""
    if mode in config.TITLE_GENRE_MODES:
        return f" ({config.MODE_LABELS[mode]})"
    return ""


def _resolve_title_template(title_template):
    """title_template="random"の場合、config.TITLE_TEMPLATE_WEIGHTSの重みに
    従って1本ごとにランダムに選ぶ(_resolve_mode()と同じ方式)。それ以外
    (テストでの固定指定用)はそのまま返す。"""
    if title_template == "random":
        templates = list(config.TITLE_TEMPLATE_WEIGHTS)
        weights = [config.TITLE_TEMPLATE_WEIGHTS[t] for t in templates]
        return random.choices(templates, weights=weights)[0]
    return title_template


def _youtube_metadata(word, label, mode, playlist_id=None, voice_label=None, is_native_script=False,
                       lang_code=None, title_template="random"):
    """生成した単語からYouTubeアップロード用のtitle/description/tagsを組み立てる。

    label は readable_label() で結合文字を落とし最大12文字に丸め済みの
    ものなので、タイトルの100文字制限には十分収まる。

    playlist_id を渡すと、説明文にShorts用再生リストへのリンクを追加し、
    視聴者が他の動画も連続して見る(回遊する)よう誘導する。

    説明文には playlist_id の有無に関わらず、常に登録を促すCTA(Call To
    Action)の一文を入れる。アナリティクスで新規視聴者がほとんど(97%超)
    でコア視聴者が0.1%未満という偏りが見えたため、1本だけ見て離脱する
    視聴者にも登録を明示的に呼びかける狙い。

    voice_label を渡すと(--voice random で言語/性別が抽選された場合のみ)、
    説明文にどの言語のボイスを使ったかを明記する。

    is_native_script=Trueの場合(アラビア文字・キリル文字等、実在の文字体系
    で単語を生成した回)、実在するその言語の単語ではなくランダムな造語である
    旨を説明文に明記する。Zalgo単語(ラテン文字+結合文字)は見た目からして
    実在の単語でないことが明らかなので対象外だが、lang_codeの
    config.VOICE_LANGUAGESエントリに"fake_word_note": Trueが立っている場合は
    例外的にこちらも明記する(スペイン語。README「ハマった罠」26番で話者数の
    少ないトルコ語でも「本物のトルコ語ではない」という指摘が繰り返されて
    言語プールから撤去した経緯があり、話者数がさらに多いスペイン語は同種の
    指摘リスクがより高いと判断したため)。

    説明文には「tongue twister」「language learners」という、上記のタイト
    ル・タグの言語名追加とは違う切り口の検索キーワードを含む一文も常に
    入れる(自然な文として、他の施策と競合しない形で追加する検索流入策)。
    タグにも"tongue twister"を追加する。

    説明文には、config.AUDIENCE_REGION_PHRASESで設定した非英語圏向けの
    検索キーワードフレーズ(視聴者属性で継続的に上位に入っているフィリピン・
    インドネシア・マレーシア向け)も、動画のボイス言語とは無関係に常に含める。

    説明文・comment_textの両方に、視聴者コメントでのリクエストを「80文字
    以内」にお願いする一文を常に含める(761文字という極端に長い--word
    リクエストが来たのがきっかけ、README「ハマった罠」68番)。comment_text
    側は追加分を最小限の長さに抑えている(既存の「実在の単語ではない」の
    注記が、Shorts視聴画面のコメント欄プレビューの行数制限で切り詰められ
    ないようにするため。本関数後半のコメント参照)。

    戻り値のcaption_text(YouTubeの手動字幕用)は、意味不明な音声を自動文字
    起こし(ASR)に任せると検索インデックス対象のテキスト枠が無駄になる
    ため、説明文と同じ趣旨のキーワード付き固定テキストとして別途組み立てる
    (youtube_upload.upload_caption()参照)。

    戻り値のcomment_text(運営者コメントの自動投稿用、_COMMENT_TEMPLATES
    参照)は、以前はcaption_textをそのまま流用していたが、固定1パターン
    だと複数本見る視聴者に「ボットの定型文」に見えやすいとの判断から
    2026-10-13に分離し、複数パターンをランダムに選ぶようにした。
    「実在の単語ではない/ジョーク」という注記はcaption_text・comment_text
    どちらにも常に含める(説明欄・フレームの注記は見ていなくても、
    コメント欄で実際にコメントを付けてくる視聴者はいることが分かったため)。

    wordが楔形文字・エジプト/アナトリア象形文字・線文字Bのいずれか
    (_is_pictograph_word()参照)の場合、title/description/caption_text/
    comment_text/localizationsのいずれにも単語そのものを埋め込まず、代わりに
    _PICTOGRAPH_TITLE等の固定の汎用フレーズを使う(動画フレーム画像はこの
    プロジェクト自身のフォントで描画するため問題無いが、YouTube自身の
    ウェブサイト/アプリのフォントにはこれらの文字体系が無く、タイトル等の
    プレーンテキストに生で埋め込むと「豆腐」になることを2026-10-14に実機で
    確認したため)。

    wordが複数単語からなる「文章」で、タイトル用のlabel(readable_label()、
    max_base_chars=12)のままだと単語の途中で切れて意味が通じなくなる場合
    (_sentence_title_snippet()参照。--wordでの文章丸ごとのリクエスト
    (animaleseモード等)が典型例)、labelをより大きい予算(23文字以内で
    安全な_TITLE_SENTENCE_SNIPPET_CHARS、20文字)で単語の区切りまでの
    スニペットに差し替える。そのため以降のtitle/caption_text/
    comment_text/localizationsの組み立ては通常の単語の場合と全く同じ
    コードパスを通り、_TITLE_TEMPLATES・_COMMENT_TEMPLATES等の言い回しの
    バリエーションもそのまま活きる(固定の汎用フレーズ1種類に揃ってしま
    うと、画一的なタイトルになり得る懸念があったため、README「ハマった
    罠」65番)。動画フレーム画像は別枠の_FRAME_MAX_BASE_CHARS(80文字)で
    既に全文表示されており(README「ハマった罠」63番)、description内の
    「Word: {word}」の行も元々wordをそのまま埋め込んでいて切り詰めが
    無いため、全文はどちらかで必ず視聴者の目に入る。

    戻り値のlocalizations(config.JAPANESE_TITLE_LOCALIZATION_ENABLED /
    config.EXTRA_TITLE_LOCALIZATION_ENABLEDがいずれもFalseならNone)は、
    YouTube側の視聴環境が該当言語の視聴者にだけ表示されるローカライズ
    タイトルを言語コードごとに含む(youtube_upload.upload_video()の
    localizations引数)。日本語はconfig.LANGUAGE_LABELS_JAで言語名の注記
    付き、それ以外(フィリピン語/インドネシア語/マレー語)は
    config.EXTRA_TITLE_LOCALIZATIONSのテンプレートをそのまま使う
    (誤訳のリスクを避けるため言語名の注記は無し)。

    lang_code を渡すと(config.VOICE_LANGUAGESのキー、例: "ar")、
      - タイトルに言語名を追加する(例: `in French?`)。「french
        pronunciation」のような、言語名込みの検索クエリにタイトルレベルで
        マッチしやすくする狙い。英語(lang_code="en")はこのチャンネルの
        既定言語という扱いのため追加しない。
      - タグにも `<言語名> pronunciation`(小文字)を追加する。英語話者が
        言語名で検索した際に見つけてもらいやすくする狙い(下記の現地語
        ハッシュタグと違い、こちらは英語で検索する側を想定)。
      - その言語で「発音」を意味するハッシュタグ(config.VOICE_LANGUAGESの
        "hashtag_word")を英語ハッシュタグに追加する。英語圏の視聴者向けの
        #Pronunciation等と違い、その言語の話者が母語のまま検索した際に
        見つけてもらいやすくするための施策。該当する語が用意されていない
        言語(英語自身、チェロキー語)では何も追加しない。

    title_template を省略(デフォルト"random")すると、config.
    TITLE_TEMPLATE_WEIGHTSの重みに従ってタイトルの言い回しをランダムに
    選ぶ(_resolve_title_template()参照)。「How to Pronounce "X"?」固定だと
    YouTube収益化審査の「reused content」判定で画一的と見なされるリスクが
    あるという懸念から導入した。2026-10-13、ユーザーの指示で全11パターン
    (_TITLE_TEMPLATES参照)を均等配分に変更した(config.TITLE_TEMPLATE_WEIGHTS
    参照)。テストでは_TITLE_TEMPLATESの特定のキーを明示的に渡して固定できる。

    modeがnightcore/8d_audio/slowed_reverbのいずれかの場合、タイトル末尾に
    " (ジャンル名)" を付ける(_mode_genre_suffix()参照)。これらは実際に
    YouTube上で検索される音楽系ジャンル名のため検索流入が見込めるが、
    glitch/reverse等の他モードは加工の技術名であって視聴者が検索する
    言葉ではないため対象外にしている。"""
    lang_entry = config.VOICE_LANGUAGES.get(lang_code)
    # 英語はこのチャンネルの既定言語なので、タイトル・タグへの言語名追加は
    # 対象外にする("in English?"は冗長なため)。
    lang_label = lang_entry["label"] if lang_entry and lang_code != "en" else None
    is_pictograph_script = _is_pictograph_word(word)
    # 文章(スペースを含む長いword)で、通常のlabel(12文字)だと単語の
    # 途中で切れてしまう場合のみ、タイトル用により大きい予算のスニペットに
    # 差し替える(本関数冒頭のdocstring、README「ハマった罠」65番参照)。
    sentence_snippet = _sentence_title_snippet(word)
    if sentence_snippet is not None:
        label = sentence_snippet
    # タイトル・字幕・コメントで豆腐/意図しない絵文字表示にならないよう
    # Symbol系文字を取り除く(README「ハマった罠」79番、_sanitize_label_
    # for_display()参照)。動画フレームの見た目には影響しない。
    label = _sanitize_label_for_display(label)

    mode_label = config.MODE_LABELS.get(mode, mode)
    if is_pictograph_script:
        title = _PICTOGRAPH_TITLE
    else:
        actual_title_template = _resolve_title_template(title_template)
        title = _TITLE_TEMPLATES[actual_title_template](label, lang_label)
    title += _mode_genre_suffix(mode)
    title += " #Shorts"
    description = "Can you pronounce this? \U0001F440\n\n"
    description += (
        f"{_PICTOGRAPH_DESCRIPTION_LINE}\n" if is_pictograph_script
        else f"Word: {_strip_api_unsafe_symbols(word)}\n"
    )
    description += f"Mode: {mode_label}\n"
    if mode == "animalese":
        # animalese_synth.pyは「どうぶつの森」風の高速ピッチシフト声を模した
        # ファンメイドの音声合成であり、実際のゲーム音源は使っていない
        # (README「ハマった罠」62番参照)。公式との誤解を避けるため、説明欄に
        # 明記する。
        description += (
            "(This voice effect is a fan-made audio synthesis inspired by a "
            "certain game series' character voices. It is not affiliated "
            "with, endorsed by, or associated with the original publisher.)\n"
        )
    if voice_label:
        description += f"Voice: {voice_label}\n"
    if is_native_script or (lang_entry and lang_entry.get("fake_word_note")):
        description += (
            "(This is a randomly generated sequence of letters, not a real word "
            "in that language!)\n"
        )
    description += (
        "\nTry saying it out loud and comment your attempt! \U0001F5E3️\n\n"
        "The ultimate tongue twister for language learners, TTS fans, and "
        "anyone up for a pronunciation challenge!\n\n"
    )
    if config.AUDIENCE_REGION_PHRASES:
        phrases = " · ".join(f"{phrase} ({lang})" for lang, phrase in config.AUDIENCE_REGION_PHRASES)
        description += f"(How do you say it? {phrases})\n\n"
    if playlist_id:
        description += (
            f"▶ Watch more pronunciation challenges: "
            f"https://www.youtube.com/playlist?list={playlist_id}\n\n"
        )
    description += "\U0001F514 Subscribe for a new unpronounceable word every day!\n\n"
    # 761文字という極端に長い--wordリクエストが来たことがきっかけで、運営者
    # から「80文字以内で」という上限をどこかに明記してほしいと要望があった
    # ため追加(README「ハマった罠」68番)。全モード共通で常に表示する。
    description += (
        "\U0001F4AC Got a word or phrase for me to try? Drop it in the "
        "comments — please keep requests to 80 characters or less!\n\n"
    )
    native_hashtag_word = lang_entry.get("hashtag_word") if lang_entry else None
    description += "#Shorts #Pronunciation #Unpronounceable #Zalgo #GlitchText #TextToSpeech #TTS #Challenge"
    if native_hashtag_word:
        description += f" #{native_hashtag_word}"
    tags = [
        "shorts", "pronunciation", "unpronounceable", "how to pronounce", mode,
        "zalgo", "glitch text", "text to speech", "pronunciation challenge",
        "tongue twister",
    ]
    if lang_label:
        tags.append(f"{lang_label.lower()} pronunciation")
    if native_hashtag_word:
        tags.append(native_hashtag_word)

    # 視聴者はshortsの説明欄やフレームの注記は見ていなくても、この文面が
    # 投稿されるコメント欄は見ている(実際にコメントを付けてくる)ことが
    # 分かったため、「実在の単語ではない/ジョークだ」という注記はここに
    # 入れるのが一番伝わる(is_native_scriptに関わらず全モード共通で入れる。
    # 実在文字体系でない場合も、言語名を付けたことで「本物のその言語の単語」
    # だと誤解されるケースがあったため)。
    #
    # 以前は"A tongue twister and pronunciation challenge — try saying it
    # out loud!"という説明文と同趣旨の一文も足していたが、Shorts視聴画面の
    # コメント欄プレビューは長い本文を数行で切り詰めて「詳細」タップが必要に
    # なる仕様で、肝心の「実在の単語ではない」の注記まで見えなくなっていた
    # (実機で確認)。tags/descriptionに既にtongue twister等のキーワードは
    # あり重複するため削り、注記が確実に切り詰められずに見える短さにした。
    if is_pictograph_script:
        caption_text = _PICTOGRAPH_CAPTION_TEXT
        comment_text = _random_pictograph_comment_text()
    else:
        caption_text = f'How to pronounce "{label}"'
        if lang_label:
            caption_text += f" in {lang_label}"
        caption_text += "? Not a real word — just a joke, give it a try! 😄"
        comment_text = _random_comment_text(label, lang_label)
    # 761文字という極端に長い--wordリクエストが来たことがきっかけで追加した
    # 文字数上限の案内(description側と同じ趣旨、README「ハマった罠」68番)。
    # 既存のcomment_text本文(68〜89文字程度)より長くしすぎると、Shorts
    # 視聴画面のコメント欄プレビューの行数制限で「実在の単語ではない」の
    # 注記ごと切り詰められてしまう(本関数前述のコメント参照)ため、
    # 追加分は最小限の長さ(40文字弱)に抑えている。
    comment_text += _REQUEST_LENGTH_NOTICE

    # タイトルの日本語ローカライズ(videos.insertのlocalizationsフィールド)。
    # YouTube側の視聴環境が日本語の視聴者には、通常のtitle/descriptionの
    # 代わりにこちらが表示される(動画本体・音声・description自体は変えない。
    # 「海外向け」という動画コンテンツ自体の方針とは別軸で、あくまで表示
    # 言語をYouTube側の視聴者設定に合わせるだけの施策)。
    localizations = {}
    # labelがヘブライ語・アラビア語のようなRTL文字体系の場合、引用符の直後に
    # 来る最初の「強い方向性を持つ文字」がlabel自身になり、Unicode双方向
    # アルゴリズム(UAX #9)によりタイトル全体の基準方向がRTLと判定されて
    # しまう(実際にYouTube上で「#Shortsの発音は?(ヘブライ語)「...」」の
    # ように語順が丸ごと入れ替わって表示される不具合として発覚)。
    # First Strong Isolate(U+2068)〜Pop Directional Isolate(U+2069)で
    # labelを囲み、周囲のテキストの基準方向にlabelの向きが影響しないよう
    # 分離する(labelがLTRの場合も無害なので、言語ごとに分岐しない)。全ての
    # ローカライズ言語で共通して使うため、ここで一度だけ組み立てる。
    #
    # [罠] 上記の分離だけでは不十分だった: 本来はUAX #9準拠なら「」の直後の
    # isolateはスキップされ、その次の強い文字(の=LTR)が基準方向を決める
    # はずだが、実機ではこの対策後に投稿した動画でも同じ語順の入れ替わりが
    # 再発した(2026-10-09アップロードのヘブライ語動画で確認)。YouTube側が
    # 表示前にゼロ幅のisolate制御文字自体を取り除いている可能性が高く、
    # 不可視文字に頼る対策はあてにできない。そのため、タイトル文字列の
    # 「最初の1文字」自体を常に実在の強いLTR文字(かな/カナ/漢字)にする
    # ことで、不可視文字が残るかどうかに関係なく基準方向をLTRに固定する
    # (括弧・鉤括弧のような中立文字を先頭に置かない)。
    isolated_label = f"⁨{label}⁩"

    if config.JAPANESE_TITLE_LOCALIZATION_ENABLED:
        if is_pictograph_script:
            # labelを埋め込まない(タイトル本文と同じ理由、本関数冒頭参照)。
            title_ja = "この古代文字、読めますか?"
        else:
            lang_label_ja = config.LANGUAGE_LABELS_JA.get(lang_code)
            if lang_label_ja:
                # 言語名(かな/カナ/漢字、常に強いLTR文字)を先頭に置き、鉤括弧
                # 「」を文頭にしない。labelが実在のRTL文字体系になり得るのは
                # lang_codeが設定されている場合に限られる(_word_generator_for()
                # 参照)ため、このルートだけで足りる。
                title_ja = f"{lang_label_ja}で「{isolated_label}」はどう発音する?"
            else:
                title_ja = f"「{isolated_label}」の発音は?"
        title_ja += " #Shorts"
        localizations["ja"] = {"title": title_ja, "description": description}

    # 日本語以外の追加言語ローカライズ(config.EXTRA_TITLE_LOCALIZATIONS参照)。
    # 「(言語名)」の注記は誤訳のリスクを避けるため付けていない。
    if config.EXTRA_TITLE_LOCALIZATION_ENABLED:
        for extra_lang_code, template in config.EXTRA_TITLE_LOCALIZATIONS.items():
            localizations[extra_lang_code] = {
                # is_pictograph_scriptの場合、翻訳済みの汎用フレーズを言語数分
                # 用意する手間をかけるほどの頻度ではないため、英語の汎用タイトル
                # をそのまま使う(labelを埋め込まないことが優先、本関数冒頭参照)。
                "title": (
                    f"{_PICTOGRAPH_TITLE} #Shorts" if is_pictograph_script
                    else template.format(label=isolated_label)
                ),
                "description": description,
            }

    return title, description, tags, caption_text, comment_text, localizations or None


def _resolve_mode(mode):
    """--mode random の場合、config.MODE_WEIGHTSの重みに従って1本ごとに
    ランダムに選ぶ(重み未設定のモードは他と同じ重み1として扱う)。
    それ以外(tts / glitch / tts_extreme)はそのまま返す。"""
    if mode == "random":
        modes = list(config.MODE_LABELS)
        weights = [config.MODE_WEIGHTS.get(m, 1) for m in modes]
        return random.choices(modes, weights=weights)[0]
    return mode


def _unposted_lang_codes(codes):
    """渡されたlang_codeのうち、upload_history.json(アップロード成功履歴)に
    一度もlang_codeとして記録されていないものだけを返す。

    lang_codeはgenerate.py側がmodeが単一ボイス(config._SINGLE_VOICE_MODES)
    の回の--upload成功時のみ記録する(upload_history.append_upload()参照)。
    そのためglitch/chorus/morseの回や、アップロードしていないローカル実行は
    「投稿済み」に数えない。

    upload_historyはgoogle-api-python-client等の重い依存を持たないため、
    ここでの遅延importは依存関係を避ける目的ではなく、他の箇所
    (generate_one()の重複単語チェック等)と同じ呼び出し方に揃える目的。"""
    from upload_history import load_upload_history

    posted = {entry.get("lang_code") for entry in load_upload_history()}
    return [c for c in codes if c not in posted]


def _resolve_voice(voice):
    """--voice random の場合、config.VOICE_LANGUAGESから言語と性別を
    ランダムに選び、(実際のespeak-ngボイスコード, 表示用ラベル, 性別)を
    返す。femaleが設定されていない言語はmaleのみが選ばれる。

    それ以外(具体的なボイスコード)は動画説明文への言語ラベルは追加しない
    (label=None)が、config.VOICE_LANGUAGESのfemaleボイスコードと一致する
    場合は性別だけ"female"として返す。--voice randomを経由しなくても
    女性ボイスを直接指定した場合にピッチ補正(config.FEMALE_VOICE_PITCH)が
    かかるようにするため。"""
    if voice != "random":
        known_female_codes = {
            entry["female"] for entry in config.VOICE_LANGUAGES.values() if entry["female"]
        }
        gender = "female" if voice in known_female_codes else None
        return voice, None, gender
    # 実在文字体系の言語(script指定あり)がラテン文字(Zalgo)系の言語より
    # 多くなったため、まず「実在文字体系」か「ラテン文字」かを
    # config.NATIVE_SCRIPT_VOICE_CHANCEの確率で決めてから、その中で言語を
    # 均等抽選する(config.VOICE_LANGUAGES参照)。
    native_script_codes = [c for c, e in config.VOICE_LANGUAGES.items() if e["script"] is not None]
    latin_codes = [c for c, e in config.VOICE_LANGUAGES.items() if e["script"] is None]
    pool = native_script_codes if random.random() < config.NATIVE_SCRIPT_VOICE_CHANCE else latin_codes
    # 選んだプール内に一度も投稿されていない言語があれば、必ずそちらから
    # 選ぶ(新しく追加した言語がなかなか抽選されない問題への対策。ユーザー
    # 要望)。プール内の全言語が投稿済みになれば通常の均等抽選に戻る。
    unposted = _unposted_lang_codes(pool)
    lang_code = random.choice(unposted if unposted else pool)
    entry = config.VOICE_LANGUAGES[lang_code]
    genders = ["male"] + (["female"] if entry["female"] else [])
    gender = random.choice(genders)
    label = f"{entry['label']} ({gender.capitalize()})"
    return entry[gender], label, gender


def _native_script_for_voice(voice_code):
    """voice_codeがconfig.VOICE_LANGUAGESの中で「実在の文字体系を使う言語」
    (script指定あり)に該当する場合、その単語生成関数を返す。該当しなければ
    None(呼び出し側は従来通りrandom_zalgo_word()を使う)。

    --voice random経由でも、"ru"等の対応言語コードを直接指定した場合でも
    同じ単語生成に切り替わる(_resolve_voice()の女性ボイス判定と同じ考え方)。"""
    for entry in config.VOICE_LANGUAGES.values():
        if voice_code not in (entry["male"], entry["female"]):
            continue
        if entry["script"] == "cluster":
            return lambda: random_script_word(entry["chars"])
        if entry["script"] == "abugida":
            return lambda: random_abugida_word(entry["consonants"], entry["vowels"])
    return None


def _pictograph_word_generator():
    """楔形文字・エジプト/アナトリア象形文字・線文字B表意文字のいずれか1つの
    文字体系をconfig.PICTOGRAPH_SCRIPT_WEIGHTSの重みに従って選び、その単語
    生成関数を返す(config.PICTOGRAPH_SCRIPTS参照)。
    _native_script_for_voice()と同様、選んだ文字体系(chars)を1回だけ
    抽選してlambdaに固定することで、_random_unique_word()の再抽選試行中に
    文字体系がぶれない(同じ「絵」の系統の中で単語違いを試す)ようにしている。

    chorus/morse以外の全モードで使われ得る(_word_generator_for()参照)。
    これらの文字をespeak-ngに読ませると無音にならず、コードポイントを
    桁ごとに読み上げる長い音声になってしまうこと(README「ハマった罠」
    参照)を実機で確認済みのため、以前はTTSを使わないglitchモード限定
    だったが、_speakable_word()でTTS合成直前にこれらの文字を取り除く
    ようになった(58番)ことで全TTS系モードでも安全に使えるようになった。"""
    chars = random.choices(
        config.PICTOGRAPH_SCRIPTS, weights=config.PICTOGRAPH_SCRIPT_WEIGHTS
    )[0]
    return lambda: random_pictograph_word(chars)


def _lang_code_for_voice(voice_code):
    """voice_codeがconfig.VOICE_LANGUAGESの中のどの言語のmale/femaleボイス
    コードと一致するか調べ、一致する言語コード(config.VOICE_LANGUAGESの
    キー。例: "ar")を返す。該当しなければNone。

    _native_script_for_voice()・_voice_pitch_for()と同じく、--voice random
    経由でも直接コードを指定した場合でも同じ判定になる。"""
    for lang_code, entry in config.VOICE_LANGUAGES.items():
        if voice_code in (entry["male"], entry["female"]):
            return lang_code
    return None


def _voice_pitch_for(voice_code, gender):
    """espeak-ngへ渡すピッチ(-p)補正値を決める。

    config.FEMALE_VOICE_PITCHはMBROLA由来の女性ボイス("mb-"で始まる
    voice_code)専用の補正。"+f3"フォルマントバリアント由来の女性ボイス
    (config.VOICE_LANGUAGESの他言語)はそれ単体で既に十分な高さになって
    おり、実機で重ねて適用すると高くなりすぎることを確認済みのため対象外
    (config.py VOICE_LANGUAGESのコメント参照)。"""
    if gender == "female" and voice_code.startswith("mb-"):
        return config.FEMALE_VOICE_PITCH
    return None


def _random_unique_word(existing_words, word_generator=random_zalgo_word, max_attempts=20):
    """existing_words に含まれない単語が出るまで生成を試みる。

    組み合わせ数が膨大なので衝突はほぼ起きないが、チャンネルへの重複投稿を
    避けるため念のため再抽選する。max_attempts回試しても衝突する場合は
    (ほぼ起こり得ないが)無限ループを避けるためそのまま返す。"""
    word = word_generator()
    for _ in range(max_attempts - 1):
        if word not in existing_words:
            break
        word = word_generator()
    return word


def _word_generator_for(actual_mode, actual_voice):
    """generate_one()が使う単語生成関数を決める。

    楔形文字・エジプト/アナトリア象形文字の「絵のような」単語
    (_pictograph_word_generator()参照)は、config.PICTOGRAPH_VISUAL_CHANCE
    の確率でglitchモードにのみ選ぶ。

    [罠] 一時期(README「ハマった罠」58番)、_speakable_word()がTTS合成
    直前にこれらの文字を取り除くようになったことで、tts/tts_extreme/
    reverse/robot_voice/telephone/slowed_reverb/nightcore/underwater/
    8d_audio/echo_caveでも「安全」と判断して解禁していた(視聴者からの
    要望)。しかし_pictograph_word_generator()が生成する単語は1つの文字
    体系の文字のみで構成されるため、_speakable_word()適用後は100%の
    確率で空文字列になる。espeak-ngは空文字列でもエラーを出さず
    _stretch_to_min_duration()が最低尺まで引き伸ばすため「実害は無い」と
    見込んでいたが、実際には引き伸ばされるのは完全な無音(-91dB、実機で
    確認済み)であり、動画全体が無音になる実害のある不具合だった
    (視聴者からの報告で発覚、README「ハマった罠」参照)。glitchモードは
    単語の内容と無関係な合成音を使うため、これらの文字体系と安全に
    組み合わせられる唯一のモード。chorus/morse/animaleseは下記の理由で
    対象外。

    chorus/morse/animaleseは、それぞれ「複数言語のボイスで同時に同じ単語を
    読む」「単語の文字をモールス符号のビープ音に変換する」「a〜zの文字
    ごとの録音済み音声をつなげる」という性質上、実在文字体系の単語
    (結合文字を含まない。楔形文字等のピクトグラフ系単語も同じ理由で
    ここに含める)だと不都合がある:
      - chorus: 特定言語の文字体系の単語を、その言語と無関係な他のボイス
        でも同時に読ませることになり、狙いと合わない。
      - morse: morse_synth.MORSE_CODEはラテン文字(+区切り記号4種)のみに
        対応しており、キリル文字・アラビア文字等は変換できない(無視される
        だけで音自体は壊れないが、単語の見た目と音の対応が薄くなる)。
      - animalese: animalese_synth._KEYSもラテン文字(a〜z + "th"/"sh"等)
        のみに対応しており、同じ理由で単語の見た目と音の対応が薄くなる
        (非ラテン文字主体の単語だとほぼ無音になってしまう)。
    そのため3モードとも常にZalgo単語(random_zalgo_word()、土台がラテン
    文字のBASE_CHARSのみ)を使う。

    それ以外(および上記の確率に外れた場合)は従来通り、実在文字体系の
    ボイスならそちらの単語生成(_native_script_for_voice()参照)、無ければ
    Zalgo単語(random_zalgo_word())を使う。"""
    if actual_mode == "glitch" and random.random() < config.PICTOGRAPH_VISUAL_CHANCE:
        return _pictograph_word_generator()
    if actual_mode in ("chorus", "morse", "animalese"):
        return random_zalgo_word
    return _native_script_for_voice(actual_voice) or random_zalgo_word


def generate_one(idx, outdir, mode=config.DEFAULT_MODE, voice=config.DEFAULT_VOICE,
                  speed=config.DEFAULT_SPEED, unit_duration=config.DEFAULT_UNIT_DURATION,
                  repeat=config.DEFAULT_REPEAT, repeat_gap=config.DEFAULT_REPEAT_GAP,
                  fade=config.DEFAULT_FADE, upload=False, privacy_status="public", word=None,
                  pitch=None):
    actual_mode = _resolve_mode(mode)
    actual_voice, voice_label, voice_gender = _resolve_voice(voice)
    voice_pitch = _voice_pitch_for(actual_voice, voice_gender)
    word_generator = _word_generator_for(actual_mode, actual_voice)
    used_native_script = word_generator is not random_zalgo_word

    # --wordで単語を固定した回(コメント欄等からの個別リクエスト対応)かどうかを
    # 後段の無音リトライ判定でも使うため、上書きされる前のwordを覚えておく。
    requested_word = word
    existing_words = None
    if requested_word is None and upload:
        # チャンネルへの重複投稿を避けるため、アップロード済みの単語と
        # 被らないものを選ぶ(--upload時のみ必要な依存関係の遅延importは
        # このファイル内で完結しているのでここでも問題ない)。ループの
        # 各試行で読み直す必要は無いため、ループの前で1回だけ取得する。
        from upload_history import load_upload_history

        existing_words = {entry["word"] for entry in load_upload_history()}

    base = os.path.join(outdir, f"{idx:03d}")
    txt_path = base + "_word.txt"
    raw_wav = base + "_raw.wav"
    rep_wav = base + "_rep.wav"
    str_wav = base + "_str.wav"
    fin_wav = base + ".wav"
    mp3_path = base + ".mp3"
    frame_path = base + "_frame.png"
    video_path = base + ".mp4"

    # 完成した音声が実質無音(_is_silent_audio()参照)だった場合、--word
    # 指定(視聴者リクエスト)でなければ単語を選び直して再試行する
    # (README「ハマった罠」69・70番参照)。glitch以外のTTS系モードで
    # ピクトグラフ単語が選ばれると無音になる不具合が実際に発生したことが
    # きっかけだが、今回判明した原因に限らず今後別の原因で無音の音声が
    # できてしまった場合にも対応できるよう、原因を特定せず「無音なら
    # 単語を変えて作り直す」安全網として汎用的に実装している。
    for attempt in range(1, _SILENCE_RETRY_ATTEMPTS + 1):
        if requested_word is not None:
            # --word指定の回。重複チェック(アップロード済み単語との被り
            # 防止)は対象外(同じ単語を再度指定したい場合もあるため)で、
            # 単語を差し替えての再試行もしない(視聴者の意図と異なる単語を
            # 勝手にアップロードすることになってしまうため)。
            word = requested_word
        elif upload:
            word = _random_unique_word(existing_words, word_generator=word_generator)
        else:
            word = word_generator()
        # 記号だけで構成された単語(_is_symbol_only_word()参照)は、通常の
        # 12文字切り詰めではなく、100文字制限の安全マージンとして確立済みの
        # _TITLE_SENTENCE_SNIPPET_CHARS(20文字)まで見せる(README「ハマった
        # 罠」84番)。
        if _is_symbol_only_word(word):
            label = readable_label(word, max_base_chars=_TITLE_SENTENCE_SNIPPET_CHARS)
        else:
            label = readable_label(word)
        # フレーム表示用は、タイトルのYouTube100文字制限(labelを使う側、言語名
        # 付きテンプレートのworst caseでも実質23文字程度までしか安全に入らない)
        # とは別の制約。フレーム画像自体には文字数の技術的な上限が無く、
        # _word_font_size()側でフォントサイズを文字数に応じて縮小するだけで
        # 済むため、こちらはより長い_FRAME_MAX_BASE_CHARSで別途truncateし直す
        # (--word指定で文章丸ごとのリクエスト(animaleseモード等)が来ても、
        # フレーム上で「Welcome to m...」のように途中で切れないようにするため。
        # README「ハマった罠」63番参照)。
        frame_label = readable_label(word, max_base_chars=_FRAME_MAX_BASE_CHARS)
        frame_word = zalgo_display_word(word, max_base_chars=_FRAME_MAX_BASE_CHARS)

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(word)

        # TTS系モードにはword自体ではなく_speakable_word(word)を渡す
        # (楔形文字等を取り除いた版。_speakable_word()参照)。さらに
        # _speak_symbols_by_name()で、はさみ・音楽記号等のSymbol文字を
        # Unicode正式名称の読み上げに変換し(README「ハマった罠」89番)、
        # cap_combining_marks()で1箇所あたりの結合文字の積み重ねを
        # 制限する(--word直接指定で結合文字を極端に積み重ねると、
        # espeak-ngの読み上げが異常に長くなりShorts判定の3分を超えて
        # しまう問題の対策、README「ハマった罠」91番)。動画フレーム・
        # label・upload_history.json記録にはword自体をそのまま使い続ける。
        tts_word = cap_combining_marks(_speak_symbols_by_name(_speakable_word(word)))
        # 単一ボイスのモード専用に、さらに現在のactual_voiceが対応していない
        # 文字体系(CJK統合漢字・タイ文字・アラビア文字・ヘブライ文字・
        # エチオピア文字)を取り除いた版を用意する
        # (strip_unspeakable_foreign_script()参照、README「ハマった罠」
        # 72・73番)。chorusは複数ボイスを内部で選ぶため、ボイスごとの判定を
        # synthesize_tts_chorus()側で個別に行う(ここでは未加工のtts_wordを
        # そのまま渡す)。
        single_voice_tts_word = strip_unspeakable_foreign_script(tts_word, actual_voice)

        if actual_mode == "tts":
            # espeak-ngが吐く長さがそのまま採用される(パディングはしない)
            synthesize_tts(single_voice_tts_word, raw_wav, voice=actual_voice, speed=speed, pitch=voice_pitch)
        elif actual_mode == "tts_extreme":
            synthesize_tts_extreme(single_voice_tts_word, raw_wav, voice=actual_voice)
        elif actual_mode == "glitch":
            # unit_durationが「1回分」の長さ。--repeatで指定した回数ぶん、
            # これがそのまま繰り返される(動画の総尺は自動的に決まる)
            synthesize_glitch_chunk(raw_wav, target_seconds=unit_duration)
        elif actual_mode == "reverse":
            synthesize_tts_reverse(single_voice_tts_word, raw_wav, voice=actual_voice, speed=speed, pitch=voice_pitch)
        elif actual_mode == "robot_voice":
            synthesize_tts_robot(single_voice_tts_word, raw_wav, voice=actual_voice, speed=speed, pitch=voice_pitch)
        elif actual_mode == "chorus":
            synthesize_tts_chorus(tts_word, raw_wav)
        elif actual_mode == "morse":
            synthesize_morse(word, raw_wav)
        elif actual_mode == "animalese":
            # espeak-ngを使わないため_speakable_word()は不要(対応表に無い
            # 文字は animalese_synth.py 側で無視される。morseと同じ方針)。
            # pitch未指定(None)ならsynthesize_animalese側で毎回ランダムに選ぶ
            synthesize_animalese(word, raw_wav, pitch=pitch)
        elif actual_mode == "telephone":
            synthesize_tts_telephone(single_voice_tts_word, raw_wav, voice=actual_voice, speed=speed, pitch=voice_pitch)
        elif actual_mode == "slowed_reverb":
            synthesize_tts_slowed_reverb(single_voice_tts_word, raw_wav, voice=actual_voice, speed=speed, pitch=voice_pitch)
        elif actual_mode == "nightcore":
            synthesize_tts_nightcore(single_voice_tts_word, raw_wav, voice=actual_voice, speed=speed, pitch=voice_pitch)
        elif actual_mode == "underwater":
            synthesize_tts_underwater(single_voice_tts_word, raw_wav, voice=actual_voice, speed=speed, pitch=voice_pitch)
        elif actual_mode == "8d_audio":
            synthesize_tts_8d_audio(single_voice_tts_word, raw_wav, voice=actual_voice, speed=speed, pitch=voice_pitch)
        elif actual_mode == "echo_cave":
            synthesize_tts_echo_cave(single_voice_tts_word, raw_wav, voice=actual_voice, speed=speed, pitch=voice_pitch)
        else:
            raise ValueError(
                f"unknown mode: {actual_mode!r} "
                "(tts / tts_extreme / glitch / reverse / robot_voice / chorus / morse / "
                "animalese / telephone / slowed_reverb / nightcore / underwater / 8d_audio / "
                "echo_cave)"
            )

        repeat_audio(raw_wav, rep_wav, times=repeat, gap=repeat_gap)
        # 短い単語はモードを問わず(tts_extreme専用のTTS_EXTREME_MIN_DURATION_
        # SECONDSとは別に)繰り返し後の最終的な尺が1〜2秒程度にしかならず、
        # 「発音」として成立していないように見えることがあったため、
        # MIN_FINAL_VIDEO_DURATION_SECONDSを下回る場合はここでさらに引き伸ばす
        # (config.py参照)。
        _stretch_to_min_duration(rep_wav, str_wav, config.MIN_FINAL_VIDEO_DURATION_SECONDS)
        # 無音パディングはしない。中身の実際の長さのまま、末尾だけ短くフェード
        # し、動画の尺もそれに合わせる(build_videoが -shortest で音声側に合わせる)
        finalize_audio(str_wav, fin_wav, fade=fade, fade_in=config.DEFAULT_FADE_IN)
        os.remove(raw_wav)
        os.remove(rep_wav)
        os.remove(str_wav)

        if not _is_silent_audio(fin_wav):
            break

        os.remove(fin_wav)
        if requested_word is not None:
            raise RuntimeError(
                f"{word!r}: 生成された音声が無音でした(--word指定のため、"
                "単語を差し替えての再試行は行いません。運営者による確認が"
                "必要です)"
            )
        if attempt == _SILENCE_RETRY_ATTEMPTS:
            raise RuntimeError(
                f"{word!r}: 生成された音声が{_SILENCE_RETRY_ATTEMPTS}回とも"
                "無音でした(単語を選び直しても無音のため、モード側の問題の"
                "可能性があります)"
            )
        print(f"[Warning] {word!r}: 生成された音声が無音でした"
              f"({attempt}/{_SILENCE_RETRY_ATTEMPTS}回目)。単語を選び直して再試行します。")

    wav_to_mp3(fin_wav, mp3_path)
    build_frame(frame_label, frame_path, mode=actual_mode, display_word=frame_word,
                is_native_script=used_native_script)
    build_video(frame_path, mp3_path, video_path)

    os.remove(fin_wav)
    os.remove(frame_path)

    result = {
        "word": word, "label": label, "video": video_path, "audio": mp3_path,
        "mode": actual_mode, "voice": actual_voice, "voice_label": voice_label,
    }

    if upload:
        # --upload時のみ必要な依存関係(google-api-python-client等)なので
        # 遅延importにして、アップロードしない通常利用に影響しないようにする
        from youtube_upload import upload_video

        # 任意。設定されていれば、説明文に「もっと見る」用の再生リストリンクを
        # 載せて視聴者の回遊(連続視聴)を促す。実際に動画を再生リストへ追加
        # する処理はアップロード成功後(video_id確定後)に別途行う。
        shorts_playlist_id = os.environ.get("YOUTUBE_SHORTS_PLAYLIST_ID")
        lang_code = _lang_code_for_voice(actual_voice)
        voice_label, lang_code = _single_voice_metadata(actual_mode, voice_label, lang_code)
        # ここで先に確定させ、_youtube_metadata()には確定済みの値を渡す
        # (title_template="random"のままだと_youtube_metadata()内部でも
        # 改めて抽選されてしまい、実際に使われたテンプレートが分からなく
        # なる)。repost_shorts.pyが同じ言い回しで通常動画のタイトルを
        # 組み立て直せるよう、upload_history.jsonにも記録する。
        actual_title_template = _resolve_title_template("random")

        title, description, tags, caption_text, comment_text, localizations = _youtube_metadata(
            word, label, actual_mode, playlist_id=shorts_playlist_id, voice_label=voice_label,
            is_native_script=used_native_script, lang_code=lang_code,
            title_template=actual_title_template,
        )
        youtube_url = upload_video(
            video_path, title=title, description=description, tags=tags,
            privacy_status=privacy_status, default_audio_language=lang_code,
            localizations=localizations,
        )
        result["youtube_url"] = youtube_url

        video_id = youtube_url.rsplit("/", 1)[-1]

        # "絵だけ"のミニマルなカスタムサムネイル(frame_builder.build_thumbnail()
        # 参照)。動画本体のフレーム(縦型Shorts)とは別に、キッカー・サブ
        # ラベル・アイコンを省いた単語だけの16:9画像を作りYouTube側に設定
        # する。YouTube側でカスタムサムネイル機能を使うには電話番号確認が
        # 必要なため、config.CUSTOM_THUMBNAIL_ENABLEDがTrueの間だけ動く
        # (README「ハマった罠」参照)。失敗しても動画自体は既に公開済み
        # なので警告に留めて処理は止めない(add_to_playlistと同じ方針)。
        if config.CUSTOM_THUMBNAIL_ENABLED:
            from frame_builder import build_thumbnail
            from youtube_upload import upload_thumbnail

            thumbnail_path = base + "_thumbnail.png"
            try:
                build_thumbnail(frame_label, thumbnail_path, display_word=frame_word)
                upload_thumbnail(video_id, thumbnail_path)
            except Exception as e:
                print(f"[Warning] {word}: カスタムサムネイルのアップロードに失敗しました: {e}")
            finally:
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)

        # 手動字幕(ASRに任せるとでたらめな音声が意味不明な文字起こしになり、
        # 検索インデックス対象のテキストが無駄になるため、代わりにキーワード
        # 付きの固定テキストを入れる)。captions.insertはyoutube.force-ssl
        # スコープが必要(README参照)で無い場合は失敗するが、動画自体は既に
        # 公開済みなので警告に留めて処理は止めない(add_to_playlistと同じ方針)。
        #
        # config.CAPTIONS_ENABLEDがFalseの間はスキップする(実機で断続的な
        # 403 forbiddenを確認したため一時無効化中。README「ハマった罠」参照)。
        if config.CAPTIONS_ENABLED:
            from audio_utils import _probe_duration
            from youtube_upload import upload_caption

            try:
                duration_seconds = _probe_duration(video_path)
                upload_caption(video_id, duration_seconds, caption_text)
            except Exception as e:
                print(f"[Warning] {word}: 字幕のアップロードに失敗しました: {e}")

        # 運営者コメントの自動投稿(_random_comment_text()で選んだcomment_text
        # を使う、caption_textとは別物。captions.insertと同じ
        # youtube.force-sslスコープを使うため、同様に断続的な403 forbiddenが
        # 起きうる(README「ハマった罠」21番)。失敗しても動画自体は既に
        # 公開済みなので警告に留めて処理は止めない。
        if config.COMMENT_ON_UPLOAD_ENABLED:
            from youtube_upload import post_comment

            try:
                post_comment(video_id, comment_text)
            except Exception as e:
                print(f"[Warning] {word}: コメントの投稿に失敗しました: {e}")

        # repost_shorts.pyが後で(この回も含めて)GitHub Actions API経由で
        # このrunのアーティファクトから動画本体を取り出せるよう、video_idを
        # そのままファイル名にしておく(アーティファクト自体のアップロードは
        # このgenerate.py実行の後、ワークフロー側で行う)。
        video_id_path = os.path.join(outdir, f"{video_id}.mp4")
        os.replace(video_path, video_id_path)
        result["video"] = video_id_path

        # アップロードが成功して初めて履歴に記録する(失敗した回を記録すると、
        # 存在しない動画IDが repost_shorts.py の変換対象に紛れ込むため)
        from upload_history import append_upload

        # glitch/chorus/morseは単一の音声言語を持たないため、voice_label/
        # lang_codeは既にNoneに戻してある(_SINGLE_VOICE_MODES参照)。ここで
        # 記録する値は、実際に_youtube_metadata()へ渡してタイトル等の生成に
        # 使った値と常に一致する。
        append_upload(
            word=word, label=label, video_id=video_id, mode=actual_mode,
            run_id=os.environ.get("GITHUB_RUN_ID"),
            voice_label=voice_label, lang_code=lang_code,
            title_template=actual_title_template,
        )

        # 任意。設定されていれば、アップロードした動画をShorts用の再生リストに
        # 追加する(失敗しても動画自体は既に公開済みなので、警告に留めて
        # 処理は止めない)。shorts_playlist_id自体は説明文へのリンク生成のため
        # 上のtitle/description組み立て時に既に読み込み済み。
        if shorts_playlist_id:
            from youtube_upload import add_to_playlist

            try:
                add_to_playlist(video_id, shorts_playlist_id)
            except Exception as e:
                print(f"[Warning] {word}: 再生リストへの追加に失敗しました: {e}")

    return result


def main():
    ap = argparse.ArgumentParser(description="How-to-Pronounce ネタ動画 自動生成")
    ap.add_argument("--count", type=int, default=3, help="生成する本数")
    ap.add_argument("--outdir", type=str, default="./out", help="出力ディレクトリ")
    ap.add_argument("--mode", type=str,
                     choices=["tts", "tts_extreme", "glitch", "reverse", "robot_voice",
                              "chorus", "morse", "animalese", "telephone", "slowed_reverb",
                              "nightcore", "underwater", "8d_audio", "echo_cave", "random"],
                     default=config.DEFAULT_MODE,
                     help="音声の作り方: tts=espeak-ngに単語を読ませる(デフォルト) / "
                          "tts_extreme=奇妙な声+極端なピッチ・速度+ffmpegの歪みフィルタで読ませる / "
                          "glitch=合成グリッチ音を当てる / "
                          "reverse=espeak-ngで読ませた音声をそのまま逆再生する / "
                          "robot_voice=espeak-ngで読ませた音声に搬送波とのリング変調をかける / "
                          "chorus=複数言語のボイスで同時に読み上げて重ねる / "
                          "morse=単語をモールス信号のビープ音に変換する / "
                          "animalese=「どうぶつの森」風に文字ごとの録音済み音声をつなげる / "
                          "telephone=電話回線のような帯域制限をかける / "
                          "slowed_reverb=ゆっくり再生+残響の「slowed + reverb」風にする / "
                          "nightcore=高速化+ピッチアップの「nightcore」風にする / "
                          "underwater=ローパス+揺らぎで水中のような質感にする / "
                          "8d_audio=ステレオ化して左右に音像を回転させる / "
                          "echo_cave=複数タップのエコーで洞窟のような反響を作る / "
                          "random=1本ごとに上記いずれかからランダムに選ぶ")
    ap.add_argument("--voice", type=str, default=config.DEFAULT_VOICE,
                     help="[tts/tts_extreme/reverse/robot_voice/telephone/slowed_reverb/"
                          "nightcore/underwater/8d_audio/echo_cave専用] espeak-ngの声"
                          "(例: en, en-us, ja)。random=1本ごとにconfig.VOICE_LANGUAGESから"
                          "言語・性別をランダムに選ぶ(発音の違いで聞こえ方が変わる)")
    ap.add_argument("--speed", type=int, default=config.DEFAULT_SPEED,
                     help="[tts専用。tts_extremeは毎回ランダムな速度を使うため対象外] "
                          "読み上げ速度(words/min)")
    ap.add_argument("--unit-duration", type=float, default=config.DEFAULT_UNIT_DURATION,
                     help="[glitch専用] 「答え」1回分の長さ(秒)")
    ap.add_argument("--repeat", type=int, default=config.DEFAULT_REPEAT,
                     help="「答え」を何回繰り返すか(デフォルト2回。How-to-Pronounce系動画が"
                          "word...word...のように2回言うことが多いのに合わせている)")
    ap.add_argument("--repeat-gap", type=float, default=config.DEFAULT_REPEAT_GAP,
                     help="繰り返し間の無音の長さ(秒)")
    ap.add_argument("--fade", type=float, default=config.DEFAULT_FADE,
                     help="末尾のフェードアウトの長さ(秒)。無音パディングはせず、"
                          "中身の実際の長さに動画尺を合わせる")
    ap.add_argument("--seed", type=int, default=None, help="乱数シード(再現したい場合)")
    ap.add_argument("--pitch", type=str, choices=["lowest", "low", "med", "high"],
                     default=None,
                     help="[animalese専用] キャラクターボイスの高さを直接指定する"
                          "(lowest=最も低い 〜 high=最も高い)。指定しない場合は"
                          "1本ごとにランダムに選ぶ(「乱数シード」のような分かりにくい"
                          "指定をしなくても、声の高さだけを直接選べるようにしたもの)")
    ap.add_argument("--upload", action="store_true",
                     help="生成した各動画をそのままYouTubeにアップロードする"
                          "(YOUTUBE_CLIENT_ID/YOUTUBE_CLIENT_SECRET/YOUTUBE_REFRESH_TOKEN"
                          "環境変数が必要。get_youtube_refresh_token.py 参照)")
    ap.add_argument("--privacy-status", type=str, choices=["public", "unlisted", "private"],
                     default="public", help="[--upload専用] アップロード時の公開範囲")
    ap.add_argument("--word", type=str, default=None,
                     help="単語をランダム生成せず、指定した文字列をそのまま使う"
                          "(視聴者からのリクエスト対応用)。指定時は--countを1に固定し、"
                          "アップロード済み単語との重複チェックも行わない")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    if args.word is not None:
        args.count = 1

    os.makedirs(args.outdir, exist_ok=True)

    results = []
    failures = []
    try:
        for i in range(1, args.count + 1):
            try:
                r = generate_one(
                    i, args.outdir, mode=args.mode,
                    voice=args.voice, speed=args.speed, unit_duration=args.unit_duration,
                    repeat=args.repeat, repeat_gap=args.repeat_gap, fade=args.fade,
                    upload=args.upload, privacy_status=args.privacy_status, word=args.word,
                    pitch=args.pitch,
                )
            except Exception as e:
                # クォータ超過や一時的なネットワークエラーなどで1本失敗しても、
                # 残りの本数の生成/アップロードまで巻き添えで止めない
                print(f"[{i}/{args.count}] failed: {e}")
                failures.append((i, e))
                continue
            voice_suffix = f" [{r['voice_label']}]" if r["voice_label"] else ""
            print(f"{jst_timestamp()} [{i}/{args.count}] ({r['mode']}){voice_suffix} {r['video']}  <-  {r['label']}")
            if "youtube_url" in r:
                print(f"{jst_timestamp()}     uploaded -> {r['youtube_url']}")
            results.append(r)
    finally:
        close_browser()

    if args.upload and results:
        # 動画ごとにログを出すとN本分埋もれてしまうため、全本処理し終えた
        # このタイミングで1回だけ、実行全体のクォータ消費/残容量をまとめて出す
        from youtube_upload import load_api_usage_from_disk, log_api_usage_summary

        load_api_usage_from_disk()
        log_api_usage_summary()

    if failures:
        print(f"\n{len(failures)}/{args.count} 本が失敗しました:")
        for i, e in failures:
            print(f"  [{i}] {e}")
        sys.exit(1)

    return results


if __name__ == "__main__":
    main()
