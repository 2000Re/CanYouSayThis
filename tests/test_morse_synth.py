"""morse_synth.py の純粋関数に対するユニットテスト。
ffmpeg呼び出し(synthesize_morse_chunk)は使わない、軽いテストのみ。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from morse_synth import MAX_MORSE_LETTERS, MORSE_CODE, _build_morse_segments, word_to_morse_letters


def test_word_to_morse_letters_encodes_known_word():
    assert word_to_morse_letters("SOS") == [MORSE_CODE["S"], MORSE_CODE["O"], MORSE_CODE["S"]]


def test_word_to_morse_letters_is_case_insensitive():
    assert word_to_morse_letters("sos") == word_to_morse_letters("SOS")


def test_word_to_morse_letters_ignores_combining_marks_and_symbols():
    word = "a" + chr(0x0301) + "(b)" + ":"
    assert word_to_morse_letters(word) == [MORSE_CODE["A"], MORSE_CODE["B"]]


def test_word_to_morse_letters_returns_empty_for_no_alnum_chars():
    word = chr(0x0301) + "(" + ")" + "☼"
    assert word_to_morse_letters(word) == []


def test_word_to_morse_letters_truncates_long_runs():
    # word_generatorは同じ母音を何十文字も連打することがあるため、
    # 先頭MAX_MORSE_LETTERS文字ぶんで打ち切られることを確認する
    # (打ち切らないと1単語で尺が数十秒に伸びてしまう)。
    word = "O" * 50
    letters = word_to_morse_letters(word)
    assert len(letters) == MAX_MORSE_LETTERS
    assert all(code == MORSE_CODE["O"] for code in letters)


def test_build_morse_segments_single_dot():
    segments = _build_morse_segments([MORSE_CODE["E"]], unit=0.1, freq=600)
    assert segments == [("sine=frequency=600:duration=0.1", 0.1)]


def test_build_morse_segments_dash_is_triple_unit():
    segments = _build_morse_segments([MORSE_CODE["T"]], unit=0.1, freq=600)
    assert segments == [("sine=frequency=600:duration=0.30000000000000004", 0.30000000000000004)]


def test_build_morse_segments_inserts_intra_letter_gap():
    # "A" = ".-" -> dot, gap(1unit), dash
    segments = _build_morse_segments([MORSE_CODE["A"]], unit=0.1, freq=600)
    assert len(segments) == 3
    assert segments[1][0] == "anullsrc=r=44100:cl=mono:d=0.1"


def test_build_morse_segments_inserts_inter_letter_gap():
    # "E" "E" -> dot, gap(3unit), dot (文字間ギャップのみ、符号間ギャップは無い)
    segments = _build_morse_segments([MORSE_CODE["E"], MORSE_CODE["E"]], unit=0.1, freq=600)
    assert len(segments) == 3
    assert segments[1][0] == "anullsrc=r=44100:cl=mono:d=0.30000000000000004"


def test_build_morse_segments_empty_letters_returns_empty():
    assert _build_morse_segments([], unit=0.1, freq=600) == []
