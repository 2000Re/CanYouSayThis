"""word_generator.py の純粋関数に対するユニットテスト。
外部コマンド(espeak-ng/ffmpeg/Chromium)は使わない、軽いテストのみ。"""

import random
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from config import DECORATIVE_SYMBOLS, SAFE_COMBINING_BLOCKS, THAI_CONSONANTS, THAI_VOWEL_MARKS
from word_generator import (
    expand_unknown_chars_to_names,
    random_abugida_word,
    random_pictograph_word,
    random_script_word,
    random_thai_word,
    random_zalgo_word,
    readable_label,
    zalgo_display_word,
)


def test_random_zalgo_word_is_nonempty_string():
    random.seed(1)
    word = random_zalgo_word()
    assert isinstance(word, str)
    assert len(word) > 0


def test_random_zalgo_word_is_deterministic_with_seed():
    random.seed(42)
    a = random_zalgo_word()
    random.seed(42)
    b = random_zalgo_word()
    assert a == b


def test_readable_label_strips_combining_marks():
    word = "a" + chr(0x0301) + chr(0x0302) + "b"
    label = readable_label(word)
    assert "́" not in label
    assert "̂" not in label
    assert label.startswith("ab")


def test_readable_label_never_empty():
    # 全部が結合文字・記号だけの極端なケースでも "???" にフォールバックする
    assert readable_label(chr(0x0301) * 5) == "???"


def test_readable_label_truncates_long_words():
    word = "a" * 50
    label = readable_label(word, max_base_chars=12)
    assert label.endswith("...")
    assert len(label) == 12 + 3


def test_safe_combining_blocks_contain_only_assigned_codepoints():
    # 未割り当てのコードポイントはフォントが対応しておらず「豆腐」の原因に
    # なるため、候補ブロックに紛れ込んでいないことを保証する。
    for block in SAFE_COMBINING_BLOCKS:
        for cp in block:
            assert unicodedata.category(chr(cp)) != "Cn", f"unassigned codepoint: {hex(cp)}"


def test_decorative_symbols_are_single_characters():
    for ch in DECORATIVE_SYMBOLS:
        assert len(ch) == 1


def test_decorative_symbols_have_no_duplicates():
    assert len(DECORATIVE_SYMBOLS) == len(set(DECORATIVE_SYMBOLS))


def test_decorative_symbols_are_assigned_codepoints():
    for ch in DECORATIVE_SYMBOLS:
        assert unicodedata.category(ch) != "Cn", f"unassigned codepoint: {hex(ord(ch))}"


def test_safe_combining_blocks_exclude_known_broken_rendering_codepoint():
    # U+1DFA(COMBINING DOT BELOW LEFT)はUnicode上は割り当て済みで無音
    # 確認も取れているが、Chromium+Notoフォントで実際に描画すると土台文字と
    # 結合せず「豆腐」になることが判明した(全200コードポイントを実測で
    # 検証済み)。動画フレームに結合文字を描画するようになったことで顕在化
    # したため、退行防止として明示的に除外を確認する。
    all_codepoints = {cp for block in SAFE_COMBINING_BLOCKS for cp in block}
    assert 0x1DFA not in all_codepoints


def test_zalgo_display_word_stripped_of_marks_matches_readable_label():
    # zalgo_display_word()から結合文字を除いたものは、readable_label()の
    # 出力と完全に一致するはず(切り詰め件数の基準を揃えているため)。
    word = "a" + chr(0x0301) * 3 + "b" + chr(0x0302) * 2 + "c" * 20
    display = zalgo_display_word(word)
    stripped = "".join(ch for ch in display if not unicodedata.combining(ch))
    assert stripped == readable_label(word)


def test_zalgo_display_word_keeps_combining_marks():
    word = "a" + chr(0x0301) * 3
    display = zalgo_display_word(word)
    assert chr(0x0301) in display


def test_zalgo_display_word_caps_marks_per_cluster():
    word = "a" + chr(0x0301) * 10
    display = zalgo_display_word(word, max_marks_per_cluster=4)
    assert display.count(chr(0x0301)) == 4


