"""audio_utils.py の純粋関数に対するユニットテスト。実際のffmpeg実行は
行わず、subprocess.runをモックする軽いテストのみ。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import audio_utils
from audio_utils import (
    _atempo_chain_for_factor,
    _is_silent_audio,
    _speed_up_to_max_duration,
    _stretch_to_min_duration,
    finalize_audio,
    repeat_audio,
)


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


def test_probe_duration_treats_na_as_zero(monkeypatch, tmp_path):
    # espeak-ngに空文字列を渡すと1サンプルも無いWAVができることがあり、
    # ffprobeはdurationとして数値ではなく文字列"N/A"を返す(README
    # 「ハマった罠」108番、実機で確認)。float()に素朴に渡すとクラッシュ
    # するため、長さ0として扱われることを確認する。
    def fake_run(cmd, **kwargs):
        class _FakeResult:
            stdout = "N/A\n"
        return _FakeResult()

    monkeypatch.setattr(audio_utils.subprocess, "run", fake_run)
    assert audio_utils._probe_duration("dummy.wav") == 0.0


def test_stretch_to_min_duration_passes_through_without_looping_when_duration_is_zero(
    monkeypatch, tmp_path
):
    # duration=0(1サンプルも無い音声)の場合、factor=0/min_duration=0になり
    # _atempo_chain_for_factor()の`remaining /= 0.5`を繰り返しても0のまま
    # 無限ループしてしまう不具合があった(README「ハマった罠」108番)。
    # atempoでは無いデータから音を作れないため、引き伸ばしを試みず素通しで
    # 完了することを確認する(タイムアウトせず終わること自体が回帰防止)。
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    monkeypatch.setattr(audio_utils, "_probe_duration", lambda path: 0.0)
    _fake_ffmpeg_writes_output_file(monkeypatch)

    _stretch_to_min_duration(str(src), str(dst), min_duration=3.0)

    assert dst.exists()


def test_speed_up_to_max_duration_passes_through_when_already_short_enough(monkeypatch, tmp_path):
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    monkeypatch.setattr(audio_utils, "_probe_duration", lambda path: 5.0)
    _fake_ffmpeg_writes_output_file(monkeypatch)

    _speed_up_to_max_duration(str(src), str(dst), max_duration=8.0)

    assert dst.exists()


def test_speed_up_to_max_duration_applies_atempo_when_too_long(monkeypatch, tmp_path):
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    # 1回目の計測は長すぎる、atempo適用後の2回目の計測では狙った長さに
    # 収まった、という想定(_stretch_to_min_durationと対称)。
    durations = iter([20.0, 8.0])
    monkeypatch.setattr(audio_utils, "_probe_duration", lambda path: next(durations))
    _fake_ffmpeg_writes_output_file(monkeypatch)

    _speed_up_to_max_duration(str(src), str(dst), max_duration=8.0)

    assert dst.exists()
    # 元のsrcファイル自体は消さない(呼び出し側が自分で管理・削除する)
    assert src.exists()


def test_speed_up_to_max_duration_stops_after_max_passes_without_infinite_loop(monkeypatch, tmp_path):
    # 何回短縮しても閾値を超えたままのケースでも無限ループせず、
    # max_passes回で打ち切って完了することの回帰防止。
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    monkeypatch.setattr(audio_utils, "_probe_duration", lambda path: 20.0)
    _fake_ffmpeg_writes_output_file(monkeypatch)

    _speed_up_to_max_duration(str(src), str(dst), max_duration=8.0, max_passes=2)

    assert dst.exists()


def _capture_run_cmd(monkeypatch):
    """subprocess.run呼び出しのcmdを記録しつつ、出力先(cmd[-1])に空ファイル
    を作るフェイクに差し替える。最後に呼ばれたcmdを返すlistを返す。"""
    calls = []

    def fake_run(cmd, check, capture_output):
        calls.append(cmd)
        Path(cmd[-1]).touch()

    monkeypatch.setattr(audio_utils.subprocess, "run", fake_run)
    return calls


def test_finalize_audio_omits_fade_in_by_default(monkeypatch, tmp_path):
    # fade_in未指定(デフォルト0.0)では従来通りフェードアウトのみ。
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    monkeypatch.setattr(audio_utils, "_probe_duration", lambda path: 2.0)
    calls = _capture_run_cmd(monkeypatch)

    finalize_audio(str(src), str(dst), fade=0.4)

    af = calls[-1][calls[-1].index("-af") + 1]
    assert af == "afade=t=out:st=1.6:d=0.4"
    assert dst.exists()


def test_finalize_audio_adds_fade_in_when_requested(monkeypatch, tmp_path):
    # ループの継ぎ目を滑らかにするため、fade_inを指定すると冒頭にも
    # フェードインがかかる(afade=t=out より前に並ぶこと)。
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    monkeypatch.setattr(audio_utils, "_probe_duration", lambda path: 5.0)
    calls = _capture_run_cmd(monkeypatch)

    finalize_audio(str(src), str(dst), fade=0.15, fade_in=0.08)

    af = calls[-1][calls[-1].index("-af") + 1]
    assert af == "afade=t=in:st=0:d=0.08,afade=t=out:st=4.85:d=0.15"
    assert dst.exists()


def test_repeat_audio_preserves_mono_channel_layout(monkeypatch, tmp_path):
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    monkeypatch.setattr(audio_utils, "_probe_channels", lambda path: 1)
    calls = _capture_run_cmd(monkeypatch)

    repeat_audio(str(src), str(dst), times=2, gap=0.4)

    cmd = calls[-1]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "channel_layouts=mono" in filter_complex
    assert "channel_layouts=stereo" not in filter_complex
    assert "cl=mono" in " ".join(cmd)
    assert dst.exists()


def test_repeat_audio_preserves_stereo_channel_layout(monkeypatch, tmp_path):
    # 8d_audioモード(ステレオ化して左右に音像を回転させる)の効果が、
    # 以前はrepeat_audio()で常にmonoへ固定されていたせいで潰れていた
    # バグの回帰防止(README「ハマった罠」参照)。
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"
    monkeypatch.setattr(audio_utils, "_probe_channels", lambda path: 2)
    calls = _capture_run_cmd(monkeypatch)

    repeat_audio(str(src), str(dst), times=2, gap=0.4)

    cmd = calls[-1]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "channel_layouts=stereo" in filter_complex
    assert "channel_layouts=mono" not in filter_complex
    assert "cl=stereo" in " ".join(cmd)
    assert dst.exists()


def _fake_volumedetect_stderr(monkeypatch, mean_volume_text, duration="1.0"):
    """ffmpegのvolumedetectフィルタが吐くstderr出力と、_is_silent_audio()が
    無音判定の前に呼ぶ_probe_duration()(ffprobe)のstdout出力の両方を
    模したフェイクにsubprocess.runを差し替える(README「ハマった罠」
    108番、_probe_duration()が追加されたことの回帰対応)。"""
    class _FakeResult:
        stdout = duration
        stderr = (
            f"[Parsed_volumedetect_0 @ 0x0] mean_volume: {mean_volume_text}\n"
            "[Parsed_volumedetect_0 @ 0x0] max_volume: -10.0 dB\n"
        )

    def fake_run(cmd, **kwargs):
        return _FakeResult()

    monkeypatch.setattr(audio_utils.subprocess, "run", fake_run)


def test_is_silent_audio_true_for_volume_below_threshold(monkeypatch):
    # 楔形文字等のピクトグラフ単語をTTS系モードで使うと、TTS合成直前に
    # 単語が空文字列になり完全な無音(-91dB)が生成される不具合が実機で
    # 確認された(README「ハマった罠」69・70番)。その値を再現して検知
    # できることを確認する。
    _fake_volumedetect_stderr(monkeypatch, "-91.0 dB")
    assert _is_silent_audio("dummy.wav") is True


def test_is_silent_audio_false_for_normal_speech_volume(monkeypatch):
    # 通常のTTS音声のmean_volumeは-30dB程度までに収まることが多い
    # (実機確認済み)。閾値(デフォルト-50dB)を下回らないので無音とは
    # 判定しない。
    _fake_volumedetect_stderr(monkeypatch, "-24.3 dB")
    assert _is_silent_audio("dummy.wav") is False


def test_is_silent_audio_respects_custom_threshold(monkeypatch):
    _fake_volumedetect_stderr(monkeypatch, "-40.0 dB")
    assert _is_silent_audio("dummy.wav", threshold_db=-50.0) is False
    assert _is_silent_audio("dummy.wav", threshold_db=-35.0) is True


def test_is_silent_audio_false_when_mean_volume_cannot_be_parsed(monkeypatch):
    # mean_volumeが取れない(解析失敗)場合は、無音として誤検知して
    # 通常の音声生成を止めてしまわないよう、安全側(無音ではない)に倒す。
    def fake_run(cmd, **kwargs):
        class _FakeResult:
            stdout = "1.0"
            stderr = "some unexpected ffmpeg output without mean_volume"
        return _FakeResult()

    monkeypatch.setattr(audio_utils.subprocess, "run", fake_run)
    assert _is_silent_audio("dummy.wav") is False


def test_is_silent_audio_true_when_duration_is_zero(monkeypatch):
    # 1サンプルも無いWAV(duration=0)はvolumedetectがmean_volume自体を
    # 出力しないため、通常の正規表現マッチでは判定できない。音声データが
    # 無い=定義上無音として、volumedetectを呼ぶ前に確定で無音判定する
    # (README「ハマった罠」108番)。
    monkeypatch.setattr(audio_utils, "_probe_duration", lambda path: 0.0)

    def fake_run(cmd, **kwargs):
        raise AssertionError("duration<=0ならvolumedetectを呼ばずに即returnするはず")

    monkeypatch.setattr(audio_utils.subprocess, "run", fake_run)
    assert _is_silent_audio("dummy.wav") is True


def test_repeat_audio_skips_channel_probe_when_times_is_one(monkeypatch, tmp_path):
    # times<=1はffmpegでそのままコピーするだけの経路のため、
    # _probe_channels()(ffprobe呼び出し)自体が不要なことの確認。
    src = tmp_path / "src.wav"
    src.touch()
    dst = tmp_path / "dst.wav"

    def fail_probe(path):
        raise AssertionError("times<=1ではチャンネル数を調べる必要は無いはず")

    monkeypatch.setattr(audio_utils, "_probe_channels", fail_probe)
    _capture_run_cmd(monkeypatch)

    repeat_audio(str(src), str(dst), times=1)

    assert dst.exists()
