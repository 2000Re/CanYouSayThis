"""tts_synth.py の純粋関数に対するユニットテスト。
espeak-ng/ffmpeg呼び出し(synthesize_tts_extreme)は実際には行わない、
軽いテストのみ。synthesize_tts()はsubprocess.runをモックし、実際の
espeak-ng実行はしないまま組み立てられるコマンドだけを検証する。"""

import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tts_synth
from tts_synth import EXTREME_VOICE_VARIANTS, _random_extreme_filter_chain, synthesize_tts


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
