#!/usr/bin/env python3
"""
upload_history.json/repost_state.json/quota_usage.json 用のgit mergeドライバ。

これらは複数のgenerate.yml実行がそれぞれ追記・加算するだけのファイルだが、
通常のテキストマージだと同じ配列末尾への追記同士が行単位で衝突する。2026-10-13
に実機で発生し、git rebaseがdetached HEADで止まったまま5回のリトライが
全滅、しかもその間に同じShortsが2回repost_shorts.pyの変換対象として選ばれ、
通常動画が重複アップロードされる事故につながった(README「ハマった罠」参照)。

そのため標準のテキストマージの代わりにこのドライバでJSONとして意味的に
正しく統合する。.gitattributesで対象ファイルにmerge=tracking-jsonを設定し、
generate.ymlの「Commit updated upload history and repost state」ステップで
`git config merge.tracking-json.driver "python3 merge_tracking_json.py %O %A %B %P"`
を実行してから使う(gitのmerge driver呼び出し規約: %O=共通祖先、
%A=自分側。結果をここに書き込む、%B=相手側、%P=対象ファイルの相対パス)。

対象外のファイルや壊れたJSONの場合は非ゼロを返し、標準のコンフリクト
マーカーによる手動解決に委ねる(無理に自動解決しようとして気付かれにくい
データ破損を生むよりは、明示的に失敗する方が安全なため)。
"""
import json
import sys


def _load(path):
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    return json.loads(content) if content else None


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_upload_history(base: list | None, ours: list | None, theirs: list | None) -> list:
    """新規追記分(= base に無いvideo_id)を、theirsを基準にoursから補う。"""
    base = base or []
    ours = ours or []
    theirs = theirs or []
    base_ids = {e["video_id"] for e in base if e.get("video_id")}
    result = list(theirs)
    seen_ids = {e["video_id"] for e in result if e.get("video_id")}
    for entry in ours:
        vid = entry.get("video_id")
        if vid and (vid in base_ids or vid in seen_ids):
            continue
        result.append(entry)
        if vid:
            seen_ids.add(vid)
    return result


def merge_repost_state(base: dict | None, ours: dict | None, theirs: dict | None) -> dict:
    """converted_video_ids/skipped_video_idsを、それぞれ重複無く和集合にする。"""
    base = base or {}
    ours = ours or {}
    theirs = theirs or {}

    def merge_list(key):
        merged = list(theirs.get(key, []))
        seen = set(merged)
        for vid in ours.get(key, []):
            if vid not in seen:
                merged.append(vid)
                seen.add(vid)
        return merged

    return {
        "converted_video_ids": merge_list("converted_video_ids"),
        "skipped_video_ids": merge_list("skipped_video_ids"),
    }


def merge_quota_usage(base: dict | None, ours: dict | None, theirs: dict | None) -> dict:
    """api_call_countsは「このrunが増やした分(ours - base)」をtheirsに加算する。

    日付が一致しない(日が変わった)場合は差分の計算自体が無意味なため、
    theirs(無ければours、どちらも無ければbase)を素通しする。"""
    base = base or {}
    ours = ours or {}
    theirs = theirs or {}
    if not theirs or base.get("date") != theirs.get("date"):
        return theirs or ours or base

    base_counts = base.get("api_call_counts", {})
    ours_counts = ours.get("api_call_counts", {})
    merged_counts = dict(theirs.get("api_call_counts", {}))
    for name, our_count in ours_counts.items():
        delta = our_count - base_counts.get(name, 0)
        merged_counts[name] = merged_counts.get(name, 0) + delta
    return {"date": theirs["date"], "api_call_counts": merged_counts}


_MERGERS = {
    "upload_history.json": merge_upload_history,
    "repost_state.json": merge_repost_state,
    "quota_usage.json": merge_quota_usage,
}


def main(argv: list) -> int:
    try:
        base_path, ours_path, theirs_path, target_path = argv[:4]
    except ValueError:
        return 1

    merger = _MERGERS.get(target_path.rsplit("/", 1)[-1])
    if merger is None:
        return 1

    try:
        base = _load(base_path)
        ours = _load(ours_path)
        theirs = _load(theirs_path)
        merged = merger(base, ours, theirs)
    except (OSError, json.JSONDecodeError) as e:
        print(f"merge_tracking_json.py: {target_path} のマージに失敗しました({e})。"
              "手動解決にフォールバックします。", file=sys.stderr)
        return 1

    _save(ours_path, merged)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
