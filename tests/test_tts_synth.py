"""tts_synth.py の純粋関数に対するユニットテスト。
espeak-ng/ffmpeg呼び出し(synthesize_tts/synthesize_tts_extreme)は使わない、
軽いテストのみ。"""

import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tts_synth import EXTREME_VOICE_VARIANTS, _random_extreme_filter_chain


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
