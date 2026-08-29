"""TTS (espeak-ng) で単語をそのまま読ませる方式 [--mode tts / デフォルト]"""

import os
import subprocess


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
