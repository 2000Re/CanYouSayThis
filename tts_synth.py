"""TTS (espeak-ng) で単語をそのまま読ませる方式 [--mode tts / デフォルト]
および、それを別々の角度で加工する9方式:
  - 奇妙な声質・極端なピッチ+ffmpegの歪みフィルタで壊す [--mode tts_extreme]
  - そのまま逆再生する [--mode reverse]
  - 搬送波とのリング変調でロボット風の声にする [--mode robot_voice]
  - 複数言語のボイスで同時に読み上げて重ねる [--mode chorus]
  - 電話越しのような帯域制限をかける [--mode telephone]
  - ゆっくり再生+残響の「slowed + reverb」風にする [--mode slowed_reverb]
  - 高速化+ピッチアップの「nightcore」風にする [--mode nightcore]
  - ローパス+揺らぎで水中のような質感にする [--mode underwater]
  - ステレオ化して左右に音像を回転させる「8D audio」風にする [--mode 8d_audio]
  - 複数タップのエコーで洞窟のような反響を作る [--mode echo_cave]
いずれも単語自体はespeak-ngに読ませており(chorusのみ複数ボイス)、
単語の内容とは無関係な合成音を当てるglitch_synth.py/morse_synth.pyとは
性質が異なる。"""

import os
import random
import subprocess

import config
from audio_utils import _probe_duration, _stretch_to_min_duration

# espeak-ng標準搭載の「奇妙な声」バリエーション(espeak-ng-data/voices/!v)。
# 実際にespeak-ngへ通してエラーなく合成できることを確認済みのもののみ採用。
EXTREME_VOICE_VARIANTS = [
    "Demonic", "Tweaky", "UniRobot", "AnxiousAndy", "croak", "whisper",
    "klatt", "klatt2", "robosoft", "robosoft3", "robosoft6",
]

