"""
視聴者リクエスト(音楽記号+はさみ記号+チェス記号混在の単語)等、label
(タイトル・字幕・コメント用)に記号文字が混じっていたせいで、公開済み
動画のタイトル表示が豆腐(❓)や意図しない絵文字になっていたケースを、
後から正しい内容に差し替える一回限りのバックフィルツール
(README「ハマった罠」79番、_sanitize_label_for_display()導入のきっかけ
になった動画の修正用)。

upload_history.jsonに記録されているword/label/mode/lang_code/
voice_label/title_templateから、現在のgenerate.py _youtube_metadata()
(修正済み)を使ってtitle/description/localizationsを組み立て直し、
videos.updateで差し替える。title_templateが記録されていない古い
エントリ(README「ハマった罠」77番参照)は、元のタイトルの言い回しを
再現できないため対象外とする。

概要欄の再生リストリンクはupload_history.jsonに記録が無いため、現在
ライブの概要欄から正規表現で抽出して引き継ぐ
(youtube_upload.append_video_description()と同じ「videos.listで現在の
スニペットを取得してから一部だけ書き換えて送り返す」方式)。

使い方:
    python3 youtube_fix_title_description.py --video-ids ABC123,DEF456
"""
import argparse
import re

from generate import _youtube_metadata
from upload_history import load_upload_history
from youtube_upload import get_youtube_client

_PLAYLIST_LINK_PATTERN = re.compile(r"playlist\?list=([\w-]+)")


def _load_upload_history_entry(video_id):
    for entry in load_upload_history():
        if entry.get("video_id") == video_id:
            return entry
    return None


def fix_video_title_description(video_id):
    """1本の動画のtitle/description/localizationsを組み立て直す(修正した場合True)。"""
    entry = _load_upload_history_entry(video_id)
    if entry is None:
        print(f"  {video_id}: upload_history.jsonに記録が無いためスキップ")
        return False
    if not entry.get("title_template"):
        print(f"  {video_id}: title_templateが記録されていないためスキップ"
              "(元の言い回しを再現できない、README「ハマった罠」77番参照)")
        return False

    youtube = get_youtube_client()
    resp = youtube.videos().list(part="snippet", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        print(f"  {video_id}: 動画が見つかりません(削除された可能性があります)")
        return False
    snippet = items[0]["snippet"]

    playlist_match = _PLAYLIST_LINK_PATTERN.search(snippet.get("description", ""))
    playlist_id = playlist_match.group(1) if playlist_match else None

    title, description, _tags, _caption, _comment, localizations = _youtube_metadata(
        entry["word"], entry["label"], entry.get("mode", "tts"),
        playlist_id=playlist_id,
        voice_label=entry.get("voice_label"),
        lang_code=entry.get("lang_code"),
        title_template=entry["title_template"],
    )

    if snippet.get("title") == title and snippet.get("description") == description:
        print(f"  {video_id}: 修正不要(既に最新の内容と一致)")
        return False

    print(f"  {video_id}: title {snippet.get('title')!r} -> {title!r}")
    snippet["title"] = title
    snippet["description"] = description

    youtube.videos().update(part="snippet", body={"id": video_id, "snippet": snippet}).execute()
    if localizations:
        youtube.videos().update(
            part="localizations",
            body={"id": video_id, "localizations": localizations},
        ).execute()
    return True


def main():
    ap = argparse.ArgumentParser(
        description="既存動画のtitle/description/localizationsを、現在の"
                     "generate.py _youtube_metadata()で組み立て直した内容に"
                     "差し替える(README「ハマった罠」79番のバックフィル用)"
    )
    ap.add_argument("--video-ids", type=str, required=True,
                     help="カンマ区切りの動画ID(例: ABC123,DEF456)")
    args = ap.parse_args()

    video_ids = [v.strip() for v in args.video_ids.split(",") if v.strip()]
    print(f"=== {len(video_ids)}本の動画のtitle/descriptionを確認します ===")
    fixed_count = sum(1 for video_id in video_ids if fix_video_title_description(video_id))
    print(f"=== {fixed_count}/{len(video_ids)}本を修正しました ===")


if __name__ == "__main__":
    main()
