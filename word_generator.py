"""
Zalgo風「発音不能な単語」のランダム生成。

実在のZalgoソング名を分析すると「vOOOOOOOooo」のように母音を連打した
“読める塊” が土台にあり、そこへ結合文字と記号を足す構造になっていた。
それに寄せて、時々同じ母音を連続させるようにしている。
"""

import random
import unicodedata

from config import (
    BASE_CHARS,
    DECORATIVE_SYMBOLS,
    SAFE_COMBINING_BLOCKS,
    SEPARATOR_SYMBOLS,
)


def _random_combining_stack(n):
    """n個の結合文字を、必ず単一ブロックの中だけから選んで生成する"""
    block = random.choice(SAFE_COMBINING_BLOCKS)
    return "".join(chr(random.choice(block)) for _ in range(n))


def random_zalgo_word(base_len=(6, 12), stack_depth=(3, 10), repeat_run_chance=0.35):
    """発音できそうな土台文字に、結合文字を大量に重ねてZalgo化する。"""
    n_base = random.randint(*base_len)
    word_chars = []
    i = 0
    while i < n_base:
        base = random.choice(BASE_CHARS)
        # 一定確率で同じ文字を連打する(実例の "OOOOOOOooo" のような塊)
        if random.random() < repeat_run_chance:
            run_len = random.randint(2, 6)
            for _ in range(min(run_len, n_base - i)):
                word_chars.append(base)
                i += 1
            continue
        n_stack = random.randint(*stack_depth)
        marks = _random_combining_stack(n_stack)
        word_chars.append(base + marks)
        i += 1

    word = "".join(word_chars)

    # 区切り記号(結合文字は乗せない、単体のまま)
    if random.random() < 0.6:
        sep = random.choice(SEPARATOR_SYMBOLS)
        word = f"{sep}{word}{random.choice(SEPARATOR_SYMBOLS)}"

    # 装飾記号をところどころ挟む(無音確認済みのものだけ)
    n_deco = random.randint(1, 3)
    deco = " ".join(random.choice(DECORATIVE_SYMBOLS) for _ in range(n_deco))

    return f"{word} {deco}"


def readable_label(word, max_base_chars=12):
    """動画タイトル・説明欄・ファイル名用に、結合文字を落として土台の文字だけ
    取り出した簡易ラベル(結合文字混じりだとタイトル等が読めなくなるため)。

    動画フレーム(サムネイル)表示にはこちらではなく zalgo_display_word() を
    使う。フォントサイズの算出だけは引き続きこちらの長さを基準にする
    (zalgo_display_word() は結合文字を含む分、単純な文字数比較がフレーム
    上の見た目の大きさと対応しなくなるため)。"""
    stripped = "".join(ch for ch in word if not unicodedata.combining(ch))
    stripped = stripped.strip()
    if len(stripped) > max_base_chars:
        stripped = stripped[:max_base_chars] + "..."
    return stripped or "???"


def zalgo_display_word(word, max_base_chars=12, max_marks_per_cluster=4):
    """動画フレーム表示用に、結合文字(Zalgoの見た目)は残したまま、
    readable_label()と同じ「土台文字の数」基準でmax_base_charsまで
    切り詰めた文字列を返す。

    readable_label()は結合文字を全て落として読みやすいラベルを作るが、
    フレームの見た目にそれをそのまま使うと肝心のZalgo感がほぼ消えてしまう
    (226種の結合文字候補のうち、Unicode上たまたま「結合文字」に分類され
    ていない数種類しかreadable_label()をすり抜けず、実質ほぼ普通の文字列
    になってしまっていた)。そのためこちらは結合文字を保持したまま、
    readable_label()と同じ件数基準で切り詰めることで、フォントサイズの
    算出(readable_label()の長さ基準)と表示内容の対応を保っている。

    max_marks_per_cluster: 1つの土台文字に乗せる結合文字を表示上は最大
    何個までにするか。random_zalgo_word()のstack_depthは最大10だが、
    それをそのままフレームに描画すると(特に短い単語でフォントサイズが
    大きくなる場合に)積み重ねが縦にキッカー文言まで達してしまうことが
    あるため、表示用にのみ切り詰める(TTSの読み上げやYouTube説明欄に載る
    実際の単語には手を付けない)。"""
    units = []
    for ch in word:
        if unicodedata.combining(ch):
            if units:
                units[-1] += ch
            # 土台文字より前に結合文字が出た場合は無視する(readable_label()も
            # 結合文字自体は出力に含めないため。word_generator側の構造上
            # 通常は起こらないが、空文字列等の異常入力での念のための処理)
        else:
            units.append(ch)

    # readable_label()の strip() 相当(先頭/末尾の空白の単位を除く。
    # word_generator側の構造上、空白に結合文字が乗ることはない)
    while units and units[0].strip() == "":
        units.pop(0)
    while units and units[-1].strip() == "":
        units.pop()

    def _cap_marks(unit):
        base, marks = unit[0], unit[1:]
        return base + marks[:max_marks_per_cluster]

    units = [_cap_marks(u) for u in units]

    if len(units) > max_base_chars:
        return "".join(units[:max_base_chars]) + "..."
    return "".join(units) or "???"