# 特定の文字体系を「対応するボイス以外に読ませると、文字を発音せず
# 'Xxx letter'のように文字種名を読み上げてしまう」罠が実機で確認された
# 文字体系の一覧(README「ハマった罠」72・73番)。(Unicodeコードポイント
# 範囲のリスト, その文字体系を正しく発音できるボイスコードの先頭一致
# タプル) のペア。範囲は各言語のcharsプール(config.py)だけでなく、同じ
# ブロック内の記号・アクセント記号も含めて実機確認した
# (例: アラビア語の母音記号も英語ボイスでは"Arabic X"と読み上げられる)。
#
# 中国語の漢字(CJK統合漢字、基本U+4E00-U+9FFF + 拡張AのU+3400-U+4DBF)は
# 中国語・日本語の漢字が共有するブロック(--wordリクエストで日本語の文字列
# を手動指定された場合も対象)。中国語系ボイスは"zh"ではなく内部コード
# "cmn"を使っている(VOICE_LANGUAGES参照)。
#
# ウイグル語(ug)はアラビア文字のUnicodeブロックをそのまま使っている
# (UYGHUR_LETTERSはARABIC_LETTERSの文字を20個流用)ため、アラビア語の
# ブロックと同じ範囲・同じボイス扱いにしている。
#
# キリル文字(ロシア語)・ギリシャ文字は、73番の時点では「Chinese letter」
# のような文字種名の読み上げではなく"p-e-i-ve-ye-te"のように1文字ずつ
# アルファベットの文字名で綴ってしまう別の罠として対象外にしていたが、
# いずれにせよ正しく発音できていないのは同じであるため、運営者からの
# 追加要望で対象に加えた(74番)。ギリシャ文字拡張(アクセント付き文字)は
# 文字種名ではなくUnicode文字名の数字読み上げになる(例:
# "letter one ef bi six")ことも確認したが、いずれにしても正しく発音
# できていないのは同じなので同様に取り除く。ロシア語(ru)に加え、
# カザフ語(kk、config.py上はVOICE_LANGUAGESのscript=Noneだが実際には
# espeak-ngのkkボイスがキリル文字を正しく発音できることを実機確認済み)
# もキリル文字の対応ボイスとして扱う。ギリシャ語は本チャンネルのボイス
# プールに無いため、常に取り除かれる(楔形文字等のピクトグラフ文字体系と
# 同じ扱い)。
#
# ハングル(韓国語)・デーヴァナーガリー(ヒンディー語)はespeak-ngが
# 自動で言語を切り替えて正しく発音できることを実機確認済みで、この罠の
# 対象外のまま。
#
# ラテン文字拡張(Latin Extended-A/B・Latin Extended Additional)の一部
# (README「ハマった罠」75番)は、上記の「文字体系」単位の罠とは別の角度の
# 問題として見つかった。これらのブロックに含まれる"ḑ"(d with cedilla)
# 等の文字は、本チャンネルのどのボイスの文字テーブルにも存在せず、
# espeak-ngがUnicodeコードポイントを1桁ずつ読み上げる
# (例: "letter one E one one" = 0x1E11)。さらに、土台の文字自体が
# 「未知の文字」と判定されると、その上に乗っている結合文字(Zalgo風の
# 装飾、本来は無音で吸収される)まで連鎖的に1つずつ読み上げられてしまう
# (一部はアクセント名で、残りは同じく"symbol"+コードポイントの数字読み)。
# 実機でLatin Extended-A(U+0100-017F)・B(U+0180-024F)・Additional
# (U+1E00-1EFF)の全文字をespeak-ng(enボイス)に通して検証したところ、
# 大半(592候補中448件)がこの罠に該当した。本チャンネルのVOICE_LANGUAGES
# はどの言語も(ロシア語等のcluster系を除き)chars=Noneでランダム生成時に
# これらのブロックを使わないため、ランダム生成側への影響は無く、--word
# でこれらの文字を含む文字列を手動指定された場合のみ関係する。該当する
# ボイスが存在しないため、ブロック全体を常に取り除く(個々の文字単位では
# 問題の無い残り144件も含めて、楔形文字等のピクトグラフ文字体系と同じ
# 「常時除外」扱いにしている)。
_FOREIGN_SCRIPT_VOICE_RULES = [
    ([(0x4E00, 0x9FFF), (0x3400, 0x4DBF)], ("cmn", "yue")),  # CJK統合漢字
    ([(0x0E00, 0x0E7F)], ("th",)),  # タイ文字
    ([(0x0600, 0x06FF), (0x0750, 0x077F)], ("ar", "ug")),  # アラビア文字(ウイグル語含む)
    ([(0x0590, 0x05FF)], ("he",)),  # ヘブライ文字
    ([(0x1200, 0x137F)], ("am",)),  # エチオピア文字(アムハラ語)
    ([(0x0400, 0x04FF), (0x0500, 0x052F)], ("ru", "kk")),  # キリル文字(+補助ブロック)
    ([(0x0370, 0x03FF), (0x1F00, 0x1FFF)], ("el", "grc")),  # ギリシャ文字(+拡張ブロック)。本チャンネルのボイスプールには無いため常に対象
    ([(0x0100, 0x017F), (0x0180, 0x024F), (0x1E00, 0x1EFF)], ()),  # ラテン文字拡張A/B/追加。対応ボイスが存在しないため常に対象
]


def _voice_handles_script(voice, allowed_prefixes):
    """voice(espeak-ngのボイスコード)がallowed_prefixesのいずれかで
    始まるかどうか。"+"以降のバリアント指定(例: "ar+f3")は無視する。"""
    base = voice.split("+")[0]
    return any(base == prefix or base.startswith(prefix) for prefix in allowed_prefixes)


