"""compile_shorts.py の download_video()/ _combined_quota_summary_lines() に
対するユニットテスト。requests.getをモックし、実際のGitHub API呼び出しは
行わない(軽いテストのみ)。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compile_shorts
import youtube_upload


def _mock_response(status_code, json_data=None, content=b""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.content = content
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(f"{status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


def test_download_video_raises_artifact_unavailable_when_run_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "dummy")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setattr(compile_shorts.requests, "get", lambda *a, **k: _mock_response(404))

    entry = {"run_id": "123", "video_id": "abc", "label": "test"}
    with pytest.raises(compile_shorts.ArtifactUnavailableError):
        compile_shorts.download_video(entry, str(tmp_path / "out.mp4"))


def test_download_video_raises_artifact_unavailable_when_download_url_gone(monkeypatch, tmp_path):
    # アーティファクト一覧取得時点ではexpired=Falseでも、実際の
    # archive_download_urlへのダウンロードが404/410を返すことがある
    # (一覧取得とダウンロードの間に削除/期限切れになった場合)。これは
    # ネットワーク的な一時エラーではなく恒久的な問題として扱われるべき、
    # という回帰テスト。
    monkeypatch.setenv("GITHUB_TOKEN", "dummy")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

    artifacts_resp = _mock_response(200, json_data={
        "artifacts": [{
            "name": compile_shorts.config.COMPILATION_ARTIFACT_NAME,
            "expired": False,
            "archive_download_url": "https://example.invalid/artifact.zip",
        }]
    })
    zip_resp = _mock_response(410)
    responses = iter([artifacts_resp, zip_resp])
    monkeypatch.setattr(compile_shorts.requests, "get", lambda *a, **k: next(responses))

    entry = {"run_id": "123", "video_id": "abc", "label": "test"}
    with pytest.raises(compile_shorts.ArtifactUnavailableError):
        compile_shorts.download_video(entry, str(tmp_path / "out.mp4"))


def test_download_video_reraises_plain_error_for_server_error(monkeypatch, tmp_path):
    # 一覧取得・ダウンロードいずれも5xx等の一時的エラーはArtifactUnavailable
    # Errorに変換せず、通常のExceptionとして送出しリトライ対象にする。
    monkeypatch.setenv("GITHUB_TOKEN", "dummy")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setattr(compile_shorts.requests, "get", lambda *a, **k: _mock_response(503))

    entry = {"run_id": "123", "video_id": "abc", "label": "test"}
    with pytest.raises(requests.exceptions.HTTPError):
        compile_shorts.download_video(entry, str(tmp_path / "out.mp4"))


def test_combined_quota_summary_lines_includes_youtube_upload_counts(monkeypatch):
    # get_youtube_client()/add_to_playlist()はyoutube_upload.py側の別の
    # _api_call_countsを加算するため、合算しないとそれらの消費量が
    # サマリーに一切反映されない回帰を防ぐテスト。
    monkeypatch.setattr(compile_shorts, "_api_call_counts", {"videos.insert": 1})
    monkeypatch.setattr(
        youtube_upload, "_api_call_counts",
        {"videos.insert": 0, "playlistItems.insert": 2, "channels.list": 1},
    )

    text = "\n".join(compile_shorts._combined_quota_summary_lines())
    assert "channels.list" in text
    assert "playlistItems.insert" in text
    assert "videos.insert" in text
