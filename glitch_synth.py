"""
合成グリッチ音を「答え」として当てる方式 [--mode glitch]

正弦波のチャープ/ビブラート音・ノイズバースト・ビットクラッシュ・エコーを
ランダムな順番と長さで組み合わせ、1本のffmpegコマンドで書き出す。単語の文
字列そのものは音には反映されない(あくまで「発音でっち上げ」パターンなの
で、動画タイトル側だけに使う)。
"""

import random
import subprocess

NOISE_COLORS = ["white", "pink", "brown"]


def _one_glitch_segment():
    """(lavfi入力文字列, セグメント個別フィルタ, 長さ秒) を1つ返す"""
    kind = random.choice(["tone", "tone_vibrato", "noise", "silence"])
    if kind == "tone":
        freq = random.randint(70, 2400)
        dur = round(random.uniform(0.12, 0.42), 2)
        src = f"sine=frequency={freq}:duration={dur}"
        filt = f"acrusher=bits={random.randint(3,6)}:mode=lin:aa=0" if random.random() < 0.6 else "anull"
    elif kind == "tone_vibrato":
        freq = random.randint(70, 2400)
        dur = round(random.uniform(0.15, 0.45), 2)
        src = f"sine=frequency={freq}:duration={dur}"
        filt = f"vibrato=f={random.randint(4,20)}:d={round(random.uniform(0.5,1.0),2)}"
    elif kind == "noise":
        color = random.choice(NOISE_COLORS)
        dur = round(random.uniform(0.1, 0.3), 2)
        amp = round(random.uniform(0.4, 0.75), 2)
        src = f"anoisesrc=d={dur}:c={color}:a={amp}"
        filt = f"acrusher=bits={random.randint(3,5)}:mode=lin:aa=0" if random.random() < 0.5 else "anull"
    else:  # silence (short gap for rhythm)
        dur = round(random.uniform(0.05, 0.15), 2)
        src = f"anullsrc=r=44100:cl=mono:d={dur}"
        filt = "anull"
    return src, filt, dur


def _build_glitch_segments(target_seconds):
    """合計の長さが target_seconds に達するまでセグメントを積む"""
    segments = []
    total = 0.0
    while total < target_seconds:
        src, filt, dur = _one_glitch_segment()
        segments.append((src, filt))
        total += dur
        if len(segments) > 60:  # 極端に短いセグメントが続いた場合の保険
            break
    return segments


def synthesize_glitch_chunk(wav_path, target_seconds=2.0):
    """ランダムなグリッチ効果音の「素の断片」を1本のffmpegコマンドで合成する。

    パディングやフェードはここではやらない(audio_utils.repeat_audio →
    audio_utils.finalize_audio に通すため)。
    """
    segments = _build_glitch_segments(target_seconds)

    cmd = ["ffmpeg", "-y"]
    for src, _ in segments:
        cmd += ["-f", "lavfi", "-i", src]

    filter_parts = []
    labels = []
    for i, (_, filt) in enumerate(segments):
        label = f"a{i}"
        filter_parts.append(f"[{i}:a]{filt}[{label}]")
        labels.append(f"[{label}]")

    concat_inputs = "".join(labels)
    filter_parts.append(f"{concat_inputs}concat=n={len(segments)}:v=0:a=1[cat]")
    filter_parts.append(
        f"[cat]aecho=0.8:0.7:{random.randint(20,60)}:{round(random.uniform(0.25,0.45),2)}[out]"
    )

    filter_complex = ";".join(filter_parts)

    cmd += ["-filter_complex", filter_complex, "-map", "[out]", wav_path]
    subprocess.run(cmd, check=True, capture_output=True)
