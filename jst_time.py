"""ログ出力用、日本時間(JST)のタイムスタンプ文字列を生成する共通ユーティリティ。

GitHub Actions上のログはUTC(または閲覧者のブラウザのタイムゾーン)で
表示され、何が何時(日本時間)に起きたかがログの文字列自体からは分からない。
generate.py(動画生成・YouTubeへのアップロード)/repost_shorts.py(通常動画
への変換)の主要な完了ログの先頭にjst_timestamp()の出力を付けることで、
ログを後から読んだときに日本時間がひと目で分かるようにする。
"""
from datetime import datetime
from zoneinfo import ZoneInfo

_JST = ZoneInfo("Asia/Tokyo")


def jst_timestamp() -> str:
    """"[HH:MM:SS]"形式(24時間表記、日本時間)のタイムスタンプ文字列を返す。"""
    return datetime.now(_JST).strftime("[%H:%M:%S]")
