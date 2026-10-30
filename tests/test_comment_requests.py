"""comment_requests.py のユニットテスト。

実際にチャンネルへ寄せられたリクエストコメント(README「ハマった罠」
104番)を分析して作ったパターンの回帰テスト。YouTube API呼び出しは一切
行わない(extract_requested_word()/find_new_requests()は純粋関数)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comment_requests import extract_requested_word, find_new_requests


def test_extract_requested_word_can_you_do_with_straight_quotes():
    assert extract_requested_word("Can you do 'AseÛmAÀneØeLē' next?") == "AseÛmAÀneØeLē"


def test_extract_requested_word_can_you_do_with_curly_quotes_and_trailing_text():
    # クォートの外側に付随テキスト("with Icelandic voice")があっても、
    # クォート内だけを正しく抜き出せること。
    text = 'Can you do “▪åaó̤e io̤ eeii” with Icelandic voice'
    assert extract_requested_word(text) == "▪åaó̤e io̤ eeii"


def test_extract_requested_word_would_it_be_possible_to_do_without_quotes():
    assert extract_requested_word("would it be possible to do ˚Ωι˚Αι⍒é˝ΩιÜ?") == "˚Ωι˚Αι⍒é˝ΩιÜ"


def test_extract_requested_word_do_prefix_without_quotes():
    assert extract_requested_word("Do 717iswatchingyouyoucantescape") == "717iswatchingyouyoucantescape"


def test_extract_requested_word_asking_for_pattern():
    assert extract_requested_word("day 2 of asking for test_word?") == "test_word"


def test_extract_requested_word_word_line_takes_priority_over_do_trigger():
    # 「Do you want to make? :」のように文頭が"do"で始まり、かつ動画の
    # 説明欄と同じ"Word:"行を含むコメント(説明欄をそのままコピペした反応
    # コメント、新規リクエストではない)。"do"トリガーで"you want to make"
    # のような無意味な文字列を拾わないよう、Word:行を優先する設計の確認。
    text = "Do you want to make? :\n\nWord:some_word\n\nMode:Synthesized glitch audio..."
    assert extract_requested_word(text) == "some_word"


def test_extract_requested_word_do_trigger_only_matches_comment_start():
    # "Do"がコメントの2行目以降に来るケース(視聴者コメントの実例)は、
    # 意図的に対象外(文中の"I'll do..."等を誤って拾わないための安全側の
    # トレードオフ、comment_requests.pyのモジュールdocstring参照)。
    assert extract_requested_word("Day 3 of\n\nDo\n\ntest_word") is None


def test_extract_requested_word_ignores_keyword_less_pattern():
    # 単語が先頭でキーワードが無いパターンは意図的に対象外。
    assert extract_requested_word("test_word in filipino?") is None


def test_extract_requested_word_ignores_unrelated_comments():
    assert extract_requested_word("I'll be ordering the sausage egg McMuffin") is None
    assert extract_requested_word("My comment?") is None
    assert extract_requested_word("I'm scared") is None


def test_extract_requested_word_rejects_too_long_candidate():
    assert extract_requested_word("Do " + "a" * 300) is None


def test_find_new_requests_skips_already_processed_comments():
    comments_by_video = {"v1": [{"comment_id": "c1", "text": "Do test_word"}]}
    new_words, newly_seen = find_new_requests(comments_by_video, set(), {"c1"}, max_candidates=5)
    assert new_words == []
    assert newly_seen == []


def test_find_new_requests_skips_words_already_in_upload_history():
    comments_by_video = {"v1": [{"comment_id": "c1", "text": "Do existing_word"}]}
    new_words, newly_seen = find_new_requests(
        comments_by_video, {"existing_word"}, set(), max_candidates=5
    )
    assert new_words == []
    assert newly_seen == ["c1"]


def test_find_new_requests_deduplicates_within_same_run():
    comments_by_video = {
        "v1": [
            {"comment_id": "c1", "text": "Do dup_word"},
            {"comment_id": "c2", "text": "Do dup_word"},
        ],
    }
    new_words, newly_seen = find_new_requests(comments_by_video, set(), set(), max_candidates=5)
    assert new_words == ["dup_word"]
    assert newly_seen == ["c1", "c2"]


def test_find_new_requests_stops_at_max_candidates_and_leaves_rest_unprocessed():
    comments_by_video = {
        "v1": [
            {"comment_id": "c1", "text": "Do word_one"},
            {"comment_id": "c2", "text": "Do word_two"},
            {"comment_id": "c3", "text": "Do word_three"},
        ],
    }
    new_words, newly_seen = find_new_requests(comments_by_video, set(), set(), max_candidates=2)
    assert new_words == ["word_one", "word_two"]
    # 上限超過分(c3)は次回に持ち越すため、処理済みとして記録しない
    assert newly_seen == ["c1", "c2"]


def test_find_new_requests_ignores_non_matching_comments_but_marks_them_processed():
    comments_by_video = {"v1": [{"comment_id": "c1", "text": "nice video!"}]}
    new_words, newly_seen = find_new_requests(comments_by_video, set(), set(), max_candidates=5)
    assert new_words == []
    assert newly_seen == ["c1"]
