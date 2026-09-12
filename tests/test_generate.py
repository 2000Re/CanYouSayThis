"""generate.py の純粋関数(_resolve_mode, _random_unique_word)に対する
ユニットテスト。外部コマンド(espeak-ng/ffmpeg/Chromium)は使わない、
軽いテストのみ。"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import generate as generate_module
from generate import _random_unique_word, _resolve_mode, _resolve_voice, _youtube_metadata

REAL_MODES = ("tts", "tts_extreme", "glitch")


def test_resolve_mode_passes_through_tts():
    assert _resolve_mode("tts") == "tts"


def test_resolve_mode_passes_through_glitch():
    assert _resolve_mode("glitch") == "glitch"


def test_resolve_mode_random_always_picks_a_real_mode():
    random.seed(0)
    for _ in range(50):
        assert _resolve_mode("random") in REAL_MODES


def test_resolve_mode_random_can_pick_all_modes():
    random.seed(0)
    picks = {_resolve_mode("random") for _ in range(100)}
    assert picks == set(config.MODE_LABELS)


def test_random_unique_word_returns_first_pick_when_no_collision(monkeypatch):
    monkeypatch.setattr(generate_module, "random_zalgo_word", lambda: "fresh")
    assert _random_unique_word(set()) == "fresh"


def test_random_unique_word_retries_until_not_in_existing(monkeypatch):
    picks = iter(["dup", "dup", "unique"])
    monkeypatch.setattr(generate_module, "random_zalgo_word", lambda: next(picks))
    assert _random_unique_word({"dup"}) == "unique"


def test_random_unique_word_gives_up_after_max_attempts(monkeypatch):
    # 常に衝突する単語しか返らない場合でも無限ループせず、諦めてそのまま返す
    monkeypatch.setattr(generate_module, "random_zalgo_word", lambda: "always-dup")
    assert _random_unique_word({"always-dup"}, max_attempts=3) == "always-dup"


def test_youtube_metadata_title_contains_label_and_shorts_hashtag():
    title, _description, _tags = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "voOn" in title
    assert "#Shorts" in title


def test_youtube_metadata_description_contains_cta():
    _title, description, _tags = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "comment" in description.lower()


def test_youtube_metadata_description_contains_hashtags():
    _title, description, _tags = _youtube_metadata("v́oOn", "voOn", "tts")
    for hashtag in ("#Shorts", "#Pronunciation", "#Unpronounceable",
                     "#Zalgo", "#GlitchText", "#TextToSpeech", "#TTS", "#Challenge"):
        assert hashtag in description


def test_youtube_metadata_tags_include_mode_and_topic_keywords():
    _title, _description, tags = _youtube_metadata("v́oOn", "voOn", "glitch")
    assert "glitch" in tags
    assert "zalgo" in tags
    assert "text to speech" in tags


def test_youtube_metadata_omits_playlist_link_when_not_given():
    _title, description, _tags = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "playlist?list=" not in description


def test_youtube_metadata_includes_playlist_link_when_given():
    _title, description, _tags = _youtube_metadata(
        "v́oOn", "voOn", "tts", playlist_id="PLexample123"
    )
    assert "https://www.youtube.com/playlist?list=PLexample123" in description


def test_youtube_metadata_omits_voice_line_when_not_given():
    _title, description, _tags = _youtube_metadata("v́oOn", "voOn", "tts")
    assert "Voice:" not in description


def test_youtube_metadata_includes_voice_line_when_given():
    _title, description, _tags = _youtube_metadata(
        "v́oOn", "voOn", "tts", voice_label="French (Female)"
    )
    assert "Voice: French (Female)" in description


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


def test_resolve_voice_random_never_picks_female_for_languages_without_it(monkeypatch):
    # yueにはfemaleが設定されていない(config.VOICE_LANGUAGES参照)ので、
    # 言語としてyueが選ばれた場合、性別の抽選候補にfemaleが含まれず
    # 必ずmaleが返ることを確認する。
    def fake_choice(seq):
        seq = list(seq)
        if seq == list(config.VOICE_LANGUAGES):
            return "yue"
        assert "female" not in seq
        return seq[0]

    monkeypatch.setattr(random, "choice", fake_choice)
    code, label, gender = _resolve_voice("random")
    assert code == config.VOICE_LANGUAGES["yue"]["male"]
    assert gender == "male"
    assert "Male" in label


def test_resolve_voice_random_can_pick_female_when_available(monkeypatch):
    def fake_choice(seq):
        seq = list(seq)
        if seq == list(config.VOICE_LANGUAGES):
            return "fr"
        assert "female" in seq
        return "female"

    monkeypatch.setattr(random, "choice", fake_choice)
    code, label, gender = _resolve_voice("random")
    assert code == config.VOICE_LANGUAGES["fr"]["female"]
    assert gender == "female"
    assert "Female" in label
