"""
YouTube Analytics API(youtubeAnalytics v2)から、アップロード済みの各Shorts
の再生数・視聴維持率を取得し、upload_history.jsonの"mode"(tts/tts_extreme/
glitch)と突き合わせて集計する。

[背景] --mode random の抽選比率(config.MODE_WEIGHTS)を、実際に単語を読み
上げないglitchモードは「発音してみて」というコンセプトへの説得力が弱い、
という主観的な判断だけで下げた(PR: --mode randomでglitchの出現比率を下げる)。
この判断を裏付ける/再調整するデータを取るのが本モジュールの目的。

[設計] 生の再生数だけでモードを比較すると、YouTubeのアルゴリズムによる展開
タイミングは投稿からの経過日数に強く依存するため、新しい動画ほど不利になる
という強いノイズが乗る(実際の観察に基づく、投稿一覧の再生数のばらつきが
投稿日と強く相関していた)。そのため、集計対象期間の終了日を基準に「投稿から
何日視聴可能だったか」で正規化した1日あたり再生数(avg_views_per_day)を
主指標として扱う(summarize_by_mode()参照)。

[注意] 本モジュールのYouTube Analytics API呼び出し部分(get_analytics_client
() / fetch_video_metrics()の実際のAPI通信)は、このリポジトリの他の実機検証
済み機能(espeak-ng・MBROLA等)とは違い、本物のGoogle認証情報を用いた実際の
API応答での動作確認がまだ取れていない(このリポジトリの開発環境からは呼び
出せないため)。公式ドキュメント
(https://developers.google.com/youtube/analytics/reference/reports/query)
に基づいて実装しているが、初回実行時は出力結果をYouTube Studioの表示と
突き合わせて確認すること。

必要な環境変数はyoutube_upload.pyと同じ(YOUTUBE_CLIENT_ID/
YOUTUBE_CLIENT_SECRET/YOUTUBE_REFRESH_TOKEN)。ただしYOUTUBE_REFRESH_TOKEN
は yt-analytics.readonly スコープを含めて発行し直したものである必要がある
(get_youtube_refresh_token.py参照。スコープはリフレッシュトークン発行時に
焼き付けられるため、既存のトークンのままだとスコープ不足で失敗する)。

使い方:
    python3 youtube_analytics.py                       # 過去28日間を集計
    python3 youtube_analytics.py --days 14              # 過去14日間を集計
    python3 youtube_analytics.py --start-date 2026-09-01 --end-date 2026-09-19
"""
import argparse
import datetime
from collections import defaultdict

from googleapiclient.discovery import build

import config
import youtube_upload
from upload_history import load_upload_history

# yt-analytics.readonlyは再生数・視聴維持率等の読み取り専用スコープ
# (収益データが必要な場合はyt-analytics-monetary.readonlyが別途必要だが、
# 本モジュールは使わない)。YOUTUBE_REFRESH_TOKENがこのスコープを含めて
# 発行されている必要がある(get_youtube_refresh_token.py参照)。


def get_analytics_client():
    """認証済みのYouTube Analytics APIクライアントを返す。

    youtube_upload._load_credentials()を再利用し、YOUTUBE_CLIENT_ID/SECRET/
    REFRESH_TOKENの読み込みロジックを二重管理しない。

    scopes=Noneを渡し、トークンリフレッシュ時にスコープを絞り込まない
    (youtube_upload.get_youtube_client()はUPLOAD_SCOPESに絞り込むが、こちら
    は絞り込み用のscope文字列がリフレッシュトークンの実際の付与範囲と厳密に
    一致しないとGoogle側でinvalid_scopeエラーになるため、それを避ける)。
    リフレッシュトークンにyt-analytics.readonlyが実際に付与されていれば、
    絞り込まなくてもAnalytics APIの呼び出しは問題なく成功する。"""
    credentials = youtube_upload._load_credentials(scopes=None)
    return build("youtubeAnalytics", "v2", credentials=credentials)


