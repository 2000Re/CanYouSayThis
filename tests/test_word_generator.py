"""word_generator.py の純粋関数に対するユニットテスト。
外部コマンド(espeak-ng/ffmpeg/Chromium)は使わない、軽いテストのみ。"""

import random
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DECORATIVE_SYMBOLS, SAFE_COMBINING_BLOCKS
from word_generator import random_zalgo_word, readable_label, zalgo_display_word


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
