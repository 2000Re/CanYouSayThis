#!/usr/bin/env python3
"""
repost_shorts.py

upload_history.json に記録された「アップロード成功済み」の動画を1本ずつ、
横型(16:9)にピラーボックスした「通常動画」として、元のShortsと同じ
タイトル・説明文のまま再アップロードする。

[設計変更の経緯] 当初はconfig.REPOST_STATE_PATHが示す通りShortsが10本
たまるごとに1本の結合動画にまとめていたが、再生数がほとんど伸びなかった。
このチャンネルの動画タイトル("How to Pronounce <word>")は「how to
pronounce (記号/単語)」という具体的な検索語との一致で再生数を得る性質が
強く、10単語ぶんを1つのタイトルにまとめると個々の単語の検索語に一致しなく
なり、この強みを自ら潰してしまっていたと判断(詳細はconfig.py参照)。その
ため1本ずつ、同じタイトルを保ったまま変換する方式に変更した。

[設計] Shorts(縦型9:16、3分以内)を単純に横型キャンバスに載せ替えるのは、
YouTubeのShorts判定がアスペクト比+尺のみで機械的に決まる仕様のため
(投稿者の意図では変えられない)。ピラーボックス配置で確実に「通常動画」
として扱われるようにする。

[設計] 動画本体の取得元について: YouTubeに公開済みの動画をyt-dlpで
再ダウンロードする方式だと、GitHub ActionsのIPがYouTube側に
「Sign in to confirm you're not a bot」でボット判定される問題があり
(cookie認証を渡しても解決しない事例が確認されている)、YouTube/yt-dlpに
一切依存しない方式にしている: generate.pyが生成した動画は既に
generate.ymlの「Upload generated videos」ステップでGitHub Actions
アーティファクト(config.REPOST_ARTIFACT_NAME)として保存されているため、
これをGitHub Actions APIから取得する。取得元のrunは、generate.pyが
upload_history.jsonへ記録する各エントリのrun_id(GITHUB_RUN_ID)で特定する
(詳細はREADME「ハマった罠」の8番を参照)。

[設計] アーティファクトの保持期限切れ・該当runが見つからない等の
「恒久的に取得不可能」なケースで、その1本のせいで変換処理全体が永久に
止まってしまわないよう、該当エントリは変換対象から除外し
(repost_state.pyのskipped_video_idsに記録)、残りの動画で処理を続行する。
run_idが記録されていない旧いエントリ(この方式導入前にアップロードされた
もの)は、そもそもどのrunのアーティファクトか特定できないため変換対象外に
する。

[設計] 各エントリは互いに独立しているため(結合動画と違い複数本まとめて
1本にする必要がない)、1本の取得が一時的なエラーで失敗しても、その回の
処理全体を止めず残りの候補へ進む。config.REPOST_MAX_PER_RUNで1回の実行
あたりの変換件数を絞り、YouTube側の1日あたりアップロード本数上限
(未認証チャンネルほど低い)にgenerate.py本編のアップロード分と合わせて
収まるようにしている。

[設計] 変換後、通常動画の概要欄に元Shortsへのリンクを、元Shortsの概要欄に
通常動画へのリンクをそれぞれ追記する(youtube_upload.append_video_description())。
検索で片方だけに辿り着いた視聴者にもう片方への導線を示し、
リピート視聴・チャンネル登録につなげる狙い。

YouTube Data API(通常動画のアップロード用)の認証方式・環境変数は
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
from moviepy import ColorClip, CompositeVideoClip, VideoFileClip

import config
from frame_builder import build_thumbnail
from repost_state import (
    extract_zip_member,
    find_artifact,
    load_repost_state,
    pillarbox_scale,
    save_repost_state,
    select_pending,
)
from upload_history import load_upload_history
import youtube_upload
from youtube_upload import add_to_playlist, append_video_description, log_api_usage_summary
from word_generator import zalgo_display_word

GITHUB_API_BASE = "https://api.github.com"


class ArtifactUnavailableError(Exception):
    """該当エントリの動画アーティファクトが恒久的に取得できない
    (該当runが見つからない/保持期限切れ/アーティファクト内に対象の
    ファイルが無い、等)。リトライしても解決しないため、呼び出し側は
    このエントリを変換対象から除外してよい。"""


def _github_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def download_video(entry: dict, output_path: str) -> None:
    """entryが記録しているGitHub Actions run_idから、その回の
    config.REPOST_ARTIFACT_NAMEアーティファクトを取得し、対象動画の
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
        timeout=config.REPOST_GITHUB_API_TIMEOUT_SECONDS,
    )
    if resp.status_code == 404:
        raise ArtifactUnavailableError(f"run {run_id} が見つかりません(削除された可能性があります)")
    resp.raise_for_status()

    artifact = find_artifact(resp.json().get("artifacts", []), config.REPOST_ARTIFACT_NAME)
    if artifact is None:
        raise ArtifactUnavailableError(
            f"run {run_id} に{config.REPOST_ARTIFACT_NAME}アーティファクトが見つかりません"
        )
    if artifact.get("expired"):
        raise ArtifactUnavailableError(
            f"run {run_id} の{config.REPOST_ARTIFACT_NAME}アーティファクトは保持期限切れです"
        )

    zip_resp = requests.get(
        artifact["archive_download_url"],
        headers=headers,
        timeout=config.REPOST_GITHUB_API_TIMEOUT_SECONDS,
    )
    # 直前のexpiredチェックをすり抜けても、一覧取得とダウンロードの間に
    # アーティファクトが実際に消えている(期限切れ・削除)ことがある。これは
    # runの404チェックと同じく恒久的な問題なので、raise_for_status()任せに
    # せずここでも明示的にArtifactUnavailableErrorにする。そうしないと
    # 「一時的なエラー」としてリトライ後に処理全体を中断してしまい、
    # かつこのエントリはskipped_video_idsに記録されないため、次回以降も
    # 同じ動画で毎回失敗し続けてしまう。
    if zip_resp.status_code in (404, 410):
        raise ArtifactUnavailableError(
            f"run {run_id} の{config.REPOST_ARTIFACT_NAME}アーティファクトの"
            "ダウンロードURLが無効です(取得直前に削除/期限切れになった可能性があります)"
        )
    zip_resp.raise_for_status()

    member_name = f"{entry['video_id']}.mp4"
    try:
        content = extract_zip_member(zip_resp.content, member_name)
    except KeyError:
        raise ArtifactUnavailableError(
            f"{config.REPOST_ARTIFACT_NAME}アーティファクト内に{member_name}が見つかりません"
        )

    with open(output_path, "wb") as f:
        f.write(content)


