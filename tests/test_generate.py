"""generate.py の純粋関数(_resolve_mode)に対するユニットテスト。
外部コマンド(espeak-ng/ffmpeg/Chromium)は使わない、軽いテストのみ。"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate import _resolve_mode


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