def strip_unspeakable_foreign_script(word, voice):
    """voiceが対応していない文字体系(_FOREIGN_SCRIPT_VOICE_RULES参照)の
    文字を取り除いた文字列を返す。

    [罠] espeak-ngはCJK統合漢字・タイ文字・アラビア文字・ヘブライ文字・
    エチオピア文字・キリル文字・ギリシャ文字を、対応するボイス以外では
    正しく発音せず、文字種名の読み上げ(「Chinese letter」「Thai letter」)
    やアルファベットの文字名での綴り読み(「ピー・イー・アイ」)、
    Unicode文字名の数字読み上げになってしまうことを実機確認した
    (--ipaオプションで検証)。最初は視聴者リクエストで発覚した中国語の
    漢字だけを対象にしていたが(72番)、運営者からの追加要望で候補を
    一通り検証して対象を広げ(73・74番)、「Xxx letter」型とは異なる
    パターン(キリル文字・ギリシャ文字のアルファベット綴り読み)も同じく
    正しく発音できていない点は変わらないため対象に含めた。対応するボイス
    なら正しく発音できるため、ボイスに応じて条件付きで取り除く。

    ラテン文字拡張A/B/追加(75番)は、文字種単位ではなく個々の文字単位の
    罠で、対応ボイスが存在しないため常に取り除かれる(他の文字体系と同じ
    _FOREIGN_SCRIPT_VOICE_RULESの仕組みで扱える。allowed_prefixesを空の
    タプルにすると_voice_handles_script()が常にFalseを返すため)。"""
    applicable_ranges = [
        rng
        for ranges, allowed_prefixes in _FOREIGN_SCRIPT_VOICE_RULES
        if not _voice_handles_script(voice, allowed_prefixes)
        for rng in ranges
    ]
    if not applicable_ranges:
        return word
    return "".join(
        ch for ch in word
        if not any(start <= ord(ch) <= end for start, end in applicable_ranges)
    )


def synthesize_tts(word, wav_path, voice="en", speed=150, pitch=None):
    """espeak-ngに単語を読ませ、生の音声(パディング無し)をwav_pathへ書き出す。

    pitch(espeak-ngの-p、0〜99、デフォルト50)を指定すると、ボイス本来の
    ピッチカーブに対して声の高さを底上げ/引き下げできる。generate.pyでは
    女性ボイス選択時にこれで少し高めに寄せている(config.FEMALE_VOICE_PITCH
    参照)。未指定時はespeak-ngのデフォルトのまま。"""
    txt_path = wav_path + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(word)
    command = ["espeak-ng", "-v", voice, "-s", str(speed)]
    if pitch is not None:
        command += ["-p", str(pitch)]
    command += ["-f", txt_path, "-w", wav_path]
    subprocess.run(command, check=True, capture_output=True)
    os.remove(txt_path)


def _random_extreme_filter_chain():
    """TTSの生音声にかける歪みフィルタをランダムに選んで返す
    (ffmpegのaudio filter文字列のリスト。glitch_synth.pyの
    「毎回パラメータをランダム化し、固定の質感にしない」方針を踏襲)。"""
    candidates = []

    if random.random() < 0.5:
        # サンプルレートを変えてから元のレートへ戻す素朴なピッチシフト
        # (テンポも一緒に変わるので、悪魔声/甲高い声の両方を作れる)。
        if random.random() < 0.5:
            factor = round(random.uniform(0.55, 0.8), 2)  # 悪魔声(低く・遅く)
        else:
            factor = round(random.uniform(1.3, 1.9), 2)  # 甲高い声(高く・速く)
        candidates.append(f"asetrate=44100*{factor},aresample=44100")

    if random.random() < 0.5:
        candidates.append(f"acrusher=bits={random.randint(2, 6)}:mode=lin:aa=0")

    if random.random() < 0.4:
        candidates.append(f"vibrato=f={random.randint(2, 20)}:d={round(random.uniform(0.3, 1.0), 2)}")

    if random.random() < 0.4:
        candidates.append(f"tremolo=f={random.randint(5, 30)}:d={round(random.uniform(0.3, 0.8), 2)}")

    if random.random() < 0.4:
        candidates.append(
            f"aecho=0.8:0.7:{random.randint(20, 80)}:{round(random.uniform(0.2, 0.5), 2)}"
        )

    if not candidates:
        # 何も選ばれなかった場合の保険(tts_extremeなので必ず何かしら歪ませる)
        candidates.append(f"acrusher=bits={random.randint(3, 6)}:mode=lin:aa=0")

    return candidates


