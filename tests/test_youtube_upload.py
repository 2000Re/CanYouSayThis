"""youtube_upload.py の純粋関数(_token_age_warning, _quota_summary_lines)に
対するユニットテスト。Google APIの実呼び出しは行わない。"""

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from youtube_upload import _quota_summary_lines, _token_age_warning


def test_token_age_warning_none_when_unset():
    assert _token_age_warning(None) is None
    assert _token_age_warning("") is None


def test_token_age_warning_none_when_fresh():
    today = datetime.date(2026, 8, 31)
    assert _token_age_warning("2026-08-30", today=today) is None


def test_token_age_warning_fires_near_expiry():
    today = datetime.date(2026, 8, 31)
    # デフォルト warning_after_days=5, expiry_days=7 のとき、5日経過は警告対象
    message = _token_age_warning("2026-08-26", today=today)
    assert message is not None
    assert "再実行" in message


def test_token_age_warning_fires_after_expiry():
    today = datetime.date(2026, 8, 31)
    # 7日以上経過は「おそらく失効済み」の文面になる
    message = _token_age_warning("2026-08-20", today=today)
    assert message is not None
    assert "超えて" in message


def test_token_age_warning_none_on_bad_format():
    assert _token_age_warning("not-a-date") is None


def test_token_age_warning_respects_custom_thresholds():
    today = datetime.date(2026, 8, 31)
    # warning_after_days/expiry_daysを変えても正しく反映される
    assert _token_age_warning("2026-08-30", today=today,
                               warning_after_days=1, expiry_days=3) is not None
    assert _token_age_warning("2026-08-30", today=today,
                               warning_after_days=5, expiry_days=7) is None


def test_quota_summary_lines_reports_consumption_and_remaining():
    counts = {"videos.insert": 3}
    costs = {"videos.insert": 100}
    lines = _quota_summary_lines(counts, costs, daily_quota_units=10000, daily_upload_limit=100)
    text = "\n".join(lines)
    assert "300" in text
    assert "9700" in text
    assert "97" in text


def test_quota_summary_lines_clamps_remaining_at_zero():
    # 消費量が上限を超えても残容量表示はマイナスにならない
    counts = {"videos.insert": 200}
    costs = {"videos.insert": 100}
    lines = _quota_summary_lines(counts, costs, daily_quota_units=10000, daily_upload_limit=100)
    text = "\n".join(lines)
    assert "残り目安: 0本" in text