def download_video_with_retry(entry: dict, output_path: str) -> None:
    """取得失敗を数回リトライする(一時的なネットワーク不調対策)。

    ArtifactUnavailableError(恒久的に取得不可能)は即座に再送出し、リトライしない
    (リトライしても結果が変わらないため)。それ以外のエラーは
    REPOST_DOWNLOAD_MAX_RETRIES回までリトライし、それでも失敗する場合は
    例外を送出する。呼び出し側は例外の型で恒久的/一時的を判別する。"""
    last_error = None
    for attempt in range(1, config.REPOST_DOWNLOAD_MAX_RETRIES + 1):
        try:
            download_video(entry, output_path)
            return
        except ArtifactUnavailableError:
            raise
        except Exception as e:
            last_error = e
            print(f"    取得{attempt}回目失敗: {e}")
            time.sleep(config.REPOST_DOWNLOAD_RETRY_BACKOFF_SECONDS)
    raise last_error


def pillarbox(clip):
    """縦長のクリップを、横型キャンバスの中央に配置し、左右を無地で埋める。"""
    scale = pillarbox_scale(clip.w, clip.h, config.REPOST_VIDEO_WIDTH, config.REPOST_VIDEO_HEIGHT)
    resized = clip.resized(scale)
    bg = ColorClip(
        size=(config.REPOST_VIDEO_WIDTH, config.REPOST_VIDEO_HEIGHT),
        color=config.REPOST_BG_COLOR,
        duration=clip.duration,
    )
    return CompositeVideoClip([bg, resized.with_position("center")]).with_duration(clip.duration)


