"""glitch_synth.py の純粋関数に対するユニットテスト。
実際のffmpeg実行はしない(synthesize_glitch_chunk関連はsubprocess.runを
モックして、組み立てられたコマンド/filter_complex文字列だけ検証する)。"""

import random
import re
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from glitch_synth import (
    _TEMPO_DENSITY_PARAMS,
    _build_glitch_segments,
    _one_glitch_segment,
    _random_echo_params,
    synthesize_glitch_chunk,
)


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


def test_one_glitch_segment_dur_scale_shrinks_duration():
    random.seed(10)
    _, _, dur_normal = _one_glitch_segment()
    random.seed(10)
    _, _, dur_scaled = _one_glitch_segment(dur_scale=0.5)
    assert dur_scaled < dur_normal


def test_one_glitch_segment_negative_silence_bias_reduces_silence_frequency():
    # weights=[1,1,1,1+silence_bias]なので、silence_biasを下げるとsilence
    # (anullsrc)が選ばれる頻度が下がるはず。
    random.seed(5)
    silence_count_normal = sum(
        1 for _ in range(500) if "anullsrc" in _one_glitch_segment()[0]
    )
    random.seed(5)
    silence_count_biased = sum(
        1 for _ in range(500) if "anullsrc" in _one_glitch_segment(silence_bias=-0.6)[0]
    )
    assert silence_count_biased < silence_count_normal


def test_tempo_density_params_has_high_and_low():
    assert set(_TEMPO_DENSITY_PARAMS) == {"high", "low"}
    for params in _TEMPO_DENSITY_PARAMS.values():
        assert "dur_scale" in params and "silence_bias" in params
    # high(音数多め・短め)がlow(音数少なめ・長め)よりdur_scaleが小さいこと
    assert _TEMPO_DENSITY_PARAMS["high"]["dur_scale"] < _TEMPO_DENSITY_PARAMS["low"]["dur_scale"]


def test_build_glitch_segments_with_density_params_reaches_target():
    random.seed(6)
    segments = _build_glitch_segments(2.0, **_TEMPO_DENSITY_PARAMS["high"])
    assert len(segments) > 0
    assert len(segments) <= 61


def _filter_complex_from_call(mock_run):
    cmd = mock_run.call_args[0][0]
    return cmd[cmd.index("-filter_complex") + 1]


def _avg_segment_duration_from_call(mock_run):
    # -iに渡すlavfiソース文字列だけを見る(sineは"duration=", anullsrc/
    # anoisesrcは"d="で長さを持つ。filter_complex側のvibratoのd=と混同
    # しないよう、-iの引数だけを対象にする)。
    cmd = mock_run.call_args[0][0]
    durations = []
    for i, tok in enumerate(cmd):
        if tok == "-i":
            m = re.search(r"(?:duration|d)=([\d.]+)", cmd[i + 1])
            if m:
                durations.append(float(m.group(1)))
    return sum(durations) / len(durations)


@patch("glitch_synth.subprocess.run")
def test_synthesize_glitch_chunk_layers_with_amix(mock_run):
    # 以前は1レイヤーをconcatするだけだったが、複数レイヤーを重ねて
    # amixするようになった(「毎回似通って聞こえる」への対策の回帰防止)。
    random.seed(7)
    synthesize_glitch_chunk("/tmp/x.wav", target_seconds=1.0, n_layers=3, tempo_density="high")
    filter_complex = _filter_complex_from_call(mock_run)
    assert "amix=inputs=3" in filter_complex
    assert filter_complex.count("concat=n=") == 3


@patch("glitch_synth.subprocess.run")
def test_synthesize_glitch_chunk_default_n_layers_is_2_or_3_and_varies(mock_run):
    random.seed(12)
    seen = set()
    for _ in range(40):
        synthesize_glitch_chunk("/tmp/x.wav", target_seconds=0.5)
        seen.add(_filter_complex_from_call(mock_run).count("concat=n="))
    assert seen == {2, 3}, "n_layersが2・3の両方出ない(固定化の回帰防止)"


@patch("glitch_synth.subprocess.run")
def test_synthesize_glitch_chunk_tempo_density_high_is_shorter_than_low(mock_run):
    random.seed(11)
    synthesize_glitch_chunk("/tmp/x.wav", target_seconds=2.0, n_layers=2, tempo_density="high")
    avg_high = _avg_segment_duration_from_call(mock_run)

    random.seed(11)
    synthesize_glitch_chunk("/tmp/x.wav", target_seconds=2.0, n_layers=2, tempo_density="low")
    avg_low = _avg_segment_duration_from_call(mock_run)

    assert avg_high < avg_low


@patch("glitch_synth.subprocess.run")
def test_synthesize_glitch_chunk_default_tempo_density_varies(mock_run):
    # tempo_density省略時にhigh/low両方が抽選されること(平均長さの分布で判定)。
    random.seed(13)
    avgs = []
    for _ in range(40):
        synthesize_glitch_chunk("/tmp/x.wav", target_seconds=1.0)
        avgs.append(_avg_segment_duration_from_call(mock_run))
    assert min(avgs) < 0.15
    assert max(avgs) > 0.3