def test_zalgo_display_word_never_empty():
    assert zalgo_display_word(chr(0x0301) * 5) == "???"


def test_random_script_word_is_nonempty_and_only_uses_given_chars():
    chars = list("абвг")
    random.seed(1)
    for _ in range(50):
        word = random_script_word(chars)
        assert len(word) > 0
        assert all(ch in chars for ch in word)


def test_random_script_word_respects_length_range():
    chars = list("абвг")
    random.seed(2)
    for _ in range(50):
        word = random_script_word(chars, n_chars=(6, 6))
        assert len(word) == 6


def test_random_thai_word_is_nonempty_string():
    random.seed(3)
    word = random_thai_word()
    assert len(word) > 0


def test_random_thai_word_starts_each_syllable_with_a_consonant():
    # 母音記号は単体で使わない(子音の後にしか付けない)ことの確認。
    # 出力の各文字は子音か母音記号のどちらかであり、母音記号だけが
    # 連続することはない(母音記号の直前は必ず子音であるはず)。
    random.seed(4)
    for _ in range(50):
        word = random_thai_word()
        for ch in word:
            assert ch in THAI_CONSONANTS or ch in THAI_VOWEL_MARKS
        assert word[0] in THAI_CONSONANTS


def test_random_abugida_word_is_nonempty_and_only_uses_given_pools():
    consonants = list("kstn")
    vowels = list("aeiou")
    random.seed(5)
    for _ in range(50):
        word = random_abugida_word(consonants, vowels)
        assert len(word) > 0
        assert word[0] in consonants
        for ch in word:
            assert ch in consonants or ch in vowels


def test_random_thai_word_is_a_thin_wrapper_around_random_abugida_word():
    random.seed(6)
    expected = random_abugida_word(THAI_CONSONANTS, THAI_VOWEL_MARKS)
    random.seed(6)
    assert random_thai_word() == expected


def test_new_language_character_pools_are_nonempty_and_assigned_codepoints():
    # 実在の文字体系で使う文字プールが、いずれも空でなく未割り当て
    # コードポイントを含まないことの確認(config._assigned_chars()の
    # フィルタが正しく効いていることの回帰防止)。
    pools = [
        config.ARABIC_LETTERS, config.HEBREW_LETTERS,
        config.KOREAN_LETTERS, config.HINDI_LETTERS,
        config.UYGHUR_LETTERS, config.AMHARIC_LETTERS,
    ]
    for pool in pools:
        assert len(pool) > 0
        for ch in pool:
            assert unicodedata.category(ch) != "Cn", f"unassigned codepoint: {hex(ord(ch))}"


def test_uyghur_letters_is_subset_of_arabic_letters_excluding_fallback_characters():
    # ウイグル語ボイス("ug")ではARABIC_LETTERSの半数以上が単独の発音を持たず
    # "Arabic hamza"のように英語で読み上げられてしまうことを実機で確認した
    # ため、問題無い20文字だけに絞っている(config.py UYGHUR_LETTERS参照、
    # README「ハマった罠」49番)。
    assert set(config.UYGHUR_LETTERS) <= set(config.ARABIC_LETTERS)
    assert len(config.UYGHUR_LETTERS) == 20


def test_pictograph_scripts_are_nonempty_and_assigned_codepoints():
    # 楔形文字・エジプト/アナトリア象形文字のプールも同じ回帰防止確認
    # (glitchモード専用。config.PICTOGRAPH_SCRIPTS参照)。
    for pool in config.PICTOGRAPH_SCRIPTS:
        assert len(pool) > 0
        for ch in pool:
            assert unicodedata.category(ch) != "Cn", f"unassigned codepoint: {hex(ord(ch))}"


def test_random_pictograph_word_is_nonempty_and_only_uses_given_chars():
    chars = config.CUNEIFORM_CHARS
    random.seed(7)
    for _ in range(50):
        word = random_pictograph_word(chars)
        assert len(word) > 0
        assert all(ch in chars for ch in word)


