import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jst_time import jst_timestamp


def test_jst_timestamp_format_is_24_hour_with_date():
    assert re.fullmatch(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]", jst_timestamp())


def test_jst_timestamp_matches_current_jst_time():
    before = datetime.now(ZoneInfo("Asia/Tokyo"))
    result = jst_timestamp()
    after = datetime.now(ZoneInfo("Asia/Tokyo"))
    assert before.strftime("[%Y-%m-%d %H:%M:%S]") <= result <= after.strftime("[%Y-%m-%d %H:%M:%S]")
