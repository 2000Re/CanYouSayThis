"""
YouTube Data API(videos.list、part=liveStreamingDetails)を使って、指定した
ライブ配信の「今この瞬間の」同時視聴者数を取得する。

[背景] 深夜〜早朝の無人配信中、視聴者が今どれくらいいるかを定期的に
確認したい(2026-10-23、ユーザーとの相談)用途向け。youtube_quick_stats.py
(通常動画の再生数)と違い、こちらは配信中のみ有効な値を返す
(youtube_upload.fetch_live_stats()参照)。

必要な環境変数はyoutube_upload.pyと同じ(YOUTUBE_CLIENT_ID/
YOUTUBE_CLIENT_SECRET/YOUTUBE_REFRESH_TOKEN)。

使い方:
    python3 youtube_live_stats.py --video-id EUHOFtn8oUc
    python3 youtube_live_stats.py --video-id EUHOFtn8oUc --video-id abc123
"""
import argparse


def main():
    ap = argparse.ArgumentParser(
        description="指定したライブ配信の同時視聴者数(concurrentViewers)を確認する"
    )
    ap.add_argument("--video-id", action="append", required=True,
                     help="確認するライブ配信の動画ID(複数回指定可)")
    args = ap.parse_args()

    # --upload時のみ必要な依存関係(google-api-python-client等)なので、
    # 遅延importにしてこのファイル自体の軽量なimportを保つ
    # (youtube_video_status.pyと同じ方針)。
    from youtube_upload import fetch_live_stats

    stats_by_id = fetch_live_stats(args.video_id)
    for video_id in args.video_id:
        stats = stats_by_id.get(video_id)
        if stats is None:
            print(f"{video_id}: 見つかりませんでした(削除済み、または存在しないIDの可能性があります)")
            continue
        if stats["concurrentViewers"] is None:
            print(f"{video_id}: 配信中ではありません(終了済み、または通常動画の可能性があります)")
            continue
        print(f"=== {video_id} ===")
        print(f"  concurrentViewers: {stats['concurrentViewers']}")
        print(f"  actualStartTime: {stats['actualStartTime']}")
        print(f"  activeLiveChatId: {stats['activeLiveChatId']}")


if __name__ == "__main__":
    main()
