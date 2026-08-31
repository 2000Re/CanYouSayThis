"""generate.py の純粋関数(_resolve_mode, _random_unique_word)に対する
ユニットテスト。外部コマンド(espeak-ng/ffmpeg/Chromium)は使わない、
軽いテストのみ。"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import generate as generate_module
from generate import _random_unique_word, _resolve_mode


def test_resolve_mode_passes_through_tts():
    assert _resolve_mode("tts") == "tts"


def test_resolve_mode_passes_through_glitch():
    assert _resolve_mode("glitch") == "glitch"


def test_resolve_mode_random_always_picks_a_real_mode():
    random.seed(0)
    for _ in range(50):
        assert _resolve_mode("random") in ("tts", "glitch")


def test_resolve_mode_random_can_pick_both():
    random.seed(0)
    picks = {_resolve_mode("random") for _ in range(50)}
    assert picks == {"tts", "glitch"}


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
