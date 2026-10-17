"""tts_synth.py の純粋関数に対するユニットテスト。
espeak-ng/ffmpeg呼び出し(synthesize_tts_extreme)は実際には行わない、
軽いテストのみ。synthesize_tts()はsubprocess.runをモックし、実際の
espeak-ng実行はしないまま組み立てられるコマンドだけを検証する。"""

import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import tts_synth
from tts_synth import (
    EXTREME_VOICE_VARIANTS,
    _random_extreme_filter_chain,
    strip_unspeakable_foreign_script,
    synthesize_tts,
    synthesize_tts_8d_audio,
    synthesize_tts_chorus,
    synthesize_tts_echo_cave,
    synthesize_tts_nightcore,
    synthesize_tts_reverse,
    synthesize_tts_robot,
    synthesize_tts_slowed_reverb,
    synthesize_tts_telephone,
    synthesize_tts_underwater,
)


def test_random_extreme_filter_chain_never_empty():
    # tts_extremeは「必ず何かしら歪ませる」のが目的なので、確率的に何も
    # 選ばれなかった場合の保険(acrusherフォールバック)が効いていることを
    # 確認する。
    random.seed(1)
    for _ in range(200):
        assert len(_random_extreme_filter_chain()) >= 1


def test_random_extreme_filter_chain_produces_valid_ffmpeg_filter_syntax():
    random.seed(2)
    for _ in range(50):
        chain = _random_extreme_filter_chain()
        filter_str = ",".join(chain)
        # 各フィルタが "name=..." の形式になっていること(ffmpeg -afへ
        # そのまま渡せる文字列であることの簡易チェック)
        for filt in chain:
            assert re.match(r"^[a-z]+=", filt), filt
        assert "," in filter_str or len(chain) == 1


def test_random_extreme_filter_chain_varies_across_calls():
    # 以前は固定値だったため、複数回呼んだ際にバリエーションが出ることを
    # 確認する(回帰防止)。
    random.seed(3)
    chains = {",".join(_random_extreme_filter_chain()) for _ in range(100)}
    assert len(chains) > 1


def test_extreme_voice_variants_are_nonempty_strings():
    assert len(EXTREME_VOICE_VARIANTS) > 0
    assert all(isinstance(v, str) and v for v in EXTREME_VOICE_VARIANTS)


