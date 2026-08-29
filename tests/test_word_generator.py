"""word_generator.py の純粋関数に対するユニットテスト。
外部コマンド(espeak-ng/ffmpeg/Chromium)は使わない、軽いテストのみ。"""

import random
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DECORATIVE_SYMBOLS, SAFE_COMBINING_BLOCKS
from word_generator import random_zalgo_word, readable_label


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
