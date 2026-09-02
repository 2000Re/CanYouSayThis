# CanYouSayThis

「How to Pronounce ▤彡...」系のネタ動画を自動生成するパイプラインです。

Zalgo風の「発音不能な単語」をランダム生成し、それに対して「これが発音で
す」という体で音声を当て、"How to Pronounce <word>" 形式の短い動画(mp4)
を量産します。

## できること

1. **単語生成**: 母音などの土台文字にUnicodeの結合文字(いわゆるZalgoテキ
   スト)や記号を大量に重ねた、見た目からして発音不能な単語をランダムに作
   ります。
2. **音声生成**: 4つの方式、またはそれらをランダムに混ぜる方式を選べます。
   - `tts`(デフォルト): [espeak-ng](https://github.com/espeak-ng/espeak-ng)
     に単語そのものを読ませ、出てきた音をそのまま採用します。
   - `tts_extreme`: espeak-ngの奇妙な声バリエーション(`Demonic` / `croak` /
     `whisper` など)+極端なピッチ・速度で単語を読ませたうえで、さらに
     ffmpegでピッチシフト・ビットクラッシュ等をランダムにかけて歪ませま
     す。`tts`と同じく単語自体は読ませていますが、声質が毎回激しく変わ
     ります。
   - `glitch`: チャープ音・ノイズバースト・ビットクラッシュを合成し、単語
     の音とは無関係な効果音を「答え」として当てます。
   - `morse`: 単語の英数字部分を実際の国際モールス符号に変換し、ビープ音
     で鳴らします。エンコード自体は本物ですが、聞いて読み取れることを狙っ
     た機能ではなく、`glitch`と同じく単語の音とは無関係な「答え」の1つで
     す。
   - `random`: 1本ごとに上記4方式からランダムに選びます(`--count`で複数
     本まとめて作る際や、自動実行の日々の投稿が単調にならないようにする
     用途)。
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

# 極端に歪ませたTTSで5本生成
python3 generate.py --count 5 --mode tts_extreme --outdir ./out_extreme

# モールス符号のビープ音で5本生成
python3 generate.py --count 5 --mode morse --outdir ./out_morse

# 4方式を1本ごとにランダムに混ぜて5本生成
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
| `--mode` | `tts` / `tts_extreme` / `glitch` / `morse` / `random`(1本ごとにランダム選択) | `tts` |
| `--voice` | [tts/tts_extreme専用] espeak-ngの声(`en`, `en-us`, `ja` など) | `en` |
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

## プロジェクト構成

```
config.py                    全モジュール共通の設定・定数
word_generator.py            Zalgo風「発音不能な単語」の生成
tts_synth.py                  TTS(espeak-ng)による音声合成 [--mode tts / tts_extreme]
glitch_synth.py               合成グリッチ音による音声生成 [--mode glitch]
morse_synth.py                モールス符号のビープ音による音声生成 [--mode morse]
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
