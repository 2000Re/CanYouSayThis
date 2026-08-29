# unpronounceable-generator

「How to Pronounce ▤彡...」系のネタ動画を自動生成するパイプラインです。

Zalgo風の「発音不能な単語」をランダム生成し、それに対して「これが発音で
す」という体で音声を当て、"How to Pronounce <word>" 形式の短い動画(mp4)
を量産します。

## できること

1. **単語生成**: 母音などの土台文字にUnicodeの結合文字(いわゆるZalgoテキ
   スト)や記号を大量に重ねた、見た目からして発音不能な単語をランダムに作
   ります。
2. **音声生成**: 2つの方式を選べます。
   - `tts`(デフォルト): [espeak-ng](https://github.com/espeak-ng/espeak-ng)
     に単語そのものを読ませ、出てきた音をそのまま採用します。
   - `glitch`: チャープ音・ノイズバースト・ビットクラッシュを合成し、単語
     の音とは無関係な効果音を「答え」として当てます。
3. **繰り返し**: 実際のHow-to-Pronounce系動画が "word... word..." のよう
   に2回言うことが多いのに合わせて、生成した音声をデフォルトで2回繰り返し
   ます。
4. **動画合成**: "How to Pronounce <word>" 形式のミニマルな静止画フレーム
   を [Playwright](https://playwright.dev/) 経由のChromiumで描画し、音声
   と合成してmp4を書き出します。動画の尺は音声の実際の長さにそのまま追従
   します(固定尺への無音パディングはしません)。

## セットアップ

```bash
# システム依存(Ubuntu/Debian系の例)
sudo apt-get install -y espeak-ng ffmpeg
sudo apt-get install -y fonts-noto-core fonts-noto-extra fonts-noto-ui-core fonts-noto-ui-extra

# Python依存
pip install -r requirements.txt
playwright install chromium   # Playwright同梱のChromiumが無い環境の場合のみ
```

開発用(テスト・lint)には追加で:

```bash
pip install -r requirements-dev.txt
```

## 使い方

```bash
# TTS方式(デフォルト)で5本生成
python3 generate.py --count 5 --outdir ./out

# グリッチ音方式で5本生成
python3 generate.py --count 5 --mode glitch --outdir ./out_glitch

# 「答え」を3回繰り返す・乱数シード固定で再現する
python3 generate.py --count 5 --repeat 3 --seed 42
```

### 主なオプション

| オプション | 説明 | デフォルト |
|---|---|---|
| `--count` | 生成する本数 | `3` |
| `--outdir` | 出力ディレクトリ | `./out` |
| `--mode` | `tts` または `glitch` | `tts` |
| `--voice` | [tts専用] espeak-ngの声(`en`, `en-us`, `ja` など) | `en` |
| `--speed` | [tts専用] 読み上げ速度(words/min) | `150` |
| `--unit-duration` | [glitch専用] 「答え」1回分の長さ(秒) | `2.0` |
| `--repeat` | 「答え」を何回繰り返すか | `2` |
| `--repeat-gap` | 繰り返し間の無音の長さ(秒) | `0.4` |
| `--fade` | 末尾のフェードアウトの長さ(秒) | `0.4` |
| `--seed` | 乱数シード(再現したい場合) | なし |

### 出力

```
out/
  001_word.txt   生成した単語そのもの
  001.mp3        音声(modeにより中身が変わる)
  001.mp4        完成動画
  002_word.txt
  ...
```

## ハマった罠(実装時のデバッグ記録)

このリポジトリの実装は「単純にespeak-ngへZalgoテキストを渡せば終わり」で
は済まなかったので、後から追う人のために記録しておきます。

### 1. 結合文字を積んでも「無音」にならないことがある

Unicodeの結合文字(Combining Diacritical Marksなど)は、同じブロックの中
でも挙動が一様ではありません。例えばヘブライ語の母音記号
(`U+05B0`-`U+05BD`)は、espeak-ngが `"Hebrew A"` のように**律儀に読み上げ
てしまいます**。つまり無音になるどころか、単語というより解説文になってし
まいます。

対策として、`config.py` の `SAFE_COMBINING_BLOCKS` は「実際にespeak-ngへ
1文字ずつ通して無音を確認できたコードポイントのみ」で構成しています。

### 2. 個別には無音でも、ブロックを混ぜると読み上げが暴発する

さらに厄介なことに、個々には無音と確認済みの結合文字でも、**異なるUnicode
ブロックのものを同じ1文字に混ぜて乗せる**と、espeak-ngが一部のマークを
「載せ忘れた」扱いにして単独の記号として読み上げてしまうことがありました
(例: acute accentを名指しで読み上げる)。同じブロック内のマーク同士なら
何個重ねても無音のままです。

そのため `word_generator.py` の `_random_combining_stack()` は、1つの土台
文字に乗せる結合文字を**必ず単一ブロックの中だけ**から選ぶようにしていま
す。

### 3. Unicode未割り当てのコードポイントは「豆腐」になる

`U+20D0`-`U+20FF`(Combining Diacritical Marks for Symbols)の一部
(`U+20F1`以降)はUnicode上まだ割り当てられていません。フォントが対応しよ
うがないので、どんなにフォントを揃えても豆腐(`□`)になります。
`SAFE_COMBINING_BLOCKS` では `0x20F1` 未満に絞ることで回避しています。

### 4. フレーム画像はPILではなくブラウザで描く

Zalgoの結合文字や記号ブロックは1つのフォントに全部入っていないことが多い
ため、PILのような単一フォント描画だと簡単に豆腐になります。
`frame_builder.py` ではChromium(Playwright同梱)にHTMLを描かせてスクリー
ンショットを撮ることで、OSのfontconfigフォールバックに解決を任せていま
す。Noto系フォント一式(`fonts-noto-core` `fonts-noto-extra` など)を入れ
ておく必要があります。

### 5. 動画尺は固定パディングしない

当初は `apad` で固定の動画尺(例: 6.5秒)まで無音パディングしていました
が、単語ごとに発話の長さが違うため不自然な無音が伸びる問題がありました。
現在は `audio_utils.finalize_audio()` が中身の実際の長さの末尾だけ短く
フェードアウトし、`video_builder.build_video()` の `-shortest` で動画尺が
音声に追従するようにしています。

## プロジェクト構成

```
config.py           全モジュール共通の設定・定数
word_generator.py   Zalgo風「発音不能な単語」の生成
tts_synth.py         TTS(espeak-ng)による音声合成 [--mode tts]
glitch_synth.py      合成グリッチ音による音声生成 [--mode glitch]
audio_utils.py       繰り返し・パディング無しフェード・mp3変換
frame_builder.py     "How to Pronounce" フレーム画像の生成(Playwright)
video_builder.py     フレーム+音声 → mp4 の合成
generate.py          CLIエントリポイント
tests/               ユニットテスト(pytest)
.github/workflows/   CI(push/PR時にテストを自動実行)
```

## ライセンス

MIT License. `LICENSE` を参照してください。
