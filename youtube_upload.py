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
from googleapiclient.http import MediaFileUpload

import config

# get_youtube_refresh_token.py が要求するスコープと一致させている
# (OAuth同意画面に登録済みのスコープに合わせて youtube.upload 単体ではなく
# youtube フルアクセスを使っている)
UPLOAD_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"

# アップロード中に一時的なサーバーエラーが起きても、無条件に諦めず
# 指数バックオフで再試行する(公式サンプルに倣った値)
_RETRIABLE_STATUS_CODES = (500, 502, 503, 504)
_MAX_RETRIES = 8

# YouTube Data API v3の公式ドキュメントに基づく、1回あたりのクォータ消費コスト
# (日次クォータの目安に対する概算を実行ログに表示するために使う)
QUOTA_COST_PER_CALL = {"videos.insert": 100}
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


def _load_credentials():
    missing = [
        name for name in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(
            "YouTubeアップロードに必要な環境変数が未設定です: " + ", ".join(missing)
            + "(get_youtube_refresh_token.py の手順を参照)"
        )
    return Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=UPLOAD_SCOPES,
    )


def _verify_channel(youtube):
    """YOUTUBE_CHANNEL_ID が設定されていれば、認証されたチャンネルと一致するか確認する。
    未設定なら何もしない(後方互換のため必須にはしていない)。"""
    expected_id = os.environ.get("YOUTUBE_CHANNEL_ID")
    if not expected_id:
        return

    try:
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


def get_youtube_client():
    """認証済みのYouTube Data APIクライアントを返す(チャンネル確認込み)。

    upload_video() と compile_shorts.py の両方から使う共通処理。"""
    credentials = _load_credentials()
    youtube = build("youtube", "v3", credentials=credentials)
    _verify_channel(youtube)
    _check_token_age()
    return youtube


def upload_video(video_path, title, description, tags=None, category_id="24",
                  privacy_status="public"):
    """video_path をYouTubeにアップロードし、公開URL(https://youtu.be/<id>)を返す。

    category_id のデフォルト "24" は Entertainment。
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

    response = None
    retries = 0
    while response is None:
        try:
            _api_call_counts["videos.insert"] += 1
            _status, response = request.next_chunk()
        except HttpError as e:
            if e.resp.status in _RETRIABLE_STATUS_CODES and retries < _MAX_RETRIES:
                retries += 1
                time.sleep(min(2 ** retries + random.random(), 60))
                continue
            raise

    return f"https://youtu.be/{response['id']}"
