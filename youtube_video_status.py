"""
YouTube Data API(videos.list、part=status,processingDetails)を使って、
指定した動画のアップロード・処理状況を確認する。

[背景] YouTube Studioで「保留中」のまま長時間変わらない動画など、
YouTube側の処理が止まっている・拒否されている疑いがある動画を診断する
ための軽量ツール。videos.insert()後に何らかの理由で処理が停止・拒否
された場合、uploadStatus/rejectionReason/processingStatus等にその理由が
表れる(youtube_quick_stats.pyの「今の再生数」とは別軸で、あくまで
処理状況そのものを見る用途)。

必要な環境変数はyoutube_upload.pyと同じ(YOUTUBE_CLIENT_ID/
YOUTUBE_CLIENT_SECRET/YOUTUBE_REFRESH_TOKEN)。

使い方:
    python3 youtube_video_status.py --video-id Y3212bkb6gI
    python3 youtube_video_status.py --video-id Y3212bkb6gI --video-id rvpCgStB8wA
"""
import argparse


def main():
    ap = argparse.ArgumentParser(
        description="指定した動画のアップロード・処理状況(status/processingDetails)を確認する"
    )
    ap.add_argument("--video-id", action="append", required=True,
                     help="確認する動画ID(複数回指定可)")
    args = ap.parse_args()

    # --upload時のみ必要な依存関係(google-api-python-client等)なので、
    # 遅延importにしてこのファイル自体の軽量なimportを保つ
    # (youtube_quick_stats.pyと同じ方針)。
    from youtube_upload import fetch_video_status

    status_by_id = fetch_video_status(args.video_id)
    for video_id in args.video_id:
        status = status_by_id.get(video_id)
        if status is None:
            print(f"{video_id}: 見つかりませんでした(削除済み、または存在しないIDの可能性があります)")
            continue
        print(f"=== {video_id} ===")
        for key, value in status.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