def test_synthesize_tts_omits_pitch_flag_by_default(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(
        tts_synth.subprocess, "run",
        lambda cmd, check, capture_output: captured.setdefault("cmd", cmd),
    )
    synthesize_tts("word", str(tmp_path / "out.wav"))
    assert "-p" not in captured["cmd"]


def test_synthesize_tts_includes_pitch_flag_when_given(monkeypatch, tmp_path):
    # 女性ボイスをより高く聞こえさせるためのconfig.FEMALE_VOICE_PITCH
    # (generate.py参照)が、実際にespeak-ngの-pへ渡ることを確認する。
    captured = {}
    monkeypatch.setattr(
        tts_synth.subprocess, "run",
        lambda cmd, check, capture_output: captured.setdefault("cmd", cmd),
    )
    synthesize_tts("word", str(tmp_path / "out.wav"), pitch=75)
    cmd = captured["cmd"]
    assert "-p" in cmd
    assert cmd[cmd.index("-p") + 1] == "75"


def _capture_all_run_calls(monkeypatch):
    """subprocess.run呼び出しをすべて記録しつつ、出力先(cmd[-1])に空
    ファイルを作るフェイクに差し替える(実際のespeak-ng/ffmpeg実行はしない)。
    呼び出しごとのコマンド列(リストのリスト)を返す。"""
    calls = []

    def fake_run(cmd, check, capture_output):
        calls.append(cmd)
        Path(cmd[-1]).touch()

    monkeypatch.setattr(tts_synth.subprocess, "run", fake_run)
    return calls


def test_synthesize_tts_reverse_applies_areverse_and_passes_through_voice(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    out = tmp_path / "out.wav"

    synthesize_tts_reverse("word", str(out), voice="fr-fr", speed=180, pitch=60)

    espeak_call = calls[0]
    assert "fr-fr" in espeak_call
    assert "180" in espeak_call
    assert espeak_call[espeak_call.index("-p") + 1] == "60"

    ffmpeg_call = calls[1]
    assert "-af" in ffmpeg_call
    assert ffmpeg_call[ffmpeg_call.index("-af") + 1] == "areverse"
    assert ffmpeg_call[-1] == str(out)
    assert out.exists()


def test_synthesize_tts_robot_uses_amultiply_with_given_carrier_freq(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    monkeypatch.setattr(tts_synth, "_probe_duration", lambda path: 1.5)
    out = tmp_path / "out.wav"

    synthesize_tts_robot("word", str(out), voice="en", carrier_freq=77)

    ffmpeg_call = calls[-1]
    assert any("sine=frequency=77" in tok for tok in ffmpeg_call)
    filter_complex = ffmpeg_call[ffmpeg_call.index("-filter_complex") + 1]
    assert "amultiply" in filter_complex
    # 実機でamultiplyだけだとRMS音量が大きく下がることを確認したため、
    # volumeで底上げ+alimiterでクリッピング防止している(README参照)。
    assert "volume=" in filter_complex
    assert "alimiter=" in filter_complex
    assert out.exists()


def test_synthesize_tts_robot_default_carrier_freq_within_range(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    monkeypatch.setattr(tts_synth, "_probe_duration", lambda path: 1.0)
    random.seed(1)

    for _ in range(30):
        synthesize_tts_robot("word", str(tmp_path / "out.wav"))
        ffmpeg_call = calls[-1]
        m = re.search(r"sine=frequency=(\d+)", " ".join(ffmpeg_call))
        assert m
        assert 30 <= int(m.group(1)) <= 120


def test_synthesize_tts_chorus_picks_multiple_distinct_languages(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    random.seed(1)
    out = tmp_path / "out.wav"

    synthesize_tts_chorus("word", str(out))

    espeak_calls = calls[:-1]
    mix_call = calls[-1]
    assert len(espeak_calls) >= 3  # n_voicesのデフォルト範囲(3,4)の最小値
    voices_used = {c[c.index("-v") + 1] for c in espeak_calls}
    assert len(voices_used) == len(espeak_calls)  # 重複無く選ばれていること

    filter_complex = mix_call[mix_call.index("-filter_complex") + 1]
    assert f"amix=inputs={len(espeak_calls)}" in filter_complex
    assert "adelay=" in filter_complex
    assert "volume=" in filter_complex
    assert "alimiter=" in filter_complex
    assert out.exists()


def test_chorus_voice_language_codes_excludes_hebrew():
    assert "he" not in config.CHORUS_VOICE_LANGUAGE_CODES
    assert set(config.CHORUS_VOICE_LANGUAGE_CODES) == set(config.VOICE_LANGUAGES) - {"he"}


def test_synthesize_tts_chorus_never_uses_hebrew_voice(monkeypatch, tmp_path):
    # ヘブライ語ボイスはZalgo単語で他言語の3倍近い長さになることを実機で
    # 確認したため、config.CHORUS_VOICE_LANGUAGE_CODESから除外済み
    # (config.py参照)。chorusが実際にこれを選ばないことの回帰防止。
    calls = _capture_all_run_calls(monkeypatch)
    random.seed(2)
    excluded_voices = {
        config.VOICE_LANGUAGES["he"]["male"], config.VOICE_LANGUAGES["he"]["female"],
    }

    for _ in range(30):
        synthesize_tts_chorus("word", str(tmp_path / "out.wav"))
        espeak_calls = calls[:-1]
        voices_used = {c[c.index("-v") + 1] for c in espeak_calls}
        assert voices_used.isdisjoint(excluded_voices)
        calls.clear()


def test_strip_unspeakable_foreign_script_removes_han_characters_for_non_chinese_voice():
    # espeak-ngはCJK統合漢字を中国語系(cmn/yue)以外のボイスでは発音せず
    # 「Chinese letter」のように文字種名を読み上げてしまうことを実機確認した
    # (--ipaオプションで検証、視聴者リクエストで発覚。README「ハマった罠」
    # 72番)。該当文字だけを取り除き、それ以外はそのまま残すことを確認する。
    word = "koO椒和koO"
    assert strip_unspeakable_foreign_script(word, "en") == "koOkoO"
    assert strip_unspeakable_foreign_script(word, "ar+f3") == "koOkoO"
    assert strip_unspeakable_foreign_script(word, "bs") == "koOkoO"


def test_strip_unspeakable_foreign_script_keeps_han_characters_for_chinese_voices():
    # 中国語系ボイス(zh=内部コード"cmn"/yue=広東語)ならCJK統合漢字を正しく
    # 発音できるため取り除かない。
    word = "koO椒和koO"
    assert strip_unspeakable_foreign_script(word, "cmn") == word
    assert strip_unspeakable_foreign_script(word, "cmn+f3") == word
    assert strip_unspeakable_foreign_script(word, "yue") == word
    assert strip_unspeakable_foreign_script(word, "yue+f3") == word


def test_strip_unspeakable_foreign_script_leaves_non_cjk_words_unchanged():
    assert strip_unspeakable_foreign_script("hello world", "en") == "hello world"


def test_strip_unspeakable_foreign_script_handles_thai_arabic_hebrew_amharic():
    # 運営者から「中国語以外にも'xx letter'と発音する言語があれば直して
    # ほしい」と要望があり、実機で候補を検証して対象を広げた
    # (README「ハマった罠」73番)。タイ文字・アラビア文字・ヘブライ文字・
    # エチオピア文字(アムハラ語)も同じ罠(対応ボイス以外では文字種名を
    # 読み上げてしまう)があることを確認済み。
    thai = "ก"  # タイ文字(コー・ガイ)
    arabic = "ا"  # アラビア文字(アリフ)
    hebrew = "א"  # ヘブライ文字(アレフ)
    amharic = "ሀ"  # エチオピア文字(ハ)

    assert strip_unspeakable_foreign_script(f"hi{thai}bye", "en") == "hibye"
    assert strip_unspeakable_foreign_script(f"hi{thai}bye", "th") == f"hi{thai}bye"

    assert strip_unspeakable_foreign_script(f"hi{arabic}bye", "en") == "hibye"
    assert strip_unspeakable_foreign_script(f"hi{arabic}bye", "ar+f3") == f"hi{arabic}bye"

    assert strip_unspeakable_foreign_script(f"hi{hebrew}bye", "en") == "hibye"
    assert strip_unspeakable_foreign_script(f"hi{hebrew}bye", "he") == f"hi{hebrew}bye"

    assert strip_unspeakable_foreign_script(f"hi{amharic}bye", "en") == "hibye"
    assert strip_unspeakable_foreign_script(f"hi{amharic}bye", "am+f3") == f"hi{amharic}bye"


def test_strip_unspeakable_foreign_script_uyghur_voice_keeps_arabic_block_characters():
    # ウイグル語(ug)はアラビア文字のUnicodeブロックをそのまま使っている
    # (UYGHUR_LETTERSはARABIC_LETTERSの文字を流用、config.py参照)ため、
    # アラビア語と同じ扱いで取り除かれないことを確認する。
    word = "hiابye"
    assert strip_unspeakable_foreign_script(word, "ug") == word
    assert strip_unspeakable_foreign_script(word, "ug+f3") == word
    assert strip_unspeakable_foreign_script(word, "en") == "hiye"


def test_strip_unspeakable_foreign_script_does_not_touch_hangul_or_devanagari():
    # ハングル(韓国語)・デーヴァナーガリー(ヒンディー語)はespeak-ngが
    # 自動で言語を切り替えて正しく発音できることを実機確認済み(--ipa検証)
    # で、この罠の対象外。_FOREIGN_SCRIPT_VOICE_RULESに含めていないため、
    # どのボイスでも取り除かれないことの回帰防止。
    hangul = "안녕"
    devanagari = "नमस्ते"
    assert strip_unspeakable_foreign_script(hangul, "en") == hangul
    assert strip_unspeakable_foreign_script(devanagari, "en") == devanagari


def test_strip_unspeakable_foreign_script_handles_cyrillic_and_greek():
    # 運営者から「ギリシャ文字も修正してほしい」と追加要望があった
    # (README「ハマった罠」74番)。キリル文字・ギリシャ文字は
    # 「Xxx letter」型ではなく、1文字ずつアルファベットの文字名で綴って
    # しまう(例: ロシア語の「привет」を英語ボイスに渡すと"pe, er, i, ve,
    # ye, te"になる)別パターンの罠だが、正しく発音できていない点は同じ
    # なので対象に含めた。
    cyrillic = "привет"  # ロシア語ボイス(ru)なら正しく発音できる
    greek = "γεια"  # 本チャンネルのボイスプールにギリシャ語ボイスは無い

    assert strip_unspeakable_foreign_script(f"hi{cyrillic}bye", "en") == "hibye"
    assert strip_unspeakable_foreign_script(f"hi{cyrillic}bye", "ru") == f"hi{cyrillic}bye"
    assert strip_unspeakable_foreign_script(f"hi{cyrillic}bye", "ru+f3") == f"hi{cyrillic}bye"

    # ギリシャ語ボイスはVOICE_LANGUAGESに存在しないため、どのボイスでも
    # 常に取り除かれる(楔形文字等のピクトグラフ文字体系と同じ扱い)。
    assert strip_unspeakable_foreign_script(f"hi{greek}bye", "en") == "hibye"
    assert strip_unspeakable_foreign_script(f"hi{greek}bye", "ru") == "hibye"


def test_strip_unspeakable_foreign_script_kazakh_voice_keeps_cyrillic_characters():
    # config.py上はカザフ語(kk)のVOICE_LANGUAGESエントリはscript=None
    # (ランダム生成時はラテン文字のZalgo単語を使う)だが、espeak-ngのkk
    # ボイス自体はキリル文字を正しく発音できることを実機確認済みのため、
    # --wordでキリル文字を手動指定された場合は取り除かないことを確認する。
    word = "hiприветbye"
    assert strip_unspeakable_foreign_script(word, "kk") == word
    assert strip_unspeakable_foreign_script(word, "kk+f3") == word


def test_synthesize_tts_chorus_strips_cjk_only_for_non_chinese_voices(monkeypatch, tmp_path):
    # chorusは複数ボイスを内部で選ぶため、CJK統合漢字混じりの単語でも
    # ボイスごとに正しく判定され、中国語系ボイスが選ばれた回だけ漢字が
    # 残ることの回帰防止(README「ハマった罠」72番)。
    calls = []

    def fake_synthesize_tts(word, wav_path, voice="en", speed=150, pitch=None):
        calls.append((word, voice))
        Path(wav_path).touch()

    monkeypatch.setattr(tts_synth, "synthesize_tts", fake_synthesize_tts)
    monkeypatch.setattr(tts_synth.subprocess, "run", lambda cmd, check, capture_output: Path(cmd[-1]).touch())

    word = "koO椒和koO"
    seen_chinese_voice = False
    seen_non_chinese_voice = False
    for seed in range(100):
        random.seed(seed)
        calls.clear()
        synthesize_tts_chorus(word, str(tmp_path / "out.wav"))
        for spoken_word, voice in calls:
            if voice.split("+")[0] in ("cmn", "yue"):
                seen_chinese_voice = True
                assert "椒和" in spoken_word, (spoken_word, voice)
            else:
                seen_non_chinese_voice = True
                assert "椒和" not in spoken_word, (spoken_word, voice)
    assert seen_chinese_voice, "テストの前提として中国語系ボイスが一度も選ばれなかった"
    assert seen_non_chinese_voice, "テストの前提として非中国語系ボイスが一度も選ばれなかった"


def test_synthesize_tts_telephone_applies_bandpass_filter(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    out = tmp_path / "out.wav"

    synthesize_tts_telephone("word", str(out), voice="fr-fr", speed=180, pitch=60)

    espeak_call = calls[0]
    assert "fr-fr" in espeak_call
    assert "180" in espeak_call
    assert espeak_call[espeak_call.index("-p") + 1] == "60"

    ffmpeg_call = calls[1]
    filter_str = ffmpeg_call[ffmpeg_call.index("-af") + 1]
    assert "highpass=f=300" in filter_str
    assert "lowpass=f=3400" in filter_str
    assert out.exists()


def test_synthesize_tts_slowed_reverb_applies_atempo_and_echo(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    random.seed(1)
    out = tmp_path / "out.wav"

    synthesize_tts_slowed_reverb("word", str(out))

    filter_str = calls[-1][calls[-1].index("-af") + 1]
    m = re.search(r"atempo=([\d.]+)", filter_str)
    assert m
    assert 0.6 <= float(m.group(1)) <= 0.8
    assert "aecho=" in filter_str
    assert out.exists()


def test_synthesize_tts_nightcore_speeds_up_and_raises_pitch(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    random.seed(1)
    out = tmp_path / "out.wav"

    synthesize_tts_nightcore("word", str(out))

    filter_str = calls[-1][calls[-1].index("-af") + 1]
    m = re.search(r"asetrate=44100\*([\d.]+)", filter_str)
    assert m
    assert 1.25 <= float(m.group(1)) <= 1.5
    assert "aresample=44100" in filter_str
    assert out.exists()


def test_synthesize_tts_underwater_applies_lowpass_and_chorus(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    out = tmp_path / "out.wav"

    synthesize_tts_underwater("word", str(out))

    filter_str = calls[-1][calls[-1].index("-af") + 1]
    assert "lowpass=f=600" in filter_str
    assert "chorus=" in filter_str
    assert out.exists()


def test_synthesize_tts_8d_audio_converts_to_stereo_with_apulsator(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    random.seed(1)
    out = tmp_path / "out.wav"

    synthesize_tts_8d_audio("word", str(out))

    filter_str = calls[-1][calls[-1].index("-af") + 1]
    # モノラルのままだと左右の移動感が出ないため、先にpanでステレオ化する
    assert "pan=stereo" in filter_str
    assert "apulsator=" in filter_str
    m = re.search(r"apulsator=mode=sine:hz=([\d.]+)", filter_str)
    assert m
    assert 0.15 <= float(m.group(1)) <= 0.3
    assert out.exists()


def test_synthesize_tts_echo_cave_applies_multi_tap_echo(monkeypatch, tmp_path):
    calls = _capture_all_run_calls(monkeypatch)
    out = tmp_path / "out.wav"

    synthesize_tts_echo_cave("word", str(out))

    filter_str = calls[-1][calls[-1].index("-af") + 1]
    # 洞窟のような深い反響を出すため、単発ではなく複数タップ(delays/decays
    # がそれぞれ"|"区切りで3段)のaechoになっていること
    assert filter_str.startswith("aecho=")
    delays = filter_str.split(":")[2]
    decays = filter_str.split(":")[3]
    assert len(delays.split("|")) == 3
    assert len(decays.split("|")) == 3
    assert out.exists()
