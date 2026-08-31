#!/usr/bin/env python3
"""
compile_shorts.py

upload_history.json に記録された「アップロード成功済み」の動画のうち、
まだ結合動画に使っていないものが config.COMPILATION_BATCH_SIZE 件たまったら、
YouTubeに公開済みの動画をyt-dlpでダウンロードして1本の横型(16:9)動画に
結合し、「通常動画」として再アップロードする。

[設計] Shorts(縦型9:16、3分以内)を単純に何本か連結しても、合計尺が
3分以内のままだと縦型ゆえにYouTubeにShorts判定されてしまう
(判定は投稿者の意図ではなく、アスペクト比+尺のみで決まる仕様のため)。
そのため結合時に各クリップを横型(16:9)キャンバスにピラーボックス
(左右に無地の帯)で配置し直し、確実に「通常動画」として扱われるようにする。

動画ファイル自体はGitHub Actionsの実行間で永続化していないため、
すでにYouTubeに公開済みの自分の動画をyt-dlpで取得し直す方式にしている
(追加のストレージや再生成コストが不要なため。ただし元動画のprivacyStatusが
public/unlisted以外だと匿名ダウンロードできないので、非公開でアップロード
した動画は結合対象にできない)。

[設計] 動画が削除・非公開化・著作権クレーム等で恒久的に取得できなく
なった場合、その1本のせいで結合処理全体が永久に止まってしまわないよう、
ダウンロードに一定回数失敗した動画は結合対象から除外し
(compilation_state.pyのskipped_video_idsに記録)、残りの動画で結合を続行する。

認証方式・環境変数は youtube_upload.py と同じ
(YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN、
任意で YOUTUBE_CHANNEL_ID)。
"""
import argparse
import os
import time
import uuid

import yt_dlp
from googleapiclient.http import MediaFileUpload
from moviepy import ColorClip, CompositeVideoClip, VideoFileClip, concatenate_videoclips

import config
from compilation_state import load_compilation_state, pillarbox_scale, save_compilation_state, select_pending
from upload_history import load_upload_history
from youtube_upload import get_youtube_client

# youtube_upload.upload_video()と同じく、実行ログだけでYouTube Data APIの
# クォータ消費量(概算)を把握できるようにする。
QUOTA_COST_PER_CALL = {"videos.insert": 100}
_api_call_counts = {name: 0 for name in QUOTA_COST_PER_CALL}


def _log_api_usage_summary():
    total_units = sum(count * QUOTA_COST_PER_CALL[name] for name, count in _api_call_counts.items())
    print("=== API使用量(YouTube Data API v3、概算) ===")
    for name, count in _api_call_counts.items():
        print(f"  {name}: {count}回 (1回あたり{QUOTA_COST_PER_CALL[name]} units)")
    print(f"  概算クォータ消費: {total_units} units (日次上限 10,000 units の目安)")


def download_video(video_id: str, output_path: str) -> None:
    """公開済みの自分の動画をyt-dlpでダウンロードする。"""
    ydl_opts = {
        "outtmpl": output_path,
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])


def download_video_with_retry(video_id: str, output_path: str) -> None:
    """ダウンロード失敗を数回リトライする(一時的なネットワーク不調対策)。

    それでも失敗する場合は例外を送出する。呼び出し側はこれを
    「恒久的に取得不可能」とみなし、結合対象から除外する
    (削除・非公開化・著作権クレーム等はリトライしても解決しないため)。"""
    last_error = None
    for attempt in range(1, config.COMPILATION_DOWNLOAD_MAX_RETRIES + 1):
        try:
            download_video(video_id, output_path)
            return
        except Exception as e:
            last_error = e
            print(f"    ダウンロード{attempt}回目失敗: {e}")
            time.sleep(config.COMPILATION_DOWNLOAD_RETRY_BACKOFF_SECONDS)
    raise last_error


def pillarbox(clip):
    """縦長のクリップを、横型キャンバスの中央に配置し、左右を無地で埋める。"""
    scale = pillarbox_scale(clip.w, clip.h, config.COMPILATION_VIDEO_WIDTH, config.COMPILATION_VIDEO_HEIGHT)
    resized = clip.resized(scale)
    bg = ColorClip(
        size=(config.COMPILATION_VIDEO_WIDTH, config.COMPILATION_VIDEO_HEIGHT),
        color=config.COMPILATION_BG_COLOR,
        duration=clip.duration,
    )
    return CompositeVideoClip([bg, resized.with_position("center")]).with_duration(clip.duration)


