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
"""

import os
import random
import time

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

UPLOAD_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_URI = "https://oauth2.googleapis.com/token"

# アップロード中に一時的なサーバーエラーが起きても、無条件に諦めず
# 指数バックオフで再試行する(公式サンプルに倣った値)
_RETRIABLE_STATUS_CODES = (500, 502, 503, 504)
_MAX_RETRIES = 8


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


def upload_video(video_path, title, description, tags=None, category_id="24",
                  privacy_status="public"):
    """video_path をYouTubeにアップロードし、公開URL(https://youtu.be/<id>)を返す。

    category_id のデフォルト "24" は Entertainment。
    """
    credentials = _load_credentials()
    youtube = build("youtube", "v3", credentials=credentials)

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
            _status, response = request.next_chunk()
        except HttpError as e:
            if e.resp.status in _RETRIABLE_STATUS_CODES and retries < _MAX_RETRIES:
                retries += 1
                time.sleep(min(2 ** retries + random.random(), 60))
                continue
            raise

    return f"https://youtu.be/{response['id']}"
