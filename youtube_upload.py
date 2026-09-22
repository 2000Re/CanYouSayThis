"""
YouTube Data API v3 への動画アップロード。

CI(GitHub Actions)のようにブラウザ操作ができない環境で動かすため、対話的な
OAuth同意フロー(InstalledAppFlow)は使わない。代わりに、あらかじめローカル
で一度だけ取得しておいたリフレッシュトークン(get_youtube_refresh_token.py
参照)から、実行のたびにアクセストークンを再発行する方式にしている。

必要な環境変数:
    YOUTUBE_CLIENT_ID       Google CloudのOAuthクライアントID
    YOUTUBE_CLIENT_SECRET   同クライアントシークレット
    YOUTUBE_REFRESH_TOKEN   get_youtube_refresh_token.py で取得したリフレッシュトークン

任意の環境変数:
    YOUTUBE_CHANNEL_ID      アップロード先として想定しているチャンネルID(UCから始まる文字列)。
                            設定しておくと、実際に認証されたチャンネルと一致するかを
                            アップロード前に確認する(下記の罠を参照)。
    YOUTUBE_REFRESH_TOKEN_ISSUED_AT
                            get_youtube_refresh_token.py を実行した日付(YYYY-MM-DD)。
                            設定しておくと、OAuth同意画面が「テスト」ステータスの場合の
                            既知の7日失効ルールが近づいた/過ぎた際に警告を出す。
    YOUTUBE_SHORTS_PLAYLIST_ID
                            設定しておくと、generate.pyがアップロードした各Shortsを
                            このIDの再生リストに自動追加する(add_to_playlist()参照)。
    YOUTUBE_COMPILATION_PLAYLIST_ID
                            設定しておくと、compile_shorts.pyがアップロードした結合動画を
                            このIDの再生リストに自動追加する。

罠: 1つのGoogleアカウントで複数のYouTubeチャンネル(ブランドアカウント)を
管理している場合、リフレッシュトークンがどのチャンネルに紐づくかは
「取得時にYouTube上でアクティブだったチャンネル」で決まり、意図したチャン
ネルとは限らない。しかもAPIはエラーを返さず黙って別チャンネルにアップロー
ドしてしまうため、気づきにくい。YOUTUBE_CHANNEL_ID を設定しておけば、
チャンネルが想定と違う場合はアップロードせずに即座にエラーで止まる。
"""

import datetime
import os
import random
import time

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaInMemoryUpload

import config

# get_youtube_refresh_token.py が要求するスコープと一致させている
# (OAuth同意画面に登録済みのスコープに合わせて youtube.upload 単体ではなく
# youtube フルアクセスを使っている)
#
# youtube.force-ssl は captions.insert(字幕アップロード、upload_caption()
# 参照)専用のスコープで、youtube単体では権限不足になる。yt-analytics.readonly
# と同じく、既存のリフレッシュトークンには後から追加できない(スコープは
# 発行時に焼き付けられる仕様)ため、追加した場合はget_youtube_refresh_token.py
# を再実行してYOUTUBE_REFRESH_TOKENを取得し直す必要がある。
UPLOAD_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"

# アップロード中に一時的なサーバーエラーが起きても、無条件に諦めず
# 指数バックオフで再試行する(公式サンプルに倣った値)
_RETRIABLE_STATUS_CODES = (500, 502, 503, 504)
_MAX_RETRIES = 8

# YouTube Data API v3の公式ドキュメントに基づく、1回あたりのクォータ消費コスト
# (日次クォータの目安に対する概算を実行ログに表示するために使う)
QUOTA_COST_PER_CALL = {
    "videos.insert": 100, "playlistItems.insert": 50, "channels.list": 1,
    "videos.list": 1, "videos.update": 50, "captions.insert": 400,
}
_api_call_counts = {name: 0 for name in QUOTA_COST_PER_CALL}


