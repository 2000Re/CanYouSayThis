import sys
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
    upload_history.append_upload(word="B́", label="B", video_id="v2", mode="glitch")
    assert upload_history.load_upload_history() == [
        {"word": "Á", "label": "A", "video_id": "v1", "mode": "tts"},
        {"word": "B́", "label": "B", "video_id": "v2", "mode": "glitch"},
    ]
