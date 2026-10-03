"""repost_shorts.py の download_video()/ build_repost_metadata()/
select_targets() に対するユニットテスト。requests.getをモックし、実際の
GitHub API呼び出しは行わない(軽いテストのみ)。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import repost_shorts


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
    monkeypatch.setattr(repost_shorts.requests, "get", lambda *a, **k: _mock_response(404))

    entry = {"run_id": "123", "video_id": "abc", "label": "test"}
    with pytest.raises(repost_shorts.ArtifactUnavailableError):
        repost_shorts.download_video(entry, str(tmp_path / "out.mp4"))


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
            "name": repost_shorts.config.REPOST_ARTIFACT_NAME,
            "expired": False,
            "archive_download_url": "https://example.invalid/artifact.zip",
        }]
    })
    zip_resp = _mock_response(410)
    responses = iter([artifacts_resp, zip_resp])
    monkeypatch.setattr(repost_shorts.requests, "get", lambda *a, **k: next(responses))

    entry = {"run_id": "123", "video_id": "abc", "label": "test"}
    with pytest.raises(repost_shorts.ArtifactUnavailableError):
        repost_shorts.download_video(entry, str(tmp_path / "out.mp4"))


def test_download_video_reraises_plain_error_for_server_error(monkeypatch, tmp_path):
    # 一覧取得・ダウンロードいずれも5xx等の一時的エラーはArtifactUnavailable
    # Errorに変換せず、通常のExceptionとして送出しリトライ対象にする。
    monkeypatch.setenv("GITHUB_TOKEN", "dummy")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setattr(repost_shorts.requests, "get", lambda *a, **k: _mock_response(503))

    entry = {"run_id": "123", "video_id": "abc", "label": "test"}
    with pytest.raises(requests.exceptions.HTTPError):
        repost_shorts.download_video(entry, str(tmp_path / "out.mp4"))


def test_download_video_raises_artifact_unavailable_when_run_id_missing(tmp_path):
    entry = {"video_id": "abc", "label": "test"}
    with pytest.raises(repost_shorts.ArtifactUnavailableError):
        repost_shorts.download_video(entry, str(tmp_path / "out.mp4"))


def test_build_repost_metadata_mirrors_short_title_without_shorts_tag():
    entry = {
        "word": "abc123", "label": "abc123", "mode": "glitch",
        "voice_label": None, "lang_code": None,
    }
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")

    assert metadata["title"] == 'How to Pronounce "abc123"?'
    assert "#Shorts" not in metadata["title"]
    assert "#Shorts" not in metadata["description"]
    assert "https://youtu.be/xyz" in metadata["description"]


def test_build_repost_metadata_adds_language_to_title_and_tags():
    entry = {
        "word": "bonjour123", "label": "bonjour123", "mode": "tts",
        "voice_label": "French (Male)", "lang_code": "fr",
    }
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")

    assert 'in French?' in metadata["title"]
    assert "french pronunciation" in metadata["tags"]
    assert "Voice: French (Male)" in metadata["description"]


def test_build_repost_metadata_skips_language_suffix_for_english():
    entry = {"word": "abc", "label": "abc", "mode": "tts", "voice_label": None, "lang_code": "en"}
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")
    assert "in English" not in metadata["title"]


def _entry(video_id, run_id):
    return {"video_id": video_id, "run_id": run_id, "label": video_id}


def test_select_targets_includes_all_own_run_entries_without_cap():
    # 同じ実行(同じGITHUB_RUN_ID)で生成されたShortsは、backlog_countが
    # どれだけ小さくても全件優先して含まれる(「Shortsと通常動画に同じ
    # 単語を」という要望のため、件数に上限を設けない)。
    pending = [
        _entry("old1", "run_a"), _entry("new1", "run_current"),
        _entry("new2", "run_current"), _entry("new3", "run_current"),
        _entry("old2", "run_b"),
    ]
    targets = repost_shorts.select_targets(pending, "run_current", backlog_count=0)
    assert {t["video_id"] for t in targets} == {"new1", "new2", "new3"}


def test_select_targets_fills_remaining_budget_from_oldest_backlog():
    pending = [
        _entry("old1", "run_a"), _entry("old2", "run_b"),
        _entry("new1", "run_current"), _entry("old3", "run_c"),
    ]
    targets = repost_shorts.select_targets(pending, "run_current", backlog_count=2)
    ids = [t["video_id"] for t in targets]
    assert ids == ["new1", "old1", "old2"]


def test_select_targets_uses_only_backlog_when_no_own_run_entries():
    pending = [_entry("old1", "run_a"), _entry("old2", "run_b"), _entry("old3", "run_c")]
    targets = repost_shorts.select_targets(pending, "run_current", backlog_count=2)
    assert [t["video_id"] for t in targets] == ["old1", "old2"]


def test_select_targets_handles_missing_current_run_id():
    # ローカル実行等でGITHUB_RUN_IDが無い場合、全てバックログ扱いになる。
    pending = [_entry("old1", "run_a"), _entry("old2", "run_b")]
    targets = repost_shorts.select_targets(pending, None, backlog_count=1)
    assert [t["video_id"] for t in targets] == ["old1"]