def synthesize_tts_extreme(word, wav_path, voice="en"):
    """espeak-ngの奇妙な声バリエーション+極端なピッチ・速度で単語を読ませた
    うえで、さらにffmpegでピッチシフト・ビットクラッシュ等をランダムに
    かけて歪ませる。synthesize_tts()と違い、毎回声質そのものが変わる。

    短い単語×速い読み上げ×テンポを上げる歪みフィルタが重なると、実機の
    検証で最短0.1秒程度まで縮み「発音」ではなく一瞬のノイズにしか聞こえな
    くなることを確認したため、最終的な長さが
    config.TTS_EXTREME_MIN_DURATION_SECONDS を下回った場合は
    _stretch_to_min_duration() で引き伸ばす。"""
    variant = random.choice(EXTREME_VOICE_VARIANTS)
    pitch = random.randint(0, 99)  # espeak-ngの-p範囲(デフォルト50)
    speed = random.randint(60, 400)  # espeak-ngの-s(デフォルト175)を大きく振る

    raw_wav = wav_path + ".raw.wav"
    txt_path = wav_path + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(word)
    subprocess.run(
        ["espeak-ng", "-v", f"{voice}+{variant}", "-p", str(pitch), "-s", str(speed),
         "-f", txt_path, "-w", raw_wav],
        check=True,
        capture_output=True,
    )
    os.remove(txt_path)

    filter_str = ",".join(_random_extreme_filter_chain())
    filtered_wav = wav_path + ".filtered.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav, "-af", filter_str, filtered_wav],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)

    _stretch_to_min_duration(filtered_wav, wav_path, config.TTS_EXTREME_MIN_DURATION_SECONDS)
    if os.path.exists(filtered_wav):
        os.remove(filtered_wav)


def synthesize_tts_reverse(word, wav_path, voice="en", speed=150, pitch=None):
    """espeak-ngで単語を読ませた音声を、そのまま逆再生する [--mode reverse]。

    tts_extremeのピッチ/速度変化とは違い、読み上げ内容(声質・速度)自体は
    一切変えず、時間軸だけを反転させる。長さはsynthesize_tts()と完全に
    同じまま保たれるため、tts_extremeのような最短尺の保険は不要。"""
    raw_wav = wav_path + ".raw.wav"
    synthesize_tts(word, raw_wav, voice=voice, speed=speed, pitch=pitch)
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav, "-af", "areverse", wav_path],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)


def synthesize_tts_robot(word, wav_path, voice="en", speed=150, pitch=None, carrier_freq=None):
    """espeak-ngで単語を読ませた音声に、搬送波(サイン波)とのリング変調
    (ffmpegの`amultiply`で2つの音声ストリームをサンプルごとに掛け合わせる)
    をかけ、ロボット/ダース・ベイダー風の声にする [--mode robot_voice]。
    tts_extremeのピッチ/速度変化+ビットクラッシュとは別の軸の歪み。

    実機で確認したところ、単純にamultiplyしただけだとRMS音量が元の音声
    より約20dB(振幅にして約1/10)下がってしまう(2つの[-1,1]信号を掛け
    合わせる性質上、振幅が縮む)ため、volumeで底上げしたうえでalimiterで
    クリッピングを防いでいる(README「ハマった罠」参照)。"""
    if carrier_freq is None:
        carrier_freq = random.randint(30, 120)  # 低いほど「ブーン」とした金属質な唸りになる

    raw_wav = wav_path + ".raw.wav"
    synthesize_tts(word, raw_wav, voice=voice, speed=speed, pitch=pitch)
    duration = _probe_duration(raw_wav)

    carrier_src = f"sine=frequency={carrier_freq}:duration={duration}"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", raw_wav,
            "-f", "lavfi", "-i", carrier_src,
            "-filter_complex", "[0:a][1:a]amultiply,volume=10,alimiter=limit=0.95[out]",
            "-map", "[out]", wav_path,
        ],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)


