"""
YouTube Data API(videos.list)を使って、直近アップロードした動画の「今この
瞬間の」公開再生数・高評価数・コメント数を取得する。

[背景] youtube_analytics.py(YouTube Analytics API)は集計対象期間の確定に
通常1〜2日程度のラグがあり、投稿直後の初動を素早く確認したい用途には
向かない。videos.list(part=statistics)が返す値は視聴ページ/YouTube Studio
の「コンテンツ」タブに表示されているのと同じ即時反映の値のため、投稿直後
〜数時間の軽い初動チェックに使う(youtube_upload.fetch_video_stats()参照)。

youtube_analytics.pyと違い、投稿からの経過日数による正規化
(avg_views_per_dayのような主指標)は行わない。あくまで「今の生の値」を
素早く見るための軽量ツールであり、モード間の公平な比較にはyoutube_analytics.py
を使うこと。

使い方:
    python3 youtube_quick_stats.py                # 過去24時間にアップロードした動画
    python3 youtube_quick_stats.py --hours 6       # 過去6時間
"""
import argparse
import datetime

from upload_history import load_upload_history


def _entries_in_last_hours(history, hours, now=None):
    """uploaded_at(ISO 8601、UTC)がnowからhours時間以内のエントリだけを返す。
    uploaded_at未記録の古いエントリ・日付の解釈に失敗したエントリは対象外に
    する(youtube_analytics._entries_in_range()と同じ方針)。"""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(hours=hours)
    filtered = []
    for entry in history:
        uploaded_at = entry.get("uploaded_at")
        if not uploaded_at:
            continue
        try:
            uploaded_dt = datetime.datetime.fromisoformat(uploaded_at)
        except ValueError:
            continue
        if uploaded_dt >= cutoff:
            filtered.append(entry)
    return filtered


def main():
    ap = argparse.ArgumentParser(
        description="直近アップロードした動画の、今この瞬間の公開再生数・高評価数・"
                     "コメント数を取得する(YouTube Analytics APIのラグを避けた即時確認用)"
    )
    ap.add_argument("--hours", type=float, default=24,
                     help="対象とする直近の時間数(デフォルト24時間)")
    args = ap.parse_args()

    # --upload時のみ必要な依存関係(google-api-python-client等)なので、
    # 遅延importにしてこのファイル自体の軽量なimportを保つ(youtube_analytics.py
    # と同じ方針)。
    from youtube_upload import fetch_video_stats

    history = load_upload_history()
    target_entries = _entries_in_last_hours(history, args.hours)
    video_ids = [e["video_id"] for e in target_entries if e.get("video_id")]
    if not video_ids:
        print(f"過去{args.hours}時間以内にuploaded_atが記録されたアップロード履歴が"
              f"ありません。")
        return

    stats_by_id = fetch_video_stats(video_ids)

    print(f"=== 直近{args.hours}時間の投稿({len(video_ids)}本)の即時統計 ===")
    for entry in target_entries:
        video_id = entry.get("video_id")
        if not video_id:
            continue
        stats = stats_by_id.get(video_id, {"views": 0, "likes": 0, "comments": 0})
        label = entry.get("label", "")
        mode = entry.get("mode", "")
        print(
            f"  {video_id} [{mode}] {label}: "
            f"再生{stats['views']}回 / 高評価{stats['likes']} / コメント{stats['comments']}"
        )


if __name__ == "__main__":
    main()
