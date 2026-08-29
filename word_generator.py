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
    """フレーム表示用に、結合文字を落として土台の文字だけ取り出した簡易ラベル"""
    stripped = "".join(ch for ch in word if not unicodedata.combining(ch))
    stripped = stripped.strip()
    if len(stripped) > max_base_chars:
        stripped = stripped[:max_base_chars] + "..."
    return stripped or "???"