def _quota_summary_lines(api_call_counts, quota_cost_per_call,
                          daily_quota_units=config.DAILY_QUOTA_UNITS,
                          daily_upload_limit=config.DAILY_UPLOAD_LIMIT):
    """クォータ使用量のサマリーを行のリストで返す(printしない、テスト容易性のため)。"""
    total_units = sum(count * quota_cost_per_call[name] for name, count in api_call_counts.items())
    remaining_units = max(daily_quota_units - total_units, 0)
    uploads = api_call_counts.get("videos.insert", 0)
    remaining_uploads = max(daily_upload_limit - uploads, 0)

    lines = ["=== API使用量(YouTube Data API v3、概算) ==="]
    for name, count in api_call_counts.items():
        lines.append(f"  {name}: {count}回 (1回あたり{quota_cost_per_call[name]} units)")
    lines.append(f"  概算クォータ消費: {total_units} units / 日次上限 {daily_quota_units} units"
                 f"(残容量目安: {remaining_units} units)")
    lines.append(f"  動画アップロード回数: {uploads}回 / 日次上限 {daily_upload_limit}本"
                 f"(残り目安: {remaining_uploads}本)")
    return lines


def log_api_usage_summary():
    """この実行(プロセス)で消費したYouTube Data APIのクォータ概算をログに出す。

    generate.py が --upload 使用時に全動画の生成後、1回だけ呼び出す想定。"""
    for line in _quota_summary_lines(_api_call_counts, QUOTA_COST_PER_CALL):
        print(line)


_token_age_warned = False


def _token_age_warning(issued_at_str, today=None,
                        warning_after_days=config.TOKEN_WARNING_AFTER_DAYS,
                        expiry_days=config.TOKEN_EXPIRY_DAYS):
    """issued_at_str(YYYY-MM-DD)から今日までの経過日数を見て、リフレッシュ
    トークンの再発行が近い/おそらく過ぎている場合は警告メッセージを返す。

    issued_at_str が未設定・不正な形式の場合は None を返す(このチェックは
    あくまでベストエフォートで、設定していない既存環境を壊さないため)。"""
    if not issued_at_str:
        return None
    try:
        issued_at = datetime.date.fromisoformat(issued_at_str.strip())
    except ValueError:
        return None

    today = today or datetime.date.today()
    age_days = (today - issued_at).days

    if age_days >= expiry_days:
        return (
            f"YOUTUBE_REFRESH_TOKEN は発行から{age_days}日経過しています。OAuth同意画面が"
            f"「テスト」ステータスの場合の既知の{expiry_days}日失効ルールをおそらく超えており、"
            "アップロードが invalid_grant 等で失敗し始めている可能性があります。"
            "get_youtube_refresh_token.py を再実行し、YOUTUBE_REFRESH_TOKEN と"
            "YOUTUBE_REFRESH_TOKEN_ISSUED_AT を更新してください。"
        )
    if age_days >= warning_after_days:
        days_left = expiry_days - age_days
        return (
            f"YOUTUBE_REFRESH_TOKEN は発行から{age_days}日経過しています。OAuth同意画面が"
            f"「テスト」ステータスの場合、あと{days_left}日程度で失効する可能性があります。"
            "近いうちに get_youtube_refresh_token.py を再実行し、YOUTUBE_REFRESH_TOKEN と"
            "YOUTUBE_REFRESH_TOKEN_ISSUED_AT を更新してください。"
        )
    return None


def _check_token_age():
    """YOUTUBE_REFRESH_TOKEN_ISSUED_AT が設定されていれば、失効が近い/過ぎている
    場合に1プロセスにつき1回だけ警告を出す(--count で複数本アップロードする際に
    同じ警告が毎回流れて埋もれないようにするため)。"""
    global _token_age_warned
    if _token_age_warned:
        return
    message = _token_age_warning(os.environ.get("YOUTUBE_REFRESH_TOKEN_ISSUED_AT"))
    if message:
        print(f"::warning::{message}")
        _token_age_warned = True


# _load_credentials()のscopes引数で「未指定(デフォルトのUPLOAD_SCOPESを使う)」
# と「明示的にNone(リフレッシュ時にscopeパラメータを付けない)」を区別するための
# 目印。Noneをデフォルト値に使うと後者を表現できなくなるため。
_SCOPES_UNSET = object()