def synthesize_tts_chorus(word, wav_path, n_voices=(3, 4)):
    """同じ単語を複数言語のTTSボイスで同時に読み上げ、重ねてミックスする
    [--mode chorus]。「多言語で一斉に発音してみたら」という、単一の声を
    加工する他方式とは別角度のギミック。

    config.VOICE_LANGUAGESから重複無くn_voices個の言語をランダムに選び、
    各言語ごとに性別もランダムに選ぶ(femaleが無い言語はmaleのみ)。開始
    タイミングを少しだけランダムにずらす(adelay)ことで、完全に揃って
    読み上げるのではなく「めいめいバラバラに話し始める」自然さを出す。

    実機で確認したところ、amix(normalize=1)だけだと単一ボイスの音声より
    RMS音量が下がる(声の数で割られるため)ため、volumeで底上げしたうえで
    alimiterでクリッピングを防いでいる(synthesize_tts_robot()と同じ理由。
    README「ハマった罠」参照)。

    候補言語はconfig.VOICE_LANGUAGES全体ではなくconfig.CHORUS_VOICE_LANGUAGE_CODES
    (ヘブライ語を除いたもの)を使う。ヘブライ語ボイスでZalgo単語を読ませると
    他言語の3倍近い長さになることを実機で確認したため(config.py参照)。

    [罠] 複数言語を同時に読ませるchorusの性質上、特定の文字体系
    (CJK統合漢字・タイ文字・アラビア文字・ヘブライ文字・エチオピア文字)
    混じりの--wordリクエストでは、選ばれたボイスの大半がその文字体系に
    対応していないボイスになる。strip_unspeakable_foreign_script()で
    ボイスごとに判定し、非対応ボイスだけ該当文字を取り除いてから読ませる
    (README「ハマった罠」72・73番)。全ボイス共通で単語を一括で取り除くの
    ではなくボイスごとに判定することで、対応するボイスが選ばれた回では
    そのまま正しく発音させられる。"""
    n = random.randint(*n_voices)
    lang_codes = random.sample(
        config.CHORUS_VOICE_LANGUAGE_CODES, k=min(n, len(config.CHORUS_VOICE_LANGUAGE_CODES))
    )

    raw_paths = []
    for i, lang_code in enumerate(lang_codes):
        entry = config.VOICE_LANGUAGES[lang_code]
        genders = ["male"] + (["female"] if entry["female"] else [])
        gender = random.choice(genders)
        voice_code = entry[gender]
        raw_path = f"{wav_path}.chorus{i}.wav"
        synthesize_tts(
            strip_unspeakable_foreign_script(word, voice_code), raw_path,
            voice=voice_code, speed=config.DEFAULT_SPEED,
        )
        raw_paths.append(raw_path)

    cmd = ["ffmpeg", "-y"]
    filter_parts = []
    labels = []
    for i, path in enumerate(raw_paths):
        cmd += ["-i", path]
        delay_ms = random.randint(0, 250)
        label = f"v{i}"
        filter_parts.append(f"[{i}:a]adelay={delay_ms}:all=1[{label}]")
        labels.append(f"[{label}]")

    mix_inputs = "".join(labels)
    filter_parts.append(
        f"{mix_inputs}amix=inputs={len(raw_paths)}:duration=longest:normalize=1,"
        "volume=2.2,alimiter=limit=0.95[out]"
    )
    filter_complex = ";".join(filter_parts)

    cmd += ["-filter_complex", filter_complex, "-map", "[out]", wav_path]
    subprocess.run(cmd, check=True, capture_output=True)

    for path in raw_paths:
        os.remove(path)


def synthesize_tts_telephone(word, wav_path, voice="en", speed=150, pitch=None):
    """espeak-ngで単語を読ませた音声に、電話回線(300〜3400Hz)相当の
    バンドパスフィルタと軽いビットクラッシュをかけ、「電話越しに聞こえる」
    質感にする [--mode telephone]。帯域を狭めるぶんRMS音量が下がるため、
    volumeで底上げする(synthesize_tts_robot()と同じ理由)。"""
    raw_wav = wav_path + ".raw.wav"
    synthesize_tts(word, raw_wav, voice=voice, speed=speed, pitch=pitch)
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav, "-af",
         "highpass=f=300,lowpass=f=3400,acrusher=bits=8:mode=lin:aa=0,volume=1.5",
         wav_path],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)


