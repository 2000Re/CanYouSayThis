"""
通常動画(Shorts→横型変換、repost_shorts.py参照)のインプレッション数・
インプレッションからのクリック率(視聴開始率)を確認する。

[背景] 通常動画の再生数がほぼ伸びない原因が「表示機会(インプレッション)
自体が少ないから」か「表示はされてもクリックされていないから(サムネイルの
問題)」かを切り分けるための診断ツール。前者ならサムネイルを変えても効果が
薄く(そもそも見られていない)、後者ならサムネイル改善が効く
(youtube_analytics.pyのモード別集計とは別軸、youtube_traffic_source.pyの
「1本を深掘りする」用途に近いが、こちらは通常動画全体を横断して見る)。

通常動画のvideo_idはupload_history.json/repost_state.jsonのどちらにも
記録されていない(どちらも元ShortsのIDしか記録していない設計のため)。その
ため、チャンネルのアップロード済み動画一覧(uploads再生リスト)から、
タイトルに" #Shorts"を含まないものを通常動画とみなして抽出する(この
チャンネルの全Shortsタイトルにはgenerate.py _youtube_metadata()が必ず
" #Shorts"を付与し、repost_shorts.py側は付与しないため、確実な判別方法に
なる)。

必要な環境変数はyoutube_analytics.pyと同じ(yt-analytics.readonlyスコープ
を含むYOUTUBE_REFRESH_TOKENが必要)に加え、動画一覧の取得(channels.list/
playlistItems.list)にはyoutube.readonly相当のスコープが必要
(youtube_upload.get_youtube_client()が使うフルアクセススコープに含まれる)。

使い方:
    python3 youtube_regular_video_impressions.py            # 過去28日間
    python3 youtube_regular_video_impressions.py --days 90
"""
import argparse
import datetime

import config
from youtube_analytics import _chunk, get_analytics_client


def list_regular_video_ids():
    """チャンネルの全アップロード動画のうち、タイトルに" #Shorts"を含まない
    (=通常動画の)(video_id, title)のタプルのリストを、新しい順で返す。"""
    from youtube_upload import get_youtube_client

    youtube = get_youtube_client()
    channel_resp = youtube.channels().list(part="contentDetails", mine=True).execute()
    uploads_playlist_id = (
        channel_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    )

    videos = []
    page_token = None
    while True:
        resp = youtube.playlistItems().list(
            part="snippet", playlistId=uploads_playlist_id,
            maxResults=50, pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            title = item["snippet"]["title"]
            if "#Shorts" not in title:
                videos.append((item["snippet"]["resourceId"]["videoId"], title))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return videos


def fetch_video_impressions(video_ids, start_date, end_date):
    """video_id -> {"views": int, "impressions": int,
    "impression_click_through_rate": float(%)} の dict を返す。期間内に
    データが無い動画(反映ラグ、またはこの期間に表示機会自体が無かった動画)
    はキーに含まれないため、呼び出し側はmetrics_by_id.get(video_id)がNoneの
    場合を考慮すること。

    impressionClickThroughRateはYouTube Analytics APIから0〜1の割合
    (例: 0.05 = 5%)で返るため、ここで100倍してパーセント表記に揃える
    (averageViewPercentageのように最初からパーセント表記のメトリクスも
    あり紛らわしいため、呼び出し側が意識しなくて済むようこの関数内で
    変換する)。"""
    analytics = get_analytics_client()
    metrics_by_id = {}
    for batch in _chunk(video_ids, config.ANALYTICS_VIDEO_BATCH_SIZE):
        response = analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views,impressions,impressionClickThroughRate",
            dimensions="video",
            filters=f"video=={','.join(batch)}",
        ).execute()
        for row in response.get("rows", []):
            video_id, views, impressions, ctr = row
            metrics_by_id[video_id] = {
                "views": views,
                "impressions": impressions,
                "impression_click_through_rate": ctr * 100,
            }
    return metrics_by_id


def main():
    ap = argparse.ArgumentParser(
        description="通常動画(Shorts→横型変換分)のインプレッション数・クリック率を確認する"
                     "(再生数が伸びない原因が露出不足かサムネイルかを切り分ける用途)"
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

    regular_videos = list_regular_video_ids()
    if not regular_videos:
        print("通常動画(タイトルに#Shortsが付いていない動画)が見つかりませんでした。")
        return

    video_ids = [video_id for video_id, _title in regular_videos]
    metrics_by_id = fetch_video_impressions(video_ids, start_date, end_date)

    title_by_id = dict(regular_videos)
    rows = [
        (video_id, title_by_id[video_id], metrics_by_id[video_id])
        for video_id in video_ids if video_id in metrics_by_id
    ]
    rows.sort(key=lambda r: -r[2]["impressions"])

    total_impressions = sum(r[2]["impressions"] for r in rows)
    total_views = sum(r[2]["views"] for r in rows)

    print(f"=== 通常動画 インプレッション数・クリック率({start_date} 〜 {end_date}、"
          f"対象{len(regular_videos)}本、データあり{len(rows)}本) ===")
    print(f"  合計インプレッション数: {total_impressions} / 合計再生数: {total_views}")
    if not rows:
        print("  データがありません(反映ラグ、またはこの期間に表示機会が無かった可能性があります)。")
        return
    for video_id, title, m in rows:
        print(
            f"  {video_id}: インプレッション{m['impressions']}回 / "
            f"クリック率{m['impression_click_through_rate']:.1f}% / "
            f"再生{m['views']}回 - {title}"
        )

    no_data_ids = [video_id for video_id in video_ids if video_id not in metrics_by_id]
    if no_data_ids:
        print(f"\n  データが無い動画({len(no_data_ids)}本、反映ラグまたは表示機会無しの可能性): "
              f"{', '.join(no_data_ids)}")


if __name__ == "__main__":
    main()
