"""
音声の後処理ユーティリティ(TTS/グリッチどちらの断片にも使う共通処理)。

- repeat_audio  : 「答え」をN回繰り返す(How-to-Pronounce系動画が
                   "word... word..." のように2回言うことが多いのに寄せた機能)
- finalize_audio: 無音パディングはせず、中身の実際の長さの末尾だけ短く
                   フェードアウトする(動画の尺は音声の実際の長さに追従する)
- wav_to_mp3    : mp3へのエンコード
"""

import subprocess


def _probe_duration(wav_path):
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", wav_path],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def repeat_audio(src_wav, dst_wav, times=2, gap=0.4, sr=44100):
    """src_wav を短い無音(gap秒)を挟んで times 回繰り返す"""
    if times <= 1:
        subprocess.run(["ffmpeg", "-y", "-i", src_wav, dst_wav], check=True, capture_output=True)
        return

    n_gaps = times - 1
    cmd = ["ffmpeg", "-y", "-i", src_wav]
    for _ in range(n_gaps):
        cmd += ["-f", "lavfi", "-i", f"anullsrc=r={sr}:cl=mono:d={gap}"]

    split_labels = "".join(f"[s{i}]" for i in range(times))
    filter_parts = [
        f"[0:a]aformat=sample_rates={sr}:channel_layouts=mono,asplit={times}{split_labels}"
    ]
    concat_labels = []
    for i in range(times):
        concat_labels.append(f"[s{i}]")
        if i < n_gaps:
            gap_input_idx = i + 1  # 0番はsrc_wav、1..n_gapsが無音入力
            filter_parts.append(
                f"[{gap_input_idx}:a]aformat=sample_rates={sr}:channel_layouts=mono[g{i}]"
            )
            concat_labels.append(f"[g{i}]")

    filter_parts.append("".join(concat_labels) + f"concat=n={len(concat_labels)}:v=0:a=1[out]")
    filter_complex = ";".join(filter_parts)

    cmd += ["-filter_complex", filter_complex, "-map", "[out]", dst_wav]
    subprocess.run(cmd, check=True, capture_output=True)


def finalize_audio(src_wav, dst_wav, fade=0.4):
    """無音パディングは行わず、中身の実際の長さそのままで、末尾だけ短く
    フェードアウトする(動画の長さは音声の実際の長さに合わせる)。"""
    duration = _probe_duration(src_wav)
    fade = min(fade, duration)  # フェード時間が中身より長くならないように
    fade_start = max(0.0, duration - fade)
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_wav, "-af", f"afade=t=out:st={fade_start}:d={fade}", dst_wav],
        check=True,
        capture_output=True,
    )


def wav_to_mp3(src_wav, dst_mp3):
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_wav, "-acodec", "libmp3lame", "-q:a", "4", dst_mp3],
        check=True,
        capture_output=True,
    )
