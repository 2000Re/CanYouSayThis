"""
合成グリッチ音を「答え」として当てる方式 [--mode glitch]

正弦波のチャープ/ビブラート音・ノイズバースト・ビットクラッシュ・エコーを
ランダムな順番と長さで組み合わせ、1本のffmpegコマンドで書き出す。単語の文
字列そのものは音には反映されない(あくまで「発音でっち上げ」パターンなの
で、動画タイトル側だけに使う)。

セグメント個々のパラメータ(周波数・長さ・クランチの強さ等)はランダムでも、
「1レイヤーだけを順番に鳴らす」「テンポ感(音数・1音の長さ・無音の多さ)は
毎回ほぼ同じ」という全体の構造は固定だったため、毎回似通って聞こえるという
指摘があった。そのため2〜3レイヤーを同時に重ねてamixする(和音的な重なりを
作る)のに加え、レイヤーごとの音数・長さ・無音比率を「high(音数多め・短め・
無音少なめ)」「low(音数少なめ・長め・無音多め)」の2パターンから毎回ランダム
に選ぶことで、構造そのものにもバリエーションを持たせている。
"""

import random
import subprocess

NOISE_COLORS = ["white", "pink", "brown"]

# レイヤーごとの音数・テンポ感のバリエーション。dur_scaleは各セグメントの
# 長さ(_one_glitch_segment()のuniform()の結果)に掛ける倍率、silence_biasは
# silenceが選ばれる相対重みへの加算(他のkindは重み1のまま)。
# highは音数を増やして忙しない密度に、lowは1音を伸ばして無音がちにゆったり
# させる方向。
_TEMPO_DENSITY_PARAMS = {
    "high": {"dur_scale": 0.45, "silence_bias": -0.6},
    "low": {"dur_scale": 2.2, "silence_bias": 1.5},
}


def _one_glitch_segment(dur_scale=1.0, silence_bias=0.0):
    """(lavfi入力文字列, セグメント個別フィルタ, 長さ秒) を1つ返す。

    dur_scale: 長さ(uniform()の結果)に掛ける倍率。テンポ密度バリエーション
    (_TEMPO_DENSITY_PARAMS)用で、デフォルト1.0なら従来通り。
    silence_bias: silenceが選ばれる相対重みへの加算(他のkindは重み1のまま)。
    負の値でsilenceを選ばれにくく、正の値で選ばれやすくする。"""
    weights = [1, 1, 1, max(1 + silence_bias, 0.05)]
    kind = random.choices(["tone", "tone_vibrato", "noise", "silence"], weights=weights)[0]
    if kind == "tone":
        freq = random.randint(70, 2400)
        dur = round(random.uniform(0.12, 0.42) * dur_scale, 2)
        src = f"sine=frequency={freq}:duration={dur}"
        # bitsの幅を広げ、かける確率も上げてクランチ感の強弱にバラつきを出す
        filt = f"acrusher=bits={random.randint(2,8)}:mode=lin:aa=0" if random.random() < 0.75 else "anull"
    elif kind == "tone_vibrato":
        freq = random.randint(70, 2400)
        dur = round(random.uniform(0.15, 0.45) * dur_scale, 2)
        src = f"sine=frequency={freq}:duration={dur}"
        filt = f"vibrato=f={random.randint(2,30)}:d={round(random.uniform(0.3,1.0),2)}"
    elif kind == "noise":
        color = random.choice(NOISE_COLORS)
        dur = round(random.uniform(0.1, 0.3) * dur_scale, 2)
        amp = round(random.uniform(0.4, 0.75), 2)
        src = f"anoisesrc=d={dur}:c={color}:a={amp}"
        filt = f"acrusher=bits={random.randint(2,7)}:mode=lin:aa=0" if random.random() < 0.65 else "anull"
    else:  # silence (short gap for rhythm)
        dur = round(random.uniform(0.05, 0.15) * dur_scale, 2)
        src = f"anullsrc=r=44100:cl=mono:d={dur}"
        filt = "anull"
    return src, filt, dur


