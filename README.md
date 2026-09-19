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
     デフォルトでは均等抽選(各1/3)より比率を下げており、`tts`:`tts_extreme`:
     `glitch` = 2:2:1(それぞれ40%/40%/20%)になっています。
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
```

出力例:

```
=== モード別 再生数・視聴維持率集計(2026-08-22 〜 2026-09-19、対象87本) ===
  tts: 35本 / 1日あたり平均12.40回(単純平均210.5回, 視聴維持率38.2%)
  tts_extreme: 34本 / 1日あたり平均11.80回(単純平均195.3回, 視聴維持率41.0%)
  glitch: 18本 / 1日あたり平均7.10回(単純平均88.9回, 視聴維持率22.5%)
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

**GitHub Actionsから実行する場合**: `.github/workflows/analytics.yml`
(workflow_dispatch)から手動実行できます。`generate.yml`と同じ
`YOUTUBE_CLIENT_ID`/`YOUTUBE_CLIENT_SECRET`/`YOUTUBE_REFRESH_TOKEN`の
Secretsをそのまま使うため、追加のSecrets登録は不要です(上記の手順3で
`YOUTUBE_REFRESH_TOKEN`をyt-analytics.readonlyスコープ込みのものに更新
済みであること)。`days`(デフォルト28)、または`start_date`/`end_date`を
入力して実行すると、集計結果がActionsのログに出力されます。

**注意**: `youtube_analytics.py`のAPI呼び出し部分は、このリポジトリの他の
機能(espeak-ng・MBROLA等)と違い、本物のGoogle認証情報を用いた実際のAPI
応答での動作確認がまだ取れていません。公式ドキュメントに基づいて実装して
いますが、初回実行時は出力結果をYouTube Studioの表示と突き合わせて確認して
ください。

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
get_youtube_refresh_token.py  YouTubeアップロード用リフレッシュトークンの取得(ローカルで一度だけ実行)
generate.py                   CLIエントリポイント
generate_channel_art.py       YouTubeチャンネル用アイコン・バナーの生成
assets/                       generate_channel_art.py の出力先(icon.png / banner.png)
tests/                        ユニットテスト(pytest)
.github/workflows/            CI(push/PR時にテストを自動実行)/ 手動実行の生成・アップロードワークフロー
```

## ライセンス

MIT License. `LICENSE` を参照してください。
