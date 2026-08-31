# CanYouSayThis

「How to Pronounce ▤彡...」系のネタ動画を自動生成するパイプラインです。

Zalgo風の「発音不能な単語」をランダム生成し、それに対して「これが発音で
す」という体で音声を当て、"How to Pronounce <word>" 形式の短い動画(mp4)
を量産します。

## できること

1. **単語生成**: 母音などの土台文字にUnicodeの結合文字(いわゆるZalgoテキ
   スト)や記号を大量に重ねた、見た目からして発音不能な単語をランダムに作
   ります。
2. **音声生成**: 2つの方式、または両方をランダムに混ぜる方式を選べます。
   - `tts`(デフォルト): [espeak-ng](https://github.com/espeak-ng/espeak-ng)
     に単語そのものを読ませ、出てきた音をそのまま採用します。
   - `glitch`: チャープ音・ノイズバースト・ビットクラッシュを合成し、単語
     の音とは無関係な効果音を「答え」として当てます。
   - `random`: 1本ごとに`tts`/`glitch`のどちらかをランダムに選びます
     (`--count`で複数本まとめて作る際や、自動実行の日々の投稿が単調に
     ならないようにする用途)。
3. **繰り返し**: 実際のHow-to-Pronounce系動画が "word... word..." のよう
   に2回言うことが多いのに合わせて、生成した音声をデフォルトで2回繰り返し
   ます。
4. **動画合成**: "How to Pronounce <word>" 形式のミニマルな静止画フレーム
   を [Playwright](https://playwright.dev/) 経由のChromiumで描画し、音声
   と合成してmp4を書き出します(縦型9:16、YouTube Shorts向け)。動画の尺
   は音声の実際の長さにそのまま追従します(固定尺への無音パディングはし
   ません)。
5. **YouTubeへの自動アップロード**(任意): `--upload` を付けると、書き出
   したmp4をそのままYouTube Data API v3経由でチャンネルにアップロードし
   ます。
6. **Shorts結合動画**(任意): アップロードしたShortsが10本たまるごとに、
   それらを結合した1本の「通常動画」を自動で作ってアップロードします
   (詳しくは後述の「Shorts結合動画」を参照)。

## セットアップ

```bash
# システム依存(Ubuntu/Debian系の例)
sudo apt-get install -y espeak-ng ffmpeg
sudo apt-get install -y fonts-noto-core fonts-noto-extra fonts-noto-ui-core fonts-noto-ui-extra

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

# tts/glitchを1本ごとにランダムに混ぜて5本生成
python3 generate.py --count 5 --mode random --outdir ./out_mixed

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
| `--mode` | `tts` / `glitch` / `random`(1本ごとにランダム選択) | `tts` |
| `--voice` | [tts専用] espeak-ngの声(`en`, `en-us`, `ja` など) | `en` |
| `--speed` | [tts専用] 読み上げ速度(words/min) | `150` |
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
  001.mp4        完成動画
  002_word.txt
  ...
```

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

### 4. 実行

- ローカル: `python3 generate.py --upload` (環境変数として上記をセットし
  ておく)
- GitHub Actions: Actions タブ → **generate** ワークフロー →
  **Run workflow**。`upload` 入力はデフォルトで有効、`privacy_status` の
  デフォルトは `public`(アップロード直後から誰でも視聴・検索可能)。テス
  ト目的で公開したくない場合は `unlisted` / `private` を選ぶか、`upload`
  をオフにして動画だけ生成しArtifactとしてダウンロードすることもできる。

## Shorts結合動画

アップロードしたShorts動画の履歴(`upload_history.json`)が10本たまるごと
に、それらをYouTubeから取得し直して1本の横型(16:9)動画に結合し、「通常
動画」として自動でアップロードします(`compile_shorts.py`。generateワーク
フローの中で `--upload` 使用時に自動実行されます)。

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

ローカルで手動実行する場合:

```bash
python3 compile_shorts.py --privacy-status unlisted
```

(認証は `--upload` と同じ `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` /
`YOUTUBE_REFRESH_TOKEN` 環境変数を使う)

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

### 6. 「ENCLOSING」系の結合文字は豆腐ではないが表示が崩れる

`U+20D0`-`U+20F0` の中には、丸・四角・ひし形・スクリーン・キーキャップ・
三角のような**大きな図形を土台の文字に重ねて描く**「ENCLOSING」系のコード
ポイントがあります(例: `U+20E3` COMBINING ENCLOSING KEYCAP)。これらは
Unicode上は正式に割り当て済みでフォントも対応しているため豆腐にはなりま
せんが、実際に描画すると小さな飾り記号ではなく黒い塊や三角形が土台の文字
を覆い隠してしまい、「Zalgo風の演出」ではなく単なる表示崩れに見えてしまい
ます。`config.py` の `_ENCLOSING_COMBINING_MARKS` でこれらを個別に除外して
います。

### 7. 1つのGoogleアカウントに複数チャンネルがあると誤爆する

YouTube Data API はエラーを返さず、**リフレッシュトークン取得時にYouTube
上でアクティブだったチャンネル**へ黙ってアップロードする。意図したチャン
ネルと違っても成功扱いになるため気づきにくい。`YOUTUBE_CHANNEL_ID` を
GitHub Secretsに設定しておくと、`youtube_upload.py` がアップロード前に
実際のチャンネルと照合し、不一致ならエラーで止めてくれる(詳細は上の
「YouTubeへの自動アップロード」を参照)。

### 8. Shorts結合動画は「作り直す」のではなく「取得し直す」

`compile_shorts.py` は結合対象の動画をGitHub Actions上で保持しておくので
はなく、**すでにYouTubeに公開済みの自分の動画をyt-dlpでダウンロードし直
す**方式にしています。GitHub Actionsのランナーはジョブごとに使い捨てで
生成物を永続化していないため、素材を保持し続けるにはリポジトリや外部
ストレージへの追加のアップロードが必要になり、コストと複雑さが増えます。
逆に「動画は一度作ったら消してよい」という前提に立てば、必要になった時
点で(すでに正しく生成・公開済みの)動画をダウンロードし直す方が単純です。
ただしこの方式では、`private` でアップロードした動画は匿名ダウンロード
できないため結合対象にできません。

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

## プロジェクト構成

```
config.py                    全モジュール共通の設定・定数
word_generator.py            Zalgo風「発音不能な単語」の生成
tts_synth.py                  TTS(espeak-ng)による音声合成 [--mode tts]
glitch_synth.py               合成グリッチ音による音声生成 [--mode glitch]
audio_utils.py                繰り返し・パディング無しフェード・mp3変換
frame_builder.py              "How to Pronounce" フレーム画像の生成(Playwright)
video_builder.py              フレーム+音声 → mp4 の合成
youtube_upload.py             YouTube Data API v3への動画アップロード [--upload]
upload_history.py             アップロード成功履歴(upload_history.json)の読み書き
compilation_state.py          Shorts結合動画の状態(compilation_state.json)管理
compile_shorts.py             Shortsが10本たまるごとに結合動画を作りアップロード
get_youtube_refresh_token.py  YouTubeアップロード用リフレッシュトークンの取得(ローカルで一度だけ実行)
generate.py                   CLIエントリポイント
generate_channel_art.py       YouTubeチャンネル用アイコン・バナーの生成
assets/                       generate_channel_art.py の出力先(icon.png / banner.png)
tests/                        ユニットテスト(pytest)
.github/workflows/            CI(push/PR時にテストを自動実行)/ 手動実行の生成・アップロードワークフロー
```

## ライセンス

MIT License. `LICENSE` を参照してください。
