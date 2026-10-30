"""
comment_request_state.py

comment_requests.py が、視聴者コメントから抽出したリクエスト単語を重複
処理しないための状態(確認済みコメントID)を管理する。

google-api-python-client等の重い依存を持たないため、requirements-dev.txt
だけの軽量なテスト環境からもインポートしてテストできる(upload_history.py/
repost_state.pyと同じ狙いでcomment_requests.pyから切り出している)。
"""
import json
import os

from config import COMMENT_REQUEST_STATE_PATH


def load_comment_request_state() -> dict:
    """確認済みコメントIDの集合を読み込む。

    {"processed_comment_ids": [...]}
    一度「リクエストかどうか判定した」コメントは、該当有無に関わらずここに
    記録する(該当無しのコメントを除外しないと、毎回全コメントを正規表現で
    再判定し続けることになるため)。

    ファイルが無い/空/壊れている場合は空の状態として扱い、処理を止めない。"""
    empty = {"processed_comment_ids": []}
    if not os.path.exists(COMMENT_REQUEST_STATE_PATH):
        return empty
    with open(COMMENT_REQUEST_STATE_PATH, encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        return empty
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"警告: {COMMENT_REQUEST_STATE_PATH} の読み込みに失敗しました({e})。"
              f"状態なしとして続行します。")
        return empty
    return {"processed_comment_ids": raw.get("processed_comment_ids", [])}


def save_comment_request_state(state: dict) -> None:
    with open(COMMENT_REQUEST_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
