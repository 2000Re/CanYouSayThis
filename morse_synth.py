"""単語をモールス信号のビープ音列に変換する方式 [--mode morse]

espeak-ngには一切頼らず、国際モールス符号表(ITU-R M.1677-1)に基づいて
ラテン文字だけをビープ音(sine波)と無音(anullsrc)の並びに変換する。
glitch_synth.pyと同じく単語の「発音」とは無関係だが、glitch_synth.pyが
完全にランダムな効果音なのに対し、こちらは単語の中身(文字)がそのまま
音のパターンに決定論的に反映される、という別角度のギミック。

結合文字(Zalgoの見た目)・装飾記号は符号表に無いため無視する
(word_generator.random_zalgo_word()の土台(BASE_CHARS)はラテン文字の
みなので、実際にはほぼ全ての「土台文字」が変換対象になる)。
"""

import random
import subprocess

# 国際モールス符号表。ラテン文字(大文字小文字問わず)と、
# word_generator.SEPARATOR_SYMBOLSに含まれる4記号のみを対象にする。
# それ以外の文字(結合文字・装飾記号)は対応表に無いため無視する。
MORSE_CODE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "(": "-.--.", ")": "-.--.-", ":": "---...", "-": "-....-",
}


def _units_for_word(word):
    """word中の各文字を、モールス符号の要素列(トーン/無音の長さ倍率の
    リスト)に変換する。1要素は (is_tone: bool, unit_count: int) のタプル。

    タイミングはITU標準に準拠: 短点(.)=1ユニット、長点(-)=3ユニット、
    同一文字内の要素間=1ユニットの無音、文字間=3ユニットの無音、
    単語間(スペース文字)=7ユニットの無音。

    対応表に無い文字(結合文字・装飾記号)は無視する(音にも反映されない)。"""
    units = []
    prev_was_letter = False
    for ch in word:
        if ch == " ":
            if units:
                units.append((False, 7))
            prev_was_letter = False
            continue
        code = MORSE_CODE.get(ch.upper())
        if code is None:
            continue
        if prev_was_letter:
            units.append((False, 3))
        for i, symbol in enumerate(code):
            if i > 0:
                units.append((False, 1))
            units.append((True, 1 if symbol == "." else 3))
        prev_was_letter = True
    return units


def synthesize_morse(word, wav_path, unit_duration=None, freq=None):
    """wordをモールス信号のビープ音列に変換してwav_pathへ書き出す。

    unit_duration(1ユニットの長さ・秒)とfreq(トーンの周波数・Hz)は
    省略時ランダムに選ぶ(他モードと同じく、毎回の質感にバリエーションを
    持たせるため)。unit_durationはアマチュア無線の標準的な速度より意図的に
    速め(実機で計測した結果、標準的な速度だと1本の単語(6〜12文字+区切り
    記号)で10秒を超えてしまい、Shortsの尺として長すぎたため。README
    「ハマった罠」参照)にしている。"""
    if unit_duration is None:
        unit_duration = round(random.uniform(0.015, 0.03), 3)
    if freq is None:
        freq = random.randint(500, 900)

    units = _units_for_word(word)
    if not units:
        # 対応表に無い文字だけの単語だった場合の保険(word_generator側の
        # 構造上、random_zalgo_word()の土台はBASE_CHARSのラテン文字のため
        # 通常は起こらない)。
        units = [(True, 1)]

    cmd = ["ffmpeg", "-y"]
    filter_parts = []
    labels = []
    for idx, (is_tone, n_units) in enumerate(units):
        dur = round(unit_duration * n_units, 3)
        if is_tone:
            src = f"sine=frequency={freq}:duration={dur}"
        else:
            src = f"anullsrc=r=44100:cl=mono:d={dur}"
        cmd += ["-f", "lavfi", "-i", src]
        label = f"s{idx}"
        filter_parts.append(f"[{idx}:a]anull[{label}]")
        labels.append(f"[{label}]")

    concat_inputs = "".join(labels)
    filter_parts.append(f"{concat_inputs}concat=n={len(labels)}:v=0:a=1[out]")
    filter_complex = ";".join(filter_parts)

    cmd += ["-filter_complex", filter_complex, "-map", "[out]", wav_path]
    subprocess.run(cmd, check=True, capture_output=True)
