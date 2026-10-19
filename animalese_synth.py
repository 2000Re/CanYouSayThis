"""「どうぶつの森」のキャラクターボイス(Animalese)風に、文字ごとの短い
効果音をつなげて読み上げ風の音を作る方式 [--mode animalese]

espeak-ngの本物のTTSとは別物で、a〜z(+"th"/"sh"の2文字組・スペース・
句読点)それぞれに対応する短い録音済み音声(animalese_sounds/<ピッチ>/
soundNN.wav)をピッチシフトしながらつなげるだけ。視聴者コメントで
紹介されたequalo-official/animalese-generator(MITライセンス、
animalese_sounds/LICENSE参照)の仕組みを、このプロジェクトの
generate_one()から呼べる形に移植した。

結合文字(Zalgoの見た目)はそのまま無視する(morse_synth.pyと同じ方針)。
一方、対応表に無い記号・非ラテン文字・楔形文字等は無視するのではなく、
word_generator.expand_unknown_chars_to_names()でUnicode正式名称に展開
してから読ませる(README「ハマった罠」89番)。espeak-ngを使わないため、
楔形文字等を読ませてコードポイントを桁ごとに読み上げてしまう問題
(README「ハマった罠」58番)はそもそも起こらない。

録音済み音声はa-z+th/sh/space/periodのみで数字の音が無いため、展開後の
名称に含まれる数字(例: CJK統合漢字の名称末尾のコードポイント表記)は、
_DIGIT_WORDSで英単語に変換したうえでa-zの音を使って読ませる。
"""

import os
import random
import unicodedata

from pydub import AudioSegment

from word_generator import expand_unknown_chars_to_names

_SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "animalese_sounds")
PITCH_PRESETS = ["lowest", "low", "med", "high"]

# equalo-official/animalese-generatorのanimalese.pyと同じ並び
# (soundNN.wavのNNがこの並びのインデックス+1に対応する、録音済みファイル
# 自体の命名規則のため変更不可)。
_KEYS = list("abcdefghijklmnopqrstuvwxyz") + ["th", "sh", " ", "."]

# 録音済み音声に数字が無いため、英単語に変換してa-zの音で読ませる
# (_infiles_for_word()参照)。
_DIGIT_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}


def _sound_path(pitch, key):
    index = _KEYS.index(key) + 1
    return os.path.join(_SOUNDS_DIR, pitch, f"sound{index:02d}.wav")


def _infiles_for_word(word, pitch):
    """wordを小文字化し、_KEYSに対応する音声ファイルパスのリストに変換する。

    "th"/"sh"の2文字組を優先的に検出し、カンマ・疑問符は句点と同じ音に
    丸める。直前と同じ文字が連続する場合はスキップ(animalese特有の
    「同じ音の連打を避ける」挙動、元実装を踏襲)。結合文字(Zalgoの見た目)
    は対応表に無いため無視する。それ以外の対応表に無い文字(記号・非
    ラテン文字・楔形文字等)は、expand_unknown_chars_to_names()でUnicode
    正式名称に展開し、名称中の数字は_DIGIT_WORDSで英単語に変換したうえで
    読ませる(README「ハマった罠」89番)。"""
    word = expand_unknown_chars_to_names(
        word,
        lambda ch: (
            unicodedata.combining(ch) != 0
            or ch.lower() in _KEYS
            or ch in (",", "?")
            or ch in _DIGIT_WORDS
        ),
    )
    word = "".join(f" {_DIGIT_WORDS[ch]} " if ch in _DIGIT_WORDS else ch for ch in word)
    stringy = word.lower()
    infiles = []
    for i, char in enumerate(stringy):
        if char == "s" and i + 1 < len(stringy) and stringy[i + 1] == "h":
            infiles.append(_sound_path(pitch, "sh"))
            continue
        if char == "t" and i + 1 < len(stringy) and stringy[i + 1] == "h":
            infiles.append(_sound_path(pitch, "th"))
            continue
        if char == "h" and i > 0 and stringy[i - 1] in ("s", "t"):
            continue
        if char in (",", "?"):
            infiles.append(_sound_path(pitch, "."))
            continue
        if i > 0 and char == stringy[i - 1]:
            continue
        if char not in _KEYS:
            continue
        infiles.append(_sound_path(pitch, char))
    return infiles


def synthesize_animalese(word, wav_path, pitch=None):
    """wordをAnimalese風の音声に変換してwav_pathへ書き出す。

    pitch("lowest"/"low"/"med"/"high")は省略時ランダムに選ぶ(他モードと
    同じく、毎回の質感にバリエーションを持たせるため)。対応する文字が
    1つも無かった場合(非ラテン文字のみの単語を--wordで直接指定した場合等)
    は、"a"の音1つだけの短い音声を代わりに使う(morse_synth.pyの
    フォールバックと同じ考え方)。"""
    if pitch is None:
        pitch = random.choice(PITCH_PRESETS)

    infiles = _infiles_for_word(word, pitch)
    if not infiles:
        infiles = [_sound_path(pitch, "a")]

    ends_with_question = word.rstrip().endswith("?")
    rnd_factor = 0.35 if pitch == "med" else 0.25

    combined = None
    for index, path in enumerate(infiles):
        sample = AudioSegment.from_wav(path)
        if ends_with_question and index >= len(infiles) * 0.8:
            octaves = random.random() * rnd_factor + (index - len(infiles) * 0.8) * 0.1 + 2.1
        else:
            octaves = random.random() * rnd_factor + 2.3
        new_sample_rate = int(sample.frame_rate * (2.0**octaves))
        shifted = sample._spawn(sample.raw_data, overrides={"frame_rate": new_sample_rate})
        shifted = shifted.set_frame_rate(44100)
        combined = shifted if combined is None else combined + shifted

    combined.export(wav_path, format="wav")
