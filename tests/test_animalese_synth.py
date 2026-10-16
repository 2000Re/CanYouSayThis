"""animalese_synth.py の純粋関数に対するユニットテスト。
実際のpydub/ffmpeg処理は行わない(synthesize_animaleseはAudioSegment.
from_wavをモックして、呼び出されたパス・最終的なexport()呼び出しだけ
検証する。他のsynthモジュールのテストと同じ方針)。"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from animalese_synth import PITCH_PRESETS, _infiles_for_word, _sound_path, synthesize_animalese


def test_sound_path_maps_letters_to_expected_filenames():
    assert _sound_path("med", "a").endswith("animalese_sounds/med/sound01.wav")
    assert _sound_path("med", "z").endswith("animalese_sounds/med/sound26.wav")
    assert _sound_path("high", "th").endswith("animalese_sounds/high/sound27.wav")
    assert _sound_path("high", "sh").endswith("animalese_sounds/high/sound28.wav")


def test_infiles_for_word_maps_simple_letters():
    infiles = _infiles_for_word("cat", "med")
    assert infiles == [
        _sound_path("med", "c"), _sound_path("med", "a"), _sound_path("med", "t"),
    ]


def test_infiles_for_word_is_case_insensitive():
    assert _infiles_for_word("CAT", "med") == _infiles_for_word("cat", "med")


def test_infiles_for_word_detects_sh_digraph():
    # "sh" -> 1つの音(sとhをそれぞれ別々には読まない)
    assert _infiles_for_word("sh", "med") == [_sound_path("med", "sh")]


def test_infiles_for_word_detects_th_digraph():
    assert _infiles_for_word("th", "med") == [_sound_path("med", "th")]


def test_infiles_for_word_skips_repeated_letters():
    # 直前と同じ文字が連続する場合はスキップ(animalese特有の挙動、
    # animalese.py元実装を踏襲)
    assert _infiles_for_word("aa", "med") == [_sound_path("med", "a")]
    assert _infiles_for_word("aaa", "med") == [_sound_path("med", "a")]


def test_infiles_for_word_maps_comma_and_question_mark_to_period_sound():
    assert _infiles_for_word(",", "med") == [_sound_path("med", ".")]
    assert _infiles_for_word("?", "med") == [_sound_path("med", ".")]


def test_infiles_for_word_ignores_combining_marks_and_non_latin_chars():
    # 結合文字(Zalgoの見た目)・非ラテン文字(キリル文字・楔形文字等)は
    # 対応表に無いため無視される(morse_synth.pyと同じ方針)
    assert _infiles_for_word("a" + chr(0x0301) + "b", "med") == [
        _sound_path("med", "a"), _sound_path("med", "b"),
    ]
    assert _infiles_for_word("крепость", "med") == []
    assert _infiles_for_word(chr(0x12042), "med") == []  # cuneiform


def test_infiles_for_word_empty_for_unmapped_only_input():
    assert _infiles_for_word(chr(0x0301) + "☼", "med") == []


class _FakeSegment:
    """pydub.AudioSegmentの代わりに使う最小限のフェイク。実際の音声処理は
    行わず、呼び出し履歴だけ記録する。"""

    def __init__(self, frame_rate=22050, raw_data=b"\x00\x01"):
        self.frame_rate = frame_rate
        self.raw_data = raw_data
        self.exported = None

    def _spawn(self, raw_data, overrides=None):
        return _FakeSegment(frame_rate=overrides.get("frame_rate", self.frame_rate), raw_data=raw_data)

    def set_frame_rate(self, rate):
        self.frame_rate = rate
        return self

    def __add__(self, other):
        return _FakeSegment(frame_rate=self.frame_rate, raw_data=self.raw_data + other.raw_data)

    def export(self, path, format=None):
        self.exported = (path, format)


@patch("animalese_synth.AudioSegment")
def test_synthesize_animalese_exports_to_given_path(mock_audio_segment):
    mock_audio_segment.from_wav.side_effect = lambda path: _FakeSegment()
    exported = {}

    def fake_export(self, path, format=None):
        exported["path"] = path
        exported["format"] = format

    with patch.object(_FakeSegment, "export", fake_export):
        synthesize_animalese("cat", "/tmp/out.wav", pitch="med")

    assert exported == {"path": "/tmp/out.wav", "format": "wav"}


@patch("animalese_synth.AudioSegment")
def test_synthesize_animalese_falls_back_for_unmapped_only_word(mock_audio_segment):
    # 対応表に無い文字だけの単語でも例外にならないこと(通常は起こらない
    # が保険の回帰防止。楔形文字等を--wordで直接指定した場合等)。
    calls = []
    mock_audio_segment.from_wav.side_effect = lambda path: calls.append(path) or _FakeSegment()

    with patch.object(_FakeSegment, "export", lambda self, path, format=None: None):
        synthesize_animalese(chr(0x12042), "/tmp/out.wav", pitch="med")

    assert calls == [_sound_path("med", "a")]


@patch("animalese_synth.AudioSegment")
def test_synthesize_animalese_default_pitch_is_one_of_presets(mock_audio_segment):
    seen_dirs = set()

    def fake_from_wav(path):
        seen_dirs.add(Path(path).parent.name)
        return _FakeSegment()

    mock_audio_segment.from_wav.side_effect = fake_from_wav
    with patch.object(_FakeSegment, "export", lambda self, path, format=None: None):
        for _ in range(30):
            synthesize_animalese("a", "/tmp/out.wav")

    assert seen_dirs <= set(PITCH_PRESETS)
    assert len(seen_dirs) > 1
