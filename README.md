# CanYouSayThis

「How to Pronounce ▤彡...」系のネタ動画を自動生成するパイプラインです。

Zalgo風の「発音不能な単語」をランダム生成し、それに対して「これが発音で
す」という体で音声を当て、"How to Pronounce <word>" 形式の短い動画(mp4)
を量産します。

## できること

1. **単語生成**: 母音などの土台文字にUnicodeの結合文字(いわゆるZalgoテキ
   スト)や記号を大量に重ねた、見た目からして発音不能な単語をランダムに作
   ります。
2. **音声生成**: 3つの方式、またはそれらをランダムに混ぜる方式を選べます。
   - `tts`(デフォルト): [espeak-ng](https://github.com/espeak-ng/espeak-ng)
     に単語そのものを読ませ、出てきた音をそのまま採用します。
   - `tts_extreme`: espeak-ngの奇妙な声バリエーション(`Demonic` / `croak` /
     `whisper` など)+極端なピッチ・速度で単語を読ませたうえで、さらに
     ffmpegでピッチシフト・ビットクラッシュ等をランダムにかけて歪ませま
     す。`tts`と同じく単語自体は読ませていますが、声質が毎回激しく変わ
     ります。
   - `glitch`: チャープ音・ノイズバースト・ビットクラッシュを合成し、単語
     の音とは無関係な効果音を「答え」として当てます。
   - `random`: 1本ごとに上記3方式から`config.MODE_WEIGHTS`の重みでランダム
     に選びます(`--count`で複数本まとめて作る際や、自動実行の日々の投稿が
     単調にならないようにする用途)。`glitch`は単語自体を読ませない合成音
     のため「発音してみて」というコンセプトへの説得力が弱いという判断から、
     一時的に均等抽選(各1/3)より比率を下げていました(`tts`:`tts_extreme`:
     `glitch` = 2:2:1)が、実測(`youtube_analytics.py`)で主指標(1日あたり
     再生数)がglitchで2回連続最上位だったため、現在は均等抽選(各1/3)に
     戻しています(「ハマった罠」参照)。
3. **多言語・声色のランダム化**(任意): `--voice random` を指定すると、
   [tts/tts_extreme専用] 英語を含む20言語・すべての言語で男性/女性ボイスも
   1本ごとにランダムに選びます。詳しくは後述の「多言語ボイス」を参照。
4. **繰り返し**: 実際のHow-to-Pronounce系動画が "word... word..." のよう
   に2回言うことが多いのに合わせて、生成した音声をデフォルトで2回繰り返し
   ます。
5. **動画合成**: "How to Pronounce <word>" 形式のミニマルな静止画フレーム
   を [Playwright](https://playwright.dev/) 経由のChromiumで描画し、音声
   と合成してmp4を書き出します(縦型9:16、YouTube Shorts向け)。動画の尺
   は音声の実際の長さにそのまま追従します(固定尺への無音パディングはし
   ません)。
6. **YouTubeへの自動アップロード**(任意): `--upload` を付けると、書き出
   したmp4をそのままYouTube Data API v3経由でチャンネルにアップロードし
   ます。
7. **Shorts結合動画**(任意): アップロードしたShortsが10本たまるごとに、
   それらを結合した1本の「通常動画」を自動で作ってアップロードします
   (詳しくは後述の「Shorts結合動画」を参照)。

## セットアップ

```bash
# システム依存(Ubuntu/Debian系の例)
sudo apt-get install -y espeak-ng ffmpeg
sudo apt-get install -y fonts-noto-core fonts-noto-extra fonts-noto-ui-core fonts-noto-ui-extra

# --voice random で英語・フランス語・ドイツ語・ハンガリー語・スウェーデン語の
# 女性ボイス(MBROLAによる自然な声質)を使う場合のみ必要。未インストールでも
# 男性ボイス・上記以外の言語の女性ボイス(espeak-ng内蔵のフォルマント
# バリアントで代替。追加パッケージ不要)は動作する(詳しくは「多言語ボイス」を参照)
sudo apt-get install -y mbrola mbrola-us1 mbrola-fr4 mbrola-de1 mbrola-hu1 mbrola-sw2

# Python依存
pip install -r requirements.txt
playwright install chromium   # Playwright同梱のChromiumが無い環境の場合のみ
```

開発用(テスト・lint・YouTubeリフレッシュトークン取得)には追加で:

```bash
pip install -r requirements-dev.txt
```

## 使い方

```bash
# TTS方式(デフォルト)で5本生成
python3 generate.py --count 5 --outdir ./out

# グリッチ音方式で5本生成
python3 generate.py --count 5 --mode glitch --outdir ./out_glitch

# 極端に歪ませたTTSで5本生成
python3 generate.py --count 5 --mode tts_extreme --outdir ./out_extreme

# 3方式を1本ごとにランダムに混ぜて5本生成
python3 generate.py --count 5 --mode random --outdir ./out_mixed

# 言語・性別(男性/女性)を1本ごとにランダムに選ぶ(詳しくは「多言語ボイス」を参照)
python3 generate.py --count 5 --voice random --outdir ./out_multilang

# 「答え」を3回繰り返す・乱数シード固定で再現する
python3 generate.py --count 5 --repeat 3 --seed 42

# 生成した動画をそのままYouTubeにアップロード(下記セットアップが必要)
python3 generate.py --count 3 --upload --privacy-status unlisted
```

### 主なオプション

| オプション | 説明 | デフォルト |
|---|---|---|
| `--count` | 生成する本数 | `3` |
| `--outdir` | 出力ディレクトリ | `./out` |
| `--mode` | `tts` / `tts_extreme` / `glitch` / `random`(1本ごとにランダム選択) | `tts` |
| `--voice` | [tts/tts_extreme専用] espeak-ngの声(`en`, `en-us`, `ja` など / `random`=言語・性別をランダムに選ぶ、詳しくは「多言語ボイス」を参照) | `en` |
| `--speed` | [tts専用。tts_extremeは毎回ランダムな速度を使うため対象外] 読み上げ速度(words/min) | `150` |
| `--unit-duration` | [glitch専用] 「答え」1回分の長さ(秒) | `2.0` |
| `--repeat` | 「答え」を何回繰り返すか | `2` |
| `--repeat-gap` | 繰り返し間の無音の長さ(秒) | `0.4` |
| `--fade` | 末尾のフェードアウトの長さ(秒) | `0.4` |
| `--seed` | 乱数シード(再現したい場合) | なし |
| `--upload` | 生成した各動画をそのままYouTubeにアップロードする | 無効 |
| `--privacy-status` | [`--upload`専用] `public` / `unlisted` / `private` | `public` |

### 出力

```
out/
  001_word.txt   生成した単語そのもの
  001.mp3        音声(modeにより中身が変わる)
  001.mp4        完成動画(--upload時は後述の通りvideo_idにリネームされる)
  002_word.txt
  ...
```

`--upload` 使用時は、YouTubeへのアップロード成功後に完成動画が
`{video_id}.mp4`(例: `dQw4w9WgXcQ.mp4`)にリネームされます。これは
`compile_shorts.py` が後から`upload_history.json`の`video_id`をキーに
GitHub Actionsアーティファクト内の該当ファイルを特定できるようにする
ためです(詳細は「Shorts結合動画」節と「ハマった罠」の8番を参照)。

## 多言語ボイス(`--voice random`)

土台の文字(母音中心)自体は変えず、espeak-ngが読み上げる**言語・性別**だ
けを1本ごとにランダムに変えることで、同じ単語でも読み上げの響きが毎回変
わるようにする機能です(`config.VOICE_LANGUAGES`)。

`--voice random` を指定すると、英語を含む以下の20言語・全言語で男性/女性
の両方のボイスからランダムに選ばれます。

| 言語 | 男性ボイス | 女性ボイス | 単語の文字体系 |
|---|---|---|---|
| 英語 | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| フランス語 | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| ドイツ語 | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| ハンガリー語 | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| スウェーデン語 | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| トルコ語 | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| ポルトガル語(ブラジル) | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| ポルトガル語(ポルトガル) | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| 中国語(標準語) | ○ | ○(フォルマントバリアント) | ラテン文字(Zalgo) |
| 広東語 | ○ | ○(フォルマントバリアント) | ラテン文字(Zalgo) |
| フィンランド語 | ○ | ○(フォルマントバリアント) | ラテン文字(Zalgo) |
| アイスランド語 | ○ | ○(フォルマントバリアント) | ラテン文字(Zalgo) |
| ベトナム語 | ○ | ○(フォルマントバリアント) | ラテン文字(Zalgo) |
| インドネシア語 | ○ | ○(フォルマントバリアント) | ラテン文字(Zalgo) |
| マレー語 | ○ | ○(フォルマントバリアント) | ラテン文字(Zalgo) |
| ルーマニア語 | ○ | ○(フォルマントバリアント) | ラテン文字(Zalgo) |
| ロシア語 | ○ | ○(フォルマントバリアント) | **キリル文字(実際の文字体系)** |
| タイ語 | ○ | ○(フォルマントバリアント) | **タイ文字(実際の文字体系)** |
| アラビア語 | ○ | ○(フォルマントバリアント) | **アラビア文字(実際の文字体系)** |
| ヘブライ語 | ○ | ○(フォルマントバリアント) | **ヘブライ文字(実際の文字体系)** |

女性ボイスには2種類の由来があります。

- **MBROLA**: [MBROLA](http://tcts.fpms.ac.be/synthesis/mbrola.html) エン
  ジン経由の専用音声データで、実際に音声合成が成功することを実機で確認で
  きた英語・フランス語・ドイツ語・ハンガリー語・スウェーデン語・トルコ語・
  ポルトガル語(ブラジル)・ポルトガル語(ポルトガル)の8言語のみ
  対応しています(セットアップ節の `mbrola-*` パッケージが必要)。素の
  ままだとやや低めに聞こえたため、espeak-ngの `-p`(ピッチ)オプションで
  通常より高めに補正しています(`config.FEMALE_VOICE_PITCH`)。
- **フォルマントバリアント**: 上記以外の12言語は、espeak-ng本体に内蔵さ
  れている `+f3` という「女性寄りのフォルマント変換」を任意のボイスコード
  に付け足すだけで使っています(`tts_extreme` の奇妙な声バリエーションと
  同じ仕組み)。MBROLAの専用データが存在しない/壊れている言語でも追加
  パッケージ無しに音程の異なる声を用意でき、実機のf0(基本周波数)計測で
  素の声(約108Hz)から約194Hzへ明確に上がることを確認済みです。これ自体
  で十分な高さになるため、MBROLA用の `-p` ピッチ補正は重ねて適用していま
  せん(重ねると約258Hzまで上がりすぎることを実機で確認したため)。
  中国語(標準語)はMBROLA(`mb-cn1`)がパッケージ自体の不具合で動かない
  問題がありましたが(詳細は「ハマった罠」の11番)、このフォルマント
  バリアント方式で回避し女性ボイスに対応できています。

`--voice random` で選ばれた言語/性別は、動画説明文に
`Voice: French (Female)` のように明記されます。

20言語のうち4言語が「実際の文字体系」を使う言語(後述)で、残る16言語が
従来のラテン文字(Zalgo)系のため、均等抽選のままだと実際の文字体系側が
過半数を占めてしまいます。そのため `--voice random` は2段階抽選になって
おり、まず `config.NATIVE_SCRIPT_VOICE_CHANCE`(デフォルト30%)の確率で
「実際の文字体系」か「ラテン文字(Zalgo)」かを決め、その中から言語を均等
抽選します(`generate.py _resolve_voice()`)。

なお `generate.py` 自体のデフォルト(`--voice` 未指定時)は引き続き `en`
固定ですが、`generate.yml`(GitHub Actions)側の `voice` 入力のデフォルト
は `random` にしているため、手動実行やcron-job.org等からの自動実行で
`voice` を明示的に指定しない場合は多言語・女性ボイスのランダム選択が有効
になります。

### 現地語ハッシュタグ

`--upload` 時、選ばれた言語に応じて動画説明文の末尾へ「発音」を意味する
現地語のハッシュタグ(例: アラビア語なら `#نطق`)を1つ追加します
(`config.VOICE_LANGUAGES` の `"hashtag_word"`、`generate.py
_youtube_metadata()` の `lang_code` 引数)。英語の `#Pronunciation` 等の
固定ハッシュタグは英語圏の視聴者しか拾えないため、その言語の話者が母語の
まま検索・タグ経由で見つけられるようにする狙いです。YouTubeのタグ
(`tags`)にも同じ語を追加しています。

英語自身は既に `#Pronunciation` があるため対象外(`hashtag_word` が
`None`)で、従来通り固定の英語ハッシュタグのみになります。訳語は一般的な
「発音」の意味で選んでいますが、機械的な検証はできないため、正確さが
重要な場合はネイティブ話者の確認を推奨します。

### タイトル・タグへの言語名追加(英語検索向け)

上記の現地語ハッシュタグはその言語の話者が母語のまま検索した場合の導線
でしたが、逆に**英語で「french pronunciation」のように言語名込みで検索する
視聴者**向けの導線も用意しています。言語が判明している回(`lang_code` が
渡された場合)は、タイトルに `in French?` のように言語名を追加し
(`generate.py _youtube_metadata()`)、YouTubeのタグにも `french
pronunciation` のような小文字の語を追加します。タイトルは検索結果・
サムネイル一覧での表示で重み付けが大きいため、タグ単体より効果を期待して
います。

英語(`lang_code="en"`)はこのチャンネルの既定言語という扱いのため、
`in English?` のような冗長な追加はしません。

### 説明文への検索キーワード追加

上記の言語名(A/B)とは違う切り口の検索キーワードとして、`tongue
twister`(早口言葉)・`language learners` という語を含む一文を、言語が
判明しているかどうかに関わらず常に説明文へ入れています。あわせてタグにも
`tongue twister` を追加します。他の施策と競合しない、追加コストの小さい
検索流入策です。

### 視聴者属性ベースの現地語キーワード(`config.AUDIENCE_REGION_PHRASES`)

上記の現地語ハッシュタグ・言語名追加はいずれも「その動画自体のボイス言語」
に連動する施策でしたが、こちらはYouTube Studioの視聴者属性(アナリティ
クス)で継続的に上位に入っているフィリピン・インドネシア・マレーシア向け
に、動画のボイス言語とは無関係に**全動画で共通して**「どう発音する?」に
相当する現地語フレーズ(`paano bigkasin` / `cara mengucapkan` / `cara
sebut`)を説明文へ追加するものです。フィリピン語(タガログ語)はespeak-ng
非対応のためボイス自体は生成できません(「ハマった罠」の14番)が、これは
音声合成とは無関係な説明文のテキスト追加のため影響を受けません。

### 実際の文字体系を使う言語

上記16言語は「土台の文字(ラテン文字・Zalgo)自体は変えず、読み上げ言語だ
けを変える」機能でしたが、ロシア語・タイ語・アラビア語・ヘブライ語の
4言語は**単語自体をその言語の実際の文字からランダムに生成**します
(`word_generator.random_script_word()` /
`random_abugida_word()`)。西洋圏の視聴者にとって文字自体が読めない、
より直接的な「発音不能」感を狙っています。実在する単語ではなく、各言語
の文字をランダムに組み合わせた造語です。

その言語の話者が見て「これは単語として意味を成さない」と誤解しないよう、
`--upload` 時はこれらの回に限り動画説明文へ
`(This is a randomly generated sequence of letters, not a real word in that
language!)` という一文を自動で付け加えます(`generate.py _youtube_metadata()`
の `is_native_script` 引数)。Zalgo単語(ラテン文字+結合文字)は見た目から
して実在の単語でないことが明らかなため対象外です。

**動画フレーム自体にも同じ注記を焼き込む**: 説明欄の注記だけでは、実際に
その言語の話者から「発音が間違っている」という誤解のコメントが付いた
(Shorts視聴者の多くは説明欄を開かないため)。そこで`frame_builder.
build_frame()`にも`is_native_script`引数を渡し、フレーム下部のサブテキスト
を`[Mode / Unpronounceable word]`から`[Mode / Not a real word!]`に切り替える
(`frame_builder._sub_label()`)。説明欄と違って動画本体は視聴時に必ず目に
入るため、より確実に伝わる。

文字体系の構造によって、2種類の生成方式を使い分けています。

- **`random_script_word()`(クラスター方式)**: ロシア語・アラビア語・
  ヘブライ語で使用。その言語の文字をランダムに選び、一定確率で同じ文字を
  連打する(子音クラスターのような見た目を作る)、Zalgo単語の生成ロジック
  と似た方式です。文字1つ(アラビア文字・ヘブライ文字は子音/アルファベッ
  ト、ロシア語はキリル文字のアルファベット)がそのまま単独で成立する文字
  体系向けです。Zalgoの結合文字・装飾記号は使いません(英語音声での無音
  確認しか取れていないため)。
- **`random_abugida_word()`(アブギダ方式)**: タイ語で使用。子音字+母音
  記号(前後左右に付く、単体では使わない)で初めて1音節が成立する
  「アブギダ」と呼ばれる文字体系のため、子音→(確率的に)母音記号、を
  繰り返して音節列を作る専用ロジックが必要です。子音字だけを並べると、
  その言語の正書法として不完全な文字列になってしまいます(元々タイ語専用
  だった`random_thai_word()`を一般化したもの。詳細は「ハマった罠」の12番
  を参照してください。汎用ロジックとしては複数の子音・母音記号プールを
  受け取れる作りのまま残しています)。

`config.VOICE_LANGUAGES` の各言語エントリで文字体系の種類
(`"script": "cluster"` / `"abugida"`)と対応する文字プール
(`"chars"`、または `"consonants"`/`"vowels"`)を管理しており、
アラビア語・ヘブライ語の2言語は、手打ちでは非現実的な文字数のため
`config._assigned_chars()`でUnicodeのコードポイント範囲から未割り当て
文字を除いて機械的に文字プールを作っています(ロシア語・タイ語の2言語は
元々手打ちのリストのまま)。

対応言語はいずれもChromium+Notoフォントでの描画、espeak-ngでの音声合成
の両方が実機で正常に動作することを確認済みです
(`unicodedata.name()`/`category()`で全コードポイントが対象言語の正式な
文字であることを個別に確認し、豆腐(未割り当てコードポイントの空白矩形)
ではないことも目視で確認済みです)。

## YouTubeへの自動アップロード

`--upload` は [YouTube Data API v3](https://developers.google.com/youtube/v3)
を使って、生成した動画をそのままチャンネルへアップロードします。GitHub
Actionsのようなブラウザ操作ができない環境でも動かせるよう、あらかじめ一度
だけ取得しておいたOAuthリフレッシュトークンを使い回す方式にしています。

### 1. Google Cloud側の準備(初回のみ)

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェク
   トを作成し、「YouTube Data API v3」を有効化する。
2. 「OAuth同意画面」を設定する(公開ステータスは「テスト」のままでよい。
   その場合はアップロード先チャンネルのGoogleアカウントを「テストユー
   ザー」に追加すること)。
3. 「認証情報」→「OAuthクライアントIDを作成」で、種類は**デスクトップ
   アプリ**を選んで作成する(クライアントID・シークレットが発行される)。

### 2. リフレッシュトークンの取得(初回のみ、ローカルで実行)

> **⚠️ 1つのGoogleアカウントで複数のYouTubeチャンネル(ブランドアカウン
> ト)を持っている場合は要注意**。次のコマンドを実行すると、**その時点で
> ブラウザ上のYouTubeでアクティブになっているチャンネル**にアップロード
> 権限が発行されます。意図しないチャンネルがアクティブなまま実行すると、
> 気づかないままそちらにアップロードされてしまいます。
>
> 先に https://www.youtube.com を開き、右上のアカウントアイコン→
> 「アカウントを切り替える」でアップロード先のチャンネル(例:
> `@Unpronounceable-word`)に切り替えてから、**同じブラウザで**下記コマ
> ンドを実行してください。

```bash
pip install -r requirements-dev.txt
python3 get_youtube_refresh_token.py --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
```

ブラウザでの認可が終わると、`YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET`
/ `YOUTUBE_REFRESH_TOKEN` の3つに加え、**実際に認可されたチャンネル名と
チャンネルID**が標準出力に表示される。ここでチャンネル名が意図したものか
必ず確認すること。

### 3. GitHub Secretsへの登録

リポジトリの Settings → Secrets and variables → Actions で、以下をSecret
として登録する。

| Secret名 | 必須 | 内容 |
|---|---|---|
| `YOUTUBE_CLIENT_ID` | ○ | OAuthクライアントID |
| `YOUTUBE_CLIENT_SECRET` | ○ | OAuthクライアントシークレット |
| `YOUTUBE_REFRESH_TOKEN` | ○ | 手順2で取得したリフレッシュトークン |
| `YOUTUBE_CHANNEL_ID` | 任意(強く推奨) | アップロード先として想定しているチャンネルID(`UC...`)。手順2の出力に表示されたものを使う。設定しておくと、認証されたチャンネルがこれと一致しない場合にアップロード前でエラーになり、誤ったチャンネルへの投稿を防げる |
| `YOUTUBE_REFRESH_TOKEN_ISSUED_AT` | 任意(強く推奨) | 手順2を実行した日付(`YYYY-MM-DD`)。手順2の出力に表示されたものを使う。設定しておくと、OAuth同意画面が「テスト」ステータスの場合の既知の7日失効ルールが近づいた/過ぎた際に実行ログへ警告が出る(下記「リフレッシュトークンの失効監視」を参照) |
| `YOUTUBE_SHORTS_PLAYLIST_ID` | 任意 | 設定しておくと、アップロードした各Shortsをこの再生リストに自動追加する(下記「再生リストへの自動追加」を参照) |
| `YOUTUBE_COMPILATION_PLAYLIST_ID` | 任意 | 設定しておくと、結合動画をこの再生リストに自動追加する |

### 4. 実行

- ローカル: `python3 generate.py --upload` (環境変数として上記をセットし
  ておく)
- GitHub Actions: Actions タブ → **generate** ワークフロー →
  **Run workflow**。`upload` 入力はデフォルトで有効、`privacy_status` の
  デフォルトは `public`(アップロード直後から誰でも視聴・検索可能)。テス
  ト目的で公開したくない場合は `unlisted` / `private` を選ぶか、`upload`
  をオフにして動画だけ生成しArtifactとしてダウンロードすることもできる。

### 5. リフレッシュトークンの失効監視

OAuth同意画面の公開ステータスを「テスト」のままにしている場合(このリポジ
トリのデフォルトの想定)、リフレッシュトークンは**発行から7日で失効**しま
す(スコープに`name`/`email`/`profile`以外を含むアプリのGoogle側の仕様。
「本番環境」へ切り替えれば無期限にできますが、`youtube`スコープはGoogleの
検証プロセス(場合によっては有料のセキュリティ監査)が必要になるため、個
人利用の規模では現実的でないことが多いです)。

`YOUTUBE_REFRESH_TOKEN_ISSUED_AT` を登録しておくと、`youtube_upload.get_youtube_client()`
(`--upload`・`compile_shorts.py`のどちらからも通る共通経路)が発行日から
の経過日数をチェックし、以下のタイミングでワークフローのログに警告
(`::warning::`)を出します(処理自体は止めません)。

- 5日経過: 「そろそろ再発行してください」の予告
- 7日経過: 「おそらく失効しています」の警告(この時点でアップロードが
  `invalid_grant` 等で失敗し始めている可能性があります)

再発行が必要になったら、`get_youtube_refresh_token.py` を再実行し、
`YOUTUBE_REFRESH_TOKEN` と `YOUTUBE_REFRESH_TOKEN_ISSUED_AT` の両方を
新しい値に更新してください。

### 6. APIクォータ使用量のログ

`--upload` 実行後(全動画処理後に1回)と `compile_shorts.py` 実行後に、
その回で消費したYouTube Data APIクォータの概算と残容量目安を実行ログへ
出力します(`youtube_upload.log_api_usage_summary()`)。GCP Consoleのクォー
タ画面を都度開かなくても、ワークフローのログだけで「あとどれくらいアップ
ロードできそうか」を把握できます。

### 7. 再生リストへの自動追加(任意)

`YOUTUBE_SHORTS_PLAYLIST_ID` / `YOUTUBE_COMPILATION_PLAYLIST_ID` を設定
しておくと、アップロードした動画をそれぞれの再生リストに自動追加します
(`youtube_upload.add_to_playlist()`)。Shortsと結合動画(横型の通常動画)
は画面比率・視聴モードが異なるため、あえて別々の再生リストに分けられる
ようにしています(1つのリストに混在させると視聴体験が途切れやすいため)。

再生リスト自体は事前にYouTube Studioで手動作成しておく必要があります
(自動作成はしません)。作成した再生リストのURL
(`https://www.youtube.com/playlist?list=PLxxxxxxxx`)の`list=`以降の
文字列がプレイリストIDです。

再生リストへの追加が失敗しても、動画本体のアップロードは既に成功して
いるため、警告(`[Warning]` / `::warning::`)を出すだけで処理全体は止め
ません。

### 8. 概要欄の登録CTA

アナリティクスで新規視聴者97%超・コア視聴者0.1%未満という偏りが見えた
ため、`generate.py`がアップロードする全Shortsの概要欄末尾に、常に
「🔔 Subscribe for a new unpronounceable word every day!」という登録を
促す一文を自動で入れています(`_youtube_metadata()`。`YOUTUBE_SHORTS_
PLAYLIST_ID`の設定有無に関わらず入ります)。

### 9. 手動字幕(`upload_caption()`)とカテゴリ変更(SEO)

**カテゴリ**: `videos.insert`の`categoryId`は、従来固定していた
`24`(Entertainment)から`26`(Howto & Style)に変更しました
(`config.YOUTUBE_CATEGORY_ID`)。「How to Pronounce」系は検索意図として
ハウツー寄りとも言えるための実験的な変更で、効果自体は未検証です。

**手動字幕**: espeak-ngが読み上げる単語はでたらめな文字列のため、字幕を
付けずにYouTubeの自動文字起こし(ASR)に任せると意味不明な字幕が生成され、
検索インデックス対象になり得るテキスト枠が無駄になります。そこで、動画
アップロード成功後に`youtube_upload.upload_caption()`で、説明文と同じ
趣旨のキーワード付き固定テキスト(例: `How to pronounce "voOn" in French.
A tongue twister and pronunciation challenge — try saying it out loud!`)
を1キューだけのSRT字幕として手動アップロードします。字幕アップロードが
失敗しても動画自体は既に公開済みなので、警告に留めて処理は止めません
(`generate.py`)。

> **⚠️ `config.CAPTIONS_ENABLED = False`で現在は無効化中**: 実機で
> 断続的な403 forbidden(下記参照)を確認したため一時的にオフにして
> います。有効化するには`config.CAPTIONS_ENABLED`を`True`に戻してください
> (「ハマった罠」の21番参照)。

> **⚠️ `captions.insert`は`youtube.force-ssl`スコープが必要**: 他の
> API呼び出し(`videos.insert`/`playlistItems.insert`等)は`youtube`
> フルアクセススコープでカバーできますが、字幕のアップロードだけは別途
> `youtube.force-ssl`が必要です。既存のリフレッシュトークンにこのスコー
> プが無い場合、字幕アップロードだけが失敗します(動画本体のアップロード
> 自体は成功する。この分離のためにupload_caption()は意図的に
> `get_youtube_client(scopes=None)`を使っています。「ハマった罠」の19番
> 参照)。反映するには以下の両方が必要です。
>
> 1. Google Cloud Console→「OAuth同意画面」→「データアクセス」→
>    「スコープを追加または削除」で`.../auth/youtube.force-ssl`を追加
>    登録する(手順1と同じ画面。登録していないスコープはリクエストしても
>    正しく付与されないことがある)
> 2. `get_youtube_refresh_token.py`を再実行してリフレッシュトークンを
>    取得し直し、`YOUTUBE_REFRESH_TOKEN`を更新する(手順2・3と同じ手順。
>    `SCOPES`は既にこのスコープを含む形に更新済み)

> **⚠️ クォータコストが大きい**: `captions.insert`は1回あたり**400
> units**と、`videos.insert`(100 units)の4倍のコストです。1日あたりの
> 投稿数を増やす場合は、日次クォータ上限(`config.DAILY_QUOTA_UNITS`、
> デフォルト10,000 units)により早く近づく点に注意してください(実行ログ
> の「APIクォータ使用量のログ」で都度確認できます)。

### 10. 運営者コメントの自動投稿・音声言語メタデータ・タイトルの日本語ローカライズ(SEO)

**運営者コメント**: 動画アップロード成功後、`youtube_upload.post_comment()`
で字幕と同じキーワード付きテキストを運営者自身のコメントとして自動投稿し
ます(`config.COMMENT_ON_UPLOAD_ENABLED`でON/OFF可能、デフォルトTrue)。
運営者のコメントは通常のコメントより目立つ表示になるため、視聴者の目に
留まりやすくする狙いです。コメント投稿が失敗しても動画自体は既に公開済み
なので、警告に留めて処理は止めません(`generate.py`)。

> **⚠️ `commentThreads.insert`も`youtube.force-ssl`スコープが必要**:
> `captions.insert`と同じスコープのため、既にスコープ登録・トークン再発行
> 済みであれば追加作業は不要です。ただし同じスコープで`captions.insert`が
> 断続的に403 forbiddenになった実績があるため(「ハマった罠」21番)、
> コメント投稿も同様に不安定になる可能性があります。問題が続く場合は
> `config.COMMENT_ON_UPLOAD_ENABLED`を`False`にしてください。
>
> なお、YouTube Data APIにはコメントを「固定表示(ピン留め)」する専用
> エンドポイントが無いため、`post_comment()`は投稿するところまでが範囲
> です。ピン留めしたい場合はYouTube Studioから手動で行ってください。

**音声言語メタデータ**: `videos.insert`の`snippet.defaultAudioLanguage`に、
espeak-ngで実際に読み上げた言語(`config.VOICE_LANGUAGES`のキー、例:
`"fr"`)を設定します(`generate.py`。glitchモードは単語を読み上げないため
設定しません)。タイトル・タグへの言語名追加(前述)とは別軸で、YouTube
側の言語ベースのマッチングに効かせる狙いです。あわせて`snippet.
defaultLanguage`にも常に`"en"`(`config.DEFAULT_LANGUAGE`)を設定し、
タイトル・説明文自体の言語を明示します。既存の`videos.insert`呼び出しに
フィールドを追加するだけなので、追加のAPI呼び出し・クォータ消費はありません。

**タイトルのローカライズ**: `videos.insert`の`localizations`フィールドに、
視聴者のYouTube表示言語ごとに出し分けるタイトルを設定します。動画本体・
音声・説明文・英語タイトル自体は変わらず、YouTube側が視聴者の表示言語
設定に応じてタイトルだけを出し分ける仕組みです。「海外向けのノリ」という
動画コンテンツ自体の方針とは別軸で、あくまで表示言語をYouTube側の視聴者
設定に合わせるだけの施策のため、コンテンツ方針とは衝突しません。
`captions.insert`/`commentThreads.insert`と異なり`youtube.force-ssl`は
不要で(`videos.insert`と同じ`youtube`/`youtube.upload`スコープで完結)、
追加のAPI呼び出し・クォータ消費もありません。

- **日本語**(例: `「voOn」の発音は?(フランス語) #Shorts`): `config.
  LANGUAGE_LABELS_JA`で言語名の注記付き。`config.
  JAPANESE_TITLE_LOCALIZATION_ENABLED`でON/OFF可能(デフォルトTrue)。
- **フィリピン語(`fil`)・インドネシア語(`id`)・マレー語(`ms`)**
  (例: `Bagaimana cara mengucapkan "voOn"? #Shorts`): `config.
  AUDIENCE_REGION_PHRASES`(説明文で既に使っている、視聴者属性で継続的に
  上位に入っている3言語)と同じフレーズをそのまま流用しています。誤訳の
  リスクを避けるため、日本語版のような「(言語名)」の注記は付けていません。
  `config.EXTRA_TITLE_LOCALIZATIONS`にテンプレートを追加すれば言語を
  増やせます。`config.EXTRA_TITLE_LOCALIZATION_ENABLED`でON/OFF可能
  (デフォルトTrue、日本語版とは独立したトグル)。

いずれも、埋め込む単語(label)がヘブライ語・アラビア語のようなRTL文字
体系の場合に表示順が入れ替わる不具合(「ハマった罠」24番)への対策として、
labelをbidi isolate文字(U+2068〜U+2069)で囲んでいます。

## Shorts結合動画

アップロードしたShorts動画の履歴(`upload_history.json`)が10本たまるごと
に、それらの動画本体をGitHub Actionsアーティファクトから取得し直して
1本の横型(16:9)動画に結合し、「通常動画」として自動でアップロードします
(`compile_shorts.py`。generateワークフローの中で `--upload` 使用時に自動
実行されます。動画本体の取得元については「ハマった罠」の8番を参照)。

**なぜ「結合」が必要か**: YouTubeはShorts判定を投稿者の意図ではなく
「アスペクト比(縦型)+尺(3分以内)」だけで機械的に行います。縦型のShorts
を単純に何本かつなげても、合計尺が短いままだと縦型ゆえに依然Shorts扱いに
なってしまいます。そのため結合時は各クリップを横型(16:9)キャンバスの
中央に配置し、左右を無地の帯で埋める(ピラーボックス)ことで、確実に
「通常動画」として扱われるようにしています。

**状態管理**: どのShortsを結合に使ったか(`compiled_video_ids`)、恒久的に
取得できず諦めたか(`skipped_video_ids`)は `compilation_state.json` に、
アップロード成功履歴は `upload_history.json` に記録し、どちらもワークフ
ローの最後にリポジトリへコミットします(GitHub Actionsのランナーはジョブ
ごとに使い捨てのため、ここに記録しないと10本のカウントが毎回リセットされ
てしまいます)。動画が削除・非公開化・著作権クレーム等で取得できなくなっ
た場合も、その1本のせいで結合処理全体が永久に止まらないよう、リトライ後
に諦めた動画は `skipped_video_ids` に記録して以後の結合対象から除外しま
す。

**投稿日時の記録**: `upload_history.json` の各エントリには、アップロード
成功直後(UTC)のタイムスタンプが `uploaded_at`(ISO 8601形式)として
記録されます(`upload_history.append_upload()`)。曜日・時間帯別の集計
など、投稿日時を使った分析に利用できます。この項目を追加する前に記録
された古いエントリには `uploaded_at` キー自体が存在しないため、参照する
際は `entry.get("uploaded_at")` を使ってください。

**元Shortsへのリンク追記(回遊導線)**: 結合動画のアップロード成功後、結合
元になった各Shortsの概要欄末尾に、その結合動画へのリンクを自動追記します
(`youtube_upload.append_video_description()`)。ランダムな単語を1本だけ
見て離脱する視聴者が多い(新規視聴者97%超・コア視聴者0.1%未満、というのが
実際のアナリティクスの傾向でした)ため、「他の単語もまとめて見られる」導線
を後付けで用意し、回遊・チャンネル登録につなげる狙いです。1本の追記に
失敗しても(動画削除等)他のShortsや結合動画自体には影響せず、警告ログの
みで処理を続行します。

ローカルで手動実行する場合:

```bash
python3 compile_shorts.py --privacy-status unlisted
```

(YouTube側の認証は `--upload` と同じ `YOUTUBE_CLIENT_ID` /
`YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REFRESH_TOKEN` 環境変数を使う。
`YOUTUBE_REFRESH_TOKEN_ISSUED_AT` を設定していれば失効監視も同様に働く。
加えて、動画本体の取得にGitHub Actions APIを使うため `GITHUB_TOKEN`
[Personal Access Token(`actions:read`権限が必要)] と `GITHUB_REPOSITORY`
[例: `2000Re/CanYouSayThis`] の環境変数も必要。GitHub Actionsのワークフロー
内では両方とも自動で設定されるため、この指定はローカル実行時のみ必要)

## モード別パフォーマンス集計(`youtube_analytics.py`)

[YouTube Analytics API](https://developers.google.com/youtube/analytics)を
使って、アップロード済みの各Shortsの再生数・視聴維持率を取得し、
`upload_history.json`の`mode`(`tts`/`tts_extreme`/`glitch`)と突き合わせて
集計します。`--mode random`の抽選比率(`config.MODE_WEIGHTS`)を「glitchは
単語を読み上げないので説得力が弱い」という主観だけで下げた判断を、後から
データで裏付け・再調整するために用意しました。

**投稿タイミングの影響を正規化した指標を使う**: 生の再生数だけで比較すると、
YouTubeのアルゴリズムによる展開は投稿からの経過日数に強く依存するため、
新しい動画ほど不利になるノイズが乗ります(投稿一覧の再生数が投稿日と強く
相関していた、という実際の観察に基づく)。そのため「投稿から何日視聴可能
だったか」で正規化した1日あたり再生数(`avg_views_per_day`)を主指標として
います(`_days_available()` / `summarize_by_mode()`参照)。

```bash
python3 youtube_analytics.py                # 過去28日間を集計(デフォルト)
python3 youtube_analytics.py --days 14       # 過去14日間を集計
python3 youtube_analytics.py --start-date 2026-09-01 --end-date 2026-09-19
python3 youtube_analytics.py --days 90 --by-week  # 週別の推移も出力(下記参照)
```

出力例:

```
=== モード別 再生数・視聴維持率集計(2026-08-22 〜 2026-09-19、対象87本) ===
  tts: 35本 / 1日あたり平均12.40回(単純平均210.5回, 視聴維持率38.2%)
  tts_extreme: 34本 / 1日あたり平均11.80回(単純平均195.3回, 視聴維持率41.0%)
  glitch: 18本 / 1日あたり平均7.10回(単純平均88.9回, 視聴維持率22.5%)
```

**投稿週別の推移(`--by-week`)**: モード別の集計とは別に、投稿週(月曜始まり)
ごとの1日あたり再生数の推移を見たい場合は`--by-week`を付けます。
`avg_views_per_day`は経過日数で正規化済みのため、新しい週と古い週を並べても
「まだ新しいから少ない」というノイズを受けにくく、この手のネタ系コンテンツ
にありがちな「視聴者が数本見るとパターンが分かって反応が落ちる」という長期
的な「飽き」傾向の有無を確認するのに使えます。傾向を見るのが目的のため、
`--days`は長め(90等)にするのが望ましいです。

```
=== 週別(月曜始まり) 1日あたり再生数の推移(2026-06-22 〜 2026-09-19) ===
  2026-06-22〜: 14本 / 1日あたり平均18.20回(単純平均240.1回, 視聴維持率35.0%)
  2026-06-29〜: 21本 / 1日あたり平均15.60回(単純平均205.3回, 視聴維持率34.1%)
  ...
```

**読み上げ言語別の集計(`--by-voice`)**: `--voice random`で実際に読み上げに
使った言語(`lang_code`)別の1日あたり再生数・視聴維持率を見たい場合は
`--by-voice`を付けます。`--voice random`の抽選比率調整(どの言語を優遇/
除外するか)の判断材料にする用途です。`lang_code`は`upload_history.json`に
この項目を追加した以降にアップロードされた`tts`/`tts_extreme`の動画にしか
記録されていない(`glitch`は単語を読み上げないため対象外)ため、当面は
サンプルが少ない状態から始まります。

```
=== 言語別(--voice random) 再生数・視聴維持率集計(2026-08-22 〜 2026-09-19) ===
  French (fr): 12本 / 1日あたり平均14.30回(単純平均180.2回, 視聴維持率39.5%)
  Arabic (ar): 8本 / 1日あたり平均9.10回(単純平均102.4回, 視聴維持率44.0%)
  ...
```

**必要な環境変数**: `--upload`/`compile_shorts.py`と同じ`YOUTUBE_CLIENT_ID`/
`YOUTUBE_CLIENT_SECRET`/`YOUTUBE_REFRESH_TOKEN`を使いますが、
`YOUTUBE_REFRESH_TOKEN`は`yt-analytics.readonly`スコープを含めて**発行し
直したもの**である必要があります。OAuthのリフレッシュトークンはスコープが
発行時に焼き付けられる仕様のため、既存のトークンのままではスコープ不足で
失敗します。手順:

1. Google Cloud Consoleで、プロジェクトの「APIとサービス」→「ライブラリ」
   から「YouTube Analytics API」を有効化する(YouTube Data API v3とは別の
   APIとして個別に有効化が必要)
2. 「OAuth同意画面」→「データアクセス」→「スコープを追加または削除」で
   `.../auth/yt-analytics.readonly`を追加する
3. `get_youtube_refresh_token.py`(このスコープを含む`SCOPES`に更新済み)
   を再実行し、新しい`YOUTUBE_REFRESH_TOKEN`を取得してGitHub Secrets/
   ローカルの環境変数を上書きする(`YOUTUBE_CLIENT_ID`/`SECRET`は変更不要)

> **⚠️ `google.auth.exceptions.RefreshError: invalid_scope`が出る場合**:
> ほぼ確実に、手順3を実行した時点のローカルのリポジトリが古く(この
> `yt-analytics.readonly`追加より前のコードのまま)、発行されたリフレッシュ
> トークンにこのスコープが乗っていないのが原因です。`git pull origin main`
> で最新化してから手順3をやり直し、ブラウザの同意画面に「YouTube
> Analyticsのレポートを表示する」等の権限項目が表示されることを確認して
> ください。

**GitHub Actionsから実行する場合**: `.github/workflows/analytics.yml`
(workflow_dispatch)から手動実行できます。`generate.yml`と同じ
`YOUTUBE_CLIENT_ID`/`YOUTUBE_CLIENT_SECRET`/`YOUTUBE_REFRESH_TOKEN`の
Secretsをそのまま使うため、追加のSecrets登録は不要です(上記の手順3で
`YOUTUBE_REFRESH_TOKEN`をyt-analytics.readonlyスコープ込みのものに更新
済みであること)。`days`(デフォルト28)、または`start_date`/`end_date`、
`by_week`(trueで週別推移も出力)を入力して実行すると、集計結果がActionsの
ログに出力されます。

**注意**: `youtube_analytics.py`のAPI呼び出し部分は、GitHub Actions経由で
本物のGoogle認証情報を用いて複数回実行し、動作確認済みです
(2026-09-19〜)。ただしYouTube Analytics APIのデータには通常1〜2日程度の
ラグがあり、リフレッシュトークン再発行直後は特に反映が遅れて見えることが
あるため、直近の投稿ほど過小評価されやすい点に注意してください。

## 即時統計の確認(`youtube_quick_stats.py`)

`youtube_analytics.py`(YouTube Analytics API)の1〜2日ラグを避けて、
投稿直後の初動を素早く確認したい場合に使います。[YouTube Data API]
(https://developers.google.com/youtube/v3)の`videos.list(part=statistics)`
は、視聴ページ/YouTube Studioの「コンテンツ」タブに表示されているのと同じ
即時反映の公開再生数・高評価数・コメント数を返します
(`youtube_upload.fetch_video_stats()`)。

```bash
python3 youtube_quick_stats.py                # 過去24時間にアップロードした動画
python3 youtube_quick_stats.py --hours 6       # 過去6時間
```

出力例:

```
=== 直近24時間の投稿(8本)の即時統計 ===
  abc123 [tts] )oav҈lrE: 再生142回 / 高評価3 / コメント1
  def456 [glitch] voOn: 再生58回 / 高評価0 / コメント0
  ...
```

`youtube_analytics.py`と違い、投稿からの経過日数による正規化
(`avg_views_per_day`のような主指標)は行いません。あくまで「今の生の値」を
素早く見るための軽量ツールで、モード間の公平な比較には引き続き
`youtube_analytics.py`を使ってください。必要な環境変数・GitHub Actions
(`.github/workflows/quick_stats.yml`、`hours`入力で実行)は`youtube_analytics.py`
と同じで、追加のSecrets登録・スコープは不要です。

## 流入元の確認(`youtube_traffic_source.py`)

`youtube_quick_stats.py`等で「他の動画より明らかに伸びている」動画を見つけた
際、それが関連動画のおすすめに乗ったのか・ホーム/Shortsフィードでの露出が
増えたのか・検索/外部(SNS等)からの流入かを切り分けるための診断ツールです。
[YouTube Analytics API](https://developers.google.com/youtube/analytics)の
`insightTrafficSourceType`ディメンションで、動画1本の流入元別再生数を
取得します。

```bash
python3 youtube_traffic_source.py --video-id mFGTwTBPy7Q            # 過去28日間
python3 youtube_traffic_source.py --video-id mFGTwTBPy7Q --days 7   # 過去7日間
```

出力例:

```
=== 動画 mFGTwTBPy7Q の流入元別再生数(2026-08-26 〜 2026-09-23、合計1070回) ===
  関連動画のおすすめ(RELATED_VIDEO): 700回 (65.4%)
  YouTube内検索(YT_SEARCH): 200回 (18.7%)
  外部サイト/SNSのリンク(EXT_URL): 170回 (15.9%)
```

**検索クエリの確認(`--search-queries`)**: `YT_SEARCH`経由の流入があった
場合、実際にどんな検索語で見つかったかも見たい場合は`--search-queries`を
付けます。`insightTrafficSourceDetail`ディメンションを`insightTrafficSourceType
==YT_SEARCH`でフィルタして取得する仕様で(YouTube Analytics APIの仕様上、
このdetailディメンションは`insightTrafficSourceType`を**フィルタとして
固定した場合のみ**、その値に応じた詳細を返す)、`insightTrafficSourceType`
と**同じAPI・同じ`yt-analytics.readonly`スコープ**で完結します。追加の
スコープ登録・Secrets追加は不要です。

```bash
python3 youtube_traffic_source.py --video-id mFGTwTBPy7Q --search-queries
```

```
=== 動画 mFGTwTBPy7Q のYT_SEARCH経由の検索クエリ別再生数 ===
  「how do you pronounce zalgo words」: 200回
  「unpronounceable word generator」: 170回
```

タイトル・タグ・ハッシュタグの施策(「タイトル・タグへの言語名追加」等)が
実際にどんな検索語でのヒットにつながっているかを直接確認でき、次の
SEO施策(タイトルの言い回しの調整等)の材料にできます。

`youtube_analytics.py`と同じAnalytics APIを使うため、投稿から1〜2日程度の
反映ラグがある点に注意してください(「ハマった罠」18番参照。投稿直後の
動画では初動チェックに`youtube_quick_stats.py`を使い、流入元の内訳は数日
おいてからこちらで確認するのが向いています)。必要な環境変数・GitHub Actions
(`.github/workflows/traffic_source.yml`、`video_id`/`days`/`search_queries`
入力で実行)は`youtube_analytics.py`と同じで、追加のSecrets登録・スコープは
不要です。

## 日本語ローカライズが崩れて表示された動画の手動修正(`youtube_fix_localization.py`)

「ハマった罠」24番のbidi(双方向文字)修正は新規アップロード分にしか
効かないため、修正前に公開した動画(ヘブライ語・アラビア語の回)の日本語
ローカライズタイトルは崩れたままです。`videos.update`(`part=localizations`)
で個別に直すためのバックフィルツールです。

```bash
python3 youtube_fix_localization.py --video-ids ABC123,DEF456
```

現在のタイトルから`「」`で囲まれた部分(label)を正規表現で取り出し、その
部分だけをbidi isolate文字(U+2068〜U+2069)で囲み直して`videos.update`
します。既に修正済み(囲み済み)の動画や`localizations.ja`が無い動画は
スキップします。`videos.insert`と同じ`youtube`/`youtube.upload`スコープ
(`get_youtube_client()`のデフォルト)で完結するため、`youtube.force-ssl`
や`yt-analytics.readonly`の追加登録は不要です。必要な環境変数・GitHub
Actions(`.github/workflows/fix_localization.yml`、`video_ids`入力で実行)
は他のワークフローと共通です。

## YouTubeチャンネル用アセット(アイコン・バナー)

チャンネルアイコンとバナー画像も同じ仕組み(Chromium描画)で生成できます。

```bash
python3 generate_channel_art.py --outdir ./assets
```

```
assets/
  icon.png    800x800   チャンネルアイコン(YouTubeは円形にクロップして表示
                          するため、重要な要素は中央の円内に収めてあります)
  banner.png  2560x1440  チャンネルバナー。どのデバイスでも見切れない中央の
                          「セーフエリア」(1546x423)にタイトル・タグライン
                          を収めてあります
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
うがないので、どんなにフォントを揃えても豆腐(`□`)になります。当初は
`SAFE_COMBINING_BLOCKS` で `0x20F1` 未満に絞ることで回避していましたが、
その後この`U+20D0`-`U+20F0`ブロック自体を丸ごと除外することになった経緯
は項目10を参照してください。

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

### 6. 「ENCLOSING」系の結合文字は豆腐ではないが表示が崩れる

`U+20D0`-`U+20F0` の中には、丸・四角・ひし形・スクリーン・キーキャップ・
三角のような**大きな図形を土台の文字に重ねて描く**「ENCLOSING」系のコード
ポイントがあります(例: `U+20E3` COMBINING ENCLOSING KEYCAP)。これらは
Unicode上は正式に割り当て済みでフォントも対応しているため豆腐にはなりま
せんが、実際に描画すると小さな飾り記号ではなく黒い塊や三角形が土台の文字
を覆い隠してしまい、「Zalgo風の演出」ではなく単なる表示崩れに見えてしまい
ます。当初は `config.py` の `_ENCLOSING_COMBINING_MARKS` でこれらだけを
個別に除外していましたが、その後 `U+20D0`-`U+20F0` ブロック自体を丸ごと
除外することになりました(経緯は項目10を参照)。

### 7. 1つのGoogleアカウントに複数チャンネルがあると誤爆する

YouTube Data API はエラーを返さず、**リフレッシュトークン取得時にYouTube
上でアクティブだったチャンネル**へ黙ってアップロードする。意図したチャン
ネルと違っても成功扱いになるため気づきにくい。`YOUTUBE_CHANNEL_ID` を
GitHub Secretsに設定しておくと、`youtube_upload.py` がアップロード前に
実際のチャンネルと照合し、不一致ならエラーで止めてくれる(詳細は上の
「YouTubeへの自動アップロード」を参照)。

### 8. Shorts結合動画の動画取得は「YouTubeから」ではなく「GitHub Actionsアーティファクトから」

`compile_shorts.py` は当初、結合対象の動画をGitHub Actions上で保持して
おくのではなく、**すでにYouTubeに公開済みの自分の動画をyt-dlpでダウン
ロードし直す**方式でした。GitHub Actionsのランナーはジョブごとに使い捨
てで生成物を永続化していないため、素材を保持し続けるにはリポジトリや外
部ストレージへの追加のアップロードが必要になり、コストと複雑さが増える
ため、「動画は一度作ったら消してよい」という前提に立って、必要になった
時点で(すでに正しく生成・公開済みの)動画をダウンロードし直す方が単純だ
と考えていたためです。

しかしこの方式は、**GitHub ActionsのランナーのIPがYouTube側にボット
判定される**(`Sign in to confirm you're not a bot` エラー)問題があり、
cookie認証を渡しても解決しない事例が別リポジトリ(SayItRight)で確認され
ています。YouTube側の対ボット対策はデータセンターのIPに対して年々強化
されており、根本的に不利な戦いです。

そのため、YouTube/yt-dlpに一切依存しない方式に変更しました:
`generate.py` が生成した動画は、`generate.yml` の
「Upload generated videos」ステップでGitHub Actionsアーティファクトと
して既に保存されているため、これを [GitHub Actions API]
(`/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts`) から取得し
直します。取得元のrunは、`generate.py` が `upload_history.json` へ記録
する各エントリの `run_id`(`GITHUB_RUN_ID`)で特定します。この方式なら
動画のprivacyStatusに関係なく取得できるため、`private` でアップロード
した動画も結合対象にできます(旧yt-dlp方式では匿名ダウンロードできる
`public`/`unlisted` にしか使えませんでした)。

この方式変更前にアップロードされたエントリ(`run_id` が記録されていない
もの)は、どのrunのアーティファクトか特定できないため結合対象外になり
ます。またGitHub Actionsアーティファクトの既定の保持期間は90日のため、
`COMPILATION_BATCH_SIZE`(10件)がその期間内にたまらないほど投稿頻度が
低い運用では、古いエントリのアーティファクトが期限切れになり結合対象か
ら除外される可能性があります。

### 9. 同じブランチにsquash mergeを繰り返すと、無関係な変更まで衝突扱いになる

長期間同じ開発ブランチ(例: `claude/xxx`)へコミットを積み続けながら、
`main`側へは毎回squash mergeする運用を続けると、Gitの共通祖先(merge-base)
がある時点で止まったまま更新されなくなる。以降のPRでは、たとえ内容的には
一方向の追加だけであっても、Gitがそれを正しく認識できず「コンフリクト」
として検出することがある(特に、mainの自動化ワークフローが
`upload_history.json` のような状態ファイルを直接コミットしている場合、
ブランチ側の古い内容と本当に競合する)。

対策: 新しい変更に着手する前に、作業ブランチへ `main` を一度マージして
おく(`git merge origin/main`)。解消時は「意図的に追加した変更」と
「mainだけが持つ実データ(履歴ファイルなど)」を区別し、後者は
`--theirs` 側(main側)を優先して取り込む。

### 10. 動画フレームは長らく「ほぼZalgoではない文字列」を表示していた

`frame_builder.build_frame()` は長い間、結合文字を全部落とした
`readable_label()` の出力だけを描画していた。`readable_label()` は本来
動画タイトルや説明欄・ファイル名向けの「読みやすい簡易ラベル」用に作った
関数だったが、それがフレーム表示にもそのまま流用されており、実際に生成
してみると土台の文字がほぼそのまま(結合文字226種のうち約97%が
`unicodedata.combining()` で正しく除去される一方、たまたま結合文字として
分類されていない数種類だけがすり抜けて見えていた)表示されるだけで、
「Zalgo感」がほぼ無い状態だった。

これに気づいたのは、実際に単語を生成してフレーム表示用の文字列を目視で
確認したことがきっかけ。対策として、結合文字を保持したまま
`readable_label()` と同じ件数基準で切り詰める `word_generator.zalgo_display_word()`
を新設し、`build_frame()` にも表示用と(フォントサイズ算出用の)ラベル用を
分けて渡すようにした(`frame_builder.build_frame(word_label, ..., display_word=...)`)。

この変更で実際に結合文字をフレームへ描画するようになったことで、さらに
2つの問題が新たに発覚した(どちらも今まで一度も画面に出したことがなかった
ため気づけなかった):

- **`U+20D0`-`U+20F0`ブロックが軒並み豆腐になる**: 音声的には無音確認済み
  だったが、Chromium+Notoフォントで実際に描画すると(ENCLOSING系を除いた
  残り約26種も含めて)ほぼ全滅だった。ブロックごと `SAFE_COMBINING_BLOCKS`
  から除外した(項目3・6も参照)。
- **`U+1DFA`(COMBINING DOT BELOW LEFT)だけが結合しない**: 他の199個の
  候補コードポイントは正常に土台文字と結合するのに、これだけ土台文字1個
  ぶんまるごと幅が伸びる(=結合せず独立した文字として描画される、実質的
  な豆腐)。目視だけでは埋もれて見落としやすいため、Playwrightで「土台
  文字単体」と「土台文字+マーク」の描画幅を比較する形で全200コードポイント
  を機械的に検証し直して発見した。この1点だけを個別に除外している。
- **結合文字の縦方向の積み重なりがキッカー文言("How to Pronounce")や
  サブテキストとぶつかる**: 短い単語ほどフォントサイズが大きくなり
  (`_word_font_size()`)、深いスタック(最大10個)が乗ると上下にはみ出す
  ケースがあった。`frame_builder.py` に単語の上下マージンを追加し、
  さらに `zalgo_display_word()` にフレーム表示専用の
  `max_marks_per_cluster`(デフォルト4)を設け、実際の単語・音声・説明欄
  はそのままに、表示だけ安全な範囲に切り詰めている。

### 11. 中国語のMBROLA女性ボイス(`mb-cn1`)はDebianパッケージ自体が壊れている

`--voice random`(多言語ボイス機能)で中国語(標準語)の女性ボイスに
`mbrola-cn1` パッケージの `mb-cn1` を割り当てようとしたところ、
`espeak-ng -v mb-cn1` が常に
`Error: The specified espeak-ng voice does not exist.` で失敗した。

原因を追ったところ、パッケージが同梱するespeak-ng用ボイス定義ファイル
(`/usr/lib/.../espeak-ng-data/voices/mb/mb-cn1`)が
`mbrola cn1 zh_phtrans` と、存在しない音素変換ファイル `zh_phtrans` を参
照していた。実際にespeak-ngが同梱しているのは `cmn_phtrans`(中国語標準語
の実際の言語コードは `cmn`)であり、`zh_phtrans` という名前のファイルはど
こにも存在しない。`mbrola-cn1` パッケージ自体の設定ミスと考えられる。

当初はこれで回避策が無いと判断し、中国語は男性ボイスのみ対応(`female`は
`None`)としていたが、後にespeak-ng内蔵のフォルマントバリアント(項目13)
でMBROLAを経由しない代替策を発見し、女性ボイスにも対応できるようになった。

### 12. タイ文字は子音字だけでは音節として成立しない

ロシア語・ジョージア語と同じ「文字をランダムに選んで並べる」方式(`random_script_word()`)
をタイ語にもそのまま使おうとしたが、これは文字体系の構造上そのままでは
使えないことが分かった。タイ文字は子音字1文字だけでは音節として成立せ
ず、母音記号(子音の前後左右に付く、単体では使わない)と組み合わせて初
めて1音節になる。子音字だけを羅列した文字列(例: `กขฃคฅฆงจฉ`)は、タイ
語の正書法として不完全な文字列になってしまう。

(当初「子音だけだとespeak-ngがアルファベットの読み方を1つずつ読み上げ
るのでは」と推測したが、実際に子音のみの文字列と母音記号付きの文字列で
音声の長さを比較したところ有意な差はなく、この推測を裏付ける証拠は得ら
れなかった。実際にespeak-ngがどう処理しているかは未検証だが、いずれに
せよ文字体系として不完全な入力である点は変わらないため、対策の方向性は
変えていない。)

対策として、タイ語専用の生成関数 `random_thai_word()` を用意し、子音字
を選ぶたびに一定確率(70%)で母音記号を後ろに付ける、構造的に妥当な音節
列を作るようにした。

その後、10言語拡張でビルマ語・シンハラ語・タミル語・テルグ語・ベンガル
語もタイ語と同じ「子音字+母音記号」のアブギダ文字体系だと判明したため、
`random_thai_word()` のロジックを `random_abugida_word(consonants, vowels, ...)`
として一般化し、`random_thai_word()` はそのタイ語専用ラッパー(後方互換
のため残存)にした。

### 13. MBROLA非対応言語の女性ボイスはespeak-ng内蔵の`+f3`バリアントで代替できる

10言語拡張で対応言語が23言語になり、そのうち女性ボイスがあるのは元々
MBROLA音声データが確認できた5言語のみだった。残り18言語向けに新たに
MBROLA音声を探す代わりに、`tts_synth.py` の `EXTREME_VOICE_VARIANTS`
(`tts_extreme` モードで使っている、espeak-ng同梱の「奇妙な声」バリエー
ション)と同じ「ボイスコードに `+バリアント名` を付け足す」仕組みに、
女性寄りのフォルマント変換バリアント `+f3` が使えることに気づいた。

実機で以下を確認した:

- `espeak-ng -v <任意の言語コード>+f3` は、MBROLAの専用音声データが一切
  無い言語(アラビア語・タミル語など)でもエラー無く合成に成功する。
  追加パッケージのインストールは不要(espeak-ng本体に内蔵)。
- 素の声(f0実測で中央値約108Hz)に対し、`+f3` を付けると約194Hzまで
  明確に上がる(MBROLA女性ボイスの実測値・約235Hzに近い自然な範囲)。
  複数の言語(英語・アラビア語)で同じ結果になることも確認済み。
- 中国語(標準語)だけは `zh+f3` だとエラーになった。原因を調べたところ、
  `zh` はmaleボイスとしては動くがバリアント付与には対応しておらず、
  実際にespeak-ng内部で使われている本来のコード `cmn`(項目11参照)に
  対しては `cmn+f3` が正常に動くことが分かった。そのため中国語の
  `female` だけ `cmn+f3` を使っている。
- `+f3` と、MBROLA用に用意していたピッチ補正(`-p`、`config.FEMALE_VOICE_PITCH`)
  を両方重ねて適用すると、f0が約258Hzまで上がりすぎることが実機で判明
  した(MBROLA版はこの補正が無いと低く聞こえたため必要だったが、`+f3`
  は単体で既に十分な高さになっている)。そのため
  `generate.py _voice_pitch_for()` で、ピッチ補正は「femaleボイスコードが
  `mb-` で始まる(MBROLA由来)場合」のみに限定し、`+f3` 由来の場合は適用
  しないようにした。

この方式に切り替えたことで、`mbrola-cn1` パッケージの不具合(項目11)で
女性ボイス非対応だった中国語も含め、全23言語で男性/女性ボイスの両方が
使えるようになった。

### 14. フィリピン語(タガログ語)はespeak-ngに存在しない、インドネシア語は存在する

YouTubeアナリティクスの視聴者地域でフィリピン・インドネシアの比率が
一定あることが分かり、対応言語に含まれているか確認したところ、いずれも
未対応だったため実機でespeak-ngの対応状況を調べた。

- `espeak-ng --voices` の全リストを検索しても、フィリピン語(タガログ語)
  に該当するボイス(`fil`/`tl`等)は存在しない。espeak-ng自体が対応して
  いないため、現状追加する手段が無い。
- インドネシア語は `id` というボイスコードで存在し、単体・`+f3`バリアント
  付与・`EXTREME_VOICE_VARIANTS`全11種との組み合わせのいずれも実機で
  エラー無く合成できることを確認した(項目13の"zh"のような不具合は無い)。
- Debianには `mbrola-id1`(インドネシア語)パッケージも存在するが、
  パッケージ説明上は男性ボイスのみのため、女性ボイス用としては使えず、
  他の18言語と同じ `+f3` フォルマントバリアント方式を採用した。

対応した結果、`config.VOICE_LANGUAGES` にインドネシア語(`id`)を追加し、
対応言語は24言語になった(詳細は「多言語ボイス」節の表を参照)。

**追記(フィリピン語の代替検討)**: フィリピン語自体は追加できないため、
代わりに近縁言語での代替を検討した。マレー語(オーストロネシア語族で
フィリピン語と同系統、ただし別言語で相互に通じるものではない)は
`ms` というボイスコードでespeak-ngに存在し、インドネシア語と同様に
単体・`+f3`・`EXTREME_VOICE_VARIANTS`全種のいずれも実機でエラー無く
動作することを確認した。「フィリピン語」として偽って追加するのは誤解を
招くため避け、`config.VOICE_LANGUAGES` へ**マレー語として正直にラベル付け**
した上で追加した(対応言語は25言語に)。フィリピンの視聴者にとって
完全に馴染みのある言語ではないが、英語のみだった状態よりは東南アジア圏
の言語的多様性を増やせると判断した。

### 15. YouTubeアナリティクスの地域データから未対応言語を洗い出す

視聴者の地域別データ(YouTube Studio「アナリティクス」→「視聴者」→
「地域」)を確認したところ、上位10か国のうちトルコ・ブラジル・
ポルトガル・ルーマニアの視聴者(合計で全視聴の約5.8%)に対応する言語が
未対応だった(日本は視聴があるものの、Zalgo系の「発音不能ネタ」は海外
向けのノリという方針のため対象外とした)。

実機でespeak-ngの対応状況を確認したところ、トルコ語(`tr`)・
ポルトガル語(ブラジル `pt-br` / ポルトガル `pt`)・ルーマニア語(`ro`)
はいずれも単体・`+f3`・`EXTREME_VOICE_VARIANTS`全種の組み合わせで
エラー無く動作した。さらに、これらはインドネシア語・マレー語と違い
Debianの`mbrola-*`パッケージに実在の女性ボイスデータがあった
(`mbrola-tr2`・`mbrola-br2`/`mbrola-br4`・`mbrola-pt1`。ルーマニア語は
男性ボイス`mbrola-ro1`のみで女性ボイスは存在しない)。

品質を優先し、女性ボイスがあるトルコ語・ポルトガル語(ブラジル/
ポルトガル)の3言語はMBROLA方式を採用し(`generate.yml`に
`mbrola-tr2`・`mbrola-br4`・`mbrola-pt1`を追加)、女性ボイスの無い
ルーマニア語のみ他の言語と同じ`+f3`フォルマントバリアント方式にした。
対応言語は29言語になった。

### 16. アナリティクスの裏付けが無い「珍しい文字体系」言語を9つ削除

29言語まで増やした後、対応言語数について「多すぎないか」を検討した。
1日の投稿本数(cron-job.orgで固定運用、1日10回程度)に対して29言語は
1言語あたり平均3日に1回程度しか出現しない頻度になり、どの言語の視聴者
にとっても「自分の言語がよく出てくるチャンネル」という認識が育ちにくい
薄さだと判断した。

削減対象を選ぶにあたり、`config.VOICE_LANGUAGES`の各言語を追加時の経緯で
2グループに分類した。

- **アナリティクスの視聴地域データに基づく追加**(インドネシア語・マレー
  語・トルコ語・ポルトガル語(ブラジル/ポルトガル)・ルーマニア語): 実際の
  視聴者が一定数いる地域に対応する言語で、削る理由が無い。
- **「珍しい文字体系」枠での追加**(項目14で触れた10言語拡張時のアラビア
  語・ヘブライ語・アルメニア語・アムハラ語・チェロキー語・ミャンマー語・
  シンハラ語・タミル語・テルグ語・ベンガル語、および元々あったロシア語・
  ジョージア語・タイ語): 対応地域の裏付けが無く、視覚的な「読めなさ」の
  インパクトが主な価値。特にタミル語・テルグ語・シンハラ語・ベンガル語の
  4言語はいずれもインド亜大陸系のアブギダ文字で、西洋圏視聴者からすると
  見た目のインパクトがほぼ同じであり、4つ揃える必然性が薄いと判断した。

上記の理由から、視聴地域の裏付けが無く、かつ他の「珍しい文字体系」言語と
役割が被っていたチェロキー語・タミル語・テルグ語・シンハラ語・ベンガル語・
アルメニア語・アムハラ語・ジョージア語・ミャンマー語の9言語を
`config.VOICE_LANGUAGES`から削除した。認知度の高いアラビア文字・キリル
文字・タイ文字(ロシア語・タイ語・アラビア語・ヘブライ語)は「見た目の
インパクト」の主力として残している。対応言語は20言語になった。

`config._assigned_chars()`で機械的に構築していた文字プール定数
(`GEORGIAN_LETTERS`・`ARMENIAN_LETTERS`・`AMHARIC_SYLLABLES`・
`CHEROKEE_SYLLABLES`・`MYANMAR_CONSONANTS`/`_VOWEL_MARKS`・
`SINHALA_CONSONANTS`/`_VOWEL_MARKS`・`TAMIL_CONSONANTS`/`_VOWEL_MARKS`・
`TELUGU_CONSONANTS`/`_VOWEL_MARKS`・`BENGALI_CONSONANTS`/`_VOWEL_MARKS`)と、
対応するNotoフォント(`FRAME_CSS_FONT_STACK`)もあわせて削除した。
`NATIVE_SCRIPT_VOICE_CHANCE`(実際の文字体系が選ばれる確率、デフォルト
30%)はこの削除により、元々の「実在文字体系がラテン文字系より多数派に
なるのを補正する」という導入理由が無くなった(実在文字体系は20言語中4と
再び少数派に戻った)が、視覚的インパクトを一定頻度で保つ狙いで値はそのまま
据え置いている。

### 17. `tts_extreme`は短い単語×速い読み上げが重なると「発音」ではなく一瞬のノイズになる

実際に公開された動画で、1秒程度しかなく「おならのような音」にしか聞こえない
`tts_extreme`動画があるという指摘を受けて調査した。

`synthesize_tts_extreme()`はespeak-ngの読み上げ速度(`-s`、60〜400の範囲で
ランダム)と、ffmpegの歪みフィルタ(音程を上げる`asetrate`はテンポも一緒に
速くなる副作用がある、1.3〜1.9倍)を組み合わせている。実機で該当の単語を
使い200回試したところ、速度の上限付近(350〜400)とテンポを上げるフィルタ
が重なるケースで、最終的な音声の長さが**最短0.1秒**まで縮むことを確認した
(0.5秒未満になる確率43%、0.3秒未満になる確率16.5%)。

espeak-ng側の速度レンジやffmpeg側のテンポ倍率を狭めるだけでは根本解決に
ならないことも実機で確認した(元々短い単語(例: `vOn`のような3文字)では、
レンジを狭めても依然として一定確率で0.5秒未満になる)。単語の長さそのもの
がランダムに決まる以上、パラメータの調整だけでは「短すぎて聞き取れない」
ケースを完全には防げない。

そのため、パラメータのランダム性はそのまま保ちつつ、生成後の音声の長さを
`config.TTS_EXTREME_MIN_DURATION_SECONDS`(0.6秒)と比較し、下回っていれば
ffmpegの`atempo`フィルタで再生速度を落として引き伸ばす方式にした
(`tts_synth._stretch_to_min_duration()`)。`atempo`は1回あたり0.5〜2.0倍
までしか指定できない仕様のため、範囲外の倍率は`_atempo_chain_for_factor()`
でその上限/下限を複数回チェーンして表現している。また、特に0.2秒未満の
ような極端に短い音声では1回のatempo適用だけでは狙った長さにきっちり収まら
ないことも実機で確認できたため、生成後の長さを都度測り直して収束するまで
(最大3回)繰り返す設計にした。

修正後、同じ条件(短い単語×極端なパラメータ)で150回試したところ、0.5秒
未満になるケースは0件になった。

### 18. 「投稿本数を減らすべきか」の判断には、経過日数の効果と長期トレンドの区別が要る

YouTube Studioの投稿一覧で「直近数日分の再生数が少ない動画が増えている」
ように見えて、投稿頻度(10回/日)を減らすべきか相談を受けた。

結論としては、直近数日のスナップショットだけでは「経過日数の効果」(公開
直後の動画はまだ再生数が積み上がっていないだけ)と、「実際の長期的な低下
傾向」(この手のネタ系コンテンツにありがちな、視聴者が数本見るとパターンが
分かって反応が落ちる「飽き」)を区別できない。実際、投稿頻度は数週間ずっと
10回/日で一定だったにもかかわらず、直近1日の投稿だけ視聴回数が低く見えた
ケースがあったが、これは単に公開からの経過時間が短かった(数時間〜半日)
だけで、頻度変化とは無関係だった。

この区別のために`summarize_by_week()`(`youtube_analytics.py`の
`--by-week`オプション)を追加した。`avg_views_per_day`はもともと
`_days_available()`で経過日数を正規化済みの指標のため、これを投稿週(月曜
始まり)ごとに集計すれば、新しい週と古い週を並べても「まだ新しいから少ない」
というノイズを受けにくい。週を追って`avg_views_per_day`が右肩下がりなら
「飽き」を疑う材料になり、横ばい〜ばらつきの範囲なら投稿頻度の問題ではなく
個々の動画のばらつき(単語・言語・モードの組み合わせによる)である可能性が
高い、という切り分けに使う。

### 19. `UPLOAD_SCOPES`に未付与のスコープを1つ混ぜただけで、アップロード全体が止まった

字幕アップロード(`upload_caption()`)用に`youtube.force-ssl`スコープを
追加した際、最初は他のAPI呼び出しと同じ`UPLOAD_SCOPES`にそのまま加えた。
その結果、字幕アップロードだけでなく`generate.yml`の全アップロードが
`invalid_scope: Bad Request`で失敗する事故になった(本番の自動投稿が
1回丸ごと失敗した)。

原因は`get_youtube_client()`の作り。この関数はデフォルトで`UPLOAD_SCOPES`
を丸ごとリクエストしてトークンをリフレッシュし(`_load_credentials()`
参照)、`upload_video()`・`add_to_playlist()`・`append_video_description()`・
`upload_caption()`の**全て**がこの関数を経由する。`UPLOAD_SCOPES`に、
リフレッシュトークンがまだ持っていないスコープ(`youtube.force-ssl`。
発行時に焼き付けられる仕様のため、コード側に追加しただけでは既存トークンに
は付与されない)を1つでも混ぜると、Google側はスコープの絞り込みリクエスト
自体を`invalid_scope`で拒否する。これは特定のAPI呼び出し(`captions.insert`)
だけの権限不足ではなく、**トークンリフレッシュという入り口の時点**で失敗
するため、その関数を経由する他の全ての呼び出しに波及する。

`youtube_analytics.get_analytics_client()`が`scopes=None`(絞り込みをしない
=リフレッシュトークンの実際の付与範囲そのままを使う)を使っている設計は、
まさにこの問題を避けるためのものだったが、字幕機能を実装した際にその教訓を
生かせず、`UPLOAD_SCOPES`に直接追加してしまった。

修正: `youtube.force-ssl`は`UPLOAD_SCOPES`(=デフォルトの絞り込み対象)
からは外し、`get_youtube_client()`に`scopes`引数を追加。`upload_caption()`
だけが`get_youtube_client(scopes=None)`を呼ぶことで、そのリフレッシュ
トークンが実際に持っている範囲のままトークンを取得する(絞り込まない)。
これなら`youtube.force-ssl`がまだ付与されていなくてもトークンリフレッシュ
自体は成功し、`captions.insert`のAPI呼び出しだけが権限不足で個別に失敗する
(動画本体のアップロード等、他の呼び出しは影響を受けない)。

教訓: **新しいスコープを追加する際は、それを使う関数だけがそのスコープを
要求するようにする**(共有のデフォルトスコープリストに混ぜない)。共有
リストに混ぜると、そのスコープがまだリフレッシュトークンに付与されていない
間(=再発行するまでの間)、無関係な呼び出しまで巻き添えで全滅する。

### 20. `MODE_WEIGHTS`でglitchを下げた判断を、実測で撤回した

「ハマった罠」18番・19番の対応と並行して`youtube_analytics.py --by-week`を
実際に運用したところ、2026-09-21・09-22の2回の集計で、主指標(投稿からの
経過日数で正規化した1日あたり再生数)が**いずれもglitchモードが最上位**
という結果になった(9/21: glitch 24.12回 > tts 10.55回 > tts_extreme
2.28回。9/22: glitch 57.26回 > tts 37.11回 > tts_extreme 6.09回)。

`MODE_WEIGHTS`は元々「glitchは単語を読み上げないので"Can You Say This?"
というコンセプトへの説得力が弱い」という主観的な判断だけで、均等抽選
(`tts`:`tts_extreme`:`glitch` = 1:1:1)から`2:2:1`に下げていた
(`youtube_analytics.py`はこの判断を裏付け/再調整するデータを取るために
作ったモジュール)。実測データが2回連続で逆の傾向を示したため、`1:1:1`の
均等抽選に戻した。

**この時点ではあえて`1:1:1`より強気の配分(glitchを優遇する方向)には
していない**。理由は各モードのサンプル数がまだ10〜19本程度と少なく、
「まず主観的な下方修正を撤回する」以上に踏み込むには材料が足りないと
判断したため。今後さらにサンプルが増え、同じ傾向が続くようであれば、
再度`MODE_WEIGHTS`を見直す可能性がある。

### 21. 手動字幕(`captions.insert`)が断続的に403 forbiddenになり、一時無効化した

19番の修正後、リフレッシュトークンを`youtube.force-ssl`込みで再発行し、
実際に3回分の投稿で字幕アップロードの結果を観察した。1回目は成功したが、
2回目・3回目は同じコード・同じ認証情報にもかかわらず

```
HttpError 403 ... "The permissions associated with the request are not
sufficient to upload the caption track. The request might not be properly
authorized." (reason: forbidden, domain: youtube.caption)
```

で失敗した(3回中2回失敗)。

`youtube.force-ssl`は「制限付きスコープ」で、このプロジェクトのOAuth同意
画面は未検証(「テスト」ステータス)のまま運用している。制限付きスコープを
未検証アプリでリクエストした場合にリクエストが断続的に拒否される、という
報告が一般に見られ、成功・失敗のタイミングのばらつきとも矛盾しない。ただし
これは確度の高い推測であり、実機で確定した原因ではない(Google側の内部
挙動のため、こちらから完全に検証する手段が無い)。

恒久的に安定させるにはGoogleのOAuthアプリ検証(審査)を通す必要があるが、
個人のホビープロジェクトには重い手続き(デモ動画の提出等、数日〜数週間)
のため、費用対効果を鑑みていったん見送った。失敗しても動画本体の投稿は
止まらない設計だが、失敗時も`captions.insert`のクォータ(400 units)を
無駄に消費し続けるだけになるため、`config.CAPTIONS_ENABLED = False`で
機能自体を一時的に無効化した(コードは残したまま、`True`に戻せば復活する)。

教訓: **Google API の「制限付きスコープ」は、コードが正しくてもOAuthアプリ
の検証状態によって挙動が変わりうる**。実機で1回成功しただけでは「直った」
と判断せず、複数回試行して安定して成功するかまで確認する必要がある。

### 22. 実在文字体系の「実在の単語ではない」注記は、説明欄だけでは伝わらなかった

「実際の文字体系を使う言語」(ロシア語・タイ語・アラビア語・ヘブライ語)の
動画に対し、実際にその言語の話者から「(TTSの発音は)間違っている、正しくは
Yuuuudsh」という趣旨のコメントが付いた。生成した文字列はランダムな文字の
組み合わせで実在の単語ではない旨を動画説明文には明記していたが
(`is_native_script`引数、本節の上記参照)、Shorts視聴者の多くは説明欄を
開かずに視聴するため、その注記が実質的に読まれていなかった。

対策として、同じ注記を**動画フレーム自体**(`frame_builder.build_frame()`
のサブテキスト、`[Mode / Not a real word!]`)にも焼き込むようにした
(`frame_builder._sub_label()`)。説明欄は視聴者の任意の操作(タップして
展開)が必要だが、フレームは視聴時に必ず画面に映るため、同じ注記でも
伝わり方が大きく異なる。

なお、この機能自体(実在文字体系でのランダム単語生成)を全廃してラテン文字
(Zalgo)のみに戻す案も検討したが、1件のコメントのみを根拠に4言語分の実装
(「ハマった罠」10〜16番)を丸ごと撤回するのは費用対効果に見合わないと判断
し、見た目の注記強化に留めた。

### 23. `--mode glitch`が毎回似通って聞こえる問題を、レイヤー重ね+テンポ密度のランダム化で緩和した

`glitch_synth.py`はセグメント個々のパラメータ(周波数・長さ・クランチの
強さ等)こそランダムだったが、「1レイヤーだけを順番に鳴らす」「テンポ感
(音数・1音の長さ・無音の多さ)は毎回ほぼ同じ」という全体の構造は固定
だったため、聴感上は毎回似た印象になりがちだった。

対策として、ローカルで実際に音を出して比較できる範囲で改善案をいくつか
試作し(セグメント重ね/テンポ密度変更/両方の組み合わせ)、以下の2案を
採用した(`synthesize_glitch_chunk()`):

- **レイヤー重ね**: 独立に組み立てたセグメント列(レイヤー)を2〜3本、
  `ffmpeg`の`amix`で同時に重ねる(以前は1本をconcatするだけだった)。
  和音的な重なりが生まれる。
- **テンポ密度のランダム化**: レイヤーごとのセグメントの長さ・無音比率を
  `high`(音数多め・短め・無音少なめ)/`low`(音数少なめ・長め・無音多め)
  の2パターンから毎回ランダムに選ぶ(`_TEMPO_DENSITY_PARAMS`)。

n_layers・tempo_densityは呼び出し側から明示指定もできるが(テスト・
デバッグ用)、`generate.py`からの通常呼び出しでは両方とも省略し、毎回
ランダムに選ばれる。

### 24. タイトルの日本語ローカライズが、ヘブライ語・アラビア語(RTL文字)の回だけ語順が入れ替わって表示された

YouTube Studioのコメント欄で、視聴者から「日本語ローカライズした場合の
語順がおかしい」との指摘があった。実際に確認すると、ヘブライ語・アラビア語
(実在文字体系の中でRTL、右から左に読む)の回だけ、`「{label}」の発音は?
(ヘブライ語) #Shorts`という組み立て順のはずが、`#Shortsの発音は?
(ヘブライ語)「{label}」`のように文全体の語順が丸ごと入れ替わって表示
されていた。ロシア語・タイ語(いずれもLTR)や英語のZalgo単語では発生しない。

原因はUnicode双方向アルゴリズム(UAX #9)。`title_ja`の文字列は`「`という
方向性を持たない中立文字から始まり、その直後に来る`label`(ヘブライ語・
アラビア語の文字)が文字列全体で最初の「強い方向性を持つ文字」になる。
このアルゴリズムでは、明示的な指定が無い文字列の基準方向は最初の強い
方向性文字で決まるため、`label`がRTL文字だと文字列全体がRTL文字列だと
判定され、後に続く日本語部分も含めて表示順が丸ごと右から左に入れ替わって
しまう(英語タイトルの方は`How to Pronounce "{label}"`と、`label`より前に
`H`という強いLTR文字があるため、この問題が起きない)。

対策として、`label`をFirst Strong Isolate(U+2068)〜Pop Directional
Isolate(U+2069)で囲み(`f"「⁨{label}⁩」の発音は?"`)、`label`の
方向性が周囲の日本語テキストの基準方向に影響しないよう分離した。
isolateで囲むこと自体はLTRの`label`に対しても無害なため、言語ごとに
分岐せず常に適用している。

教訓: **ある言語のテキストを別方向のテキストに埋め込むときは、埋め込む側
の文字列自体をbidi isolateで囲む**。埋め込まれる文字列がLTR/RTLどちらに
なるか(あるいは将来どの言語が増えるか)を個別に判定・分岐する必要が無く、
最も汎用的で壊れにくい。

なお、この修正は新規アップロード分にしか効かないため、修正前に公開済みの
動画のタイトルは直っていない。個別に直すための`youtube_fix_localization.py`
を追加した(「日本語ローカライズが崩れて表示された動画の手動修正」節参照)。

## プロジェクト構成

```
config.py                    全モジュール共通の設定・定数
word_generator.py            Zalgo風「発音不能な単語」の生成
tts_synth.py                  TTS(espeak-ng)による音声合成 [--mode tts / tts_extreme]
glitch_synth.py               合成グリッチ音による音声生成 [--mode glitch]
audio_utils.py                繰り返し・パディング無しフェード・mp3変換
frame_builder.py              "How to Pronounce" フレーム画像の生成(Playwright)
video_builder.py              フレーム+音声 → mp4 の合成
youtube_upload.py             YouTube Data API v3への動画アップロード [--upload]
upload_history.py             アップロード成功履歴(upload_history.json)の読み書き
compilation_state.py          Shorts結合動画の状態(compilation_state.json)管理
compile_shorts.py             Shortsが10本たまるごとに結合動画を作りアップロード
youtube_analytics.py          YouTube Analytics APIでモード別の再生数・視聴維持率を集計
youtube_quick_stats.py         videos.listで直近投稿の即時再生数・高評価数・コメント数を取得
get_youtube_refresh_token.py  YouTubeアップロード用リフレッシュトークンの取得(ローカルで一度だけ実行)
generate.py                   CLIエントリポイント
generate_channel_art.py       YouTubeチャンネル用アイコン・バナーの生成
assets/                       generate_channel_art.py の出力先(icon.png / banner.png)
tests/                        ユニットテスト(pytest)
.github/workflows/            CI(push/PR時にテストを自動実行)/ 手動実行の生成・アップロードワークフロー
```

## ライセンス

MIT License. `LICENSE` を参照してください。