def synthesize_tts_slowed_reverb(word, wav_path, voice="en", speed=150, pitch=None):
    """espeak-ngで単語を読ませた音声をゆっくり再生(atempo)したうえで
    残響(aecho)を重ね、音楽/音声ミームで定番の「slowed + reverb」ジャンル
    風に加工する [--mode slowed_reverb]。atempoは減速方向のみなので単一の
    atempoフィルタで足りる(0.5〜2.0倍の範囲内、audio_utils._atempo_chain_for_factor()
    のようなチェーンは不要)。"""
    raw_wav = wav_path + ".raw.wav"
    synthesize_tts(word, raw_wav, voice=voice, speed=speed, pitch=pitch)
    tempo = round(random.uniform(0.6, 0.8), 2)
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav, "-af",
         f"atempo={tempo},aecho=0.8:0.9:60|120:0.4|0.3",
         wav_path],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)


def synthesize_tts_nightcore(word, wav_path, voice="en", speed=150, pitch=None):
    """espeak-ngで単語を読ませた音声を、サンプルレートを上げてから元の
    レートへ戻すことでピッチとテンポを同時に上げる(悪魔声と逆方向の
    「甲高く速く」)、「nightcore」ジャンル風に加工する [--mode nightcore]。
    slowed_reverbと対になる、高速化方向のジャンル。"""
    raw_wav = wav_path + ".raw.wav"
    synthesize_tts(word, raw_wav, voice=voice, speed=speed, pitch=pitch)
    factor = round(random.uniform(1.25, 1.5), 2)
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav, "-af",
         f"asetrate=44100*{factor},aresample=44100",
         wav_path],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)


def synthesize_tts_underwater(word, wav_path, voice="en", speed=150, pitch=None):
    """espeak-ngで単語を読ませた音声に強めのローパスフィルタ+揺らぎ
    (ffmpegの`chorus`)をかけ、水中で喋っているような質感にする
    [--mode underwater]。ローパスでこもらせるぶんRMS音量が下がるため、
    volumeで底上げする。"""
    raw_wav = wav_path + ".raw.wav"
    synthesize_tts(word, raw_wav, voice=voice, speed=speed, pitch=pitch)
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav, "-af",
         "lowpass=f=600,chorus=0.7:0.9:55:0.4:0.25:2,volume=1.8",
         wav_path],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)


def synthesize_tts_8d_audio(word, wav_path, voice="en", speed=150, pitch=None):
    """espeak-ngで単語を読ませた音声(モノラル)を、`pan`で左右両チャンネル
    に複製してステレオ化したうえで、`apulsator`で左右の音量を交互に
    揺らし、音像がゆっくり回転しているように聞こえる「8D audio」ジャンル風
    に加工する [--mode 8d_audio]。ヘッドホンで聴くことを前提にしたジャンル。
    モノラルのままapulsatorをかけても単一チャンネルの音量が揺れるだけで
    左右の移動感は出ないため、先にステレオ化するのが肝。"""
    raw_wav = wav_path + ".raw.wav"
    synthesize_tts(word, raw_wav, voice=voice, speed=speed, pitch=pitch)
    hz = round(random.uniform(0.15, 0.3), 2)
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav, "-af",
         f"pan=stereo|c0=c0|c1=c0,apulsator=mode=sine:hz={hz}",
         wav_path],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)


def synthesize_tts_echo_cave(word, wav_path, voice="en", speed=150, pitch=None):
    """espeak-ngで単語を読ませた音声に、複数タップ(遅延/減衰をそれぞれ
    3段)のエコー(aecho)を重ね、洞窟や大聖堂のような深い反響を作る
    [--mode echo_cave]。tts_extremeのランダム歪みフィルタ内でも軽いaecho
    単発が候補に入ることがあるが(_random_extreme_filter_chain()参照)、
    こちらは反響そのものを主役にした専用モードとして、複数タップでより
    深く・意図的な残響にしている。"""
    raw_wav = wav_path + ".raw.wav"
    synthesize_tts(word, raw_wav, voice=voice, speed=speed, pitch=pitch)
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw_wav, "-af",
         "aecho=0.8:0.9:60|150|280:0.5|0.35|0.2",
         wav_path],
        check=True,
        capture_output=True,
    )
    os.remove(raw_wav)