def build_repost_metadata(entry: dict, original_url: str) -> dict:
    """元ShortsのYouTubeタイトル・説明文のフォーマットを踏襲しつつ、通常
    動画向けに組み立て直す。#Shortsタグ・Shorts専用ハッシュタグは外し、
    元Shortsへのリンクを添える(実際の再生数を左右するのはタイトルの検索
    語一致なので、labelを含むタイトル自体はShortsと完全に同じにする、
    generate.py _youtube_metadata()参照)。"""
    label = entry["label"]
    mode = entry.get("mode", "")
    mode_label = config.MODE_LABELS.get(mode, mode)
    lang_code = entry.get("lang_code")
    lang_entry = config.VOICE_LANGUAGES.get(lang_code) if lang_code else None
    lang_label = lang_entry["label"] if lang_entry and lang_code != "en" else None

    title = f'How to Pronounce "{label}"'
    if lang_label:
        title += f" in {lang_label}?"
    else:
        title += "?"

    description = (
        "Can you pronounce this? \U0001F440\n\n"
        f"Word: {entry['word']}\n"
        f"Mode: {mode_label}\n"
    )
    if entry.get("voice_label"):
        description += f"Voice: {entry['voice_label']}\n"
    description += (
        "\n(This is a randomly generated sequence, not a real word in any "
        "language — just a fun pronunciation challenge!)\n\n"
        f"\U0001F3AC Watch the original Short: {original_url}\n\n"
        "#Pronunciation #Unpronounceable #HowToPronounce #CanYouSayThis"
    )
    tags = ["pronunciation", "unpronounceable", "how to pronounce", mode, "pronunciation challenge"]
    if lang_label:
        tags.append(f"{lang_label.lower()} pronunciation")

    return {"title": title, "description": description, "tags": tags}


