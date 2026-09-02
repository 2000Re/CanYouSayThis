#!/usr/bin/env python3
"""
How-to-Pronounce ネタ動画 自動生成パイプライン(メインCLI)
=================================================

1. Zalgo風「発音不能な単語」をランダム生成          -> word_generator.py
   (--upload時は、upload_history.jsonに既に記録済みの単語と被らないものを
   選ぶ。チャンネルへの重複投稿を避けるため)
2. 音声を作る(5方式から選択):     -> tts_synth.py / glitch_synth.py / morse_synth.py
     --mode tts          : espeak-ng に単語そのものを読ませ、出てきた音を採用
                            (デフォルト。単語の文字列がそのまま音に反映され
                            るので「本当にその単語を読ませている」感が出せる)
     --mode tts_extreme  : espeak-ngの奇妙な声バリエーション+極端なピッチ・
                            速度で読ませ、さらにffmpegでピッチシフト・
                            ビットクラッシュ等をランダムにかけて歪ませる
                            (ttsと同じく単語自体は読ませているが、声質が
                            毎回激しく変わる)
     --mode glitch       : チャープ音・ノイズバースト・ビットクラッシュを
                            合成(単語の音とは無関係な効果音を当てる)
     --mode morse        : 単語の英数字部分を実際の国際モールス符号に変換
                            し、ビープ音で鳴らす(単語の音とは無関係だが、
                            エンコード自体は本物)
     --mode random       : 1本ごとに上記4方式からランダムに選ぶ
                            (--countで複数本まとめて作る際や、自動実行の
                            日々の投稿に単調さが出ないようにする用途)
3. 「答え」を --repeat 回(デフォルト2回)繰り返す      -> audio_utils.py
4. 無音パディングはしない。中身の実際の長さの末尾だけ短くフェードアウトし、
   動画の尺はその音声の長さにそのまま合わせる(固定尺に引き伸ばさない)
5. "How to Pronounce <word>" 形式のミニマルな静止画フレームを生成 -> frame_builder.py
6. 音声+フレームを合成して mp4 を書き出す(尺は音声の長さに追従)  -> video_builder.py
7. --upload 指定時は、書き出したmp4をそのままYouTubeにアップロードする -> youtube_upload.py
   (アップロード成功時は upload_history.json にも記録し、compile_shorts.py が
    10本たまるごとに結合動画を作れるようにする。--mode random で作った回も、
    実際に使われた方式(tts/tts_extreme/glitch/morseのいずれか)が記録される)

--count で複数本生成する場合、1本の失敗(クォータ超過・一時的なネットワーク
エラー等)で残りの本数まで巻き添えで止めることはしない。失敗した回は記録
して次に進み、最後に失敗一覧を表示したうえで異常終了(exit code 1)する。

必要なもの:
    apt-get install -y espeak-ng ffmpeg
    apt-get install -y fonts-noto-core fonts-noto-extra fonts-noto-ui-core fonts-noto-ui-extra
    pip install -r requirements.txt
    playwright install chromium   # 同梱のChromiumが無い環境の場合のみ

    --upload を使う場合はさらに環境変数
    YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN が必要
    (取得方法は get_youtube_refresh_token.py を参照)

使い方:
    python3 generate.py --count 5 --outdir ./out
    python3 generate.py --count 5 --mode glitch --outdir ./out_glitch
    python3 generate.py --count 5 --mode tts_extreme --outdir ./out_extreme
    python3 generate.py --count 5 --mode morse --outdir ./out_morse
    python3 generate.py --count 5 --mode random --outdir ./out_mixed
    python3 generate.py --count 3 --upload --privacy-status unlisted

出力:
    ./out/001_word.txt   (生成した単語そのもの)
    ./out/001.mp3        (音声。modeにより中身が変わる)
    ./out/001.mp4        (完成動画)

詳しい経緯・ハマった罠は README.md を参照。
"""

import argparse
import os
import random
import sys

import config
from audio_utils import finalize_audio, repeat_audio, wav_to_mp3
from frame_builder import build_frame, close_browser
from glitch_synth import synthesize_glitch_chunk
from morse_synth import synthesize_morse_chunk
from tts_synth import synthesize_tts, synthesize_tts_extreme
from video_builder import build_video
from word_generator import random_zalgo_word, readable_label, zalgo_display_word


def _youtube_metadata(word, label, mode):
    """生成した単語からYouTubeアップロード用のtitle/description/tagsを組み立てる。

    label は readable_label() で結合文字を落とし最大12文字に丸め済みの
    ものなので、タイトルの100文字制限には十分収まる。"""
    mode_label = config.MODE_LABELS.get(mode, mode)
    title = f'How to Pronounce "{label}" #Shorts'
    description = (
        "Can you pronounce this? \U0001F440\n\n"
        f"Word: {word}\n"
        f"Mode: {mode_label}\n\n"
        "#Shorts #Pronunciation #Unpronounceable"
    )
    tags = ["shorts", "pronunciation", "unpronounceable", "how to pronounce", mode]
    return title, description, tags


