import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import upload_history


def test_load_upload_history_missing_file_returns_empty(tmp_path, monkeypatch):
    path = tmp_path / "upload_history.json"
    monkeypatch.setattr(upload_history, "UPLOAD_HISTORY_PATH", str(path))
    assert upload_history.load_upload_history() == []


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "upload_history.json"
    monkeypatch.setattr(upload_history, "UPLOAD_HISTORY_PATH", str(path))
    history = [{"word": "Á", "label": "A", "video_id": "v1", "mode": "tts"}]
    upload_history.save_upload_history(history)
    assert upload_history.load_upload_history() == history


def test_load_upload_history_handles_empty_file(tmp_path, monkeypatch):
    path = tmp_path / "upload_history.json"
    path.write_text("")
    monkeypatch.setattr(upload_history, "UPLOAD_HISTORY_PATH", str(path))
    assert upload_history.load_upload_history() == []


def test_load_upload_history_handles_broken_json(tmp_path, monkeypatch):
    path = tmp_path / "upload_history.json"
    path.write_text("{not valid json")
    monkeypatch.setattr(upload_history, "UPLOAD_HISTORY_PATH", str(path))
    assert upload_history.load_upload_history() == []


def test_append_upload_adds_entry_to_existing_history(tmp_path, monkeypatch):
    path = tmp_path / "upload_history.json"
    monkeypatch.setattr(upload_history, "UPLOAD_HISTORY_PATH", str(path))
    upload_history.append_upload(word="Á", label="A", video_id="v1", mode="tts")
    upload_history.append_upload(word="B́", label="B", video_id="v2", mode="glitch", run_id="12345")
    history = upload_history.load_upload_history()
    # uploaded_atは呼び出し時刻で毎回変わるため、それ以外のフィールドだけ
    # 厳密比較し、uploaded_atは別途フォーマットを検証する。
    assert [{k: v for k, v in entry.items() if k != "uploaded_at"} for entry in history] == [
        {"word": "Á", "label": "A", "video_id": "v1", "mode": "tts", "run_id": None},
        {"word": "B́", "label": "B", "video_id": "v2", "mode": "glitch", "run_id": "12345"},
    ]
    for entry in history:
        assert entry["uploaded_at"] is not None


def test_append_upload_records_uploaded_at_as_iso8601_utc(tmp_path, monkeypatch):
    from datetime import timezone

    path = tmp_path / "upload_history.json"
    monkeypatch.setattr(upload_history, "UPLOAD_HISTORY_PATH", str(path))

    before = datetime.now(timezone.utc)
    upload_history.append_upload(word="Á", label="A", video_id="v1", mode="tts")
    after = datetime.now(timezone.utc)

    entry = upload_history.load_upload_history()[0]
    parsed = datetime.fromisoformat(entry["uploaded_at"])
    assert parsed.tzinfo is not None  # UTCオフセット情報を含む(ナイーブ時刻でない)
    assert before <= parsed <= after


def test_load_upload_history_tolerates_entries_without_uploaded_at(tmp_path, monkeypatch):
    # uploaded_at追加前の古い履歴データ(このキー自体が無い)を読み込んでも
    # 壊れないことの回帰防止。参照側はentry.get("uploaded_at")でNoneを
    # 受け取れる想定。
    path = tmp_path / "upload_history.json"
    monkeypatch.setattr(upload_history, "UPLOAD_HISTORY_PATH", str(path))
    old_entry = {"word": "Á", "label": "A", "video_id": "v1", "mode": "tts", "run_id": None}
    upload_history.save_upload_history([old_entry])
    loaded = upload_history.load_upload_history()
    assert loaded == [old_entry]
    assert loaded[0].get("uploaded_at") is None
