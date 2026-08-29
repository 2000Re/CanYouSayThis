"""静止画フレーム + 音声 を mp4 に合成する。動画の尺は -shortest により
音声側の実際の長さに追従する(固定尺への引き伸ばしはしない)。"""

import subprocess


def build_video(frame_path, audio_path, video_path):
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", frame_path, "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p", "-shortest",
            "-vf", "fps=15,format=yuv420p",
            video_path,
        ],
        check=True,
        capture_output=True,
    )
