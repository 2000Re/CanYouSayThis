"""glitch_synth.py の純粋関数に対するユニットテスト。
ffmpeg呼び出し(synthesize_glitch_chunk)は使わない、軽いテストのみ。"""

import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from glitch_synth import _build_glitch_segments, _one_glitch_segment, _random_echo_params


def test_one_glitch_segment_returns_valid_tuple():
    random.seed(1)
    src, filt, dur = _one_glitch_segment()
    assert isinstance(src, str) and src
    assert isinstance(filt, str) and filt
    assert dur > 0


def test_build_glitch_segments_reaches_target_duration():
    random.seed(2)
    segments = _build_glitch_segments(target_seconds=2.0)
    assert len(segments) > 0
    assert len(segments) <= 61  # 保険の上限(60個)+1


def test_random_echo_params_respects_ranges_and_skip_chance():
    # 何度も呼んで、Noneと具体値の両方が出ること・値が想定レンジ内に収まる
    # ことを確認する(以前は0.8:0.7に固定されていたため、幅が出ることが
    # 重要な回帰防止ポイント)。
    random.seed(3)
    results = [_random_echo_params() for _ in range(200)]
    skipped = [r for r in results if r is None]
    applied = [r for r in results if r is not None]
    assert skipped, "エコーなし(素通し)が一度も出ないのはおかしい"
    assert applied, "エコーありが一度も出ないのはおかしい"

    in_gains = {r[0] for r in applied}
    out_gains = {r[1] for r in applied}
    assert len(in_gains) > 1, "in_gainが常に同じ値になっている"
    assert len(out_gains) > 1, "out_gainが常に同じ値になっている"
    for in_gain, out_gain, delay, decay in applied:
        assert 0.5 <= in_gain <= 0.9
        assert 0.4 <= out_gain <= 0.85
        assert 15 <= delay <= 90
        assert 0.15 <= decay <= 0.55


def test_one_glitch_segment_tone_bits_vary_across_trials():
    # acrusherのbitsが固定値に偏っていないか(クランチ感のバラつき回帰防止)。
    random.seed(4)
    bits_seen = set()
    for _ in range(300):
        _, filt, _ = _one_glitch_segment()
        m = re.search(r"acrusher=bits=(\d+)", filt)
        if m:
            bits_seen.add(int(m.group(1)))
    assert len(bits_seen) > 3
    assert all(2 <= b <= 8 for b in bits_seen)
