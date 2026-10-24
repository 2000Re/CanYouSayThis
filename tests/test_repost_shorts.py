"""repost_shorts.py の download_video()/ build_repost_metadata()/
select_targets() に対するユニットテスト。requests.getをモックし、実際の
GitHub API呼び出しは行わない(軽いテストのみ)。"""

import random
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import generate
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

    # title_templateが記録されていない(機能追加前の)エントリは、
    # generate.py側と同じ重み付けランダム選択で言い回しを選ぶため
    # (README「ハマった罠」77番)、全テンプレートのいずれかと一致することを
    # 確認する。
    expected_titles = {template("abc123", None) for template in generate._TITLE_TEMPLATES.values()}
    assert metadata["title"] in expected_titles
    assert "#Shorts" not in metadata["title"]
    assert "#Shorts" not in metadata["description"]
    assert "https://youtu.be/xyz" in metadata["description"]
    # comment_textはgenerate._random_comment_text()が複数パターンから
    # ランダムに選ぶため(2026-10-13)、いずれかの出力と一致することを確認する。
    expected_comments = {template("abc123", None) for template in generate._COMMENT_TEMPLATES}
    assert metadata["comment_text"] in expected_comments


def test_build_repost_metadata_adds_language_to_title_and_tags():
    entry = {
        "word": "bonjour123", "label": "bonjour123", "mode": "tts",
        "voice_label": "French (Male)", "lang_code": "fr",
    }
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")

    assert 'in French?' in metadata["title"]
    assert "french pronunciation" in metadata["tags"]
    assert "Voice: French (Male)" in metadata["description"]
    assert "in French" in metadata["comment_text"]


def test_build_repost_metadata_skips_language_suffix_for_english():
    entry = {"word": "abc", "label": "abc", "mode": "tts", "voice_label": None, "lang_code": "en"}
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")
    assert "in English" not in metadata["title"]


def test_build_repost_metadata_without_recorded_title_template_varies_across_calls():
    # title_templateが記録されていない古いエントリ(2026-10-18時点で
    # upload_history.jsonの424件中360件が該当)を再投稿すると、以前は常に
    # "how_to_pronounce"固定だったため、バックログの再投稿分でタイトルの
    # 言い回しがほとんど多様化していなかった(運営者の指摘で発覚、README
    # 「ハマった罠」77番)。generate.py _resolve_title_template("random")を
    # 使うようになったことで複数パターンに分散することを確認する。
    random.seed(0)
    entry = {
        "word": "abc123", "label": "abc123", "mode": "glitch",
        "voice_label": None, "lang_code": None,
    }
    titles = {
        repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")["title"]
        for _ in range(100)
    }
    assert len(titles) > 1


def test_build_repost_metadata_uses_recorded_title_template():
    # Shortsが実際に使った言い回し(title_template)と揃える(ユーザーからの
    # 「通常動画もhow to pronounce以外になるか」という問いへの対応)。
    entry = {
        "word": "abc123", "label": "abc123", "mode": "glitch",
        "voice_label": None, "lang_code": None, "title_template": "can_you_say",
    }
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")
    assert metadata["title"] == 'Can You Say "abc123"'


def test_build_repost_metadata_uses_recorded_title_template_with_language():
    entry = {
        "word": "bonjour123", "label": "bonjour123", "mode": "tts",
        "voice_label": "French (Male)", "lang_code": "fr", "title_template": "try_to_say",
    }
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")
    assert metadata["title"] == 'Try to Say "bonjour123" in French'


def test_build_repost_metadata_appends_genre_suffix_for_nightcore():
    # Shorts側(generate.py _mode_genre_suffix())と同じく、実際にYouTube上
    # で検索されるジャンル名を持つモードはタイトル末尾に付ける。
    entry = {
        "word": "abc123", "label": "abc123", "mode": "nightcore",
        "voice_label": None, "lang_code": None, "title_template": "how_to_pronounce",
    }
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")
    assert metadata["title"] == 'How to Pronounce "abc123" (Nightcore)'


def test_build_repost_metadata_omits_genre_suffix_for_non_genre_mode():
    entry = {
        "word": "abc123", "label": "abc123", "mode": "glitch",
        "voice_label": None, "lang_code": None, "title_template": "how_to_pronounce",
    }
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")
    assert "(" not in metadata["title"]


def test_build_repost_metadata_comment_omits_request_length_notice():
    # generate.py _youtube_metadata()(通常のShorts投稿)は以前、80文字上限の
    # 案内を必ずcomment_textに付けていたが、リクエストが処理しきれないほど
    # 増えたため2026-10-24に削除した(README「ハマった罠」103番)。
    # repost_shorts.py側も同じ案内を付けていたので、こちらも再度紛れ込んで
    # いないことの回帰防止(pictograph系のコメントテンプレートも対象)。
    entry = {
        "word": "abc123", "label": "abc123", "mode": "glitch",
        "voice_label": None, "lang_code": None,
    }
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")
    assert "80 characters" not in metadata["comment_text"]

    pictograph_word = generate.config.CUNEIFORM_CHARS[0] + generate.config.CUNEIFORM_CHARS[1]
    pictograph_entry = {
        "word": pictograph_word, "label": pictograph_word, "mode": "glitch",
        "voice_label": None, "lang_code": None,
    }
    pictograph_metadata = repost_shorts.build_repost_metadata(pictograph_entry, "https://youtu.be/xyz")
    assert "80 characters" not in pictograph_metadata["comment_text"]