def _chunk(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def fetch_video_metrics(video_ids, start_date, end_date):
    """video_id -> {"views": int, "average_view_percentage": float} の dict
    を返す。期間内に再生が無かった/データがまだ反映されていない(Analytics
    データには通常1〜2日程度のラグがある)動画はキーに含まれないため、
    呼び出し側はmetrics_by_id.get(video_id)がNoneの場合を考慮すること。

    video_idsはconfig.ANALYTICS_VIDEO_BATCH_SIZE件ずつバッチ分割してAPIを
    呼ぶ(reports.query()のvideoフィルタに渡せる件数の安全マージン、
    config.py参照)。"""
    analytics = get_analytics_client()
    metrics_by_id = {}
    for batch in _chunk(video_ids, config.ANALYTICS_VIDEO_BATCH_SIZE):
        response = analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views,averageViewPercentage",
            dimensions="video",
            filters=f"video=={','.join(batch)}",
        ).execute()
        rows = response.get("rows", [])
        # [デバッグ用] 初回運用時、想定通りの動画に想定通りの値が返ってきて
        # いるかを目視確認できるよう、生のAPI応答の概要を毎回ログに出す。
        # 動作が安定して確認が不要になったら削除して良い。
        column_names = [h.get("name") for h in response.get("columnHeaders", [])]
        print(f"    [debug] video=={','.join(batch)} -> {len(rows)}行"
              f"(columnHeaders: {column_names})")
        if not rows:
            print(f"    [debug] 0行の生レスポンス全体: {response}")
        for row in rows:
            video_id, views, avg_pct = row[0], row[1], row[2]
            metrics_by_id[video_id] = {"views": views, "average_view_percentage": avg_pct}
    return metrics_by_id


def _entries_in_range(history, start_date, end_date):
    """uploaded_at(ISO 8601、UTC)がstart_date〜end_date(両端含む)の範囲内
    にあるエントリだけを返す。uploaded_at未記録の古いエントリ(この項目の
    追加前にアップロードされたもの)や、日付の解釈に失敗したエントリは対象
    外にする。Analytics APIへの問い合わせ対象を絞り込み、無駄なバッチ数を
    減らす狙いもある。"""
    start = datetime.date.fromisoformat(start_date)
    end = datetime.date.fromisoformat(end_date)
    filtered = []
    for entry in history:
        uploaded_at = entry.get("uploaded_at")
        if not uploaded_at:
            continue
        try:
            uploaded_date = datetime.datetime.fromisoformat(uploaded_at).date()
        except ValueError:
            continue
        if start <= uploaded_date <= end:
            filtered.append(entry)
    return filtered


def _days_available(uploaded_at, end_date):
    """uploaded_atからend_date(集計対象期間の終了日)までの、動画が実際に
    視聴可能だった日数(公開日を1日目として数える、最低1日)。

    投稿直後で経過日数が短い動画ほど再生数が少なくなるのは当然のため
    (YouTubeのアルゴリズムによる展開タイミング依存が強いという実際の観察
    に基づく)、モード間で公平に比較するにはこの日数で正規化する必要がある。"""
    uploaded_date = datetime.datetime.fromisoformat(uploaded_at).date()
    end = datetime.date.fromisoformat(end_date)
    return max((end - uploaded_date).days + 1, 1)


