"""モールス信号風のビープ音を「答え」として当てる方式 [--mode morse]

単語の中から英数字の土台文字だけを取り出し、実際の国際モールス符号に変換
してビープ音で鳴らす。エンコード自体は本物だが、「聞いてモールス符号を
読み取れる」ことを狙った機能ではなく、glitch_synth.pyと同じく「これが
発音だ」と主張する別系統のでっち上げパターンの1つ(word_generator側の
単語文字列そのものや、frame_builder側の表示には一切手を付けない)。
"""

import random
import subprocess

# 国際モールス符号(英数字のみ)。word_generator.BASE_CHARSは母音+v/n/m/r/l
# 中心で、結合文字・記号(SEPARATOR_SYMBOLS/DECORATIVE_SYMBOLS)は元々ここに
# 含まれないため未対応でよい。
MORSE_CODE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".",
    "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---",
    "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---",
    "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-",
    "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--",
    "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
}

# フォールバック用(英数字を1文字も含まない単語だった場合の、それっぽい
# ダミー符号)。word_generator.BASE_CHARSの構造上、実際にはほぼ発生しない。
_FALLBACK_SYMBOLS = [".", "-", "..", "--", ".-", "-."]

# word_generator.random_zalgo_word()は同じ母音を何十文字も連打すること
# がある(モジュールdocstring参照)。1文字ずつ律儀にモールス符号化すると
# 単語によって尺が数十秒単位でばらついてしまうため、readable_label()の
# max_base_charsと同じ発想で、先頭からこの文字数ぶんだけ符号化する
# (tts/glitchモードの典型的な尺(数秒程度)に揃えるため、6ではなく4に
# 抑えている。6だと"O"連打のような重い符号が続く単語で10秒を超えていた)。
MAX_MORSE_LETTERS = 4


def word_to_morse_letters(word, max_letters=MAX_MORSE_LETTERS):
    """英数字だけをモールス符号のリストに変換する(1要素が1文字分の符号)。
    結合文字・記号など非対応の文字は無視し、先頭からmax_letters文字ぶん
    だけを符号化する。英数字を1文字も含まない場合は空リストを返す
    (呼び出し側でフォールバックする)。"""
    letters = [MORSE_CODE[ch] for ch in word.upper() if ch in MORSE_CODE]
    return letters[:max_letters]


def _build_morse_segments(letters, unit, freq):
    """モールス符号(文字ごとの.-のリスト)を、(lavfi入力文字列, 長さ秒)の
    リストに変換する。国際モールス符号の標準タイミング比率
    (dot=1unit、dash=3unit、符号間の無音=1unit、文字間の無音=3unit)。"""
    segments = []
    for letter_idx, code in enumerate(letters):
        for symbol_idx, symbol in enumerate(code):
            dur = unit if symbol == "." else unit * 3
            segments.append((f"sine=frequency={freq}:duration={dur}", dur))
            if symbol_idx < len(code) - 1:
                segments.append((f"anullsrc=r=44100:cl=mono:d={unit}", unit))
        if letter_idx < len(letters) - 1:
            gap = unit * 3
            segments.append((f"anullsrc=r=44100:cl=mono:d={gap}", gap))
    return segments


def synthesize_morse_chunk(word, wav_path):
    """wordをモールス符号に変換し、ビープ音1本のffmpegコマンドで合成する。
    unit(1符号あたりの長さ)とfreq(トーンの高さ)は毎回ランダムに変え、
    同じ単語でも「答え」の質感が固定にならないようにする
    (glitch_synth.pyと同じ狙い)。"""
    letters = word_to_morse_letters(word)
    if not letters:
        letters = [random.choice(_FALLBACK_SYMBOLS) for _ in range(5)]

    unit = round(random.uniform(0.035, 0.08), 3)
    freq = random.randint(450, 900)

    segments = _build_morse_segments(letters, unit, freq)

    cmd = ["ffmpeg", "-y"]
    for src, _ in segments:
        cmd += ["-f", "lavfi", "-i", src]

    labels = "".join(f"[{i}:a]" for i in range(len(segments)))
    filter_complex = f"{labels}concat=n={len(segments)}:v=0:a=1[out]"

    cmd += ["-filter_complex", filter_complex, "-map", "[out]", wav_path]
    subprocess.run(cmd, check=True, capture_output=True)