def build_compilation_metadata(labels: list, privacy_status: str) -> dict:
    title = f"{len(labels)} Unpronounceable Words | Compilation #Shorts"
    description = (
        f"A compilation of {len(labels)} words nobody can pronounce:\n"
        + ", ".join(labels)
        + "\n\n#Pronunciation #Unpronounceable #Compilation #CanYouSayThis"
    )
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["pronunciation", "unpronounceable", "compilation", "how to pronounce", "shorts"],
            "categoryId": "24",  # Entertainment (youtube_upload.upload_video()と同じ)
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }


def upload_compilation(youtube, video_path: str, metadata: dict) -> str:
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=metadata, media_body=media)
    _api_call_counts["videos.insert"] += 1
    response = request.execute()
    return response["id"]


def main():
    ap = argparse.ArgumentParser(description="貯まったShortsを結合して通常動画としてアップロードする")
    ap.add_argument("--privacy-status", type=str, choices=["public", "unlisted", "private"],
                     default="public", help="結合動画の公開範囲")
    args = ap.parse_args()

    history = load_upload_history()
    state = load_compilation_state()
    pending = select_pending(history, state)

    if not pending:
        print("結合対象がありません。")
        return

    os.makedirs(config.COMPILATION_DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(config.COMPILATION_OUTPUT_DIR, exist_ok=True)

    batch = []
    downloaded_paths = []
    newly_skipped_ids = []
    raw_clips = []
    pillarboxed_clips = []
    final_clip = None
    upload_succeeded = False

    try:
        for entry in pending:
            if len(batch) >= config.COMPILATION_BATCH_SIZE:
                break
            path = os.path.join(config.COMPILATION_DOWNLOAD_DIR, f"{entry['video_id']}.mp4")
            print(f"  ダウンロード中: {entry['label']} ({entry['video_id']})")
            try:
                download_video_with_retry(entry["video_id"], path)
            except Exception as e:
                print(f"::warning::{entry['label']} ({entry['video_id']}) のダウンロードに"
                      f"{config.COMPILATION_DOWNLOAD_MAX_RETRIES}回失敗したため、結合対象から除外します"
                      f"(動画の削除/非公開化/著作権クレーム等の可能性があります: {e})")
                newly_skipped_ids.append(entry["video_id"])
                continue
            downloaded_paths.append(path)
            batch.append(entry)

        if len(batch) < config.COMPILATION_BATCH_SIZE:
            print(f"結合対象がまだ{len(batch)}件です"
                  f"({config.COMPILATION_BATCH_SIZE}件たまったら結合します)。今回はスキップします。")
            return

        print(f"{len(batch)}件の動画を結合します: {[b['label'] for b in batch]}")

        for path in downloaded_paths:
            clip = VideoFileClip(path)
            raw_clips.append(clip)
            pillarboxed_clips.append(pillarbox(clip))

        final_clip = concatenate_videoclips(pillarboxed_clips, method="compose")
        output_path = os.path.join(config.COMPILATION_OUTPUT_DIR, f"compilation_{uuid.uuid4().hex}.mp4")
        final_clip.write_videofile(
            output_path, fps=30, codec="libx264", audio_codec="aac", logger=None
        )

        youtube = get_youtube_client()
        metadata = build_compilation_metadata([b["label"] for b in batch], args.privacy_status)
        video_id = upload_compilation(youtube, output_path, metadata)
        print(f"[Compilation] アップロード完了: https://youtu.be/{video_id}")
        _log_api_usage_summary()

        # アップロードが成功して初めて結合済みとして記録する
        # (途中で失敗した場合は次回同じバッチで再挑戦できるようにするため)
        state["compiled_video_ids"].extend(b["video_id"] for b in batch)
        upload_succeeded = True

    finally:
        if newly_skipped_ids:
            state["skipped_video_ids"].extend(newly_skipped_ids)
        if newly_skipped_ids or upload_succeeded:
            save_compilation_state(state)

        if final_clip:
            try:
                final_clip.close()
            except Exception:
                pass
        for clip in pillarboxed_clips:
            try:
                clip.close()
            except Exception:
                pass
        for clip in raw_clips:
            try:
                clip.close()
            except Exception:
                pass
        for path in downloaded_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print(f"[Warning] Failed to remove temp file {path}: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 結合動画は本編パイプラインとは独立した追加機能のため、
        # ここで失敗しても当日の生成・アップロード処理は止めない
        # (ジョブは失敗させない)。ただし::error::ワークフローコマンドで
        # GitHub ActionsのUIにエラー注釈を出し、ログを見なくても
        # 失敗に気づけるようにする。
        print(f"::error::結合動画の処理中にエラーが発生しました: {e}")
