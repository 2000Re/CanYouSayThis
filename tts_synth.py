"""TTS (espeak-ng) で単語をそのまま読ませる方式 [--mode tts / デフォルト]
および、それを奇妙な声質・極端なピッチ+ffmpegの歪みフィルタで壊す方式
[--mode tts_extreme]。"""

import os
import random
import subprocess

# espeak-ng標準搭載の「奇妙な声」バリエーション(espeak-ng-data/voices/!v)。
# 実際にespeak-ngへ通してエラーなく合成できることを確認済みのもののみ採用。
EXTREME_VOICE_VARIANTS = [
    "Demonic", "Tweaky", "UniRobot", "AnxiousAndy", "croak", "whisper",
    "klatt", "klatt2", "robosoft", "robosoft3", "robosoft6",
]


def synthesize_tts(word, wav_path, voice="en", speed=150):
    """espeak-ngに単語を読ませ、生の音声(パディング無し)をwav_pathへ書き出す"""
    txt_path = wav_path + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(word)
    subprocess.run(
        ["espeak-ng", "-v", voice, "-s", str(speed), "-f", txt_path, "-w", wav_path],
        check=True,
        capture_output=True,
    )
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


def synthesize_tts_extreme(word, wav_path, voice="en"):
    """espeak-ngの奇妙な声バリエーション+極端なピッチ・速度で単語を読ませた
    うえで、さらにffmpegでピッチシフト・ビットクラッシュ等をランダムに
    かけて歪ませる。synthesize_tts()と違い、毎回声質そのものが変わる。"""
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
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav, "-af", filter_str, wav_path],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)
