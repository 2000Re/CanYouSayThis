"""
repost_state.py

repost_shorts.py の変換状態(変換済み・恒久的に取得不可能な動画)を管理する。

google-api-python-client等の重い依存を持たないため、requirements-dev.txt
だけの軽量なテスト環境からもインポートしてテストできる(upload_history.py
と同じ狙いでrepost_shorts.pyから切り出している)。
"""
import io
import json
import os
import zipfile

from config import REPOST_STATE_PATH


def load_repost_state() -> dict:
    """変換状態を読み込む。

    {"converted_video_ids": [...], "skipped_video_ids": [...]}
    - converted_video_ids: 過去に個別の通常動画への変換・アップロードに
      成功した動画のvideo_id。
    - skipped_video_ids: ダウンロードを試みたが恒久的に失敗し、変換対象から
      除外したvideo_id(動画の削除・非公開化・著作権クレーム等が主な原因で、
      リトライしても解決しない)。ここに記録しておかないと、同じ動画の
      ダウンロードに毎回失敗し続け、それ以降の単語が永久に変換されなくなる。

    ファイルが無い/空/壊れている場合は空の状態として扱い、処理を止めない。"""
    empty = {"converted_video_ids": [], "skipped_video_ids": []}
    if not os.path.exists(REPOST_STATE_PATH):
        return empty
    with open(REPOST_STATE_PATH, encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        return empty
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"警告: {REPOST_STATE_PATH} の読み込みに失敗しました({e})。状態なしとして続行します。")
        return empty
    return {
        "converted_video_ids": raw.get("converted_video_ids", []),
        "skipped_video_ids": raw.get("skipped_video_ids", []),
    }


def save_repost_state(state: dict) -> None:
    with open(REPOST_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def select_pending(repostable: list, state: dict) -> list:
    """変換済みでも恒久スキップ済みでもないエントリを、元の順序のまま返す。"""
    exclude = set(state["converted_video_ids"]) | set(state["skipped_video_ids"])
    return [h for h in repostable if h["video_id"] not in exclude]


def find_artifact(artifacts: list, name: str) -> dict | None:
    """GitHub Actions APIが返すアーティファクト一覧から、名前が一致する
    ものを探す(見つからなければNone)。"""
    return next((a for a in artifacts if a.get("name") == name), None)


def extract_zip_member(zip_bytes: bytes, member_name: str) -> bytes:
    """GitHub Actionsアーティファクト(zip)のバイト列から、指定した
    ファイル1件の中身を取り出す。見つからない場合はKeyErrorを送出する
    (zipfile.ZipFile.readの標準動作)。"""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return zf.read(member_name)
