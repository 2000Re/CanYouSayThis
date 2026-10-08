"""TTS (espeak-ng) で単語をそのまま読ませる方式 [--mode tts / デフォルト]
および、それを別々の角度で加工する3方式:
  - 奇妙な声質・極端なピッチ+ffmpegの歪みフィルタで壊す [--mode tts_extreme]
  - そのまま逆再生する [--mode reverse]
  - 搬送波とのリング変調でロボット風の声にする [--mode robot_voice]
  - 複数言語のボイスで同時に読み上げて重ねる [--mode chorus]
いずれも単語自体はespeak-ngに読ませており(chorusのみ複数ボイス)、
単語の内容とは無関係な合成音を当てるglitch_synth.py/morse_synth.pyとは
性質が異なる。"""

import os
import random
import subprocess

import config
from audio_utils import _probe_duration, _stretch_to_min_duration

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


def synthesize_tts_reverse(word, wav_path, voice="en", speed=150, pitch=None):
    """espeak-ngで単語を読ませた音声を、そのまま逆再生する [--mode reverse]。

    tts_extremeのピッチ/速度変化とは違い、読み上げ内容(声質・速度)自体は
    一切変えず、時間軸だけを反転させる。長さはsynthesize_tts()と完全に
    同じまま保たれるため、tts_extremeのような最短尺の保険は不要。"""
    raw_wav = wav_path + ".raw.wav"
    synthesize_tts(word, raw_wav, voice=voice, speed=speed, pitch=pitch)
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav, "-af", "areverse", wav_path],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)


def synthesize_tts_robot(word, wav_path, voice="en", speed=150, pitch=None, carrier_freq=None):
    """espeak-ngで単語を読ませた音声に、搬送波(サイン波)とのリング変調
    (ffmpegの`amultiply`で2つの音声ストリームをサンプルごとに掛け合わせる)
    をかけ、ロボット/ダース・ベイダー風の声にする [--mode robot_voice]。
    tts_extremeのピッチ/速度変化+ビットクラッシュとは別の軸の歪み。

    実機で確認したところ、単純にamultiplyしただけだとRMS音量が元の音声
    より約20dB(振幅にして約1/10)下がってしまう(2つの[-1,1]信号を掛け
    合わせる性質上、振幅が縮む)ため、volumeで底上げしたうえでalimiterで
    クリッピングを防いでいる(README「ハマった罠」参照)。"""
    if carrier_freq is None:
        carrier_freq = random.randint(30, 120)  # 低いほど「ブーン」とした金属質な唸りになる

    raw_wav = wav_path + ".raw.wav"
    synthesize_tts(word, raw_wav, voice=voice, speed=speed, pitch=pitch)
    duration = _probe_duration(raw_wav)

    carrier_src = f"sine=frequency={carrier_freq}:duration={duration}"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", raw_wav,
            "-f", "lavfi", "-i", carrier_src,
            "-filter_complex", "[0:a][1:a]amultiply,volume=10,alimiter=limit=0.95[out]",
            "-map", "[out]", wav_path,
        ],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)


def synthesize_tts_chorus(word, wav_path, n_voices=(3, 4)):
    """同じ単語を複数言語のTTSボイスで同時に読み上げ、重ねてミックスする
    [--mode chorus]。「多言語で一斉に発音してみたら」という、単一の声を
    加工する他方式とは別角度のギミック。

    config.VOICE_LANGUAGESから重複無くn_voices個の言語をランダムに選び、
    各言語ごとに性別もランダムに選ぶ(femaleが無い言語はmaleのみ)。開始
    タイミングを少しだけランダムにずらす(adelay)ことで、完全に揃って
    読み上げるのではなく「めいめいバラバラに話し始める」自然さを出す。

    実機で確認したところ、amix(normalize=1)だけだと単一ボイスの音声より
    RMS音量が下がる(声の数で割られるため)ため、volumeで底上げしたうえで
    alimiterでクリッピングを防いでいる(synthesize_tts_robot()と同じ理由。
    README「ハマった罠」参照)。

    候補言語はconfig.VOICE_LANGUAGES全体ではなくconfig.CHORUS_VOICE_LANGUAGE_CODES
    (ヘブライ語を除いたもの)を使う。ヘブライ語ボイスでZalgo単語を読ませると
    他言語の3倍近い長さになることを実機で確認したため(config.py参照)。"""
    n = random.randint(*n_voices)
    lang_codes = random.sample(
        config.CHORUS_VOICE_LANGUAGE_CODES, k=min(n, len(config.CHORUS_VOICE_LANGUAGE_CODES))
    )

    raw_paths = []
    for i, lang_code in enumerate(lang_codes):
        entry = config.VOICE_LANGUAGES[lang_code]
        genders = ["male"] + (["female"] if entry["female"] else [])
        gender = random.choice(genders)
        raw_path = f"{wav_path}.chorus{i}.wav"
        synthesize_tts(word, raw_path, voice=entry[gender], speed=config.DEFAULT_SPEED)
        raw_paths.append(raw_path)

    cmd = ["ffmpeg", "-y"]
    filter_parts = []
    labels = []
    for i, path in enumerate(raw_paths):
        cmd += ["-i", path]
        delay_ms = random.randint(0, 250)
        label = f"v{i}"
        filter_parts.append(f"[{i}:a]adelay={delay_ms}:all=1[{label}]")
        labels.append(f"[{label}]")

    mix_inputs = "".join(labels)
    filter_parts.append(
        f"{mix_inputs}amix=inputs={len(raw_paths)}:duration=longest:normalize=1,"
        "volume=2.2,alimiter=limit=0.95[out]"
    )
    filter_complex = ";".join(filter_parts)

    cmd += ["-filter_complex", filter_complex, "-map", "[out]", wav_path]
    subprocess.run(cmd, check=True, capture_output=True)

    for path in raw_paths:
        os.remove(path)
