"""
既に公開済みの動画に対し、日本語ローカライズタイトル(localizations.ja.title)
のbidi(双方向文字)修正を後から適用する一回限りのバックフィルツール。

[背景] generate.py の _youtube_metadata() は、ヘブライ語・アラビア語(RTL
文字)の label で日本語ローカライズタイトル全体の語順が入れ替わって表示
される不具合を修正済み(README「ハマった罠」24番。label を First Strong
Isolate(U+2068)〜Pop Directional Isolate(U+2069)で囲む)。この修正は
新規アップロード分にしか効かないため、修正前に公開した動画のタイトルは
videos.update で個別に直す必要がある。

タイトルは `「{label}」の発音は?(言語名) #Shorts` という固定の組み立て方
なので、現在のタイトルから「」で囲まれた部分を正規表現で取り出し、その
部分だけを isolate文字で囲み直す(video_idからlang_code等を復元する必要が
無いため、upload_history.jsonに記録されていない情報にも依存しない)。

使い方:
    python3 youtube_fix_localization.py --video-ids ABC123,DEF456
"""
import argparse
import re

from youtube_upload import get_youtube_client

_LABEL_PATTERN = re.compile(r"「(.+?)」")


def _rewrap_title_label(title):
    """タイトル中の「」で囲まれた部分をbidi isolate文字
    (U+2068 FSI 〜 U+2069 PDI)で囲み直した文字列を返す。「」パターンが
    見つからない、または既に囲み済み(修正後にアップロードされた動画)の
    場合はNoneを返す(変更不要)。"""
    m = _LABEL_PATTERN.search(title)
    if not m:
        return None
    label = m.group(1)
    if label.startswith("⁨") and label.endswith("⁩"):
        return None
    return title.replace(f"「{label}」", f"「⁨{label}⁩」", 1)


def fix_video_localization(video_id):
    """1本の動画のlocalizations.ja.titleを修正する(修正した場合True)。"""
    youtube = get_youtube_client()
    resp = youtube.videos().list(part="localizations", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        print(f"  {video_id}: 動画が見つかりません(削除された可能性があります)")
        return False

    localizations = items[0].get("localizations", {})
    ja = localizations.get("ja")
    if not ja:
        print(f"  {video_id}: localizations.jaが無いためスキップ")
        return False

    fixed_title = _rewrap_title_label(ja["title"])
    if fixed_title is None:
        print(f"  {video_id}: 修正不要(該当パターンなし、または修正済み): {ja['title']!r}")
        return False

    print(f"  {video_id}: {ja['title']!r} -> {fixed_title!r}")
    ja["title"] = fixed_title
    localizations["ja"] = ja

    youtube.videos().update(
        part="localizations",
        body={"id": video_id, "localizations": localizations},
    ).execute()
    return True


def main():
    ap = argparse.ArgumentParser(
        description="既存動画のlocalizations.ja.titleに、bidi isolate文字による"
                     "語順修正を後から適用する"
    )
    ap.add_argument("--video-ids", type=str, required=True,
                     help="カンマ区切りの動画ID(例: ABC123,DEF456)")
    args = ap.parse_args()

    video_ids = [v.strip() for v in args.video_ids.split(",") if v.strip()]
    print(f"=== {len(video_ids)}本の動画のlocalizations.ja.titleを確認します ===")
    fixed_count = sum(1 for video_id in video_ids if fix_video_localization(video_id))
    print(f"=== {fixed_count}/{len(video_ids)}本を修正しました ===")


if __name__ == "__main__":
    main()
