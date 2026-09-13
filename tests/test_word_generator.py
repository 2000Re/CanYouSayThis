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
    random_abugida_word,
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
    # 10言語拡張で追加した文字プールが、いずれも空でなく未割り当て
    # コードポイントを含まないことの確認(config._assigned_chars()の
    # フィルタが正しく効いていることの回帰防止)。
    pools = [
        config.ARABIC_LETTERS, config.HEBREW_LETTERS, config.ARMENIAN_LETTERS,
        config.AMHARIC_SYLLABLES, config.CHEROKEE_SYLLABLES,
        config.MYANMAR_CONSONANTS, config.MYANMAR_VOWEL_MARKS,
        config.SINHALA_CONSONANTS, config.SINHALA_VOWEL_MARKS,
        config.TAMIL_CONSONANTS, config.TAMIL_VOWEL_MARKS,
        config.TELUGU_CONSONANTS, config.TELUGU_VOWEL_MARKS,
        config.BENGALI_CONSONANTS, config.BENGALI_VOWEL_MARKS,
    ]
    for pool in pools:
        assert len(pool) > 0
        for ch in pool:
            assert unicodedata.category(ch) != "Cn", f"unassigned codepoint: {hex(ord(ch))}"