def _random_echo_params(skip_chance=0.25):
    """aechoにかけるin_gain/out_gain/delay/decayをまとめて返す(素通しならNone)。

    以前はin_gain/out_gainが0.8:0.7で固定されており、個々のセグメントの
    音程や長さを変えても「エコーのかかり方」という支配的な質感だけは毎回
    同じだった。ここを丸ごとランダム化し、さらに一定確率でエコー自体を
    かけない(ドライな音)ことで、ウェット/ドライという別軸のバリエーション
    を持たせる。"""
    if random.random() < skip_chance:
        return None
    in_gain = round(random.uniform(0.5, 0.9), 2)
    out_gain = round(random.uniform(0.4, 0.85), 2)
    delay = random.randint(15, 90)
    decay = round(random.uniform(0.15, 0.55), 2)
    return in_gain, out_gain, delay, decay


def _build_glitch_segments(target_seconds, dur_scale=1.0, silence_bias=0.0):
    """合計の長さが target_seconds に達するまでセグメントを積む"""
    segments = []
    total = 0.0
    while total < target_seconds:
        src, filt, dur = _one_glitch_segment(dur_scale, silence_bias)
        segments.append((src, filt))
        total += dur
        if len(segments) > 60:  # 極端に短いセグメントが続いた場合の保険
            break
    return segments


def synthesize_glitch_chunk(wav_path, target_seconds=2.0, n_layers=None, tempo_density=None):
    """ランダムなグリッチ効果音の「素の断片」を1本のffmpegコマンドで合成する。

    n_layers本のレイヤー(それぞれ_build_glitch_segments()で独立に組み立てた
    セグメント列)を同時にamixで重ね、その上に(確率で)aechoをかける。
    n_layers/tempo_density省略時はそれぞれランダムに選ぶ(2〜3レイヤー、
    high/lowのテンポ密度を等確率で選択)。単体で毎回の音の違いを聴き比べたい
    場合など、テスト・デバッグ用に明示指定もできる。

    パディングやフェードはここではやらない(audio_utils.repeat_audio →
    audio_utils.finalize_audio に通すため)。
    """
    if n_layers is None:
        n_layers = random.randint(2, 3)
    if tempo_density is None:
        tempo_density = random.choice(list(_TEMPO_DENSITY_PARAMS))
    density_params = _TEMPO_DENSITY_PARAMS[tempo_density]

    all_segments = [
        _build_glitch_segments(target_seconds, **density_params) for _ in range(n_layers)
    ]

    cmd = ["ffmpeg", "-y"]
    idx = 0
    filter_parts = []
    layer_labels = []
    for layer_idx, segments in enumerate(all_segments):
        seg_labels = []
        for src, filt in segments:
            cmd += ["-f", "lavfi", "-i", src]
            label = f"l{layer_idx}_{idx}"
            filter_parts.append(f"[{idx}:a]{filt}[{label}]")
            seg_labels.append(f"[{label}]")
            idx += 1
        concat_inputs = "".join(seg_labels)
        filter_parts.append(f"{concat_inputs}concat=n={len(segments)}:v=0:a=1[layer{layer_idx}]")
        layer_labels.append(f"[layer{layer_idx}]")

    mix_inputs = "".join(layer_labels)
    filter_parts.append(f"{mix_inputs}amix=inputs={n_layers}:duration=longest:normalize=1[mixed]")

    echo = _random_echo_params()
    if echo is None:
        filter_parts.append("[mixed]anull[out]")
    else:
        in_gain, out_gain, delay, decay = echo
        filter_parts.append(f"[mixed]aecho={in_gain}:{out_gain}:{delay}:{decay}[out]")

    filter_complex = ";".join(filter_parts)

    cmd += ["-filter_complex", filter_complex, "-map", "[out]", wav_path]
    subprocess.run(cmd, check=True, capture_output=True)