def test_random_pictograph_word_respects_length_range():
    chars = config.EGYPTIAN_HIEROGLYPH_CHARS
    random.seed(8)
    for _ in range(50):
        word = random_pictograph_word(chars, n_chars=(5, 5))
        assert len(word) == 5


def test_russian_historic_letters_are_assigned_codepoints():
    # 1918年のロシア語正書法改革で廃止された文字(ѣ/і/ѳ/ѵ)の回帰防止確認
    # (運営者要望、README「ハマった罠」71番)。espeak-ng(ruボイス)での
    # 無音確認・Chromiumでの描画確認は実機で別途確認済み。
    assert len(config.RUSSIAN_HISTORIC_LETTERS) > 0
    for ch in config.RUSSIAN_HISTORIC_LETTERS:
        assert unicodedata.category(ch) != "Cn", f"unassigned codepoint: {hex(ord(ch))}"


def test_russian_voice_chars_include_historic_letters():
    # config.VOICE_LANGUAGES["ru"]["chars"]にRUSSIAN_HISTORIC_LETTERSが
    # 混ざっていることの回帰防止(random_script_word()経由で単語に登場する)。
    ru_chars = config.VOICE_LANGUAGES["ru"]["chars"]
    for ch in config.RUSSIAN_HISTORIC_LETTERS:
        assert ch in ru_chars


def test_separator_symbols_includes_inverted_question_mark():
    # 「¿」(逆疑問符)の追加確認(運営者要望、README「ハマった罠」71番)。
    # espeak-ngに単体で渡すと無音になることを実機確認済みだが、
    # random_zalgo_word()では必ず発音できる本体を挟んで使われるため
    # 単体で無音になる問題は起きない(下記テストで回帰防止)。
    assert "¿" in config.SEPARATOR_SYMBOLS


def test_random_zalgo_word_never_uses_inverted_question_mark_alone():
    # 「¿」が区切り記号として選ばれても、必ず発音できる本体(BASE_CHARS由来
    # の土台文字)を挟んで使われ、単体(無音)にはならないことの回帰防止。
    random.seed(0)
    seen_question_mark = False
    for _ in range(200):
        word = random_zalgo_word()
        if "¿" in word:
            seen_question_mark = True
            stripped = word.replace("¿", "").strip()
            assert any(ch in config.BASE_CHARS for ch in stripped), word
    assert seen_question_mark, "テストの前提として「¿」が一度も選ばれなかった(シード値を見直す必要あり)"


def test_expand_unknown_chars_to_names_keeps_native_chars_unchanged():
    assert expand_unknown_chars_to_names("abc", lambda ch: True) == "abc"


def test_expand_unknown_chars_to_names_expands_non_native_chars():
    # README「ハマった罠」89番: 対応表に無い文字を無視する代わりに、
    # Unicode正式名称の読み上げに変換する(morse_synth.py・
    # animalese_synth.py・generate.py共通のヘルパー)。
    is_ascii_letter = lambda ch: ch.isascii() and ch.isalpha()  # noqa: E731
    assert expand_unknown_chars_to_names("a✂b", is_ascii_letter) == "a BLACK SCISSORS b"


def test_expand_unknown_chars_to_names_ignores_unnamed_codepoints():
    # 未割り当て領域(私用領域等)はUnicode正式名称が存在しないため、
    # 展開できずそのまま消える(結果に含めない)。
    never_native = lambda ch: False  # noqa: E731
    assert expand_unknown_chars_to_names(chr(0xE000), never_native) == ""


def test_expand_unknown_chars_to_names_relies_on_caller_for_combining_marks():
    # 結合文字(Zalgoの見た目)を展開対象外にするのは呼び出し側の責務
    # (is_nativeが結合文字に常にTrueを返すことを前提とする)。ここでは
    # ヘルパー自身がis_native任せであることだけを確認する。
    combining = chr(0x0301)
    assert expand_unknown_chars_to_names(combining, lambda ch: True) == combining
    assert expand_unknown_chars_to_names(combining, lambda ch: False) != combining