def summarize_by_mode(metrics_by_id, entries, end_date):
    """entries(_entries_in_range()で絞り込んだupload_history.jsonのエント
    リ)とmetrics_by_id(fetch_video_metrics()の結果)をvideo_idで突き合わせ、
    mode別に集計したdict(mode -> {"videos", "total_views", "avg_views",
    "avg_view_percentage", "avg_views_per_day"})を返す。

    - avg_views: 単純な平均再生数(参考値。投稿からの経過日数の影響を受ける)。
    - avg_view_percentage: 再生数で重み付けした視聴維持率の平均。
    - avg_views_per_day: _days_available()で正規化した「1日あたり再生数」の
      動画ごとの値を単純平均したもの。投稿タイミングの影響を受けにくい主指標。

    metrics_by_idに無い(=期間内の再生数データが無い/未反映の)video_idは
    views=0、average_view_percentage=0.0として扱う。"""
    totals = defaultdict(lambda: {
        "videos": 0, "total_views": 0, "weighted_pct_sum": 0.0, "views_per_day_sum": 0.0,
    })
    for entry in entries:
        video_id = entry.get("video_id")
        mode = entry.get("mode")
        uploaded_at = entry.get("uploaded_at")
        if not video_id or not mode or not uploaded_at:
            continue
        metrics = metrics_by_id.get(video_id, {"views": 0, "average_view_percentage": 0.0})
        views = metrics["views"]
        pct = metrics["average_view_percentage"]
        days_available = _days_available(uploaded_at, end_date)

        data = totals[mode]
        data["videos"] += 1
        data["total_views"] += views
        data["weighted_pct_sum"] += views * pct
        data["views_per_day_sum"] += views / days_available

    summary = {}
    for mode, data in totals.items():
        avg_views = data["total_views"] / data["videos"] if data["videos"] else 0.0
        avg_pct = (data["weighted_pct_sum"] / data["total_views"]) if data["total_views"] else 0.0
        avg_views_per_day = data["views_per_day_sum"] / data["videos"] if data["videos"] else 0.0
        summary[mode] = {
            "videos": data["videos"],
            "total_views": data["total_views"],
            "avg_views": avg_views,
            "avg_view_percentage": avg_pct,
            "avg_views_per_day": avg_views_per_day,
        }
    return summary


def main():
    ap = argparse.ArgumentParser(
        description="mode(tts/tts_extreme/glitch)別に再生数・視聴維持率を集計する"
                     "(投稿からの経過日数で正規化した1日あたり再生数を主指標とする)"
    )
    ap.add_argument("--start-date", type=str, default=None,
                     help="集計開始日(YYYY-MM-DD、省略時は--daysから自動計算)")
    ap.add_argument("--end-date", type=str, default=None,
                     help="集計終了日(YYYY-MM-DD、省略時は今日)")
    ap.add_argument("--days", type=int, default=config.ANALYTICS_DEFAULT_LOOKBACK_DAYS,
                     help=f"--start-date省略時に使う集計対象の日数"
                          f"(デフォルト{config.ANALYTICS_DEFAULT_LOOKBACK_DAYS}日)")
    args = ap.parse_args()

    end_date = args.end_date or datetime.date.today().isoformat()
    start_date = args.start_date or (
        datetime.date.fromisoformat(end_date) - datetime.timedelta(days=args.days)
    ).isoformat()

    history = load_upload_history()
    target_entries = _entries_in_range(history, start_date, end_date)
    video_ids = [e["video_id"] for e in target_entries if e.get("video_id")]
    if not video_ids:
        print(f"{start_date} 〜 {end_date} の期間にuploaded_atが記録されたアップロード履歴が"
              f"ありません(uploaded_atはこの項目を追加した以降のエントリにのみ記録されています)。")
        return

    metrics_by_id = fetch_video_metrics(video_ids, start_date, end_date)
    summary = summarize_by_mode(metrics_by_id, target_entries, end_date)

    print(f"=== モード別 再生数・視聴維持率集計({start_date} 〜 {end_date}、対象{len(video_ids)}本) ===")
    for mode in sorted(summary, key=lambda m: -summary[m]["avg_views_per_day"]):
        data = summary[mode]
        print(
            f"  {mode}: {data['videos']}本 / 1日あたり平均{data['avg_views_per_day']:.2f}回"
            f"(単純平均{data['avg_views']:.1f}回, 視聴維持率{data['avg_view_percentage']:.1f}%)"
        )


if __name__ == "__main__":
    main()
