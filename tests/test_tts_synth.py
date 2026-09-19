"""tts_synth.py の純粋関数に対するユニットテスト。
espeak-ng/ffmpeg呼び出し(synthesize_tts_extreme)は実際には行わない、
軽いテストのみ。synthesize_tts()はsubprocess.runをモックし、実際の
espeak-ng実行はしないまま組み立てられるコマンドだけを検証する。"""

import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import tts_synth
from tts_synth import (
    EXTREME_VOICE_VARIANTS,
    _atempo_chain_for_factor,
    _random_extreme_filter_chain,
    _stretch_to_min_duration,
    synthesize_tts,
)


def test_random_extreme_filter_chain_never_empty():
    # tts_extremeは「必ず何かしら歪ませる」のが目的なので、確率的に何も
    # 選ばれなかった場合の保険(acrusherフォールバック)が効いていることを
    # 確認する。
    random.seed(1)
    for _ in range(200):
        assert len(_random_extreme_filter_chain()) >= 1


def test_random_extreme_filter_chain_produces_valid_ffmpeg_filter_syntax():
    random.seed(2)
    for _ in range(50):
        chain = _random_extreme_filter_chain()
        filter_str = ",".join(chain)
        # 各フィルタが "name=..." の形式になっていること(ffmpeg -afへ
        # そのまま渡せる文字列であることの簡易チェック)
        for filt in chain:
            assert re.match(r"^[a-z]+=", filt), filt
        assert "," in filter_str or len(chain) == 1


def test_random_extreme_filter_chain_varies_across_calls():
    # 以前は固定値だったため、複数回呼んだ際にバリエーションが出ることを
    # 確認する(回帰防止)。
    random.seed(3)
    chains = {",".join(_random_extreme_filter_chain()) for _ in range(100)}
    assert len(chains) > 1


def test_extreme_voice_variants_are_nonempty_strings():
    assert len(EXTREME_VOICE_VARIANTS) > 0
    assert all(isinstance(v, str) and v for v in EXTREME_VOICE_VARIANTS)


def test_synthesize_tts_omits_pitch_flag_by_default(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(
        tts_synth.subprocess, "run",
        lambda cmd, check, capture_output: captured.setdefault("cmd", cmd),
    )
    synthesize_tts("word", str(tmp_path / "out.wav"))
    assert "-p" not in captured["cmd"]


def test_synthesize_tts_includes_pitch_flag_when_given(monkeypatch, tmp_path):
    # 女性ボイスをより高く聞こえさせるためのconfig.FEMALE_VOICE_PITCH
    # (generate.py参照)が、実際にespeak-ngの-pへ渡ることを確認する。
    captured = {}
    monkeypatch.setattr(
        tts_synth.subprocess, "run",
        lambda cmd, check, capture_output: captured.setdefault("cmd", cmd),
    )
    synthesize_tts("word", str(tmp_path / "out.wav"), pitch=75)
    cmd = captured["cmd"]
    assert "-p" in cmd
    assert cmd[cmd.index("-p") + 1] == "75"


def test_atempo_chain_for_factor_within_range_needs_no_chaining():
    # atempoは1回あたり0.5〜2.0倍まで指定できるので、その範囲内ならチェーン
    # 不要で1個だけになる
    assert _atempo_chain_for_factor(0.8) == "atempo=0.8"


def test_atempo_chain_for_factor_below_range_chains_to_reach_target():
    # 0.5未満の倍率は1回で表現できないため、0.5を複数回チェーンして表現する
    chain = _atempo_chain_for_factor(0.1)
    stages = chain.split(",")
    assert len(stages) > 1
    product = 1.0
    for stage in stages:
        value = float(stage.split("=")[1])
        assert 0.5 <= value <= 2.0
        product *= value
    assert product == pytest.approx(0.1, rel=0.01)


def test_atempo_chain_for_factor_above_range_chains_to_reach_target():
    chain = _atempo_chain_for_factor(5.0)
    stages = chain.split(",")
    assert len(stages) > 1
    product = 1.0
    for stage in stages:
        value = float(stage.split("=")[1])
        assert 0.5 <= value <= 2.0
        product *= value
    assert product == pytest.approx(5.0, rel=0.01)


def _fake_ffmpeg_writes_output_file(monkeypatch):
    """subprocess.run呼び出しを、コマンド末尾(出力先パス)に空ファイルを
    作るだけのフェイクに差し替える(実際のffmpeg実行はしない)。"""
    def fake_run(cmd, check, capture_output):
        Path(cmd[-1]).touch()
    monkeypatch.setattr(tts_synth.subprocess, "run", fake_run)


def test_stretch_to_min_duration_passes_through_when_already_long_enough(monkeypatch, tmp_path):
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    monkeypatch.setattr(tts_synth, "_probe_duration", lambda path: 1.0)
    _fake_ffmpeg_writes_output_file(monkeypatch)

    _stretch_to_min_duration(str(src), str(dst), min_duration=0.6)

    assert dst.exists()


def test_stretch_to_min_duration_applies_atempo_when_too_short(monkeypatch, tmp_path):
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    # 1回目の計測は短すぎる、atempo適用後の2回目の計測では十分な長さに
    # なった、という想定(実機でも1回のatempo適用でほぼ狙った長さに収まる
    # ことを確認済み)。
    durations = iter([0.1, 0.6])
    monkeypatch.setattr(tts_synth, "_probe_duration", lambda path: next(durations))
    _fake_ffmpeg_writes_output_file(monkeypatch)

    _stretch_to_min_duration(str(src), str(dst), min_duration=0.6)

    assert dst.exists()
    # 元のsrcファイル自体は消さない(呼び出し側=synthesize_tts_extreme()が
    # 自分で管理・削除する)
    assert src.exists()


def test_stretch_to_min_duration_stops_after_max_passes_without_infinite_loop(monkeypatch, tmp_path):
    # 何回引き伸ばしても閾値に届かないケースでも無限ループせず、
    # max_passes回で打ち切って完了することの回帰防止。
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    monkeypatch.setattr(tts_synth, "_probe_duration", lambda path: 0.1)
    _fake_ffmpeg_writes_output_file(monkeypatch)

    _stretch_to_min_duration(str(src), str(dst), min_duration=0.6, max_passes=2)

    assert dst.exists()
