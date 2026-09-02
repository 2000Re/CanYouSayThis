"""
upload_history.json(YouTubeへのアップロード成功履歴)の読み書きを共通化する。

generate.py(アップロード成功時に記録)と compile_shorts.py(結合対象の
選定に使う)の両方から参照するため、ここに集約する。

moviepy/google-api-python-client等の重い依存を持たないため、
requirements-dev.txtだけの軽量なテスト環境からもインポートしてテストできる。
"""
import json
import os

from config import UPLOAD_HISTORY_PATH


def load_upload_history() -> list:
    """アップロード成功履歴を古い→新しい順で読み込む。

    各要素は {"word": str, "label": str, "video_id": str, "mode": str, "run_id": str|None}。
    run_idはcompile_shorts.pyが、この動画が生成された回のGitHub Actions
    アーティファクトを取得し直すために使う(GITHUB_RUN_IDはGitHub Actions
    が各実行に自動設定する環境変数。ローカル実行等でrunがない場合はNone)。

    ここへの記録は generate.py が youtube_upload.upload_video() の成功を
    確認した後にのみ行う。TTS/動画生成/アップロードのいずれかで失敗した
    回をここに記録すると、実際には存在しない動画IDが compile_shorts.py の
    結合対象に紛れ込んでしまうため。

    ファイルが無い/空/壊れている場合は履歴なしとして扱い、処理を止めない
    (手動編集や書き込み中の異常終了で空ファイルになるケースがあるため)。"""
    if not os.path.exists(UPLOAD_HISTORY_PATH):
        return []
    with open(UPLOAD_HISTORY_PATH, encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        return []
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"警告: {UPLOAD_HISTORY_PATH} の読み込みに失敗しました({e})。"
              f"履歴なしとして続行します。")
        return []


def save_upload_history(history: list) -> None:
    with open(UPLOAD_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def append_upload(word: str, label: str, video_id: str, mode: str, run_id: str | None = None) -> None:
    """1件のアップロード成功を履歴に追記する。"""
    history = load_upload_history()
    history.append({"word": word, "label": label, "video_id": video_id, "mode": mode, "run_id": run_id})
    save_upload_history(history)
