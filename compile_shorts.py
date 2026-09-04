#!/usr/bin/env python3
"""
compile_shorts.py

upload_history.json に記録された「アップロード成功済み」の動画のうち、
まだ結合動画に使っていないものが config.COMPILATION_BATCH_SIZE 件たまったら、
1本の横型(16:9)動画に結合し、「通常動画」として再アップロードする。

[設計] Shorts(縦型9:16、3分以内)を単純に何本か連結しても、合計尺が
3分以内のままだと縦型ゆえにYouTubeにShorts判定されてしまう
(判定は投稿者の意図ではなく、アスペクト比+尺のみで決まる仕様のため)。
そのため結合時に各クリップを横型(16:9)キャンバスにピラーボックス
(左右に無地の帯)で配置し直し、確実に「通常動画」として扱われるようにする。

[設計] 動画本体の取得元について: 当初はYouTubeに公開済みの動画をyt-dlpで
再ダウンロードする方式だったが、GitHub ActionsのIPがYouTube側に
「Sign in to confirm you're not a bot」でボット判定される問題があり
(cookie認証を渡しても解決しない事例が確認されている)、YouTube/yt-dlpに
一切依存しない方式に変更した: generate.pyが生成した動画は既に
generate.ymlの「Upload generated videos」ステップでGitHub Actions
アーティファクト(config.COMPILATION_ARTIFACT_NAME)として保存されている
ため、これをGitHub Actions APIから取得する。取得元のrunは、generate.pyが
upload_history.jsonへ記録する各エントリのrun_id(GITHUB_RUN_ID)で特定する
(詳細はREADME「ハマった罠」の8番を参照)。

[設計] アーティファクトの保持期限切れ・該当runが見つからない等の
「恒久的に取得不可能」なケースで、その1本のせいで結合処理全体が永久に
止まってしまわないよう、該当エントリは結合対象から除外し
(compilation_state.pyのskipped_video_idsに記録)、残りの動画で結合を続行する。
run_idが記録されていない旧いエントリ(この方式導入前にアップロードされた
もの)は、そもそもどのrunのアーティファクトか特定できないため結合対象外にする。

YouTube Data API(結合動画のアップロード用)の認証方式・環境変数は
youtube_upload.py と同じ(YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET /
YOUTUBE_REFRESH_TOKEN、任意で YOUTUBE_CHANNEL_ID)。GitHub Actions APIの
認証には環境変数 GITHUB_TOKEN(ワークフロー側で secrets.GITHUB_TOKEN を
渡す。追加のシークレット登録は不要)を使う。
"""
import argparse
import os
import time
import uuid

import requests
from googleapiclient.http import MediaFileUpload
from moviepy import ColorClip, CompositeVideoClip, VideoFileClip, concatenate_videoclips

import config
from compilation_state import (
    extract_zip_member,
    find_artifact,
    load_compilation_state,
    pillarbox_scale,
    save_compilation_state,
    select_pending,
)
from upload_history import load_upload_history
from youtube_upload import _quota_summary_lines, get_youtube_client

GITHUB_API_BASE = "https://api.github.com"


class ArtifactUnavailableError(Exception):
    """該当エントリの動画アーティファクトが恒久的に取得できない
    (該当runが見つからない/保持期限切れ/アーティファクト内に対象の
    ファイルが無い、等)。リトライしても解決しないため、呼び出し側は
    このエントリを結合対象から除外してよい。"""

# youtube_upload.upload_video()と同じく、実行ログだけでYouTube Data APIの
# クォータ消費量・残容量(概算)を把握できるようにする(集計ロジック自体は
# youtube_upload._quota_summary_lines() を共用し、二重管理を避けている。
# ただしカウンタ自体は本スクリプトのプロセス内消費分として別で持つ)。
QUOTA_COST_PER_CALL = {"videos.insert": 100}
_api_call_counts = {name: 0 for name in QUOTA_COST_PER_CALL}


def _log_api_usage_summary():
    for line in _quota_summary_lines(_api_call_counts, QUOTA_COST_PER_CALL):
        print(line)