def _load_credentials(scopes=_SCOPES_UNSET):
    """環境変数からOAuth認証情報を組み立てる。

    scopesを省略するとUPLOAD_SCOPES(アップロード/チャンネル確認用)になる。
    youtube_analytics.pyから呼ぶ際はscopes=Noneを渡す想定で、ここを共通化して
    いる(YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKENの読み込みロジックはどちらも
    同じ)。

    scopes=Noneの場合、Credentialsのrefresh()はトークンリフレッシュ要求に
    scopeパラメータを含めなくなり、リフレッシュトークン発行時に実際に付与
    された範囲そのままのアクセストークンが返る(スコープの絞り込みをしない)。
    scopesにUPLOAD_SCOPES等の具体的なリストを渡すと、それがリフレッシュ
    トークンの発行時に付与された範囲の部分集合である場合に限り、その範囲に
    絞り込んだアクセストークンを要求する(部分集合でない場合はGoogle側で
    invalid_scopeエラーになる)。"""
    if scopes is _SCOPES_UNSET:
        scopes = UPLOAD_SCOPES
    missing = [
        name for name in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(
            "YouTube APIに必要な環境変数が未設定です: " + ", ".join(missing)
            + "(get_youtube_refresh_token.py の手順を参照)"
        )
    return Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=scopes,
    )


_channel_verified = False


def _verify_channel(youtube):
    """YOUTUBE_CHANNEL_ID が設定されていれば、認証されたチャンネルと一致するか確認する。
    未設定なら何もしない(後方互換のため必須にはしていない)。

    1プロセス内でチャンネルが途中で変わることはないため、検証に成功したら
    以降の呼び出しはAPIを叩かずスキップする(--count で複数本アップロードする際、
    upload_video()/add_to_playlist() それぞれが get_youtube_client() 経由でこの
    関数を呼ぶため、キャッシュしないと動画本数の倍近いchannels.list呼び出しが
    無駄に発生してしまう)。失敗時はキャッシュせず、次回呼び出し時も再検証する。"""
    global _channel_verified
    if _channel_verified:
        return

    expected_id = os.environ.get("YOUTUBE_CHANNEL_ID")
    if not expected_id:
        return

    try:
        _api_call_counts["channels.list"] += 1
        resp = youtube.channels().list(part="id,snippet", mine=True).execute()
    except HttpError as e:
        if e.resp.status == 403:
            raise RuntimeError(
                "チャンネル確認用のAPI呼び出し(channels.list)が権限不足で失敗しました。"
                "現在の YOUTUBE_REFRESH_TOKEN は youtube / youtube.readonly スコープ無しで"
                "取得された古いものである可能性が高いです。get_youtube_refresh_token.py を"
                "再実行して新しいリフレッシュトークンを取得し、YOUTUBE_REFRESH_TOKEN を"
                "更新してください。"
            ) from e
        raise

    channels = resp.get("items", [])
    if not channels:
        raise RuntimeError("認証されたGoogleアカウントに紐づくYouTubeチャンネルが見つかりません")

    actual = channels[0]
    if actual["id"] != expected_id:
        raise RuntimeError(
            f"アップロード先チャンネルが想定と異なります: "
            f"期待 YOUTUBE_CHANNEL_ID={expected_id} / "
            f"実際は {actual['snippet']['title']} (id={actual['id']})。"
            "同じGoogleアカウントが複数チャンネルを持つ場合、リフレッシュトークン取得時に"
            "YouTube上でアクティブだったチャンネルが使われるため、意図したチャンネルで"
            "get_youtube_refresh_token.py を実行し直してください。"
        )

    _channel_verified = True


def get_youtube_client():
    """認証済みのYouTube Data APIクライアントを返す(チャンネル確認込み)。

    upload_video() と compile_shorts.py の両方から使う共通処理。"""
    credentials = _load_credentials()
    youtube = build("youtube", "v3", credentials=credentials)
    _verify_channel(youtube)
    _check_token_age()
    return youtube


