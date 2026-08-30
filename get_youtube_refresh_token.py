#!/usr/bin/env python3
"""
YouTube Data API 用リフレッシュトークンを、開発者のローカルマシンで一度だけ
取得するためのヘルパースクリプト。

GitHub Actions側(youtube_upload.py)はブラウザ操作ができないCI環境なので、
対話的なOAuth同意フローをそこで実行することはできない。そのため、このスク
リプトを手元で一度だけ実行してリフレッシュトークンを取得し、それを
GitHub Secretsに登録しておく運用にしている(取得したトークンは以後失効
しない限り使い回せる)。

事前準備(Google Cloud Console):
    1. プロジェクトを作成し、「YouTube Data API v3」を有効化する
    2. 「OAuth同意画面」を設定する(公開ステータスは「テスト」のままでよい。
       その場合は自分のGoogleアカウントを「テストユーザー」に追加すること)
    3. 「認証情報」→「OAuthクライアントIDを作成」で、種類は
       「デスクトップアプリ」を選んで作成する
       (このスクリプトはループバックアドレス http://localhost でリダイレクト
        を受け取るため、デスクトップアプリ種別である必要がある)

重要: 認可した**Googleアカウントに複数のYouTubeチャンネル(ブランドアカ
ウント)が紐づいている場合、認可した時点でYouTube上で「アクティブ」だった
チャンネルにアップロード権限が発行される**。意図したチャンネルにアップ
ロードしたい場合は、このスクリプトを実行する前に
https://www.youtube.com を開き、右上のアカウントメニューから対象の
チャンネルに切り替えてから実行すること。

使い方:
    pip install -r requirements-dev.txt
    python3 get_youtube_refresh_token.py --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET

実行するとブラウザが開いてGoogleアカウントでの認可を求められる。認可すると
リフレッシュトークンが標準出力に表示されるので、それを
YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN として
GitHub Secretsに登録する。表示されるチャンネル名が意図したものか、必ず
確認すること。
"""

import argparse

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# youtube.readonly は、アップロード先チャンネルが想定通りか確認する
# youtube_upload.py の YOUTUBE_CHANNEL_ID チェックのために必要
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def main():
    ap = argparse.ArgumentParser(description="YouTubeアップロード用リフレッシュトークンの取得")
    ap.add_argument("--client-id", required=True, help="OAuthクライアントID")
    ap.add_argument("--client-secret", required=True, help="OAuthクライアントシークレット")
    args = ap.parse_args()

    client_config = {
        "installed": {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    # prompt="consent" を明示し、2回目以降の認可でもrefresh_tokenが
    # 確実に返るようにする(省略すると初回以外はNoneになることがある)
    credentials = flow.run_local_server(port=0, prompt="consent")

    print("\n取得できました。以下をGitHub Secretsに登録してください:\n")
    print(f"  YOUTUBE_CLIENT_ID={args.client_id}")
    print(f"  YOUTUBE_CLIENT_SECRET={args.client_secret}")
    print(f"  YOUTUBE_REFRESH_TOKEN={credentials.refresh_token}")

    try:
        youtube = build("youtube", "v3", credentials=credentials)
        channels = youtube.channels().list(part="id,snippet", mine=True).execute().get("items", [])
        if channels:
            ch = channels[0]
            print(f"\n認可されたチャンネル: {ch['snippet']['title']} (id={ch['id']})")
            print("  -> このチャンネルが意図したものであることを確認してください。")
            print(f"  -> 誤アップロード防止のため、任意で YOUTUBE_CHANNEL_ID={ch['id']} も"
                  " GitHub Secretsに登録することを推奨します。")
        else:
            print("\n警告: このアカウントに紐づくYouTubeチャンネルが見つかりませんでした。")
    except Exception as e:  # noqa: BLE001 - 確認用の付加情報なので失敗しても致命的ではない
        print(f"\n(チャンネル確認に失敗しましたが、トークン自体は取得済みです: {e})")


if __name__ == "__main__":
    main()
