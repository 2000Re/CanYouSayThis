#!/usr/bin/env python3
"""
comment_requests.py

視聴者コメントから単語リクエストを自動検出し、検出した単語を
comment_request_words.txt(1行1件)に書き出すCLIスクリプト
(comment_requests.ymlから実行)。

[背景] 元々はコミュニティ投稿でリクエスト受付案内を出していたが誰も見て
おらず、視聴者は動画自体のコメント欄に「Can you do 'X'?」のような形で
リクエストを書き込み続けていた(README「ハマった罠」104番)。運営者が
手動でコメントを読んでgenerate.pyを個別実行する運用が続かなくなった
ため自動化する(2026-10-30、ユーザーとの相談)。

[スコープ] 実際のリクエストコメントを分析した結果、「do/can you do/
asking for」等の明示的なキーワードを伴うパターンはある程度の精度で正規
表現抽出できる一方、キーワード無しでいきなり単語から始まるパターン
(例: "X in Finnish?")は手がかりが無く誤検知が増えるため、意図的に対象
外にしている(一部のリクエストを拾えないトレードオフを許容する判断、
config.py参照)。

[安全網] 誤検知した場合に備え、ここで検出した単語は常に非公開(private)
でアップロードする(comment_requests.yml参照。generate.yml --word指定時
と同じ運用で、手動確認後にYouTube Studio側で公開する想定)。
"""
import argparse
import re

import config
from comment_request_state import load_comment_request_state, save_comment_request_state
from upload_history import load_upload_history
from youtube_upload import fetch_comments

# 実際に寄せられたリクエストコメントを分析して作ったパターン(README
# 「ハマった罠」104番参照)。
#
# [優先順位] まず動画の説明欄と同じ"Word: ..."形式の行が無いか確認する
# (_WORD_LINE_PATTERN)。これを最優先するのは、"Do you want to make? :\n\n
# Word:...\n\nMode:..."のように、動画の説明欄をそのままコピペしただけの
# 反応コメントが実際にあり、"Do"をトリガーに素朴に抽出すると"you want to
# make"のような無意味な文字列を拾ってしまうため。Word:行を優先することで、
# この種のコメントは「現在の動画と同じ単語」として_filter_known_words()の
# 重複チェックに確実に引っかかり、新規リクエストとして誤検知しない。
#
# Word:行が無い場合のみ、以下のトリガーを順に試す。"do"単体のトリガーは
# コメント全体の先頭(複数行の途中ではない)に限定している。"I'll do my
# homework"のような文中の"do"や、"Do you think...?"のような無関係な疑問文
# を誤って拾わないようにするため(トレードオフとして、"Day 3 of\n\nDo\n\n
# [単語]"のように"Do"が2行目以降に来るコメントは拾えなくなるが、安全側に
# 倒す判断)。
_WORD_LINE_PATTERN = re.compile(r"^word\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_REQUEST_TRIGGERS = [
    re.compile(r"(?:can|could)\s+you\s+do\b", re.IGNORECASE),
    re.compile(r"would it be possible to do\b", re.IGNORECASE),
    re.compile(r"asking for\b", re.IGNORECASE),
    re.compile(r"^do\b", re.IGNORECASE),
]

# クォート文字(straight/curly、シングル/ダブル)。開始クォートの直後から
# 対応する終了クォードまでを単語として抜き出す(例: 'Can you do "X" with
# Icelandic voice'のような、クォートの外側に付随テキストがあるケースに
# 対応するため)。
_QUOTE_CHARS = "\"'‘“"
_CLOSING_QUOTE = {"‘": "’", "“": "”"}  # straight quotesは自分自身が終了側

# 761文字という極端に長い--wordリクエストが来た実例(README「ハマった罠」
# 68番)を踏まえた常識的な上限。
_MAX_WORD_LENGTH = 200


def _extract_after_trigger(text, trigger):
    """trigger(正規表現)にマッチした直後から、クォートがあればその中身
    だけを、無ければ改行までの1行を取り出す(末尾の"?"は取り除く)。
    マッチしない/残りが空の場合はNoneを返す。"""
    m = trigger.search(text)
    if m is None:
        return None
    rest = text[m.end():].strip()
    if not rest:
        return None
    quote_match = re.search(f"[{_QUOTE_CHARS}]", rest)
    if quote_match:
        open_ch = quote_match.group()
        close_ch = _CLOSING_QUOTE.get(open_ch, open_ch)
        start = quote_match.end()
        end = rest.find(close_ch, start)
        if end > start:
            return rest[start:end].strip()
    line = rest.split("\n", 1)[0]
    line = re.sub(r"\s*\bnext\b\s*$", "", line, flags=re.IGNORECASE)
    return line.rstrip("?").strip()


