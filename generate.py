#!/usr/bin/env python3
"""
How-to-Pronounce ネタ動画 自動生成パイプライン(メインCLI)
=================================================

1. Zalgo風「発音不能な単語」をランダム生成          -> word_generator.py
   (--upload時は、upload_history.jsonに既に記録済みの単語と被らないものを
   選ぶ。チャンネルへの重複投稿を避けるため)
2. 音声を作る(4方式から選択):     -> tts_synth.py / glitch_synth.py
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
     --mode random       : 1本ごとに上記3方式からランダムに選ぶ
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
    実際に使われた方式(tts/tts_extreme/glitchのいずれか)が記録される)

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
from tts_synth import synthesize_tts, synthesize_tts_extreme
from video_builder import build_video
from word_generator import (
    random_abugida_word,
    random_script_word,
    random_zalgo_word,
    readable_label,
    zalgo_display_word,
)


def _youtube_metadata(word, label, mode, playlist_id=None, voice_label=None, is_native_script=False,
                       lang_code=None):
    """生成した単語からYouTubeアップロード用のtitle/description/tagsを組み立てる。

    label は readable_label() で結合文字を落とし最大12文字に丸め済みの
    ものなので、タイトルの100文字制限には十分収まる。

    playlist_id を渡すと、説明文にShorts用再生リストへのリンクを追加し、
    視聴者が他の動画も連続して見る(回遊する)よう誘導する。

    説明文には playlist_id の有無に関わらず、常に登録を促すCTA(Call To
    Action)の一文を入れる。アナリティクスで新規視聴者がほとんど(97%超)
    でコア視聴者が0.1%未満という偏りが見えたため、1本だけ見て離脱する
    視聴者にも登録を明示的に呼びかける狙い。

    voice_label を渡すと(--voice random で言語/性別が抽選された場合のみ)、
    説明文にどの言語のボイスを使ったかを明記する。

    is_native_script=Trueの場合(アラビア文字・キリル文字等、実在の文字体系
    で単語を生成した回)、実在するその言語の単語ではなくランダムな造語である
    旨を説明文に明記する。Zalgo単語(ラテン文字+結合文字)は見た目からして
    実在の単語でないことが明らかなので対象外。

    説明文には「tongue twister」「language learners」という、上記のタイト
    ル・タグの言語名追加とは違う切り口の検索キーワードを含む一文も常に
    入れる(自然な文として、他の施策と競合しない形で追加する検索流入策)。
    タグにも"tongue twister"を追加する。

    説明文には、config.AUDIENCE_REGION_PHRASESで設定した非英語圏向けの
    検索キーワードフレーズ(視聴者属性で継続的に上位に入っているフィリピン・
    インドネシア・マレーシア向け)も、動画のボイス言語とは無関係に常に含める。

    戻り値のcaption_text(YouTubeの手動字幕用)は、意味不明な音声を自動
    文字起こし(ASR)に任せると検索インデックス対象のテキスト枠が無駄になる
    ため、説明文と同じ趣旨のキーワード付き固定テキストとして別途組み立てる
    (youtube_upload.upload_caption()参照)。

    戻り値のlocalizations(config.JAPANESE_TITLE_LOCALIZATION_ENABLEDが
    Trueの場合のみ、それ以外はNone)は、YouTube側の視聴環境が日本語の視聴者
    にだけ表示される日本語タイトルを含む(youtube_upload.upload_video()の
    localizations引数、config.LANGUAGE_LABELS_JA参照)。

    lang_code を渡すと(config.VOICE_LANGUAGESのキー、例: "ar")、
      - タイトルに言語名を追加する(例: `in French?`)。「french
        pronunciation」のような、言語名込みの検索クエリにタイトルレベルで
        マッチしやすくする狙い。英語(lang_code="en")はこのチャンネルの
        既定言語という扱いのため追加しない。
      - タグにも `<言語名> pronunciation`(小文字)を追加する。英語話者が
        言語名で検索した際に見つけてもらいやすくする狙い(下記の現地語
        ハッシュタグと違い、こちらは英語で検索する側を想定)。
      - その言語で「発音」を意味するハッシュタグ(config.VOICE_LANGUAGESの
        "hashtag_word")を英語ハッシュタグに追加する。英語圏の視聴者向けの
        #Pronunciation等と違い、その言語の話者が母語のまま検索した際に
        見つけてもらいやすくするための施策。該当する語が用意されていない
        言語(英語自身、チェロキー語)では何も追加しない。"""
    lang_entry = config.VOICE_LANGUAGES.get(lang_code)
    # 英語はこのチャンネルの既定言語なので、タイトル・タグへの言語名追加は
    # 対象外にする("in English?"は冗長なため)。
    lang_label = lang_entry["label"] if lang_entry and lang_code != "en" else None

    mode_label = config.MODE_LABELS.get(mode, mode)
    title = f'How to Pronounce "{label}"'
    if lang_label:
        title += f" in {lang_label}?"
    title += " #Shorts"
    description = (
        "Can you pronounce this? \U0001F440\n\n"
        f"Word: {word}\n"
        f"Mode: {mode_label}\n"
    )
    if voice_label:
        description += f"Voice: {voice_label}\n"
    if is_native_script:
        description += (
            "(This is a randomly generated sequence of letters, not a real word "
            "in that language!)\n"
        )
    description += (
        "\nTry saying it out loud and comment your attempt! \U0001F5E3️\n\n"
        "The ultimate tongue twister for language learners, TTS fans, and "
        "anyone up for a pronunciation challenge!\n\n"
    )
    if config.AUDIENCE_REGION_PHRASES:
        phrases = " · ".join(f"{phrase} ({lang})" for lang, phrase in config.AUDIENCE_REGION_PHRASES)
        description += f"(How do you say it? {phrases})\n\n"
    if playlist_id:
        description += (
            f"▶ Watch more pronunciation challenges: "
            f"https://www.youtube.com/playlist?list={playlist_id}\n\n"
        )
    description += "\U0001F514 Subscribe for a new unpronounceable word every day!\n\n"
    native_hashtag_word = lang_entry.get("hashtag_word") if lang_entry else None
    description += "#Shorts #Pronunciation #Unpronounceable #Zalgo #GlitchText #TextToSpeech #TTS #Challenge"
    if native_hashtag_word:
        description += f" #{native_hashtag_word}"
    tags = [
        "shorts", "pronunciation", "unpronounceable", "how to pronounce", mode,
        "zalgo", "glitch text", "text to speech", "pronunciation challenge",
        "tongue twister",
    ]
    if lang_label:
        tags.append(f"{lang_label.lower()} pronunciation")
    if native_hashtag_word:
        tags.append(native_hashtag_word)

    caption_text = f'How to pronounce "{label}"'
    if lang_label:
        caption_text += f" in {lang_label}"
    caption_text += ". A tongue twister and pronunciation challenge — try saying it out loud!"

    # タイトルの日本語ローカライズ(videos.insertのlocalizationsフィールド)。
    # YouTube側の視聴環境が日本語の視聴者には、通常のtitle/descriptionの
    # 代わりにこちらが表示される(動画本体・音声・description自体は変えない。
    # 「海外向け」という動画コンテンツ自体の方針とは別軸で、あくまで表示
    # 言語をYouTube側の視聴者設定に合わせるだけの施策)。
    localizations = None
    if config.JAPANESE_TITLE_LOCALIZATION_ENABLED:
        lang_label_ja = config.LANGUAGE_LABELS_JA.get(lang_code)
        # labelがヘブライ語・アラビア語のようなRTL文字体系の場合、「」の直後に
        # 来る最初の「強い方向性を持つ文字」がlabel自身になり、Unicode双方向
        # アルゴリズム(UAX #9)によりタイトル全体の基準方向がRTLと判定されて
        # しまう(実際にYouTube上で「#Shortsの発音は?(ヘブライ語)「...」」の
        # ように語順が丸ごと入れ替わって表示される不具合として発覚)。
        # First Strong Isolate(U+2068)〜Pop Directional Isolate(U+2069)で
        # labelを囲み、周囲の日本語テキストの基準方向にlabelの向きが影響しない
        # よう分離する(labelがLTRの場合も無害なので、言語ごとに分岐しない)。
        title_ja = f"「⁨{label}⁩」の発音は?"
        if lang_label_ja:
            title_ja += f"({lang_label_ja})"
        title_ja += " #Shorts"
        localizations = {"ja": {"title": title_ja, "description": description}}

    return title, description, tags, caption_text, localizations


def _resolve_mode(mode):
    """--mode random の場合、config.MODE_WEIGHTSの重みに従って1本ごとに
    ランダムに選ぶ(重み未設定のモードは他と同じ重み1として扱う)。
    それ以外(tts / glitch / tts_extreme)はそのまま返す。"""
    if mode == "random":
        modes = list(config.MODE_LABELS)
        weights = [config.MODE_WEIGHTS.get(m, 1) for m in modes]
        return random.choices(modes, weights=weights)[0]
    return mode


def _resolve_voice(voice):
    """--voice random の場合、config.VOICE_LANGUAGESから言語と性別を
    ランダムに選び、(実際のespeak-ngボイスコード, 表示用ラベル, 性別)を
    返す。femaleが設定されていない言語はmaleのみが選ばれる。

    それ以外(具体的なボイスコード)は動画説明文への言語ラベルは追加しない
    (label=None)が、config.VOICE_LANGUAGESのfemaleボイスコードと一致する
    場合は性別だけ"female"として返す。--voice randomを経由しなくても
    女性ボイスを直接指定した場合にピッチ補正(config.FEMALE_VOICE_PITCH)が
    かかるようにするため。"""
    if voice != "random":
        known_female_codes = {
            entry["female"] for entry in config.VOICE_LANGUAGES.values() if entry["female"]
        }
        gender = "female" if voice in known_female_codes else None
        return voice, None, gender
    # 実在文字体系の言語(script指定あり)がラテン文字(Zalgo)系の言語より
    # 多くなったため、まず「実在文字体系」か「ラテン文字」かを
    # config.NATIVE_SCRIPT_VOICE_CHANCEの確率で決めてから、その中で言語を
    # 均等抽選する(config.VOICE_LANGUAGES参照)。
    native_script_codes = [c for c, e in config.VOICE_LANGUAGES.items() if e["script"] is not None]
    latin_codes = [c for c, e in config.VOICE_LANGUAGES.items() if e["script"] is None]
    pool = native_script_codes if random.random() < config.NATIVE_SCRIPT_VOICE_CHANCE else latin_codes
    lang_code = random.choice(pool)
    entry = config.VOICE_LANGUAGES[lang_code]
    genders = ["male"] + (["female"] if entry["female"] else [])
    gender = random.choice(genders)
    label = f"{entry['label']} ({gender.capitalize()})"
    return entry[gender], label, gender


def _native_script_for_voice(voice_code):
    """voice_codeがconfig.VOICE_LANGUAGESの中で「実在の文字体系を使う言語」
    (script指定あり)に該当する場合、その単語生成関数を返す。該当しなければ
    None(呼び出し側は従来通りrandom_zalgo_word()を使う)。

    --voice random経由でも、"ru"等の対応言語コードを直接指定した場合でも
    同じ単語生成に切り替わる(_resolve_voice()の女性ボイス判定と同じ考え方)。"""
    for entry in config.VOICE_LANGUAGES.values():
        if voice_code not in (entry["male"], entry["female"]):
            continue
        if entry["script"] == "cluster":
            return lambda: random_script_word(entry["chars"])
        if entry["script"] == "abugida":
            return lambda: random_abugida_word(entry["consonants"], entry["vowels"])
    return None


def _lang_code_for_voice(voice_code):
    """voice_codeがconfig.VOICE_LANGUAGESの中のどの言語のmale/femaleボイス
    コードと一致するか調べ、一致する言語コード(config.VOICE_LANGUAGESの
    キー。例: "ar")を返す。該当しなければNone。

    _native_script_for_voice()・_voice_pitch_for()と同じく、--voice random
    経由でも直接コードを指定した場合でも同じ判定になる。"""
    for lang_code, entry in config.VOICE_LANGUAGES.items():
        if voice_code in (entry["male"], entry["female"]):
            return lang_code
    return None


def _voice_pitch_for(voice_code, gender):
    """espeak-ngへ渡すピッチ(-p)補正値を決める。

    config.FEMALE_VOICE_PITCHはMBROLA由来の女性ボイス("mb-"で始まる
    voice_code)専用の補正。"+f3"フォルマントバリアント由来の女性ボイス
    (config.VOICE_LANGUAGESの他言語)はそれ単体で既に十分な高さになって
    おり、実機で重ねて適用すると高くなりすぎることを確認済みのため対象外
    (config.py VOICE_LANGUAGESのコメント参照)。"""
    if gender == "female" and voice_code.startswith("mb-"):
        return config.FEMALE_VOICE_PITCH
    return None


def _random_unique_word(existing_words, word_generator=random_zalgo_word, max_attempts=20):
    """existing_words に含まれない単語が出るまで生成を試みる。

    組み合わせ数が膨大なので衝突はほぼ起きないが、チャンネルへの重複投稿を
    避けるため念のため再抽選する。max_attempts回試しても衝突する場合は
    (ほぼ起こり得ないが)無限ループを避けるためそのまま返す。"""
    word = word_generator()
    for _ in range(max_attempts - 1):
        if word not in existing_words:
            break
        word = word_generator()
    return word


def generate_one(idx, outdir, mode=config.DEFAULT_MODE, voice=config.DEFAULT_VOICE,
                  speed=config.DEFAULT_SPEED, unit_duration=config.DEFAULT_UNIT_DURATION,
                  repeat=config.DEFAULT_REPEAT, repeat_gap=config.DEFAULT_REPEAT_GAP,
                  fade=config.DEFAULT_FADE, upload=False, privacy_status="public"):
    actual_mode = _resolve_mode(mode)
    actual_voice, voice_label, voice_gender = _resolve_voice(voice)
    voice_pitch = _voice_pitch_for(actual_voice, voice_gender)
    word_generator = _native_script_for_voice(actual_voice) or random_zalgo_word
    used_native_script = word_generator is not random_zalgo_word

    if upload:
        # チャンネルへの重複投稿を避けるため、アップロード済みの単語と
        # 被らないものを選ぶ(--upload時のみ必要な依存関係の遅延importは
        # このファイル内で完結しているのでここでも問題ない)
        from upload_history import load_upload_history

        existing_words = {entry["word"] for entry in load_upload_history()}
        word = _random_unique_word(existing_words, word_generator=word_generator)
    else:
        word = word_generator()
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
        synthesize_tts(word, raw_wav, voice=actual_voice, speed=speed, pitch=voice_pitch)
    elif actual_mode == "tts_extreme":
        synthesize_tts_extreme(word, raw_wav, voice=actual_voice)
    elif actual_mode == "glitch":
        # unit_durationが「1回分」の長さ。--repeatで指定した回数ぶん、
        # これがそのまま繰り返される(動画の総尺は自動的に決まる)
        synthesize_glitch_chunk(raw_wav, target_seconds=unit_duration)
    else:
        raise ValueError(f"unknown mode: {actual_mode!r} (tts / tts_extreme / glitch)")

    repeat_audio(raw_wav, rep_wav, times=repeat, gap=repeat_gap)
    # 無音パディングはしない。中身の実際の長さのまま、末尾だけ短くフェード
    # し、動画の尺もそれに合わせる(build_videoが -shortest で音声側に合わせる)
    finalize_audio(rep_wav, fin_wav, fade=fade)
    os.remove(raw_wav)
    os.remove(rep_wav)

    wav_to_mp3(fin_wav, mp3_path)
    build_frame(label, frame_path, mode=actual_mode, display_word=frame_word,
                is_native_script=used_native_script)
    build_video(frame_path, mp3_path, video_path)

    os.remove(fin_wav)
    os.remove(frame_path)

    result = {
        "word": word, "label": label, "video": video_path, "audio": mp3_path,
        "mode": actual_mode, "voice": actual_voice, "voice_label": voice_label,
    }

    if upload:
        # --upload時のみ必要な依存関係(google-api-python-client等)なので
        # 遅延importにして、アップロードしない通常利用に影響しないようにする
        from youtube_upload import upload_video

        # 任意。設定されていれば、説明文に「もっと見る」用の再生リストリンクを
        # 載せて視聴者の回遊(連続視聴)を促す。実際に動画を再生リストへ追加
        # する処理はアップロード成功後(video_id確定後)に別途行う。
        shorts_playlist_id = os.environ.get("YOUTUBE_SHORTS_PLAYLIST_ID")
        lang_code = _lang_code_for_voice(actual_voice)

        title, description, tags, caption_text, localizations = _youtube_metadata(
            word, label, actual_mode, playlist_id=shorts_playlist_id, voice_label=voice_label,
            is_native_script=used_native_script, lang_code=lang_code,
        )
        # glitchモードは単語を読み上げない合成音のみで、対応する音声言語が
        # 無いためdefault_audio_languageは設定しない(YouTube側の自動判定に
        # 任せる)。tts/tts_extremeのみ、実際に読み上げた言語をメタデータに
        # 反映する(タイトル・タグへの言語名追加とは別軸のSEO施策、README参照)。
        default_audio_language = lang_code if actual_mode in ("tts", "tts_extreme") else None
        youtube_url = upload_video(
            video_path, title=title, description=description, tags=tags,
            privacy_status=privacy_status, default_audio_language=default_audio_language,
            localizations=localizations,
        )
        result["youtube_url"] = youtube_url

        video_id = youtube_url.rsplit("/", 1)[-1]

        # 手動字幕(ASRに任せるとでたらめな音声が意味不明な文字起こしになり、
        # 検索インデックス対象のテキストが無駄になるため、代わりにキーワード
        # 付きの固定テキストを入れる)。captions.insertはyoutube.force-ssl
        # スコープが必要(README参照)で無い場合は失敗するが、動画自体は既に
        # 公開済みなので警告に留めて処理は止めない(add_to_playlistと同じ方針)。
        #
        # config.CAPTIONS_ENABLEDがFalseの間はスキップする(実機で断続的な
        # 403 forbiddenを確認したため一時無効化中。README「ハマった罠」参照)。
        if config.CAPTIONS_ENABLED:
            from audio_utils import _probe_duration
            from youtube_upload import upload_caption

            try:
                duration_seconds = _probe_duration(video_path)
                upload_caption(video_id, duration_seconds, caption_text)
            except Exception as e:
                print(f"[Warning] {word}: 字幕のアップロードに失敗しました: {e}")

        # 運営者コメントの自動投稿(caption_textをそのまま流用。字幕用に
        # 組み立てたキーワード付きテキストがコメントとしてもそのまま使える
        # ため)。captions.insertと同じyoutube.force-sslスコープを使うため、
        # 同様に断続的な403 forbiddenが起きうる(README「ハマった罠」21番)。
        # 失敗しても動画自体は既に公開済みなので警告に留めて処理は止めない。
        if config.COMMENT_ON_UPLOAD_ENABLED:
            from youtube_upload import post_comment

            try:
                post_comment(video_id, caption_text)
            except Exception as e:
                print(f"[Warning] {word}: コメントの投稿に失敗しました: {e}")

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

        # 任意。設定されていれば、アップロードした動画をShorts用の再生リストに
        # 追加する(失敗しても動画自体は既に公開済みなので、警告に留めて
        # 処理は止めない)。shorts_playlist_id自体は説明文へのリンク生成のため
        # 上のtitle/description組み立て時に既に読み込み済み。
        if shorts_playlist_id:
            from youtube_upload import add_to_playlist

            try:
                add_to_playlist(video_id, shorts_playlist_id)
            except Exception as e:
                print(f"[Warning] {word}: 再生リストへの追加に失敗しました: {e}")

    return result


def main():
    ap = argparse.ArgumentParser(description="How-to-Pronounce ネタ動画 自動生成")
    ap.add_argument("--count", type=int, default=3, help="生成する本数")
    ap.add_argument("--outdir", type=str, default="./out", help="出力ディレクトリ")
    ap.add_argument("--mode", type=str, choices=["tts", "tts_extreme", "glitch", "random"],
                     default=config.DEFAULT_MODE,
                     help="音声の作り方: tts=espeak-ngに単語を読ませる(デフォルト) / "
                          "tts_extreme=奇妙な声+極端なピッチ・速度+ffmpegの歪みフィルタで読ませる / "
                          "glitch=合成グリッチ音を当てる / "
                          "random=1本ごとに上記3方式からランダムに選ぶ")
    ap.add_argument("--voice", type=str, default=config.DEFAULT_VOICE,
                     help="[tts/tts_extreme専用] espeak-ngの声(例: en, en-us, ja)。"
                          "random=1本ごとにconfig.VOICE_LANGUAGESから言語・性別を"
                          "ランダムに選ぶ(発音の違いで聞こえ方が変わる)")
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
            voice_suffix = f" [{r['voice_label']}]" if r["voice_label"] else ""
            print(f"[{i}/{args.count}] ({r['mode']}){voice_suffix} {r['video']}  <-  {r['label']}")
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
