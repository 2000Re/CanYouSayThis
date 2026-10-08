"""
音声の後処理ユーティリティ(TTS/グリッチどちらの断片にも使う共通処理)。

- repeat_audio      : 「答え」をN回繰り返す(How-to-Pronounce系動画が
                       "word... word..." のように2回言うことが多いのに
                       寄せた機能)
- finalize_audio    : 無音パディングはせず、中身の実際の長さの末尾だけ短く
                       フェードアウトする(動画の尺は音声の実際の長さに追従する)
- wav_to_mp3        : mp3へのエンコード
- extract_audio_track: 動画ファイルから音声トラックだけを取り出す
                       (repost_shorts.py参照)
- _stretch_to_min_duration: 短すぎる音声をatempoで引き伸ばす(元々
                       tts_synth.synthesize_tts_extreme()専用だったが、
                       generate.pyが全モード共通の最終尺チェックにも使う
                       ため、ここに置いている)
"""

import os
import subprocess


def _probe_duration(wav_path):
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", wav_path],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def _atempo_chain_for_factor(factor):
    """任意の倍率をffmpegの`atempo`フィルタ文字列(カンマ区切りでチェーン
    可能)に変換する。`atempo`は1回あたり0.5〜2.0倍の範囲しか指定できない
    仕様のため、範囲外の倍率はその上限/下限を複数回チェーンして表現する。"""
    parts = []
    remaining = factor
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    parts.append(f"atempo={round(remaining, 3)}")
    return ",".join(parts)


def _stretch_to_min_duration(src_path, dst_path, min_duration, max_passes=3):
    """src_pathの長さがmin_duration未満であれば、atempoで再生速度を落として
    引き伸ばす。1回のatempo適用だけだと(特に0.2秒未満のような極端に短い
    音声で)狙った長さにきっちり収まらないことが実機で確認できたため、
    再生成後の長さを都度測り直して収束するまで(最大max_passes回)繰り返す。
    元々min_duration以上あれば何もせずそのままdst_pathにコピーする。"""
    current = src_path
    for pass_index in range(max_passes):
        duration = _probe_duration(current)
        if duration >= min_duration:
            break
        factor = duration / min_duration
        # ffmpegはinput/outputに同じファイルを指定できないため、パスごとに
        # 別名にする(同名を使い回すと直前の出力を読みながら同時に上書き
        # しようとして壊れる)。
        next_path = f"{dst_path}.stretch_tmp{pass_index}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", current, "-af", _atempo_chain_for_factor(factor), next_path],
            check=True,
            capture_output=True,
        )
        if current != src_path:
            os.remove(current)
        current = next_path
    if current == src_path:
        subprocess.run(["ffmpeg", "-y", "-i", current, dst_path], check=True, capture_output=True)
    else:
        os.replace(current, dst_path)


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


def finalize_audio(src_wav, dst_wav, fade=0.4, fade_in=0.0):
    """無音パディングは行わず、中身の実際の長さそのままで、末尾だけ短く
    フェードアウトする(動画の長さは音声の実際の長さに合わせる)。

    fade_in(秒)を指定すると、冒頭にも短いフェードインをかける。Shorts側の
    自動ループ再生で「末尾の無音→いきなりフルボリュームで単語が始まる」と
    いう段差がループの継ぎ目にでき、そこで視聴者がスワイプしやすいのでは
    という狙いから追加(README「ハマった罠」参照)。デフォルト0.0(フェード
    インなし、従来通りの挙動)で、呼び出し側が明示的に指定した場合のみ
    かかる。"""
    duration = _probe_duration(src_wav)
    fade = min(fade, duration)  # フェード時間が中身より長くならないように
    fade_in = min(fade_in, duration)
    fade_start = max(0.0, duration - fade)
    filters = [f"afade=t=out:st={fade_start}:d={fade}"]
    if fade_in > 0:
        filters.insert(0, f"afade=t=in:st=0:d={fade_in}")
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_wav, "-af", ",".join(filters), dst_wav],
        check=True,
        capture_output=True,
    )


def wav_to_mp3(src_wav, dst_mp3):
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_wav, "-acodec", "libmp3lame", "-q:a", "4", dst_mp3],
        check=True,
        capture_output=True,
    )


def extract_audio_track(video_path, audio_path):
    """動画ファイル(video_path)から音声トラックだけを取り出し、
    audio_pathに書き出す(映像は破棄)。再エンコードせずストリームコピー
    するため高速・無劣化(-acodec copy)。

    repost_shorts.pyが、ダウンロードし直した元Shortsの音声を、新しく
    生成した横型フレーム画像と合成して通常動画を作るために使う
    (video_builder.build_video()参照)。"""
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "copy", audio_path],
        check=True,
        capture_output=True,
    )