def extract_requested_word(comment_text):
    """1件のコメント本文から、リクエストされた単語を抽出する。該当しない
    場合はNoneを返す。_WORD_LINE_PATTERN/_REQUEST_TRIGGERSのdocstring
    (モジュール冒頭)で説明した優先順位・トレードオフに従う。"""
    word_match = _WORD_LINE_PATTERN.search(comment_text)
    if word_match:
        candidate = word_match.group(1).strip()
    else:
        candidate = None
        for trigger in _REQUEST_TRIGGERS:
            candidate = _extract_after_trigger(comment_text, trigger)
            if candidate:
                break
    if not candidate:
        return None
    candidate = candidate.strip()
    if not candidate:
        return None
    # [罠] 壊れたクライアントが投稿したコメントには、対応する片割れの無い
    # UTF-16サロゲートコードポイント(例: U+DCB9)が紛れ込むことが実機で
    # 確認された(README「ハマった罠」107番)。googleapiclientのJSONパース
    # 自体はこれを許容してそのままPython文字列に含めてしまうため、
    # そのままgenerate.pyに渡すと--word引数の処理中にUnicodeEncodeError
    # ("surrogates not allowed")でクラッシュする。encode(errors="replace")は
    # 変換できない文字をASCIIの"?"に置き換える(Pythonの仕様上、デコード側の
    # errors="replace"と違いU+FFFDにはならない)。見た目の情報は一部失うが、
    # 以降のパイプライン(ファイル書き込み・subprocess引数・YouTube API
    # 呼び出し)のどこでも確実にUTF-8として扱えるようにする。
    candidate = candidate.encode("utf-8", errors="replace").decode("utf-8")
    if len(candidate) > _MAX_WORD_LENGTH:
        return None
    return candidate


def find_new_requests(comments_by_video, existing_words, processed_comment_ids, max_candidates):
    """comments_by_video(youtube_upload.fetch_comments()の戻り値)から、
    未処理かつ新規のリクエスト単語を抽出する。

    戻り値は (new_words, newly_seen_comment_ids) のタプル。
    - new_words: 新規リクエストと判断した単語のリスト(重複・既存単語を
      除いた、最大max_candidates件)
    - newly_seen_comment_ids: 今回実際に判定したコメントID(該当有無に
      関わらず)。processed_comment_idsへのマージ元として呼び出し側が使う。
      max_candidatesの上限に達して判定しなかった分はここに含めない
      (次回以降に持ち越すため、処理済み扱いにしない)。"""
    new_words = []
    newly_seen_ids = []
    seen_words_this_run = set()
    for comments in comments_by_video.values():
        for comment in comments:
            comment_id = comment["comment_id"]
            if comment_id in processed_comment_ids:
                continue
            if len(new_words) >= max_candidates:
                continue
            newly_seen_ids.append(comment_id)
            candidate = extract_requested_word(comment["text"])
            if candidate is None:
                continue
            if candidate in existing_words or candidate in seen_words_this_run:
                continue
            new_words.append(candidate)
            seen_words_this_run.add(candidate)
    return new_words, newly_seen_ids


def main():
    ap = argparse.ArgumentParser(description="視聴者コメントからの単語リクエストを自動検出する")
    ap.add_argument("--max-videos", type=int, default=config.COMMENT_REQUEST_VIDEOS_TO_SCAN,
                     help="直近何本の動画のコメントを確認対象にするか")
    ap.add_argument("--max-candidates", type=int, default=config.COMMENT_REQUEST_MAX_PER_RUN,
                     help="1回の実行で検出する新規リクエストの上限本数")
    ap.add_argument("--output-file", type=str, default="comment_request_words.txt",
                     help="検出した単語を1行1件で書き出すファイル"
                          "(comment_requests.yml側がこれを読んでgenerate.pyを回す)")
    args = ap.parse_args()

    history = load_upload_history()
    existing_words = {entry["word"] for entry in history}
    # 直近の動画ほどリクエストが集まりやすいので、新しい順に対象にする
    recent_video_ids = [entry["video_id"] for entry in history[-args.max_videos:]]
    recent_video_ids.reverse()

    state = load_comment_request_state()
    processed_ids = set(state["processed_comment_ids"])

    comments_by_video = fetch_comments(recent_video_ids)
    new_words, newly_seen_ids = find_new_requests(
        comments_by_video, existing_words, processed_ids, args.max_candidates
    )

    state["processed_comment_ids"] = list(processed_ids | set(newly_seen_ids))
    save_comment_request_state(state)

    with open(args.output_file, "w", encoding="utf-8") as f:
        for word in new_words:
            f.write(word + "\n")

    total_comments = sum(len(c) for c in comments_by_video.values())
    print(f"{len(recent_video_ids)}本の動画、{total_comments}件のコメントを確認し、"
          f"新規リクエスト{len(new_words)}件を検出しました。")
    for word in new_words:
        print(f"  - {word!r}")


if __name__ == "__main__":
    main()
