"""merge_tracking_json.py のユニットテスト。

upload_history.json/repost_state.json/quota_usage.jsonは複数のgenerate.yml
実行が追記・加算するだけのファイルで、通常のテキストマージだと同じ配列
末尾への追記同士が衝突する(2026-10-13に実機で発生し、同じShortsが2回
repost_shorts.pyの変換対象に選ばれて通常動画が重複アップロードされる
事故につながった)。このモジュールはgit merge driverとしてJSONを意味的に
統合し、その衝突を自動解決する。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from merge_tracking_json import (
    main,
    merge_quota_usage,
    merge_repost_state,
    merge_upload_history,
)


def test_merge_upload_history_keeps_both_sides_new_entries():
    base = [{"video_id": "a"}]
    ours = [{"video_id": "a"}, {"video_id": "b"}]
    theirs = [{"video_id": "a"}, {"video_id": "c"}]
    merged = merge_upload_history(base, ours, theirs)
    assert [e["video_id"] for e in merged] == ["a", "c", "b"]


def test_merge_upload_history_does_not_duplicate_entry_added_by_both_sides():
    # 両方の実行が(例えば自分自身の実行で生成した)同じvideo_idを追記した
    # 場合でも、重複して2件にはならないこと。
    base = []
    entry = {"video_id": "x", "word": "x"}
    merged = merge_upload_history(base, [entry], [entry])
    assert [e["video_id"] for e in merged] == ["x"]


def test_merge_upload_history_handles_none_inputs():
    assert merge_upload_history(None, None, None) == []
    assert merge_upload_history(None, [{"video_id": "a"}], None) == [{"video_id": "a"}]


def test_merge_repost_state_unions_both_lists_without_duplicates():
    base = {"converted_video_ids": ["a"], "skipped_video_ids": []}
    ours = {"converted_video_ids": ["a", "b"], "skipped_video_ids": ["z"]}
    theirs = {"converted_video_ids": ["a", "c"], "skipped_video_ids": []}
    merged = merge_repost_state(base, ours, theirs)
    assert merged == {"converted_video_ids": ["a", "c", "b"], "skipped_video_ids": ["z"]}


def test_merge_repost_state_handles_none_inputs():
    assert merge_repost_state(None, None, None) == {
        "converted_video_ids": [], "skipped_video_ids": [],
    }


def test_merge_quota_usage_sums_deltas_from_both_sides():
    base = {"date": "2026-10-13", "api_call_counts": {"videos.insert": 10}}
    ours = {"date": "2026-10-13", "api_call_counts": {"videos.insert": 15}}  # +5
    theirs = {"date": "2026-10-13", "api_call_counts": {"videos.insert": 13}}  # +3
    merged = merge_quota_usage(base, ours, theirs)
    assert merged == {"date": "2026-10-13", "api_call_counts": {"videos.insert": 18}}


def test_merge_quota_usage_adds_new_counter_key_introduced_by_ours():
    base = {"date": "2026-10-13", "api_call_counts": {}}
    ours = {"date": "2026-10-13", "api_call_counts": {"captions.insert": 2}}
    theirs = {"date": "2026-10-13", "api_call_counts": {"videos.insert": 1}}
    merged = merge_quota_usage(base, ours, theirs)
    assert merged == {
        "date": "2026-10-13",
        "api_call_counts": {"videos.insert": 1, "captions.insert": 2},
    }


def test_merge_quota_usage_falls_back_to_theirs_when_date_differs():
    # 日が変わった場合、differenceを取っても意味が無いためtheirsをそのまま使う。
    base = {"date": "2026-10-13", "api_call_counts": {"videos.insert": 10}}
    ours = {"date": "2026-10-14", "api_call_counts": {"videos.insert": 1}}
    theirs = {"date": "2026-10-14", "api_call_counts": {"videos.insert": 2}}
    assert merge_quota_usage(base, ours, theirs) == theirs


def _write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_main_merges_upload_history_in_place_and_returns_zero(tmp_path):
    base_path = tmp_path / "base.json"
    ours_path = tmp_path / "ours.json"
    theirs_path = tmp_path / "theirs.json"
    _write_json(base_path, [{"video_id": "a"}])
    _write_json(ours_path, [{"video_id": "a"}, {"video_id": "b"}])
    _write_json(theirs_path, [{"video_id": "a"}, {"video_id": "c"}])

    code = main([str(base_path), str(ours_path), str(theirs_path), "upload_history.json"])

    assert code == 0
    result = json.loads(ours_path.read_text(encoding="utf-8"))
    assert [e["video_id"] for e in result] == ["a", "c", "b"]


def test_main_returns_nonzero_for_unrecognized_file(tmp_path):
    base_path = tmp_path / "base.json"
    ours_path = tmp_path / "ours.json"
    theirs_path = tmp_path / "theirs.json"
    for p in (base_path, ours_path, theirs_path):
        _write_json(p, {})

    code = main([str(base_path), str(ours_path), str(theirs_path), "some_other_file.json"])
    assert code == 1


def test_main_returns_nonzero_on_invalid_json(tmp_path):
    base_path = tmp_path / "base.json"
    ours_path = tmp_path / "ours.json"
    theirs_path = tmp_path / "theirs.json"
    base_path.write_text("not json", encoding="utf-8")
    _write_json(ours_path, [])
    _write_json(theirs_path, [])

    code = main([str(base_path), str(ours_path), str(theirs_path), "upload_history.json"])
    assert code == 1