def _resolve_mode(mode):
    """--mode random の場合、tts/glitchのどちらかを1本ごとにランダムに選ぶ。
    それ以外(tts / glitch)はそのまま返す。"""
    if mode == "random":
        return random.choice(list(config.MODE_LABELS))
    return mode


def _random_unique_word(existing_words, max_attempts=20):
    """existing_words に含まれない単語が出るまで生成を試みる。

    組み合わせ数が膨大なので衝突はほぼ起きないが、チャンネルへの重複投稿を
    避けるため念のため再抽選する。max_attempts回試しても衝突する場合は
    (ほぼ起こり得ないが)無限ループを避けるためそのまま返す。"""
    word = random_zalgo_word()
    for _ in range(max_attempts - 1):
        if word not in existing_words:
            break
        word = random_zalgo_word()
    return word


def generate_one(idx, outdir, mode=config.DEFAULT_MODE, voice=config.DEFAULT_VOICE,
                  speed=config.DEFAULT_SPEED, unit_duration=config.DEFAULT_UNIT_DURATION,
                  repeat=config.DEFAULT_REPEAT, repeat_gap=config.DEFAULT_REPEAT_GAP,
                  fade=config.DEFAULT_FADE, upload=False, privacy_status="public"):
    actual_mode = _resolve_mode(mode)

    if upload:
        # チャンネルへの重複投稿を避けるため、アップロード済みの単語と
        # 被らないものを選ぶ(--upload時のみ必要な依存関係の遅延importは
        # このファイル内で完結しているのでここでも問題ない)
        from upload_history import load_upload_history

        existing_words = {entry["word"] for entry in load_upload_history()}
        word = _random_unique_word(existing_words)
    else:
        word = random_zalgo_word()
    label = readable_label(word)
    frame_word = zalgo_display_word(word)

    base = os.path.join(outdir, f"{idx:03d}")
    txt_path = base + "_word.txt"
    raw_wav = base + "_raw.wav"
    rep_wav = base + "_rep.wav"
    fin_wav = base + ".wav"
    mp3_path = base + ".mp3"
    frame_path = base + "_frame.png"
    video_path = base + ".mp4"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(word)

    if actual_mode == "tts":
        # espeak-ngが吐く長さがそのまま採用される(パディングはしない)
        synthesize_tts(word, raw_wav, voice=voice, speed=speed)
    elif actual_mode == "tts_extreme":
        synthesize_tts_extreme(word, raw_wav, voice=voice)
    elif actual_mode == "glitch":
        # unit_durationが「1回分」の長さ。--repeatで指定した回数ぶん、
        # これがそのまま繰り返される(動画の総尺は自動的に決まる)
        synthesize_glitch_chunk(raw_wav, target_seconds=unit_duration)
    elif actual_mode == "morse":
        synthesize_morse_chunk(word, raw_wav)
    else:
        raise ValueError(f"unknown mode: {actual_mode!r} (tts / tts_extreme / glitch / morse)")

    repeat_audio(raw_wav, rep_wav, times=repeat, gap=repeat_gap)
    # 無音パディングはしない。中身の実際の長さのまま、末尾だけ短くフェード
    # し、動画の尺もそれに合わせる(build_videoが -shortest で音声側に合わせる)
    finalize_audio(rep_wav, fin_wav, fade=fade)
    os.remove(raw_wav)
    os.remove(rep_wav)

    wav_to_mp3(fin_wav, mp3_path)
    build_frame(label, frame_path, mode=actual_mode, display_word=frame_word)
    build_video(frame_path, mp3_path, video_path)

    os.remove(fin_wav)
    os.remove(frame_path)

    result = {"word": word, "label": label, "video": video_path, "audio": mp3_path, "mode": actual_mode}

    if upload:
        # --upload時のみ必要な依存関係(google-api-python-client等)なので
        # 遅延importにして、アップロードしない通常利用に影響しないようにする
        from youtube_upload import upload_video

        title, description, tags = _youtube_metadata(word, label, actual_mode)
        youtube_url = upload_video(
            video_path, title=title, description=description, tags=tags,
            privacy_status=privacy_status,
        )
        result["youtube_url"] = youtube_url

        video_id = youtube_url.rsplit("/", 1)[-1]

        # compile_shorts.pyが後で(この回も含めて)GitHub Actions API経由で
        # このrunのアーティファクトから動画本体を取り出せるよう、video_idを
        # そのままファイル名にしておく(アーティファクト自体のアップロードは
        # このgenerate.py実行の後、ワークフロー側で行う)。
        video_id_path = os.path.join(outdir, f"{video_id}.mp4")
        os.replace(video_path, video_id_path)
        result["video"] = video_id_path

        # アップロードが成功して初めて履歴に記録する(失敗した回を記録すると、
        # 存在しない動画IDが compile_shorts.py の結合対象に紛れ込むため)
        from upload_history import append_upload

        append_upload(
            word=word, label=label, video_id=video_id, mode=actual_mode,
            run_id=os.environ.get("GITHUB_RUN_ID"),
        )

    return result