def main():
    ap = argparse.ArgumentParser(description="アップロード済みShortsを1本ずつ通常動画として変換・再アップロードする")
    ap.add_argument("--privacy-status", type=str, choices=["public", "unlisted", "private"],
                     default="public", help="変換後の通常動画の公開範囲")
    ap.add_argument("--max-count", type=int, default=config.REPOST_MAX_PER_RUN,
                     help="1回の実行あたりの変換件数上限")
    args = ap.parse_args()

    history = load_upload_history()
    # run_idが無い(この方式導入前にアップロードされた)エントリは、どのrunの
    # アーティファクトか特定できないため変換対象外にする。
    repostable = [h for h in history if h.get("video_id") and h.get("run_id")]

    state = load_repost_state()
    pending = select_pending(repostable, state)

    if not pending:
        print("変換対象がありません。")
        return

    os.makedirs(config.REPOST_DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(config.REPOST_OUTPUT_DIR, exist_ok=True)

    newly_skipped_ids = []
    newly_converted_ids = []
    converted_count = 0

    repost_playlist_id = os.environ.get("YOUTUBE_REPOST_PLAYLIST_ID")

    try:
        for entry in pending:
            if converted_count >= args.max_count:
                break

            path = os.path.join(config.REPOST_DOWNLOAD_DIR, f"{entry['video_id']}.mp4")
            print(f"  取得中: {entry['label']} ({entry['video_id']}, run {entry['run_id']})")
            try:
                download_video_with_retry(entry, path)
            except ArtifactUnavailableError as e:
                print(f"::warning::{entry['label']} ({entry['video_id']}) のアーティファクトが"
                      f"恒久的に取得できないため、変換対象から除外します: {e}")
                newly_skipped_ids.append(entry["video_id"])
                continue
            except Exception as e:
                # ネットワークエラー・GitHub API側の5xx等、恒久的とは判断
                # できない一時的な問題である可能性が高い。除外はせず、この
                # エントリだけ今回は諦めて次の候補に進む(次回同じ動画から
                # 再試行する)。各エントリは独立しているため、1本の一時的な
                # 失敗で他の変換まで止める必要はない。
                print(f"::warning::{entry['label']} ({entry['video_id']}) の取得に"
                      f"{config.REPOST_DOWNLOAD_MAX_RETRIES}回失敗しました。恒久的な問題とは"
                      f"判断できないため、変換対象から除外せず今回はスキップします"
                      f"(次回同じ動画から再試行します): {e}")
                continue

            clip = None
            boxed_clip = None
            output_path = os.path.join(config.REPOST_OUTPUT_DIR, f"repost_{uuid.uuid4().hex}.mp4")
            try:
                clip = VideoFileClip(path)
                boxed_clip = pillarbox(clip)
                boxed_clip.write_videofile(
                    output_path, fps=30, codec="libx264", audio_codec="aac", logger=None
                )

                original_url = f"https://youtu.be/{entry['video_id']}"
                metadata = build_repost_metadata(entry, original_url)
                repost_url = youtube_upload.upload_video(
                    output_path, title=metadata["title"], description=metadata["description"],
                    tags=metadata["tags"], privacy_status=args.privacy_status,
                )
                print(f"[Repost] アップロード完了: {entry['label']} -> {repost_url}")
                repost_video_id = repost_url.rsplit("/", 1)[-1]

                # "絵だけ"のミニマルなカスタムサムネイル(frame_builder.
                # build_thumbnail()参照)。元Shortsと同じ単語をそのまま
                # 16:9画像として設定する(generate.py同様の方針)。YouTube側
                # でカスタムサムネイル機能を使うには電話番号確認が必要なため、
                # config.CUSTOM_THUMBNAIL_ENABLEDがTrueの間だけ動く。失敗
                # しても動画自体は既に公開済みなので警告に留めて処理は止めない。
                if config.CUSTOM_THUMBNAIL_ENABLED:
                    thumbnail_path = output_path + "_thumbnail.png"
                    try:
                        display_word = zalgo_display_word(entry["word"])
                        build_thumbnail(entry["label"], thumbnail_path, display_word=display_word)
                        youtube_upload.upload_thumbnail(repost_video_id, thumbnail_path)
                    except Exception as e:
                        print(f"::warning::{entry['label']} ({entry['video_id']}) のカスタムサムネイル"
                              f"のアップロードに失敗しました: {e}")
                    finally:
                        if os.path.exists(thumbnail_path):
                            os.remove(thumbnail_path)

                # 任意。設定されていれば、変換後の通常動画専用の再生リストに
                # 追加する(失敗しても動画自体は既に公開済みなので、警告に
                # 留めて処理は止めない)。
                if repost_playlist_id:
                    try:
                        add_to_playlist(repost_video_id, repost_playlist_id)
                    except Exception as e:
                        print(f"::warning::通常動画の再生リストへの追加に失敗しました: {e}")

                # 元Shorts <-> 通常動画を相互にリンクする。検索でどちらか
                # 片方にだけ辿り着いた視聴者にもう片方への導線を示す狙い
                # (失敗しても動画自体には影響しないため、警告に留める)。
                try:
                    append_video_description(
                        entry["video_id"],
                        f"\U0001F3AC Also available as a regular video: {repost_url}",
                    )
                except Exception as e:
                    print(f"::warning::{entry['label']} ({entry['video_id']}) の概要欄への"
                          f"通常動画リンク追記に失敗しました: {e}")

                newly_converted_ids.append(entry["video_id"])
                converted_count += 1
            finally:
                if boxed_clip:
                    try:
                        boxed_clip.close()
                    except Exception:
                        pass
                if clip:
                    try:
                        clip.close()
                    except Exception:
                        pass
                for p in (path, output_path):
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception as e:
                        print(f"[Warning] Failed to remove temp file {p}: {e}")

        if converted_count == 0 and not newly_skipped_ids:
            print("今回変換できた動画はありませんでした。")

        log_api_usage_summary()

    finally:
        if newly_converted_ids:
            state["converted_video_ids"].extend(newly_converted_ids)
        if newly_skipped_ids:
            state["skipped_video_ids"].extend(newly_skipped_ids)
        if newly_converted_ids or newly_skipped_ids:
            save_repost_state(state)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 通常動画への変換は本編パイプラインとは独立した追加機能のため、
        # ここで失敗しても当日の生成・アップロード処理は止めない
        # (ジョブは失敗させない)。ただし::error::ワークフローコマンドで
        # GitHub ActionsのUIにエラー注釈を出し、ログを見なくても
        # 失敗に気づけるようにする。
        print(f"::error::Shorts→通常動画変換の処理中にエラーが発生しました: {e}")
