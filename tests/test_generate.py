"""generate.py の純粋関数(_resolve_mode, _random_unique_word)に対する
ユニットテスト。外部コマンド(espeak-ng/ffmpeg/Chromium)は使わない、
軽いテストのみ。"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import upload_history
from generate import (
    _COMMENT_TEMPLATES,
    _FRAME_MAX_BASE_CHARS,
    _PICTOGRAPH_TITLE,
    _SINGLE_VOICE_MODES,
    _TITLE_SENTENCE_SNIPPET_CHARS,
    _TITLE_TEMPLATES,
    _is_pictograph_word,
    _lang_code_for_voice,
    _mode_genre_suffix,
    _native_script_for_voice,
    _pictograph_word_generator,
    _random_comment_text,
    _random_pictograph_comment_text,
    _random_unique_word,
    _resolve_mode,
    _resolve_title_template,
    _resolve_voice,
    _sanitize_label_for_display,
    _sentence_title_snippet,
    _speakable_word,
    _unposted_lang_codes,
    _voice_pitch_for,
    _word_generator_for,
    _youtube_metadata,
)
from word_generator import random_zalgo_word, readable_label, zalgo_display_word


def _use_empty_upload_history(tmp_path, monkeypatch):
    """_unposted_lang_codes()が実際のupload_history.json(本番の投稿履歴)を
    読んでテスト結果が実行時の履歴に左右されないよう、空の履歴に差し替える。"""
    monkeypatch.setattr(upload_history, "UPLOAD_HISTORY_PATH", str(tmp_path / "upload_history.json"))

REAL_MODES = (
    "tts", "tts_extreme", "glitch", "reverse", "robot_voice", "chorus", "morse", "animalese",
    "telephone", "slowed_reverb", "nightcore", "underwater", "8d_audio", "echo_cave",
)


def test_single_voice_modes_excludes_multi_or_no_voice_modes():
    # default_audio_language・upload_history.jsonのvoice_label/lang_code
    # 記録の対象になるのは「単一の言語・ボイスで実際に発音を読み上げる」
    # モードのみ(generate_one()参照)。
    assert set(_SINGLE_VOICE_MODES) == {
        "tts", "tts_extreme", "reverse", "robot_voice",
        "telephone", "slowed_reverb", "nightcore", "underwater", "8d_audio", "echo_cave",
    }
    assert "glitch" not in _SINGLE_VOICE_MODES
    assert "chorus" not in _SINGLE_VOICE_MODES
    assert "morse" not in _SINGLE_VOICE_MODES
    assert "animalese" not in _SINGLE_VOICE_MODES


def test_resolve_mode_passes_through_tts():
    assert _resolve_mode("tts") == "tts"


def test_resolve_mode_passes_through_glitch():
    assert _resolve_mode("glitch") == "glitch"


def test_resolve_mode_random_always_picks_a_real_mode():
    random.seed(0)
    for _ in range(50):
        assert _resolve_mode("random") in REAL_MODES


def test_resolve_mode_random_can_pick_all_modes():
    # モード数が増えた分、低い重み(1)のモードも十分な確率で拾えるよう
    # 試行回数に余裕を持たせている(300回なら各モード最低1回選ばれる
    # 確率が十分高い)。
    random.seed(0)
    picks = {_resolve_mode("random") for _ in range(300)}
    assert picks == set(config.MODE_LABELS)


def test_resolve_mode_random_weighting_matches_mode_weights():
    # 統計的な検証: 十分な試行回数で、各モードが選ばれる比率が
    # config.MODE_WEIGHTSの相対的な重みに近いことを確認する
    # (MODE_WEIGHTSの値自体が変わっても壊れないよう、動的に読み取って
    # 比較している)。
    random.seed(0)
    trials = 6000
    counts = {mode: 0 for mode in config.MODE_LABELS}
    for _ in range(trials):
        counts[_resolve_mode("random")] += 1

    total_weight = sum(config.MODE_WEIGHTS.get(m, 1) for m in config.MODE_LABELS)
    for mode in config.MODE_LABELS:
        expected_ratio = config.MODE_WEIGHTS.get(mode, 1) / total_weight
        actual_ratio = counts[mode] / trials
        assert abs(actual_ratio - expected_ratio) < 0.03, mode


def test_random_unique_word_returns_first_pick_when_no_collision():
    assert _random_unique_word(set(), word_generator=lambda: "fresh") == "fresh"


def test_random_unique_word_retries_until_not_in_existing():
    picks = iter(["dup", "dup", "unique"])
    assert _random_unique_word({"dup"}, word_generator=lambda: next(picks)) == "unique"


def test_random_unique_word_gives_up_after_max_attempts():
    # 常に衝突する単語しか返らない場合でも無限ループせず、諦めてそのまま返す
    result = _random_unique_word(
        {"always-dup"}, word_generator=lambda: "always-dup", max_attempts=3
    )
    assert result == "always-dup"


def test_random_unique_word_defaults_to_random_zalgo_word():
    # word_generator省略時は、従来通りrandom_zalgo_word()が使われることの確認
    # (同じシードで直接呼んだ場合と同じ結果になるはず)
    random.seed(0)
    expected = random_zalgo_word()
    random.seed(0)
    assert _random_unique_word(set()) == expected


def test_native_script_for_voice_returns_none_for_latin_languages():
    # "script"未設定の言語(英語等)は従来通りNone(random_zalgo_word()を使う)
    assert _native_script_for_voice(config.VOICE_LANGUAGES["en"]["male"]) is None
    assert _native_script_for_voice("en-us") is None


def test_native_script_for_voice_returns_generator_for_cluster_languages():
    # 文字をランダムに並べるだけの言語はrandom_script_word()ベースの
    # 生成関数が返る
    for lang in ("ru", "ar", "he", "ko", "hi", "ug", "am"):
        generator = _native_script_for_voice(config.VOICE_LANGUAGES[lang]["male"])
        assert generator is not None
        word = generator()
        assert len(word) > 0
        assert all(ch in config.VOICE_LANGUAGES[lang]["chars"] for ch in word)


def test_native_script_for_voice_returns_generator_for_abugida_languages():
    # 子音字+母音記号で音節を作る言語はrandom_abugida_word()ベースの
    # 生成関数が返り、子音・母音記号以外の文字は混ざらない
    for lang in ("th",):
        entry = config.VOICE_LANGUAGES[lang]
        generator = _native_script_for_voice(entry["male"])
        assert generator is not None
        word = generator()
        assert len(word) > 0
        allowed = set(entry["consonants"]) | set(entry["vowels"])
        assert all(ch in allowed for ch in word)
        assert word[0] in entry["consonants"]


def test_pictograph_word_generator_picks_one_script_and_stays_within_it():
    # 生成された単語の全文字が、config.PICTOGRAPH_SCRIPTSのどれか1つの
    # プールだけに収まっていること(複数の文字体系が1単語に混ざらないこと)
    # の確認(_pictograph_word_generator()参照)。
    random.seed(9)
    for _ in range(20):
        generator = _pictograph_word_generator()
        word = generator()
        assert len(word) > 0
        assert any(all(ch in pool for ch in word) for pool in config.PICTOGRAPH_SCRIPTS)


def test_pictograph_word_generator_fixes_script_across_repeated_calls():
    # _random_unique_word()の再抽選中に文字体系がぶれず、同じ系統の中で
    # 単語違いを試せることの確認(1回のgenerator()呼び出しごとにプールを
    # 選び直さない)。
    random.seed(10)
    generator = _pictograph_word_generator()
    words = [generator() for _ in range(10)]
    matching_pools = [
        pool for pool in config.PICTOGRAPH_SCRIPTS
        if all(all(ch in pool for ch in word) for word in words)
    ]
    assert len(matching_pools) == 1


def test_pictograph_word_generator_weighting_matches_script_weights():
    # 文字体系の選ばれる比率がconfig.PICTOGRAPH_SCRIPT_WEIGHTSの重みに
    # 従っていること(エジプト・ヒエログリフが他の2倍出やすいこと)の確認。
    random.seed(14)
    trials = 6000
    counts = [0] * len(config.PICTOGRAPH_SCRIPTS)
    for _ in range(trials):
        generator = _pictograph_word_generator()
        word = generator()
        for i, pool in enumerate(config.PICTOGRAPH_SCRIPTS):
            if all(ch in pool for ch in word):
                counts[i] += 1
                break
    total_weight = sum(config.PICTOGRAPH_SCRIPT_WEIGHTS)
    for count, weight in zip(counts, config.PICTOGRAPH_SCRIPT_WEIGHTS):
        expected_ratio = weight / total_weight
        actual_ratio = count / trials
        assert abs(actual_ratio - expected_ratio) < 0.03


def test_word_generator_for_never_uses_pictograph_in_tts_modes():
    # ピクトグラフ生成の単語は_speakable_word()でTTS合成直前に文字が
    # 全て取り除かれ空文字列になる(1つの文字体系のみで構成されるため)。
    # これをglitch以外のTTS系モードで使うと動画全体が無音になる不具合が
    # 実機で確認された(README「ハマった罠」参照)ため、glitch限定に戻した。
    # 常にrandom_zalgo_wordが使われることを確認する(確率的な挙動では
    # ないので、試行回数を抑えて確認すれば十分)。
    random.seed(11)
    en_voice = config.VOICE_LANGUAGES["en"]["male"]
    for mode in ("tts", "tts_extreme", "reverse", "robot_voice", "telephone",
                 "slowed_reverb", "nightcore", "underwater", "8d_audio", "echo_cave"):
        for _ in range(80):
            assert _word_generator_for(mode, en_voice) is random_zalgo_word, mode


def test_word_generator_for_can_use_pictograph_in_glitch_mode():
    # glitchモードでは、十分な試行回数のうちいずれかでピクトグラフ生成
    # (random_zalgo_word以外)が選ばれることの確認(確率的な挙動なので
    # 統計的に確認する)。
    random.seed(12)
    en_voice = config.VOICE_LANGUAGES["en"]["male"]
    picks = [_word_generator_for("glitch", en_voice) for _ in range(80)]
    assert any(g is not random_zalgo_word for g in picks)
    assert any(g is random_zalgo_word for g in picks)


def test_word_generator_for_glitch_weighting_matches_pictograph_chance():
    random.seed(13)
    trials = 4000
    en_voice = config.VOICE_LANGUAGES["en"]["male"]
    pictograph_count = sum(
        1 for _ in range(trials) if _word_generator_for("glitch", en_voice) is not random_zalgo_word
    )
    actual_ratio = pictograph_count / trials
    assert abs(actual_ratio - config.PICTOGRAPH_VISUAL_CHANCE) < 0.03


def test_word_generator_for_chorus_morse_and_animalese_always_use_zalgo():
    # chorus(複数言語同時読み上げ)・morse(ラテン文字のみ対応の符号表)・
    # animalese(a〜zのみ対応)は実在文字体系の単語だと不都合があるため、
    # 常にrandom_zalgo_wordを使う(_word_generator_for()のdocstring参照)。
    # voiceが実在文字体系の言語(例: ロシア語)でも上書きされないことを
    # 確認する。
    random.seed(14)
    ru_voice = config.VOICE_LANGUAGES["ru"]["male"]
    for mode in ("chorus", "morse", "animalese"):
        for _ in range(30):
            assert _word_generator_for(mode, ru_voice) is random_zalgo_word


def test_youtube_metadata_title_contains_label_and_shorts_hashtag():
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "voOn" in title
    assert "#Shorts" in title


def test_youtube_metadata_description_contains_cta():
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "comment" in description.lower()


def test_youtube_metadata_description_contains_hashtags():
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    for hashtag in ("#Shorts", "#Pronunciation", "#Unpronounceable",
                     "#Zalgo", "#GlitchText", "#TextToSpeech", "#TTS", "#Challenge"):
        assert hashtag in description


def test_youtube_metadata_tags_include_mode_and_topic_keywords():
    _title, _description, tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "glitch")
    assert "glitch" in tags
    assert "zalgo" in tags
    assert "text to speech" in tags


def test_youtube_metadata_description_contains_alternate_search_keywords():
    # タイトル・タグの言語名追加(A/B)とは違う切り口の検索キーワード
    # ("tongue twister"/"language learners")を、言語が判明していない回でも
    # 常に含めることの回帰防止。
    _title, description, tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "tongue twister" in description.lower()
    assert "language learners" in description.lower()
    assert "tongue twister" in tags


def test_youtube_metadata_description_contains_subscribe_cta():
    # 新規視聴者がほとんど(コア視聴者0.1%未満)というアナリティクスの偏りを
    # 踏まえ、playlist_idの有無に関わらず常に登録CTAを含める回帰テスト。
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "Subscribe" in description


def test_youtube_metadata_omits_playlist_link_when_not_given():
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "playlist?list=" not in description


def test_youtube_metadata_description_contains_request_length_notice():
    # 761文字という極端に長い--wordリクエストが来たことがきっかけで、
    # 視聴者向けに文字数上限(80文字)を常に案内するようにした
    # (README「ハマった罠」68番)。モードに関わらず常に含める。
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "80 characters or less" in description


def test_youtube_metadata_comment_contains_request_length_notice():
    # descriptionと同じ趣旨の案内を、運営者コメントにも常に自動投稿する
    # (README「ハマった罠」68番)。
    _title, _description, _tags, _caption, comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "80 characters max" in comment


def test_youtube_metadata_comment_request_length_notice_also_applies_to_pictograph_word():
    word = config.CUNEIFORM_CHARS[0] + config.CUNEIFORM_CHARS[1]
    _title, _description, _tags, _caption, comment, _localizations = _youtube_metadata(word, word, "glitch")
    assert "80 characters max" in comment


def test_sanitize_label_for_display_removes_symbol_category_characters():
    # 視聴者リクエスト(音楽記号+はさみ記号+チェス記号混在)で、タイトルに
    # 音楽記号・チェス駒記号・はさみ記号等が紛れ込み、YouTube自身
    # のタイトル表示フォントで豆腐(❓)や意図しない絵文字表示になることが
    # 発覚した(README「ハマった罠」79番)。Symbol系Unicodeカテゴリ
    # (Sm/Sc/Sk/So)だけを取り除くことの回帰防止。結合文字(Mcカテゴリの
    # 音楽記号用コンビニングステム等)はSymbolではないため対象外で残る
    # (README「ハマった罠」80番、除去範囲をSymbolカテゴリのみに絞った
    # 際の仕様)。
    label = "\U0001D1DA✂\U0001D158\U0001D165\U0001D172⚷⚷iǫúụủv"
    assert _sanitize_label_for_display(label) == "\U0001D165\U0001D172iǫúụủv"


def test_sanitize_label_for_display_keeps_non_symbol_punctuation():
    # ꧁/꧂(JAVANESE LEFT/RIGHT RERENGGAN、インターネット上で広く使われる
    # 装飾目的の括弧)はUnicodeカテゴリがPo(Symbolではなく句読点)のため、
    # 豆腐化の実例が無いにも関わらず誤って削除されてしまっていた
    # (README「ハマった罠」80番、動画VFGUo1CKJT8の実例で発覚)。
    label = "꧁ඞ꧂"
    assert _sanitize_label_for_display(label) == label


def test_sanitize_label_for_display_keeps_safe_ascii_punctuation_and_spaces():
    # animaleseモード等、--wordで文章丸ごとのリクエストが来た場合でも、
    # 感嘆符・カンマ・空白のような通常のASCII記号は豆腐/絵文字化しない
    # ため残す。
    label = "!uhUYIHeyoooooooq rb ,HIHih oyoy"
    assert _sanitize_label_for_display(label) == label


def test_sanitize_label_for_display_falls_back_to_question_marks_when_empty():
    assert _sanitize_label_for_display("✂⚷") == "???"


def test_youtube_metadata_title_excludes_symbol_characters_from_label():
    label = "\U0001D1DA✂iv"  # 音楽記号+はさみ記号+通常の文字
    title, _description, _tags, caption, comment, _localizations = _youtube_metadata(
        label, label, "glitch"
    )
    for text in (title, caption, comment):
        assert "✂" not in text
        assert "\U0001D1DA" not in text
        assert "iv" in text


def test_youtube_metadata_includes_playlist_link_when_given():
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", playlist_id="PLexample123"
    )
    assert "https://www.youtube.com/playlist?list=PLexample123" in description


def test_youtube_metadata_omits_voice_line_when_not_given():
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "Voice:" not in description


def test_youtube_metadata_includes_voice_line_when_given():
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", voice_label="French (Female)"
    )
    assert "Voice: French (Female)" in description


def test_youtube_metadata_omits_native_script_note_by_default():
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "not a real word" not in description


def test_youtube_metadata_includes_native_script_note_when_flagged():
    # 実在の文字体系(アラビア文字等)で生成した回は、実在の単語ではなく
    # ランダムな造語である旨を説明文に明記する
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "صغاافك", "صغاافك", "tts", voice_label="Arabic (Male)", is_native_script=True
    )
    assert "not a real word" in description


def test_youtube_metadata_includes_fake_word_note_for_spanish_despite_latin_script():
    # スペイン語(config.VOICE_LANGUAGES["es"]["fake_word_note"])はZalgo単語
    # (is_native_script=False)だが、トルコ語撤去の経緯(README「ハマった罠」
    # 26番)を踏まえ例外的に実在単語ではない旨の注記を出す。
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", voice_label="Spanish (Male)", lang_code="es"
    )
    assert "not a real word" in description


def test_youtube_metadata_omits_fan_made_note_for_non_animalese_modes():
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "fan-made" not in description


def test_youtube_metadata_includes_fan_made_note_for_animalese():
    # 「どうぶつの森」風ボイスが公式音源ではなくファンメイドの模倣合成である旨を
    # 明記し、公式提供コンテンツだという誤解を避ける(README「ハマった罠」62番)。
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "hello", "hello", "animalese"
    )
    assert "fan-made" in description
    assert "not affiliated" in description


def test_youtube_metadata_omits_native_hashtag_when_lang_code_not_given():
    _title, description, tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert description.count("#") == 8
    assert config.VOICE_LANGUAGES["ar"]["hashtag_word"] not in tags


def test_youtube_metadata_includes_native_hashtag_when_lang_code_given():
    # その言語の話者が母語のまま検索して見つけられるよう、「発音」を意味する
    # 現地語ハッシュタグを説明文とtagsの両方に追加する(config.VOICE_LANGUAGES
    # の"hashtag_word"参照)。
    hashtag_word = config.VOICE_LANGUAGES["ar"]["hashtag_word"]
    _title, description, tags, _caption, _comment, _localizations = _youtube_metadata(
        "صغاافك", "صغاافك", "tts", voice_label="Arabic (Male)", lang_code="ar"
    )
    assert f"#{hashtag_word}" in description
    assert hashtag_word in tags


def test_youtube_metadata_omits_native_hashtag_for_languages_without_one():
    # 英語自身はhashtag_wordがNoneなので追加しない(固定の8個の英語
    # ハッシュタグのみになる)
    for lang_code in ("en",):
        assert config.VOICE_LANGUAGES[lang_code]["hashtag_word"] is None
        _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata(
            "word", "word", "tts", lang_code=lang_code
        )
        assert description.count("#") == 8


def test_youtube_metadata_title_includes_language_name_when_lang_code_given():
    # 「french pronunciation」のような言語名込みの検索クエリにタイトル
    # レベルでマッチしやすくするための施策(README参照)。title_templateを
    # 明示的に固定し、ランダムなタイトル言い回し(try_to_sayは"?"を
    # 付けない等)によるテストのflakyさを避ける。
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", voice_label="French (Female)", lang_code="fr",
        title_template="how_to_pronounce",
    )
    assert "in French?" in title


def test_youtube_metadata_title_omits_language_name_when_lang_code_not_given():
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert " in " not in title


def test_mode_genre_suffix_appends_label_for_search_genre_modes():
    # nightcore/8d_audio/slowed_reverbは実際にYouTube上で検索される音楽系
    # ジャンル名のため、タイトルに含めると検索流入が見込める(glitch/reverse
    # 等は加工の技術名であって視聴者が検索する言葉ではないため対象外、
    # 「ハマった罠」45番)。
    assert _mode_genre_suffix("nightcore") == " (Nightcore)"
    assert _mode_genre_suffix("8d_audio") == " (8D Audio)"
    assert _mode_genre_suffix("slowed_reverb") == " (Slowed + Reverb)"


def test_mode_genre_suffix_empty_for_non_genre_modes():
    for mode in ("tts", "tts_extreme", "glitch", "reverse", "robot_voice",
                 "chorus", "morse", "telephone", "underwater", "echo_cave"):
        assert _mode_genre_suffix(mode) == ""


def test_youtube_metadata_title_includes_genre_suffix_for_nightcore():
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "nightcore", title_template="how_to_pronounce",
    )
    assert title == 'How to Pronounce "voOn" (Nightcore) #Shorts'


def test_youtube_metadata_title_omits_genre_suffix_for_non_genre_mode():
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "glitch", title_template="how_to_pronounce",
    )
    assert "(" not in title


def test_youtube_metadata_title_omits_language_name_for_english():
    # 英語はこのチャンネルの既定言語のため、"in English?"は冗長なので付けない
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts", lang_code="en")
    assert " in " not in title


def test_youtube_metadata_tags_include_english_language_pronunciation_tag():
    _title, _description, tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", voice_label="French (Female)", lang_code="fr"
    )
    assert "french pronunciation" in tags


def test_resolve_title_template_passes_through_explicit_value():
    assert _resolve_title_template("can_you_say") == "can_you_say"


def test_resolve_title_template_random_always_picks_a_configured_template():
    random.seed(0)
    for _ in range(50):
        assert _resolve_title_template("random") in config.TITLE_TEMPLATE_WEIGHTS


def test_resolve_title_template_random_weighting_matches_title_template_weights():
    # 統計的な検証: 十分な試行回数で、各言い回しが選ばれる比率が
    # config.TITLE_TEMPLATE_WEIGHTSの相対的な重みに近いことを確認する
    # (test_resolve_mode_random_weighting_matches_mode_weights()と同じ方式)。
    random.seed(0)
    trials = 6000
    counts = {template: 0 for template in config.TITLE_TEMPLATE_WEIGHTS}
    for _ in range(trials):
        counts[_resolve_title_template("random")] += 1

    total_weight = sum(config.TITLE_TEMPLATE_WEIGHTS.values())
    for template, weight in config.TITLE_TEMPLATE_WEIGHTS.items():
        expected_ratio = weight / total_weight
        actual_ratio = counts[template] / trials
        assert abs(actual_ratio - expected_ratio) < 0.03, template


def test_youtube_metadata_title_template_how_to_pronounce():
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", title_template="how_to_pronounce",
    )
    assert title == 'How to Pronounce "voOn" #Shorts'


def test_youtube_metadata_title_template_can_you_say():
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", title_template="can_you_say",
    )
    assert title == 'Can You Say "voOn" #Shorts'


def test_youtube_metadata_title_template_can_you_pronounce():
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", title_template="can_you_pronounce",
    )
    assert title == 'Can You Pronounce "voOn" #Shorts'


def test_youtube_metadata_title_template_try_to_say_omits_question_mark():
    # Try to Sayは命令形であり、How to Pronounce等と違い"?"は付けない
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", title_template="try_to_say",
    )
    assert title == 'Try to Say "voOn" #Shorts'


def test_youtube_metadata_title_template_is_pronounceable():
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", title_template="is_pronounceable",
    )
    assert title == 'Is "voOn" Pronounceable? #Shorts'


def test_youtube_metadata_title_templates_include_language_name_when_given():
    # try_to_sayは疑問形ではないため"?"を付けないが、lang_labelは他の
    # テンプレートと同様に挿入されることの確認。
    for template_name, expected in [
        ("how_to_pronounce", 'How to Pronounce "voOn" in French? #Shorts'),
        ("can_you_say", 'Can You Say "voOn" in French? #Shorts'),
        ("can_you_pronounce", 'Can You Pronounce "voOn" in French? #Shorts'),
        ("try_to_say", 'Try to Say "voOn" in French #Shorts'),
        ("is_pronounceable", 'Is "voOn" Pronounceable in French? #Shorts'),
    ]:
        title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
            "v́oOn", "voOn", "tts", lang_code="fr", title_template=template_name,
        )
        assert title == expected, template_name


def test_title_templates_keys_match_config_weights():
    # _TITLE_TEMPLATES(実装)とconfig.TITLE_TEMPLATE_WEIGHTS(重み設定)の
    # キーがずれていないことの回帰防止(片方だけ更新して不整合になる事故を防ぐ)。
    assert set(_TITLE_TEMPLATES) == set(config.TITLE_TEMPLATE_WEIGHTS)


def test_youtube_metadata_tags_omit_language_pronunciation_tag_when_not_given():
    _title, _description, tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert not any(t.endswith(" pronunciation") for t in tags)


def test_youtube_metadata_description_contains_audience_region_phrases():
    # 視聴者属性で継続的に上位に入っている非英語圏(フィリピン・インドネシア・
    # マレーシア)向けの検索キーワードフレーズを、動画の言語に関わらず常に
    # 含める回帰テスト(config.AUDIENCE_REGION_PHRASES参照)。
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    for _lang, phrase in config.AUDIENCE_REGION_PHRASES:
        assert phrase in description


def test_youtube_metadata_caption_contains_label():
    _title, _description, _tags, caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "voOn" in caption


def test_youtube_metadata_caption_includes_language_name_when_lang_code_given():
    _title, _description, _tags, caption, _comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", voice_label="French (Female)", lang_code="fr"
    )
    assert "in French" in caption


def test_youtube_metadata_caption_omits_language_name_when_lang_code_not_given():
    _title, _description, _tags, caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert " in " not in caption


def test_youtube_metadata_caption_notes_not_a_real_word():
    # 字幕(caption_text)にも「実在の単語ではない/ジョーク」の注記を必ず
    # 入れる回帰確認(運営者コメント用のcomment_textとは別に、字幕自体にも
    # 同じ注記を入れる方針)。
    _title, _description, _tags, caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "not a real word" in caption.lower()
    assert "joke" in caption.lower()


def test_youtube_metadata_caption_notes_not_a_real_word_regardless_of_mode():
    for mode in ("tts", "tts_extreme", "glitch"):
        _title, _description, _tags, caption, _comment, _localizations = _youtube_metadata("v́oOn", "voOn", mode)
        assert "not a real word" in caption.lower()


def test_random_comment_text_picks_from_configured_templates():
    # 固定1パターンだと「ボットの定型文」に見えやすいとの判断で複数
    # パターンをランダムに選ぶようにした(2026-10-13)。_COMMENT_TEMPLATES
    # のいずれかの出力と一致することを確認する回帰テスト。
    expected = {template("voOn", None) for template in _COMMENT_TEMPLATES}
    for _ in range(50):
        assert _random_comment_text("voOn", None) in expected


def test_random_comment_text_varies_across_calls():
    random.seed(1)
    results = {_random_comment_text("voOn", None) for _ in range(50)}
    assert len(results) > 1


def test_random_comment_text_contains_label():
    for _ in range(20):
        assert "voOn" in _random_comment_text("voOn", None)


def test_random_comment_text_includes_language_name_when_given():
    for _ in range(20):
        assert "in French" in _random_comment_text("voOn", "French")


def test_random_comment_text_omits_language_name_when_not_given():
    for _ in range(20):
        assert " in " not in _random_comment_text("voOn", None)


def test_youtube_metadata_comment_is_separate_from_caption():
    # comment_textはcaption_textの使い回しではなく、_random_comment_text()
    # で独立に選ばれる(2026-10-13の分離、caption_textは引き続き字幕専用)。
    # 文字数上限の案内(80文字以内、README「ハマった罠」68番)が末尾に
    # 常に付くため、比較前にその分を取り除く。
    suffix = " Requests: 80 characters max, please! \U0001F4AC"
    expected = {template("voOn", None) for template in _COMMENT_TEMPLATES}
    _title, _description, _tags, caption, comment, _localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts"
    )
    assert comment.endswith(suffix)
    assert comment[: -len(suffix)] in expected
    assert comment != caption


def test_is_pictograph_word_detects_cuneiform_and_hieroglyphs():
    for pool in config.PICTOGRAPH_SCRIPTS:
        assert _is_pictograph_word(pool[0])


def test_is_pictograph_word_false_for_ordinary_words():
    assert not _is_pictograph_word("voOn")
    assert not _is_pictograph_word("v́oOn")


def test_random_pictograph_comment_text_never_contains_placeholder_braces():
    # プレースホルダの埋め忘れ(f文字列の{label}未置換等)の回帰防止。
    for _ in range(20):
        assert "{" not in _random_pictograph_comment_text()


def test_speakable_word_strips_pictograph_chars_only():
    cuneiform = config.CUNEIFORM_CHARS[0]
    word = f"ab{cuneiform}cd"
    assert _speakable_word(word) == "abcd"


def test_speakable_word_returns_empty_string_for_pure_pictograph_word():
    for pool in config.PICTOGRAPH_SCRIPTS:
        assert _speakable_word(pool[0] + pool[1]) == ""


def test_speakable_word_leaves_ordinary_words_unchanged():
    assert _speakable_word("voOn") == "voOn"
    assert _speakable_word("v́oOn") == "v́oOn"


def test_youtube_metadata_omits_word_from_title_for_pictograph_word():
    # 楔形文字・ヒエログリフ系の単語はYouTube自身のフォントが対応しておらず
    # タイトルに生で埋め込むと「豆腐」になるため(2026-10-14に実機で確認)、
    # 単語そのものは埋め込まない(_PICTOGRAPH_TITLE固定文言を使う)。
    word = config.CUNEIFORM_CHARS[0] + config.CUNEIFORM_CHARS[1]
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        word, word, "glitch"
    )
    assert word not in title
    assert title.startswith(_PICTOGRAPH_TITLE)


def test_youtube_metadata_omits_word_from_description_caption_comment_for_pictograph_word():
    word = config.EGYPTIAN_HIEROGLYPH_CHARS[0] + config.EGYPTIAN_HIEROGLYPH_CHARS[1]
    _title, description, _tags, caption, comment, _localizations = _youtube_metadata(
        word, word, "glitch"
    )
    assert word not in description
    assert word not in caption
    assert word not in comment


def test_youtube_metadata_omits_word_from_localizations_for_pictograph_word():
    word = config.ANATOLIAN_HIEROGLYPH_CHARS[0] + config.ANATOLIAN_HIEROGLYPH_CHARS[1]
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata(
        word, word, "glitch"
    )
    assert localizations is not None
    for entry in localizations.values():
        assert word not in entry["title"]


def test_youtube_metadata_still_embeds_word_in_title_for_ordinary_word():
    # 通常の単語(非ピクトグラフ)は従来通りタイトルに埋め込まれることの
    # 回帰防止(今回の変更が誤って全モードに適用されていないことの確認)。
    _title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        "voOn", "voOn", "glitch", title_template="can_you_say"
    )
    assert "voOn" in _title


def test_sentence_title_snippet_cuts_at_word_boundary_for_long_sentence():
    # --wordでの文章丸ごとのリクエスト(animaleseモード等)で、タイトル用の
    # 通常のlabel(readable_label()、12文字)では単語の途中で切れてしまう
    # 場合、単語の区切り(スペース)より手前までを返す(README「ハマった
    # 罠」65番)。
    sentence = "Welcome to my island! I hope you enjoy your stay. Make yourself at home!"
    assert _sentence_title_snippet(sentence) == "Welcome to my..."


def test_sentence_title_snippet_none_for_short_sentence_within_title_limit():
    # スペースを含んでいても、_TITLE_SENTENCE_SNIPPET_CHARS以内に収まる
    # なら切り詰め自体が発生しないため、Noneを返す(呼び出し側は通常の
    # readable_label()の結果をそのまま使う)。
    assert _sentence_title_snippet("say hi") is None


def test_sentence_title_snippet_none_for_long_word_without_spaces():
    # スペースを含まない通常の自動生成単語(zalgo単語等)は、長くても
    # 「文章」ではないため対象外(従来通りの「...」省略のままでよい)。
    assert _sentence_title_snippet("O" * 20) is None


def test_youtube_metadata_embeds_word_boundary_snippet_in_title_for_long_sentence():
    # 文章丸ごとのリクエストでも、単語の途中で切れた断片(「Welcome to
    # m...」)ではなく、単語の区切りまでのスニペット(「Welcome to
    # my...」)がタイトルに埋め込まれる。固定の汎用フレーズ1種類に揃えて
    # しまうと画一的なタイトルになる懸念があったため、通常の単語と同じ
    # _TITLE_TEMPLATESのバリエーションがそのまま活きるようにしてある
    # (README「ハマった罠」65番)。
    sentence = "Welcome to my island! I hope you enjoy your stay. Make yourself at home!"
    title, _description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        sentence, sentence, "animalese", title_template="can_you_say"
    )
    assert "Welcome to my..." in title
    assert "Welcome to m..." not in title
    assert sentence not in title


def test_youtube_metadata_keeps_full_sentence_in_description_for_long_sentence():
    # タイトルには断片しか入らないが、description(Word: {word}の行)には
    # 元々切り詰め無しで全文が入っているため、視聴者が全文を見られること
    # 自体は変わらない。
    sentence = "Welcome to my island! I hope you enjoy your stay. Make yourself at home!"
    _title, description, _tags, _caption, _comment, _localizations = _youtube_metadata(
        sentence, sentence, "animalese"
    )
    assert sentence in description


def test_youtube_metadata_caption_and_comment_use_word_boundary_snippet_for_long_sentence():
    sentence = "Welcome to my island! I hope you enjoy your stay. Make yourself at home!"
    _title, _description, _tags, caption, comment, _localizations = _youtube_metadata(
        sentence, sentence, "animalese"
    )
    assert sentence not in caption
    assert sentence not in comment
    assert "Welcome to m..." not in caption
    assert "Welcome to m..." not in comment


def test_youtube_metadata_localizations_use_word_boundary_snippet_for_long_sentence():
    sentence = "Welcome to my island! I hope you enjoy your stay. Make yourself at home!"
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata(
        sentence, sentence, "animalese"
    )
    assert localizations is not None
    for entry in localizations.values():
        assert sentence not in entry["title"]
        assert "Welcome to m..." not in entry["title"]


def test_youtube_metadata_localizations_includes_japanese_title():
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert localizations is not None
    assert "voOn" in localizations["ja"]["title"]
    assert "#Shorts" in localizations["ja"]["title"]


def test_youtube_metadata_localizations_reuses_description_for_japanese():
    _title, description, _tags, _caption, _comment, localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert localizations["ja"]["description"] == description


def test_youtube_metadata_localizations_includes_japanese_language_name_when_lang_code_given():
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata(
        "v́oOn", "voOn", "tts", voice_label="French (Female)", lang_code="fr"
    )
    assert "フランス語" in localizations["ja"]["title"]


def test_youtube_metadata_localizations_omits_language_name_when_lang_code_not_given():
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "(" not in localizations["ja"]["title"]


def test_youtube_metadata_localizations_wraps_label_in_bidi_isolate():
    # ヘブライ語・アラビア語等のRTL文字がlabelに含まれると、「」直後の
    # 最初の強い方向性を持つ文字になり、タイトル全体の基準方向がRTLと
    # 判定されて語順が入れ替わって見える不具合があった(実際にYouTube上で
    # 確認済み)。First Strong Isolate(U+2068)/Pop Directional Isolate
    # (U+2069)でlabelを囲んで分離していることを回帰確認する。
    hebrew_label = "קקעמדחפ"
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata(
        hebrew_label, hebrew_label, "tts", lang_code="he",
    )
    title_ja = localizations["ja"]["title"]
    assert f"⁨{hebrew_label}⁩" in title_ja


def test_youtube_metadata_localizations_japanese_title_starts_with_strong_ltr_char():
    # bidi isolate(FSI/PDI)で囲むだけでは不十分だった: YouTube側が表示前に
    # ゼロ幅のisolate制御文字を取り除いている可能性が高く、2026-10-09に
    # アップロードされたヘブライ語動画で同じ語順の入れ替わりが実機再発した。
    # 不可視文字が失われても壊れないよう、タイトル文字列の最初の1文字自体を
    # 常に実在の強いLTR文字(ここでは言語名のかな/カナ)にし、鉤括弧「」の
    # ような中立文字を先頭に置かないことを回帰確認する。
    hebrew_label = "קקעמדחפ"
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata(
        hebrew_label, hebrew_label, "tts", lang_code="he",
    )
    title_ja = localizations["ja"]["title"]
    assert title_ja.startswith("ヘブライ語")


def test_youtube_metadata_localizations_bidi_isolate_wraps_any_label():
    # RTL文字かどうかで分岐していない(常にlabelを囲む)ことの確認。
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    title_ja = localizations["ja"]["title"]
    assert "⁨voOn⁩" in title_ja


def test_youtube_metadata_localizations_none_when_both_disabled(monkeypatch):
    monkeypatch.setattr(config, "JAPANESE_TITLE_LOCALIZATION_ENABLED", False)
    monkeypatch.setattr(config, "EXTRA_TITLE_LOCALIZATION_ENABLED", False)
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert localizations is None


def test_youtube_metadata_localizations_japanese_disabled_independently(monkeypatch):
    # 日本語を無効化しても、追加言語ローカライズは独立して有効なまま。
    monkeypatch.setattr(config, "JAPANESE_TITLE_LOCALIZATION_ENABLED", False)
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "ja" not in localizations
    assert "id" in localizations


def test_youtube_metadata_localizations_extra_disabled_independently(monkeypatch):
    # 追加言語ローカライズを無効化しても、日本語は独立して有効なまま。
    monkeypatch.setattr(config, "EXTRA_TITLE_LOCALIZATION_ENABLED", False)
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "ja" in localizations
    assert "id" not in localizations
    assert "fil" not in localizations
    assert "ms" not in localizations


def test_youtube_metadata_localizations_includes_extra_languages():
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    for lang_code in config.EXTRA_TITLE_LOCALIZATIONS:
        assert lang_code in localizations
        assert "voOn" in localizations[lang_code]["title"]
        assert "#Shorts" in localizations[lang_code]["title"]


def test_youtube_metadata_localizations_extra_languages_reuse_description():
    _title, description, _tags, _caption, _comment, localizations = _youtube_metadata("v́oOn", "voOn", "tts")
    for lang_code in config.EXTRA_TITLE_LOCALIZATIONS:
        assert localizations[lang_code]["description"] == description


def test_youtube_metadata_localizations_extra_languages_wrap_label_in_bidi_isolate():
    hebrew_label = "קקעמדחפ"
    _title, _description, _tags, _caption, _comment, localizations = _youtube_metadata(
        hebrew_label, hebrew_label, "tts", lang_code="he",
    )
    for lang_code in config.EXTRA_TITLE_LOCALIZATIONS:
        assert f"⁨{hebrew_label}⁩" in localizations[lang_code]["title"]


def test_lang_code_for_voice_returns_none_for_unknown_code():
    assert _lang_code_for_voice("en-us") is None


def test_lang_code_for_voice_matches_male_and_female_codes():
    for lang_code, entry in config.VOICE_LANGUAGES.items():
        assert _lang_code_for_voice(entry["male"]) == lang_code
        assert _lang_code_for_voice(entry["female"]) == lang_code


def test_resolve_voice_passes_through_explicit_code():
    assert _resolve_voice("en-us") == ("en-us", None, None)


def test_resolve_voice_detects_gender_for_explicit_known_female_code():
    # --voice randomを経由せず直接女性ボイスのコードを指定した場合でも、
    # ピッチ補正(config.FEMALE_VOICE_PITCH)が効くようgenderは検出される。
    code, label, gender = _resolve_voice(config.VOICE_LANGUAGES["fr"]["female"])
    assert code == config.VOICE_LANGUAGES["fr"]["female"]
    assert label is None
    assert gender == "female"


def test_resolve_voice_explicit_male_code_has_no_gender():
    code, label, gender = _resolve_voice(config.VOICE_LANGUAGES["fr"]["male"])
    assert gender is None


def test_resolve_voice_random_always_returns_a_known_code_and_label():
    random.seed(0)
    for _ in range(50):
        code, label, gender = _resolve_voice("random")
        all_codes = {
            entry[g]
            for entry in config.VOICE_LANGUAGES.values()
            for g in ("male", "female")
            if entry[g]
        }
        assert code in all_codes
        assert label is not None
        assert gender in ("male", "female")


def test_voice_languages_avoid_known_broken_zh_alias():
    # "zh"はespeak-ngのエイリアスとしてボイス単体では動くが、"+バリアント名"
    # を付けると"voice does not exist"エラーになる不具合が実機(全23言語×
    # 男女×EXTREME_VOICE_VARIANTS全種の総当たり)で見つかった。本来のコード
    # "cmn"は単体・バリアント付与どちらも動く。tts_extremeモードでランダムに
    # バリアントが付与されるため、"zh"を再度使わないようにする回帰防止。
    for entry in config.VOICE_LANGUAGES.values():
        assert entry["male"] != "zh"
        assert entry["female"] != "zh"


def test_all_voice_languages_have_both_genders():
    # 10言語拡張時の改善で、MBROLA非対応言語にも"+f3"フォルマント
    # バリアントで疑似的な女性ボイスを割り当てたため、全言語がmale/female
    # 両方を持つはずであることの回帰防止(config.VOICE_LANGUAGES参照)。
    for code, entry in config.VOICE_LANGUAGES.items():
        assert entry["male"], code
        assert entry["female"], code


def test_resolve_voice_random_picks_from_native_script_pool_below_threshold(monkeypatch, tmp_path):
    # random.random() が NATIVE_SCRIPT_VOICE_CHANCE 未満のときは、実在の
    # 文字体系を使う言語のプールから選ばれる(config._resolve_voice()参照)。
    # 投稿済み言語の優先ロジック(_unposted_lang_codes())は本テストの対象
    # 外なので、空の履歴にして無効化する。
    _use_empty_upload_history(tmp_path, monkeypatch)
    native_codes = [c for c, e in config.VOICE_LANGUAGES.items() if e["script"] is not None]

    def fake_choice(seq):
        seq = list(seq)
        if seq == native_codes:
            return "ar"
        assert "female" in seq
        return seq[0]

    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "choice", fake_choice)
    code, label, gender = _resolve_voice("random")
    assert code == config.VOICE_LANGUAGES["ar"]["male"]
    assert label.startswith("Arabic")


def test_resolve_voice_random_picks_from_latin_pool_above_threshold(monkeypatch, tmp_path):
    # random.random() が NATIVE_SCRIPT_VOICE_CHANCE 以上のときは、ラテン文字
    # (Zalgo)系の言語のプールから選ばれる。
    _use_empty_upload_history(tmp_path, monkeypatch)
    latin_codes = [c for c, e in config.VOICE_LANGUAGES.items() if e["script"] is None]

    def fake_choice(seq):
        seq = list(seq)
        if seq == latin_codes:
            return "fr"
        assert "female" in seq
        return seq[0]

    monkeypatch.setattr(random, "random", lambda: 0.999)
    monkeypatch.setattr(random, "choice", fake_choice)
    code, label, gender = _resolve_voice("random")
    assert code == config.VOICE_LANGUAGES["fr"]["male"]
    assert label.startswith("French")


def test_resolve_voice_random_can_pick_female_when_available(monkeypatch, tmp_path):
    _use_empty_upload_history(tmp_path, monkeypatch)
    latin_codes = [c for c, e in config.VOICE_LANGUAGES.items() if e["script"] is None]

    def fake_choice(seq):
        seq = list(seq)
        if seq == latin_codes:
            return "fr"
        assert "female" in seq
        return "female"

    monkeypatch.setattr(random, "random", lambda: 0.999)
    monkeypatch.setattr(random, "choice", fake_choice)
    code, label, gender = _resolve_voice("random")
    assert code == config.VOICE_LANGUAGES["fr"]["female"]
    assert gender == "female"
    assert "Female" in label


def test_resolve_voice_random_weighting_matches_native_script_chance(monkeypatch, tmp_path):
    # 統計的な検証: 十分な試行回数で、実在文字体系言語が選ばれる比率が
    # config.NATIVE_SCRIPT_VOICE_CHANCEに近いことを確認する。プール内の
    # 言語選択(投稿済み優先ロジック)は対象外なので、空の履歴にして無効化
    # する(実行時点の本番投稿履歴に結果が左右されないようにする意味もある)。
    _use_empty_upload_history(tmp_path, monkeypatch)
    random.seed(0)
    native_codes = {c for c, e in config.VOICE_LANGUAGES.items() if e["script"] is not None}
    trials = 3000
    hits = 0
    for _ in range(trials):
        code, _label, _gender = _resolve_voice("random")
        lang_code = next(
            c for c, e in config.VOICE_LANGUAGES.items() if code in (e["male"], e["female"])
        )
        if lang_code in native_codes:
            hits += 1
    ratio = hits / trials
    assert abs(ratio - config.NATIVE_SCRIPT_VOICE_CHANCE) < 0.05


def test_unposted_lang_codes_filters_out_already_posted_codes(monkeypatch, tmp_path):
    monkeypatch.setattr(upload_history, "UPLOAD_HISTORY_PATH", str(tmp_path / "upload_history.json"))
    upload_history.save_upload_history([
        {"word": "a", "label": "a", "video_id": "v1", "mode": "tts", "lang_code": "fr"},
        {"word": "b", "label": "b", "video_id": "v2", "mode": "tts", "lang_code": "de"},
        # lang_codeキー自体が無い古い形式のエントリも、Noneとして安全に扱う
        {"word": "c", "label": "c", "video_id": "v3", "mode": "glitch"},
    ])
    assert _unposted_lang_codes(["fr", "de", "ja"]) == ["ja"]


def test_unposted_lang_codes_returns_all_when_history_empty(monkeypatch, tmp_path):
    _use_empty_upload_history(tmp_path, monkeypatch)
    assert _unposted_lang_codes(["fr", "de", "ja"]) == ["fr", "de", "ja"]


def test_resolve_voice_random_prioritizes_unposted_language_in_pool(monkeypatch, tmp_path):
    # いままで一度も投稿されていない言語(ここでは"ug")がプール内にあれば、
    # 均等抽選ではなく必ずそちらが選ばれる(ユーザー要望: 新規追加言語が
    # なかなか抽選されない問題への対策)。
    monkeypatch.setattr(upload_history, "UPLOAD_HISTORY_PATH", str(tmp_path / "upload_history.json"))
    native_codes = [c for c, e in config.VOICE_LANGUAGES.items() if e["script"] is not None]
    # "ug"以外の実在文字体系言語は全て投稿済みにしておく
    upload_history.save_upload_history([
        {"word": "x", "label": "x", "video_id": f"v{i}", "mode": "tts", "lang_code": code}
        for i, code in enumerate(c for c in native_codes if c != "ug")
    ])
    monkeypatch.setattr(random, "random", lambda: 0.0)  # 必ず実在文字体系プールを選ぶ

    for _ in range(20):
        code, label, _gender = _resolve_voice("random")
        assert code in (config.VOICE_LANGUAGES["ug"]["male"], config.VOICE_LANGUAGES["ug"]["female"])
        assert label.startswith("Uyghur")


def test_resolve_voice_random_falls_back_to_full_pool_once_all_posted(monkeypatch, tmp_path):
    # プール内の全言語が投稿済みになれば、通常の均等抽選に戻る
    # (_unposted_lang_codes()が空リストを返すため)。
    monkeypatch.setattr(upload_history, "UPLOAD_HISTORY_PATH", str(tmp_path / "upload_history.json"))
    native_codes = [c for c, e in config.VOICE_LANGUAGES.items() if e["script"] is not None]
    upload_history.save_upload_history([
        {"word": "x", "label": "x", "video_id": f"v{i}", "mode": "tts", "lang_code": code}
        for i, code in enumerate(native_codes)
    ])
    monkeypatch.setattr(random, "random", lambda: 0.0)

    random.seed(0)
    seen_codes = set()
    for _ in range(200):
        code, _label, _gender = _resolve_voice("random")
        seen_codes.add(code)
    # 投稿済み優先ロジックが無効化されていれば、実在文字体系プールの複数の
    # 言語が選ばれるはず(1言語に固定されない)。
    assert len(seen_codes) > 1


def test_voice_pitch_for_boosts_only_mbrola_female_voices():
    # config.FEMALE_VOICE_PITCHはMBROLA由来("mb-"で始まる)女性ボイス専用。
    # "+f3"フォルマントバリアント由来の女性ボイスは対象外(重ねると
    # 高くなりすぎるため)。
    assert _voice_pitch_for("mb-us1", "female") == config.FEMALE_VOICE_PITCH
    assert _voice_pitch_for("ar+f3", "female") is None
    assert _voice_pitch_for("en", "male") is None
    assert _voice_pitch_for("mb-us1", None) is None


def test_frame_max_base_chars_is_longer_than_a_realistic_sentence():
    # --wordで文章丸ごとのリクエスト(animaleseモード等)が来た場合でも、
    # フレーム表示(readable_label()/zalgo_display_word()に_FRAME_MAX_
    # BASE_CHARSを渡す側)で途中で切れないことの確認
    # (README「ハマった罠」63番)。
    sentence = "Welcome to my island! I hope you enjoy your stay. Make yourself at home!"
    assert len(sentence) <= _FRAME_MAX_BASE_CHARS
    assert readable_label(sentence, max_base_chars=_FRAME_MAX_BASE_CHARS) == sentence
    assert zalgo_display_word(sentence, max_base_chars=_FRAME_MAX_BASE_CHARS) == sentence


def test_frame_max_base_chars_is_too_long_to_safely_embed_in_a_title():
    # 一方で、_FRAME_MAX_BASE_CHARSはYouTubeタイトルの100文字制限を守る
    # ためのreadable_label()の既定値(12文字、titleに使う側)とは別物で、
    # そのままtitleに使うと長すぎることの確認(_FRAME_MAX_BASE_CHARSを
    # titleの組み立てに流用しないようにする回帰防止)。
    longest_lang_label = max(v["label"] for v in config.VOICE_LANGUAGES.values())
    worst_case_overhead = max(
        len(fn("", longest_lang_label)) for fn in _TITLE_TEMPLATES.values()
    ) + len(" (Slowed + Reverb) #Shorts")
    assert _FRAME_MAX_BASE_CHARS + worst_case_overhead > 100


def test_title_sentence_snippet_chars_stays_within_the_100_char_title_limit():
    # _TITLE_SENTENCE_SNIPPET_CHARS(文章スニペットの文字数上限)は、
    # _FRAME_MAX_BASE_CHARSとは逆に、YouTubeタイトルの100文字制限の
    # worst case(最長の言語名+最長のタイトルテンプレート+ジャンル
    # サフィックス+" #Shorts")でも安全に収まることの確認
    # (README「ハマった罠」65番)。
    longest_lang_label = max(v["label"] for v in config.VOICE_LANGUAGES.values())
    snippet_placeholder = "a" * _TITLE_SENTENCE_SNIPPET_CHARS
    worst_case_title_length = max(
        len(fn(snippet_placeholder, longest_lang_label)) for fn in _TITLE_TEMPLATES.values()
    ) + len(" (Slowed + Reverb) #Shorts")
    assert worst_case_title_length <= 100
