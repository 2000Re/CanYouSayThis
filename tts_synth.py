"""TTS (espeak-ng) で単語をそのまま読ませる方式 [--mode tts / デフォルト]
および、それを奇妙な声質・極端なピッチ+ffmpegの歪みフィルタで壊す方式
[--mode tts_extreme]。"""

import os
import random
import subprocess

import config
from audio_utils import _probe_duration

# espeak-ng標準搭載の「奇妙な声」バリエーション(espeak-ng-data/voices/!v)。
# 実際にespeak-ngへ通してエラーなく合成できることを確認済みのもののみ採用。
EXTREME_VOICE_VARIANTS = [
    "Demonic", "Tweaky", "UniRobot", "AnxiousAndy", "croak", "whisper",
    "klatt", "klatt2", "robosoft", "robosoft3", "robosoft6",
]


def synthesize_tts(word, wav_path, voice="en", speed=150, pitch=None):
    """espeak-ngに単語を読ませ、生の音声(パディング無し)をwav_pathへ書き出す。

    pitch(espeak-ngの-p、0〜99、デフォルト50)を指定すると、ボイス本来の
    ピッチカーブに対して声の高さを底上げ/引き下げできる。generate.pyでは
    女性ボイス選択時にこれで少し高めに寄せている(config.FEMALE_VOICE_PITCH
    参照)。未指定時はespeak-ngのデフォルトのまま。"""
    txt_path = wav_path + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(word)
    command = ["espeak-ng", "-v", voice, "-s", str(speed)]
    if pitch is not None:
        command += ["-p", str(pitch)]
    command += ["-f", txt_path, "-w", wav_path]
    subprocess.run(command, check=True, capture_output=True)
    os.remove(txt_path)


def _random_extreme_filter_chain():
    """TTSの生音声にかける歪みフィルタをランダムに選んで返す
    (ffmpegのaudio filter文字列のリスト。glitch_synth.pyの
    「毎回パラメータをランダム化し、固定の質感にしない」方針を踏襲)。"""
    candidates = []

    if random.random() < 0.5:
        # サンプルレートを変えてから元のレートへ戻す素朴なピッチシフト
        # (テンポも一緒に変わるので、悪魔声/甲高い声の両方を作れる)。
        if random.random() < 0.5:
            factor = round(random.uniform(0.55, 0.8), 2)  # 悪魔声(低く・遅く)
        else:
            factor = round(random.uniform(1.3, 1.9), 2)  # 甲高い声(高く・速く)
        candidates.append(f"asetrate=44100*{factor},aresample=44100")

    if random.random() < 0.5:
        candidates.append(f"acrusher=bits={random.randint(2, 6)}:mode=lin:aa=0")

    if random.random() < 0.4:
        candidates.append(f"vibrato=f={random.randint(2, 20)}:d={round(random.uniform(0.3, 1.0), 2)}")

    if random.random() < 0.4:
        candidates.append(f"tremolo=f={random.randint(5, 30)}:d={round(random.uniform(0.3, 0.8), 2)}")

    if random.random() < 0.4:
        candidates.append(
            f"aecho=0.8:0.7:{random.randint(20, 80)}:{round(random.uniform(0.2, 0.5), 2)}"
        )

    if not candidates:
        # 何も選ばれなかった場合の保険(tts_extremeなので必ず何かしら歪ませる)
        candidates.append(f"acrusher=bits={random.randint(3, 6)}:mode=lin:aa=0")

    return candidates


def _atempo_chain_for_factor(factor):
    """任意の倍率をffmpegの`atempo`フィルタ文字列(カンマ区切りでチェーン
    可能)に変換する。`atempo`は1回あたり0.5〜2.0倍の範囲しか指定できない
    仕様のため、範囲外の倍率はその上限/下限を複数回チェーンして表現する。"""
    parts = []
    remaining = factor
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    parts.append(f"atempo={round(remaining, 3)}")
    return ",".join(parts)


def _stretch_to_min_duration(src_path, dst_path, min_duration, max_passes=3):
    """src_pathの長さがmin_duration未満であれば、atempoで再生速度を落として
    引き伸ばす。1回のatempo適用だけだと(特に0.2秒未満のような極端に短い
    音声で)狙った長さにきっちり収まらないことが実機で確認できたため、
    再生成後の長さを都度測り直して収束するまで(最大max_passes回)繰り返す。
    元々min_duration以上あれば何もせずそのままdst_pathにコピーする。"""
    current = src_path
    for pass_index in range(max_passes):
        duration = _probe_duration(current)
        if duration >= min_duration:
            break
        factor = duration / min_duration
        # ffmpegはinput/outputに同じファイルを指定できないため、パスごとに
        # 別名にする(同名を使い回すと直前の出力を読みながら同時に上書き
        # しようとして壊れる)。
        next_path = f"{dst_path}.stretch_tmp{pass_index}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", current, "-af", _atempo_chain_for_factor(factor), next_path],
            check=True,
            capture_output=True,
        )
        if current != src_path:
            os.remove(current)
        current = next_path
    if current == src_path:
        subprocess.run(["ffmpeg", "-y", "-i", current, dst_path], check=True, capture_output=True)
    else:
        os.replace(current, dst_path)


def synthesize_tts_extreme(word, wav_path, voice="en"):
    """espeak-ngの奇妙な声バリエーション+極端なピッチ・速度で単語を読ませた
    うえで、さらにffmpegでピッチシフト・ビットクラッシュ等をランダムに
    かけて歪ませる。synthesize_tts()と違い、毎回声質そのものが変わる。

    短い単語×速い読み上げ×テンポを上げる歪みフィルタが重なると、実機の
    検証で最短0.1秒程度まで縮み「発音」ではなく一瞬のノイズにしか聞こえな
    くなることを確認したため、最終的な長さが
    config.TTS_EXTREME_MIN_DURATION_SECONDS を下回った場合は
    _stretch_to_min_duration() で引き伸ばす。"""
    variant = random.choice(EXTREME_VOICE_VARIANTS)
    pitch = random.randint(0, 99)  # espeak-ngの-p範囲(デフォルト50)
    speed = random.randint(60, 400)  # espeak-ngの-s(デフォルト175)を大きく振る

    raw_wav = wav_path + ".raw.wav"
    txt_path = wav_path + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(word)
    subprocess.run(
        ["espeak-ng", "-v", f"{voice}+{variant}", "-p", str(pitch), "-s", str(speed),
         "-f", txt_path, "-w", raw_wav],
        check=True,
        capture_output=True,
    )
    os.remove(txt_path)

    filter_str = ",".join(_random_extreme_filter_chain())
    filtered_wav = wav_path + ".filtered.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav, "-af", filter_str, filtered_wav],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)

    _stretch_to_min_duration(filtered_wav, wav_path, config.TTS_EXTREME_MIN_DURATION_SECONDS)
    if os.path.exists(filtered_wav):
        os.remove(filtered_wav)
