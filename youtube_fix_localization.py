"""
既に公開済みの動画に対し、日本語ローカライズタイトル(localizations.ja.title)
の語順修正を後から適用する一回限りのバックフィルツール。

[背景] 当初、generate.py の _youtube_metadata() は`「{label}」の発音は?
(言語名) #Shorts`という形で日本語タイトルを組み立てていたが、ヘブライ語・
アラビア語(RTL文字)のlabelだとタイトル全体の語順が入れ替わって表示される
不具合があった(README「ハマった罠」24番)。label を First Strong Isolate
(U+2068)〜Pop Directional Isolate(U+2069)で囲む対策を一度入れたが、
この対策を適用した後の新規アップロード分でも同じ不具合が実機で再発した
(2026-10-09アップロード分で確認)。YouTube側が表示前にこのゼロ幅isolate
制御文字自体を取り除いている可能性が高く、不可視文字に頼る対策はあてに
できないと判断し、タイトル文字列の最初の1文字自体を常に実在の強いLTR文字
(言語名のかな/カナ)にする構成へ変更した(「ハマった罠」24番更新、
generate.py _youtube_metadata()参照): 言語名がある場合は
`{言語名}で「{label}」はどう発音する? #Shorts`、無い場合は従来通り
`「{label}」の発音は? #Shorts`。

この変更後の構成は新規アップロード分にしか効かないため、それ以前に公開した
動画のタイトルは videos.update で個別に直す必要がある。現在のタイトルが
旧形式(`「{label}」の発音は?(言語名)? #Shorts`、isolate文字の有無は
問わない)に一致する場合、言語名部分を前に出した新形式へ組み立て直す
(video_idからlang_code等を復元する必要が無いため、upload_history.jsonに
記録されていない情報にも依存しない)。

[罠] lang_codeの記録自体が無かった初期の投稿分は、タイトルに言語名の
`(言語名)`が最初から付いていない(`「{label}」の発音は? #Shorts`のみ)。
このケースでもlabelが実在のヘブライ語・アラビア語文字そのものであれば
同じ語順入れ替わりの不具合が起きるため、タイトルの言語名有無だけでなく
label自体の文字体系(config.HEBREW_LETTERS/ARABIC_LETTERS)からも言語名を
補って判定する。

使い方:
    python3 youtube_fix_localization.py --video-ids ABC123,DEF456
"""
import argparse
import re

from config import ARABIC_LETTERS, HEBREW_LETTERS
from youtube_upload import get_youtube_client

# 「」内のlabelは既にisolate文字(⁨⁩)で囲まれている場合とそうでない場合が
# あるため、どちらも受け付ける。言語名の()は無い回もある。
_OLD_TITLE_PATTERN = re.compile(r"^「(?P<label>.+?)」の発音は\?(?:\((?P<lang>.+?)\))? #Shorts$")


def _detect_rtl_lang_label_ja(label):
    """labelが実在のヘブライ語・アラビア語文字体系かどうかをconfig.py同梱
    の文字集合から判定し、該当すれば日本語の言語名("ヘブライ語"/
    "アラビア語")を返す。どちらでもなければNone。

    lang_codeの記録が無い初期の投稿分(タイトルに言語名の注記自体が無い)
    でも、labelの実際の文字から言語名を復元できるようにするための処理。"""
    if any(c in HEBREW_LETTERS for c in label):
        return "ヘブライ語"
    if any(c in ARABIC_LETTERS for c in label):
        return "アラビア語"
    return None


def _rebuild_title(title):
    """旧形式のタイトルを、言語名を先頭に出した新形式へ組み立て直した文字列
    を返す。旧形式に一致しない(既に新形式、または想定外のタイトル)場合や、
    組み立て直しても変化が無い場合はNoneを返す(変更不要)。"""
    m = _OLD_TITLE_PATTERN.match(title)
    if not m:
        return None
    # 既にisolate文字で囲まれていれば一旦剥がしてから組み立て直す
    # (二重に囲むのを避けるため)。
    label = m.group("label").strip("⁨⁩")
    isolated_label = f"⁨{label}⁩"
    lang = m.group("lang") or _detect_rtl_lang_label_ja(label)
    if lang:
        new_title = f"{lang}で「{isolated_label}」はどう発音する? #Shorts"
    else:
        new_title = f"「{isolated_label}」の発音は? #Shorts"
    return new_title if new_title != title else None


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

    fixed_title = _rebuild_title(ja["title"])
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
