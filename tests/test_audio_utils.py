"""audio_utils.py の純粋関数に対するユニットテスト。実際のffmpeg実行は
行わず、subprocess.runをモックする軽いテストのみ。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import audio_utils
from audio_utils import _atempo_chain_for_factor, _stretch_to_min_duration


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
    monkeypatch.setattr(audio_utils.subprocess, "run", fake_run)


def test_stretch_to_min_duration_passes_through_when_already_long_enough(monkeypatch, tmp_path):
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    monkeypatch.setattr(audio_utils, "_probe_duration", lambda path: 1.0)
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
    monkeypatch.setattr(audio_utils, "_probe_duration", lambda path: next(durations))
    _fake_ffmpeg_writes_output_file(monkeypatch)

    _stretch_to_min_duration(str(src), str(dst), min_duration=0.6)

    assert dst.exists()
    # 元のsrcファイル自体は消さない(呼び出し側が自分で管理・削除する)
    assert src.exists()


def test_stretch_to_min_duration_stops_after_max_passes_without_infinite_loop(monkeypatch, tmp_path):
    # 何回引き伸ばしても閾値に届かないケースでも無限ループせず、
    # max_passes回で打ち切って完了することの回帰防止。
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    monkeypatch.setattr(audio_utils, "_probe_duration", lambda path: 0.1)
    _fake_ffmpeg_writes_output_file(monkeypatch)

    _stretch_to_min_duration(str(src), str(dst), min_duration=0.6, max_passes=2)

    assert dst.exists()
