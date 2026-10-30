import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import comment_request_state


def test_load_comment_request_state_missing_file_returns_empty(tmp_path, monkeypatch):
    path = tmp_path / "comment_request_state.json"
    monkeypatch.setattr(comment_request_state, "COMMENT_REQUEST_STATE_PATH", str(path))
    assert comment_request_state.load_comment_request_state() == {"processed_comment_ids": []}


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "comment_request_state.json"
    monkeypatch.setattr(comment_request_state, "COMMENT_REQUEST_STATE_PATH", str(path))
    state = {"processed_comment_ids": ["c1", "c2"]}
    comment_request_state.save_comment_request_state(state)
    assert comment_request_state.load_comment_request_state() == state


def test_load_comment_request_state_handles_empty_file(tmp_path, monkeypatch):
    path = tmp_path / "comment_request_state.json"
    path.write_text("")
    monkeypatch.setattr(comment_request_state, "COMMENT_REQUEST_STATE_PATH", str(path))
    assert comment_request_state.load_comment_request_state() == {"processed_comment_ids": []}


def test_load_comment_request_state_handles_broken_json(tmp_path, monkeypatch):
    path = tmp_path / "comment_request_state.json"
    path.write_text("{not valid json")
    monkeypatch.setattr(comment_request_state, "COMMENT_REQUEST_STATE_PATH", str(path))
    assert comment_request_state.load_comment_request_state() == {"processed_comment_ids": []}
