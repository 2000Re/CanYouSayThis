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


def test_units_for_word_ignores_combining_marks_and_decorative_symbols():
    # 結合文字(U+0301)や装飾記号(☼)は符号表に無いため無視される
    assert _units_for_word("E" + chr(0x0301) + "☼") == [(True, 1)]


def test_units_for_word_maps_separator_symbols():
    # word_generator.SEPARATOR_SYMBOLSの4記号も符号表に含まれていること
    for sep in ["(", ")", ":", "-"]:
        assert sep in MORSE_CODE
        units = _units_for_word(sep)
        assert len(units) > 0


def test_units_for_word_empty_for_unmapped_only_input():
    assert _units_for_word(chr(0x0301) + "☼") == []


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
    # 対応表に無い文字だけの単語でも例外にならず、最低限のトーン1つで
    # フォールバックすること(通常は起こらないが保険の回帰防止)。
    synthesize_morse(chr(0x0301) + "☼", "/tmp/x.wav", unit_duration=0.05, freq=700)
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
