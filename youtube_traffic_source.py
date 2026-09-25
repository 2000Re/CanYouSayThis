"""
YouTube Analytics API(youtubeAnalytics v2)を使って、指定した動画1本の
流入元(insightTrafficSourceType)別の再生数を取得する。

[背景] youtube_quick_stats.py(videos.list)で「他の動画より明らかに伸びている」
動画を見つけた後、それが関連動画のおすすめに乗ったのか・ホーム/Shortsフィード
での露出が増えたのか・検索から来たのか・外部(SNS等)からの流入かを切り分ける
ための診断ツール。youtube_analytics.pyのモード別集計とは別軸(あくまで1本の
動画を深掘りする用途)。

[注意] youtube_analytics.pyと同じAnalytics APIを使うため、投稿から1〜2日
程度の反映ラグがある(README「ハマった罠」18番参照)。投稿直後の動画では
データが薄い/まだ返ってこない場合がある。

必要な環境変数はyoutube_analytics.pyと同じ(YOUTUBE_CLIENT_ID/
YOUTUBE_CLIENT_SECRET/YOUTUBE_REFRESH_TOKEN、yt-analytics.readonlyスコープ
を含めて発行したもの)。

使い方:
    python3 youtube_traffic_source.py --video-id mFGTwTBPy7Q            # 過去28日間
    python3 youtube_traffic_source.py --video-id mFGTwTBPy7Q --days 7   # 過去7日間
"""
import argparse
import datetime

import config
from youtube_analytics import get_analytics_client

# YouTube Analytics APIのinsightTrafficSourceTypeが返す値の日本語ラベル。
# 網羅を保証するものではない(Google側で値が追加される可能性がある)ため、
# 未知の値はコードそのままを表示する(_breakdown_with_labels()のfallback)。
TRAFFIC_SOURCE_LABELS_JA = {
    "ADVERTISING": "広告",
    "ANNOTATION": "動画内アノテーション/カード",
    "CAMPAIGN_CARD": "キャンペーンカード",
    "END_SCREEN": "エンドスクリーン",
    "EXT_URL": "外部サイト/SNSのリンク",
    "NOTIFICATION": "チャンネル登録者への通知",
    "NO_LINK_EMBEDDED": "埋め込みプレーヤー(リンク元不明)",
    "NO_LINK_OTHER": "その他(リンク元不明)",
    "PLAYLIST": "再生リスト",
    "PROMOTED": "プロモーション",
    "RELATED_VIDEO": "関連動画のおすすめ",
    "SOUND_PAGE": "使用音源ページ",
    "SUBSCRIBER": "登録者のホーム/フィード",
    "YT_CHANNEL": "チャンネルページ",
    "YT_OTHER_PAGE": "YouTube内のその他のページ",
    "YT_PLAYLIST_PAGE": "再生リストページ",
    "YT_SEARCH": "YouTube内検索",
    "SHORTS": "Shortsフィード",
}


def fetch_traffic_source_breakdown(video_id, start_date, end_date):
    """(insightTrafficSourceTypeのコード, 再生数)のタプルのリストを返す
    (順不同。並び替え・ラベル付けは_breakdown_with_labels()で行う)。"""
    analytics = get_analytics_client()
    response = analytics.reports().query(
        ids="channel==MINE",
        startDate=start_date,
        endDate=end_date,
        metrics="views",
        dimensions="insightTrafficSourceType",
        filters=f"video=={video_id}",
    ).execute()
    return [(row[0], row[1]) for row in response.get("rows", [])]


def _breakdown_with_labels(breakdown):
    """fetch_traffic_source_breakdown()の結果を、日本語ラベル・割合(%)付きの
    (label, source_type, views, pct)のリスト(views降順)に変換する。

    API呼び出しから独立させ、集計ロジックだけを単体テストできるようにしている。"""
    total_views = sum(views for _, views in breakdown)
    rows = sorted(breakdown, key=lambda r: -r[1])
    result = []
    for source_type, views in rows:
        label = TRAFFIC_SOURCE_LABELS_JA.get(source_type, source_type)
        pct = (views / total_views * 100) if total_views else 0.0
        result.append((label, source_type, views, pct))
    return result


def main():
    ap = argparse.ArgumentParser(
        description="動画1本の流入元(YouTube Analytics APIのinsightTrafficSourceType)別"
                     "再生数を取得する(急に伸びた動画の要因を調べる用途)"
    )
    ap.add_argument("--video-id", type=str, required=True, help="対象の動画ID")
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

    breakdown = fetch_traffic_source_breakdown(args.video_id, start_date, end_date)
    rows = _breakdown_with_labels(breakdown)
    total_views = sum(views for _, _, views, _ in rows)

    print(f"=== 動画 {args.video_id} の流入元別再生数({start_date} 〜 {end_date}、合計{total_views}回) ===")
    if not rows:
        print("  データがありません(反映ラグでまだAPIに載っていない可能性があります。"
              "youtube_quick_stats.pyで即時の再生数自体は確認できます)")
        return
    for label, source_type, views, pct in rows:
        print(f"  {label}({source_type}): {views}回 ({pct:.1f}%)")


if __name__ == "__main__":
    main()