def test_build_repost_metadata_sanitizes_symbol_characters_from_label():
    # generate.py _youtube_metadata()と同じく、タイトル・コメントに使う
    # labelから_BLOCKED_SYMBOLS(はさみ等)だけを取り除く(README「ハマった
    # 罠」79・92番)。音楽記号(So、ブロック対象外)は原則通り残る。
    # entry["label"]自体(サムネイル表示用に別途使われる)は変更しないことも
    # 確認する。
    label = "\U0001D1DA✂iv"  # 音楽記号+はさみ記号+通常の文字
    entry = {
        "word": label, "label": label, "mode": "glitch",
        "voice_label": None, "lang_code": None,
    }
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")
    assert "✂" not in metadata["title"]
    assert "\U0001D1DA" in metadata["title"]
    assert "iv" in metadata["title"]
    assert entry["label"] == label  # entry自体は変更しない(サムネイル用)


def test_build_repost_metadata_strips_angle_brackets_from_description_word():
    # generate.py _youtube_metadata()と同じく、説明欄の「Word: {word}」行
    # (生のwordをそのまま埋め込む)から山括弧<>だけを取り除く。YouTube
    # Data API自体がHTMLタグと誤認し"invalidDescription"でアップロードを
    # 拒否することが実機で確認されたため(README「ハマった罠」95番)。
    word = "-%@><_><@%-"
    entry = {
        "word": word, "label": word, "mode": "glitch",
        "voice_label": None, "lang_code": None,
    }
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")
    assert "<" not in metadata["description"]
    assert ">" not in metadata["description"]
    assert "Word: -%@_@%-" in metadata["description"]


def test_build_repost_metadata_omits_word_for_pictograph_entry():
    # 楔形文字等(generate._is_pictograph_word()参照)はYouTube自身のフォントが
    # 対応しておらずタイトル等に生で埋め込むと「豆腐」になるため(2026-10-14に
    # 実機で確認)、通常動画への変換時も単語そのものを埋め込まない。
    word = generate.config.CUNEIFORM_CHARS[0] + generate.config.CUNEIFORM_CHARS[1]
    entry = {
        "word": word, "label": word, "mode": "glitch",
        "voice_label": None, "lang_code": None, "title_template": "how_to_pronounce",
    }
    metadata = repost_shorts.build_repost_metadata(entry, "https://youtu.be/xyz")
    assert word not in metadata["title"]
    assert metadata["title"].startswith(generate._PICTOGRAPH_TITLE)
    assert word not in metadata["description"]
    assert word not in metadata["comment_text"]


def _entry(video_id, run_id, uploaded_at=None):
    return {"video_id": video_id, "run_id": run_id, "label": video_id, "uploaded_at": uploaded_at}


def test_select_targets_returns_oldest_entries_up_to_backlog_count():
    # Shorts投稿当日中の変換をやめた(README「ハマった罠」98番)ため、
    # select_targets()自体はpendingの記録順(=古い順)のまま先頭から
    # backlog_count件を返すだけのシンプルな関数になった。
    pending = [_entry("old1", "run_a"), _entry("old2", "run_b"), _entry("old3", "run_c")]
    targets = repost_shorts.select_targets(pending, backlog_count=2)
    assert [t["video_id"] for t in targets] == ["old1", "old2"]


def test_select_targets_returns_empty_when_backlog_count_is_zero():
    pending = [_entry("old1", "run_a")]
    assert repost_shorts.select_targets(pending, backlog_count=0) == []


def test_uploaded_today_true_for_same_pacific_date():
    # today(_quota_reset_date_today()と同じPacific Time基準)と同じ日に
    # アップロードされたエントリはTrueになる。
    entry = _entry("v1", "run_a", uploaded_at="2026-10-21T10:00:00+00:00")
    # 2026-10-21T10:00:00+00:00 はPacific Time(UTC-7、夏時間)で同日10/21
    assert repost_shorts._uploaded_today(entry, "2026-10-21") is True


def test_uploaded_today_false_for_different_pacific_date():
    entry = _entry("v1", "run_a", uploaded_at="2026-10-19T10:00:00+00:00")
    assert repost_shorts._uploaded_today(entry, "2026-10-21") is False


def test_uploaded_today_false_when_uploaded_at_missing():
    # uploaded_atが記録されていない旧いエントリは除外しない(Falseを返す)。
    entry = _entry("v1", "run_a", uploaded_at=None)
    assert repost_shorts._uploaded_today(entry, "2026-10-21") is False
