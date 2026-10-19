"""morse_synth.py の純粋関数に対するユニットテスト。
実際のffmpeg実行はしない(synthesize_morseはsubprocess.runをモックして、
組み立てられたfilter_complex文字列だけ検証する)。"""

import random
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from morse_synth import MORSE_CODE, _units_for_word, synthesize_morse


def test_units_for_word_maps_simple_letter_to_dit():
    # "E"は国際モールス符号で最短の"."(1ユニットのトーン)
    assert _units_for_word("E") == [(True, 1)]


def test_units_for_word_maps_dash_letter():
    # "T"は"-"(3ユニットのトーン)
    assert _units_for_word("T") == [(True, 3)]


def test_units_for_word_inserts_intra_character_gap():
    # "A" = ".-" -> トーン1、要素間ギャップ(1ユニット)、トーン3
    assert _units_for_word("A") == [(True, 1), (False, 1), (True, 3)]


def test_units_for_word_inserts_inter_character_gap():
    # 2文字("E"."T")の間には3ユニットの無音が入る
    units = _units_for_word("ET")
    assert units == [(True, 1), (False, 3), (True, 3)]


def test_units_for_word_inserts_inter_word_gap_for_space():
    units = _units_for_word("E T")
    assert units == [(True, 1), (False, 7), (True, 3)]


def test_units_for_word_is_case_insensitive():
    assert _units_for_word("e") == _units_for_word("E")


def test_units_for_word_ignores_combining_marks():
    # 結合文字(U+0301)は符号表に無いため無視される(Zalgo単語の読み上げ・
    # リズムが、装飾記号の展開(README「ハマった罠」89番)によって変わって
    # しまわないようにするための挙動)
    assert _units_for_word("E" + chr(0x0301)) == [(True, 1)]


def test_units_for_word_expands_decorative_symbol_to_unicode_name():
    # 符号表に無い装飾記号(☼)は無視されるのではなく、Unicode正式名称
    # "WHITE SUN WITH RAYS"に展開してから符号化される(README「ハマった罠」
    # 89番)。無視していた旧実装では[(True, 1)](Eの分だけ)になっていた。
    units = _units_for_word("E☼")
    assert units[:1] == [(True, 1)]
    assert len(units) > 1


def test_units_for_word_maps_separator_symbols():
    # word_generator.SEPARATOR_SYMBOLSのうちITU符号表に実在する4記号は
    # 符号表に含まれていること
    for sep in ["(", ")", ":", "-"]:
        assert sep in MORSE_CODE
        units = _units_for_word(sep)
        assert len(units) > 0


def test_units_for_word_maps_digits():
    # 0-9はITU国際モールス符号表に正式な割り当てがあり、符号表に直接
    # 含まれる(README「ハマった罠」89番、視聴者リクエストの顔文字
    # Ψ( ` 皿 ´ )Ψのような記号混在の単語でもmorseモードが選べるようにする
    # 一環)。
    for digit, code in [("0", "-----"), ("1", ".----"), ("9", "----.")]:
        assert MORSE_CODE[digit] == code
        assert _units_for_word(digit)


def test_units_for_word_expands_inverted_question_mark_separator():
    # 「¿」(SEPARATOR_SYMBOLS、71番で追加)はITU国際モールス符号表に
    # 割り当てが無いため、Unicode正式名称"INVERTED QUESTION MARK"に
    # 展開してから符号化される(README「ハマった罠」89番)。
    assert "¿" not in MORSE_CODE
    # 展開後は前後に半角スペースが付く(expand_unknown_chars_to_names()の
    # 仕様。隣接する文字と結合しないようにするためのもので、単独の文字が
    # 対象の場合は単語末尾に追加の無音ギャップが入る)
    assert _units_for_word("¿") == _units_for_word(" INVERTED QUESTION MARK ")
    assert _units_for_word("¿") != []


def test_units_for_word_empty_for_unmapped_only_input():
    # 未割り当て領域(U+E000、私用領域)はUnicode正式名称が存在しない
    # ため、展開しようとしても何も読み方が無く、結局無視される
    # (結合文字と同様)。
    assert _units_for_word(chr(0x0301) + chr(0xE000)) == []


def test_morse_code_table_only_uses_dots_and_dashes():
    for code in MORSE_CODE.values():
        assert set(code) <= {".", "-"}
        assert len(code) > 0


@patch("morse_synth.subprocess.run")
def test_synthesize_morse_builds_concat_filter_matching_unit_count(mock_run):
    random.seed(1)
    synthesize_morse("ET", "/tmp/x.wav", unit_duration=0.05, freq=700)
    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    # "ET" -> 3要素(トーン, 無音, トーン)のはず
    assert filter_complex.count("concat=n=") == 1
    assert "concat=n=3" in filter_complex


@patch("morse_synth.subprocess.run")
def test_synthesize_morse_uses_given_frequency_for_tones(mock_run):
    synthesize_morse("E", "/tmp/x.wav", unit_duration=0.05, freq=440)
    cmd = mock_run.call_args[0][0]
    assert any("sine=frequency=440" in tok for tok in cmd)


@patch("morse_synth.subprocess.run")
def test_synthesize_morse_falls_back_to_single_tone_for_unmapped_only_word(mock_run):
    # 展開してもUnicode正式名称が存在しない文字だけの単語でも例外になら
    # ず、最低限のトーン1つでフォールバックすること(通常は起こらないが
    # 保険の回帰防止)。
    synthesize_morse(chr(0x0301) + chr(0xE000), "/tmp/x.wav", unit_duration=0.05, freq=700)
    cmd = mock_run.call_args[0][0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=1" in filter_complex


@patch("morse_synth.subprocess.run")
def test_synthesize_morse_default_unit_duration_and_freq_vary(mock_run):
    random.seed(2)
    freqs = set()
    for _ in range(30):
        synthesize_morse("E", "/tmp/x.wav")
        cmd = mock_run.call_args[0][0]
        src = next(tok for tok in cmd if tok.startswith("sine="))
        freqs.add(src)
    assert len(freqs) > 1
