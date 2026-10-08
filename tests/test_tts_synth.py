"""tts_synth.py の純粋関数に対するユニットテスト。
espeak-ng/ffmpeg呼び出し(synthesize_tts_extreme)は実際には行わない、
軽いテストのみ。synthesize_tts()はsubprocess.runをモックし、実際の
espeak-ng実行はしないまま組み立てられるコマンドだけを検証する。"""

import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import tts_synth
from tts_synth import (
    EXTREME_VOICE_VARIANTS,
    _random_extreme_filter_chain,
    synthesize_tts,
    synthesize_tts_chorus,
    synthesize_tts_reverse,
    synthesize_tts_robot,
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


def _capture_all_run_calls(monkeypatch):
    """subprocess.run呼び出しをすべて記録しつつ、出力先(cmd[-1])に空
    ファイルを作るフェイクに差し替える(実際のespeak-ng/ffmpeg実行はしない)。
    呼び出しごとのコマンド列(リストのリスト)を返す。"""
    calls = []

    def fake_run(cmd, check, capture_output):
        calls.append(cmd)
        Path(cmd[-1]).touch()

    monkeypatch.setattr(tts_synth.subprocess, "run", fake_run)
    return calls


def test_synthesize_tts_reverse_applies_areverse_and_passes_through_voice(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    out = tmp_path / "out.wav"

    synthesize_tts_reverse("word", str(out), voice="fr-fr", speed=180, pitch=60)

    espeak_call = calls[0]
    assert "fr-fr" in espeak_call
    assert "180" in espeak_call
    assert espeak_call[espeak_call.index("-p") + 1] == "60"

    ffmpeg_call = calls[1]
    assert "-af" in ffmpeg_call
    assert ffmpeg_call[ffmpeg_call.index("-af") + 1] == "areverse"
    assert ffmpeg_call[-1] == str(out)
    assert out.exists()


def test_synthesize_tts_robot_uses_amultiply_with_given_carrier_freq(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    monkeypatch.setattr(tts_synth, "_probe_duration", lambda path: 1.5)
    out = tmp_path / "out.wav"

    synthesize_tts_robot("word", str(out), voice="en", carrier_freq=77)

    ffmpeg_call = calls[-1]
    assert any("sine=frequency=77" in tok for tok in ffmpeg_call)
    filter_complex = ffmpeg_call[ffmpeg_call.index("-filter_complex") + 1]
    assert "amultiply" in filter_complex
    # 実機でamultiplyだけだとRMS音量が大きく下がることを確認したため、
    # volumeで底上げ+alimiterでクリッピング防止している(README参照)。
    assert "volume=" in filter_complex
    assert "alimiter=" in filter_complex
    assert out.exists()


def test_synthesize_tts_robot_default_carrier_freq_within_range(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    monkeypatch.setattr(tts_synth, "_probe_duration", lambda path: 1.0)
    random.seed(1)

    for _ in range(30):
        synthesize_tts_robot("word", str(tmp_path / "out.wav"))
        ffmpeg_call = calls[-1]
        m = re.search(r"sine=frequency=(\d+)", " ".join(ffmpeg_call))
        assert m
        assert 30 <= int(m.group(1)) <= 120


def test_synthesize_tts_chorus_picks_multiple_distinct_languages(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    random.seed(1)
    out = tmp_path / "out.wav"

    synthesize_tts_chorus("word", str(out))

    espeak_calls = calls[:-1]
    mix_call = calls[-1]
    assert len(espeak_calls) >= 3  # n_voicesのデフォルト範囲(3,4)の最小値
    voices_used = {c[c.index("-v") + 1] for c in espeak_calls}
    assert len(voices_used) == len(espeak_calls)  # 重複無く選ばれていること

    filter_complex = mix_call[mix_call.index("-filter_complex") + 1]
    assert f"amix=inputs={len(espeak_calls)}" in filter_complex
    assert "adelay=" in filter_complex
    assert "volume=" in filter_complex
    assert "alimiter=" in filter_complex
    assert out.exists()


def test_chorus_voice_language_codes_excludes_hebrew_only():
    assert "he" not in config.CHORUS_VOICE_LANGUAGE_CODES
    assert set(config.CHORUS_VOICE_LANGUAGE_CODES) == set(config.VOICE_LANGUAGES) - {"he"}


def test_synthesize_tts_chorus_never_uses_hebrew_voice(monkeypatch, tmp_path):
    # ヘブライ語ボイスはZalgo単語で他言語の3倍近い長さになることを実機で
    # 確認したため、config.CHORUS_VOICE_LANGUAGE_CODESから除外済み
    # (config.py参照)。chorusが実際にヘブライ語を選ばないことの回帰防止。
    calls = _capture_all_run_calls(monkeypatch)
    random.seed(2)
    hebrew_voices = {config.VOICE_LANGUAGES["he"]["male"], config.VOICE_LANGUAGES["he"]["female"]}

    for _ in range(30):
        synthesize_tts_chorus("word", str(tmp_path / "out.wav"))
        espeak_calls = calls[:-1]
        voices_used = {c[c.index("-v") + 1] for c in espeak_calls}
        assert voices_used.isdisjoint(hebrew_voices)
        calls.clear()