def upload_video(video_path, title, description, tags=None, category_id=config.YOUTUBE_CATEGORY_ID,
                  privacy_status="public"):
    """video_path をYouTubeにアップロードし、公開URL(https://youtu.be/<id>)を返す。

    category_id のデフォルトはconfig.YOUTUBE_CATEGORY_ID(Howto & Style)。
    """
    youtube = get_youtube_client()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    # 一時的なサーバーエラーでリトライが発生しても、実際に消費されるクォータは
    # 動画1本ぶんだけなので、リトライのたびに加算せずここで1回だけ数える。
    _api_call_counts["videos.insert"] += 1
    response = None
    retries = 0
    while response is None:
        try:
            _status, response = request.next_chunk()
        except HttpError as e:
            if e.resp.status in _RETRIABLE_STATUS_CODES and retries < _MAX_RETRIES:
                retries += 1
                time.sleep(min(2 ** retries + random.random(), 60))
                continue
            raise

    return f"https://youtu.be/{response['id']}"


def append_video_description(video_id, extra_text):
    """既存動画(video_id)の概要欄の末尾に extra_text を追記する。

    videos.update の part=snippet はスニペット全体を丸ごと置き換える仕様
    (パッチではない)なので、事前に videos.list で現在のスニペットを取得
    してから description だけ書き換えて送り返す必要がある(取得せずに
    description のみ送ると title 等の他フィールドが失われてしまう)。

    compile_shorts.py が、結合動画の元になった各Shortsの概要欄に結合動画
    へのリンクを追記し、回遊(リピート視聴)を誘導するために使う。"""
    youtube = get_youtube_client()

    _api_call_counts["videos.list"] += 1
    resp = youtube.videos().list(part="snippet", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError(f"動画 {video_id} が見つかりません(削除された可能性があります)")

    snippet = items[0]["snippet"]
    snippet["description"] = f"{snippet['description']}\n\n{extra_text}"

    _api_call_counts["videos.update"] += 1
    youtube.videos().update(part="snippet", body={"id": video_id, "snippet": snippet}).execute()


def add_to_playlist(video_id, playlist_id):
    """video_idの動画をplaylist_idの再生リストに追加する。

    動画本体のアップロードとは別のAPI呼び出しなので、失敗しても動画自体は
    既に公開済みである(呼び出し側はこの関数の例外を警告に留め、処理全体は
    止めない想定。generate.py / compile_shorts.py 参照)。"""
    youtube = get_youtube_client()
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    _api_call_counts["playlistItems.insert"] += 1
    youtube.playlistItems().insert(part="snippet", body=body).execute()


def _srt_timestamp(seconds):
    """SRTのタイムスタンプ形式(HH:MM:SS,mmm)に変換する。"""
    total_ms = max(round(seconds * 1000), 0)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _build_srt(text, duration_seconds):
    """text を動画全体(0秒〜duration_seconds)にかかる1キューだけのSRT文字列
    にする。発話内容とタイミングを同期させる必要が無い固定テキストのため、
    複数キューに分割する意味が無い。"""
    return f"1\n00:00:00,000 --> {_srt_timestamp(duration_seconds)}\n{text}\n"


def upload_caption(video_id, duration_seconds, text, language=config.CAPTION_LANGUAGE):
    """video_idの動画に、text全体を1キューのSRT字幕として手動でアップロード
    する。

    [背景] espeak-ngが読み上げる単語はでたらめな文字列のため、字幕を付けずに
    YouTubeの自動文字起こし(ASR)に任せると、意味不明な字幕が生成され、検索
    インデックス対象になり得るテキスト枠が無駄になる。代わりに動画の説明文
    と同じ趣旨のキーワード付き固定テキストを手動字幕として入れることで、
    アクセシビリティと検索キーワードの両方を稼ぐ狙い。

    captions.insertはyoutube.force-ssl スコープが必要(UPLOAD_SCOPES参照)。
    動画本体のアップロードとは別のAPI呼び出しなので、呼び出し側はこの関数の
    例外を警告に留め、処理全体は止めない想定(add_to_playlist()と同じ方針、
    generate.py参照)。"""
    youtube = get_youtube_client()
    srt_body = _build_srt(text, duration_seconds)
    media = MediaInMemoryUpload(srt_body.encode("utf-8"), mimetype="text/plain")
    body = {
        "snippet": {
            "videoId": video_id,
            "language": language,
            "name": "",
            "isDraft": False,
        }
    }
    _api_call_counts["captions.insert"] += 1
    youtube.captions().insert(part="snippet", body=body, media_body=media).execute()