def main():
    ap = argparse.ArgumentParser(description="How-to-Pronounce ネタ動画 自動生成")
    ap.add_argument("--count", type=int, default=3, help="生成する本数")
    ap.add_argument("--outdir", type=str, default="./out", help="出力ディレクトリ")
    ap.add_argument("--mode", type=str, choices=["tts", "tts_extreme", "glitch", "morse", "random"],
                     default=config.DEFAULT_MODE,
                     help="音声の作り方: tts=espeak-ngに単語を読ませる(デフォルト) / "
                          "tts_extreme=奇妙な声+極端なピッチ・速度+ffmpegの歪みフィルタで読ませる / "
                          "glitch=合成グリッチ音を当てる / "
                          "morse=単語をモールス符号のビープ音に変換する / "
                          "random=1本ごとに上記4方式からランダムに選ぶ")
    ap.add_argument("--voice", type=str, default=config.DEFAULT_VOICE,
                     help="[tts/tts_extreme専用] espeak-ngの声(例: en, en-us, ja)")
    ap.add_argument("--speed", type=int, default=config.DEFAULT_SPEED,
                     help="[tts専用。tts_extremeは毎回ランダムな速度を使うため対象外] "
                          "読み上げ速度(words/min)")
    ap.add_argument("--unit-duration", type=float, default=config.DEFAULT_UNIT_DURATION,
                     help="[glitch専用] 「答え」1回分の長さ(秒)")
    ap.add_argument("--repeat", type=int, default=config.DEFAULT_REPEAT,
                     help="「答え」を何回繰り返すか(デフォルト2回。How-to-Pronounce系動画が"
                          "word...word...のように2回言うことが多いのに合わせている)")
    ap.add_argument("--repeat-gap", type=float, default=config.DEFAULT_REPEAT_GAP,
                     help="繰り返し間の無音の長さ(秒)")
    ap.add_argument("--fade", type=float, default=config.DEFAULT_FADE,
                     help="末尾のフェードアウトの長さ(秒)。無音パディングはせず、"
                          "中身の実際の長さに動画尺を合わせる")
    ap.add_argument("--seed", type=int, default=None, help="乱数シード(再現したい場合)")
    ap.add_argument("--upload", action="store_true",
                     help="生成した各動画をそのままYouTubeにアップロードする"
                          "(YOUTUBE_CLIENT_ID/YOUTUBE_CLIENT_SECRET/YOUTUBE_REFRESH_TOKEN"
                          "環境変数が必要。get_youtube_refresh_token.py 参照)")
    ap.add_argument("--privacy-status", type=str, choices=["public", "unlisted", "private"],
                     default="public", help="[--upload専用] アップロード時の公開範囲")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    os.makedirs(args.outdir, exist_ok=True)

    results = []
    failures = []
    try:
        for i in range(1, args.count + 1):
            try:
                r = generate_one(
                    i, args.outdir, mode=args.mode,
                    voice=args.voice, speed=args.speed, unit_duration=args.unit_duration,
                    repeat=args.repeat, repeat_gap=args.repeat_gap, fade=args.fade,
                    upload=args.upload, privacy_status=args.privacy_status,
                )
            except Exception as e:
                # クォータ超過や一時的なネットワークエラーなどで1本失敗しても、
                # 残りの本数の生成/アップロードまで巻き添えで止めない
                print(f"[{i}/{args.count}] failed: {e}")
                failures.append((i, e))
                continue
            print(f"[{i}/{args.count}] ({r['mode']}) {r['video']}  <-  {r['label']}")
            if "youtube_url" in r:
                print(f"    uploaded -> {r['youtube_url']}")
            results.append(r)
    finally:
        close_browser()

    if args.upload and results:
        # 動画ごとにログを出すとN本分埋もれてしまうため、全本処理し終えた
        # このタイミングで1回だけ、実行全体のクォータ消費/残容量をまとめて出す
        from youtube_upload import log_api_usage_summary

        log_api_usage_summary()

    if failures:
        print(f"\n{len(failures)}/{args.count} 本が失敗しました:")
        for i, e in failures:
            print(f"  [{i}] {e}")
        sys.exit(1)

    return results


if __name__ == "__main__":
    main()