def _github_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def download_video(entry: dict, output_path: str) -> None:
    """entryが記録しているGitHub Actions run_idから、その回の
    config.COMPILATION_ARTIFACT_NAMEアーティファクトを取得し、対象動画の
    mp4を取り出す。

    run_id未記録・該当runが見つからない・アーティファクトの保持期限切れ・
    アーティファクト内に対象ファイルが無い、のいずれもArtifactUnavailableError
    (恒久的に取得不可能)を送出する。それ以外(ネットワークエラー・GitHub API側の
    5xx等)は通常のExceptionとして送出し、一時的な問題として上位でリトライ対象にする。"""
    run_id = entry.get("run_id")
    if not run_id:
        raise ArtifactUnavailableError(
            f"{entry['label']}: run_idが記録されていないため取得できません"
            "(この方式の導入前にアップロードされたエントリの可能性があります)"
        )

    repo = os.environ["GITHUB_REPOSITORY"]
    headers = _github_headers()

    resp = requests.get(
        f"{GITHUB_API_BASE}/repos/{repo}/actions/runs/{run_id}/artifacts",
        headers=headers,
        timeout=config.COMPILATION_GITHUB_API_TIMEOUT_SECONDS,
    )
    if resp.status_code == 404:
        raise ArtifactUnavailableError(f"run {run_id} が見つかりません(削除された可能性があります)")
    resp.raise_for_status()

    artifact = find_artifact(resp.json().get("artifacts", []), config.COMPILATION_ARTIFACT_NAME)
    if artifact is None:
        raise ArtifactUnavailableError(
            f"run {run_id} に{config.COMPILATION_ARTIFACT_NAME}アーティファクトが見つかりません"
        )
    if artifact.get("expired"):
        raise ArtifactUnavailableError(
            f"run {run_id} の{config.COMPILATION_ARTIFACT_NAME}アーティファクトは保持期限切れです"
        )

    zip_resp = requests.get(
        artifact["archive_download_url"],
        headers=headers,
        timeout=config.COMPILATION_GITHUB_API_TIMEOUT_SECONDS,
    )
    zip_resp.raise_for_status()

    member_name = f"{entry['video_id']}.mp4"
    try:
        content = extract_zip_member(zip_resp.content, member_name)
    except KeyError:
        raise ArtifactUnavailableError(
            f"{config.COMPILATION_ARTIFACT_NAME}アーティファクト内に{member_name}が見つかりません"
        )

    with open(output_path, "wb") as f:
        f.write(content)


def download_video_with_retry(entry: dict, output_path: str) -> None:
    """取得失敗を数回リトライする(一時的なネットワーク不調対策)。

    ArtifactUnavailableError(恒久的に取得不可能)は即座に再送出し、リトライしない
    (リトライしても結果が変わらないため)。それ以外のエラーは
    COMPILATION_DOWNLOAD_MAX_RETRIES回までリトライし、それでも失敗する場合は
    例外を送出する。呼び出し側は例外の型で恒久的/一時的を判別する。"""
    last_error = None
    for attempt in range(1, config.COMPILATION_DOWNLOAD_MAX_RETRIES + 1):
        try:
            download_video(entry, output_path)
            return
        except ArtifactUnavailableError:
            raise
        except Exception as e:
            last_error = e
            print(f"    取得{attempt}回目失敗: {e}")
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
    title = f"{len(labels)} Unpronounceable Words | Compilation"
    description = (
        f"A compilation of {len(labels)} words nobody can pronounce:\n"
        + ", ".join(labels)
        + "\n\n#Pronunciation #Unpronounceable #Compilation #CanYouSayThis"
    )
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["pronunciation", "unpronounceable", "compilation", "how to pronounce"],
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
    # run_idが無い(この方式導入前にアップロードされた)エントリは、どのrunの
    # アーティファクトか特定できないため結合対象外にする。
    compilable = [h for h in history if h.get("video_id") and h.get("run_id")]

    state = load_compilation_state()
    pending = select_pending(compilable, state)

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
            print(f"  取得中: {entry['label']} ({entry['video_id']}, run {entry['run_id']})")
            try:
                download_video_with_retry(entry, path)
            except ArtifactUnavailableError as e:
                print(f"::warning::{entry['label']} ({entry['video_id']}) のアーティファクトが"
                      f"恒久的に取得できないため、結合対象から除外します: {e}")
                newly_skipped_ids.append(entry["video_id"])
                continue
            except Exception as e:
                # ネットワークエラー・GitHub API側の5xx等、恒久的とは判断
                # できない一時的な問題である可能性が高い。ここで結合対象から
                # 除外してしまうと、実際には取得可能な動画が二度と結合対象に
                # ならなくなるため、除外せずに今回の結合処理自体を中断する
                # (次回同じ動画から再試行する)。
                print(f"::warning::{entry['label']} ({entry['video_id']}) の取得に"
                      f"{config.COMPILATION_DOWNLOAD_MAX_RETRIES}回失敗しました。恒久的な問題とは"
                      f"判断できないため、結合対象から除外せず今回の結合処理を中断します"
                      f"(次回同じ動画から再試行します): {e}")
                raise
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
