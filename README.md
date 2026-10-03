# CanYouSayThis

「How to Pronounce ▤彡...」系のネタ動画を自動生成するパイプラインです。

Zalgo風の「発音不能な単語」をランダム生成し、それに対して「これが発音で
す」という体で音声を当て、"How to Pronounce <word>" 形式の短い動画(mp4)
を量産します。

## できること

1. **単語生成**: 母音などの土台文字にUnicodeの結合文字(Zalgoテキスト)や
   記号を大量に重ねた、見た目からして発音不能な単語をランダムに作ります。
2. **音声生成**: 7つの方式、またはそれらをランダムに混ぜる方式を選べます。
   - `tts`(デフォルト): [espeak-ng](https://github.com/espeak-ng/espeak-ng)に単語そのものを読ませる。
   - `tts_extreme`: 奇妙な声バリエーション+極端なピッチ・速度で読ませ、ffmpegでさらに歪ませる。
   - `glitch`: 単語の音とは無関係な合成効果音を当てる。単語自体も一定確率(`config.PICTOGRAPH_VISUAL_CHANCE`、デフォルト0.4)で楔形文字・エジプト/アナトリア象形文字・線文字B表意文字を組み合わせた「絵のように見える」単語になる(`glitch`限定、「ハマった罠」27番)。
   - `reverse`: espeak-ngの読み上げ音声をそのまま逆再生する。
   - `robot_voice`: 読み上げ音声に搬送波とのリング変調(ffmpegの`amultiply`)をかけロボット風の声にする。
   - `chorus`: 同じ単語を複数言語(3〜4言語、`config.CHORUS_VOICE_LANGUAGE_CODES`)のボイスで同時に読み上げて重ねる(「ハマった罠」28番)。
   - `morse`: espeak-ngは使わず、単語の文字を国際モールス符号のビープ音列に変換する(結合文字・装飾記号は無視)。
   - `random`: `config.MODE_WEIGHTS`の重みで上記からランダムに選ぶ。現在は均等配分(実測で`glitch`の優位が確認され下方修正を撤回、「ハマった罠」20番)。新方式4つはまだ実測データが無いためデフォルト重み。
3. **多言語・声色のランダム化**(任意): `--voice random`(tts/tts_extreme/reverse/robot_voice専用)で、英語を含む19言語・男性/女性ボイスをランダムに選ぶ。詳しくは「多言語ボイス」を参照。
4. **繰り返し**: 音声をデフォルトで2回繰り返す("word... word..."形式)。
5. **動画合成**: [Playwright](https://playwright.dev/)経由のChromiumでフレームを描画し音声と合成(縦型9:16、Shorts向け)。動画尺は音声の実際の長さに追従(固定尺パディング無し)。
6. **YouTubeへの自動アップロード**(任意): `--upload`でYouTube Data API v3経由でチャンネルにアップロード。
7. **カスタムサムネイル**(任意、`config.CUSTOM_THUMBNAIL_ENABLED`): 単語だけを大きく表示したミニマルな16:9画像を生成・アップロード。電話番号確認が必要なため現在デフォルト無効(「カスタムサムネイル」参照)。
8. **通常動画への変換**(任意): アップロード済みのShortsを1本ずつ、同じタイトルのまま横型(16:9)の「通常動画」として自動的に再アップロード(「Shorts→通常動画への変換」参照)。

## セットアップ

```bash
# システム依存(Ubuntu/Debian系の例)
sudo apt-get install -y espeak-ng ffmpeg
sudo apt-get install -y fonts-noto-core fonts-noto-extra fonts-noto-ui-core fonts-noto-ui-extra

# --voice random で英語・フランス語・ドイツ語・ハンガリー語・スウェーデン語・
# ポルトガル語(ブラジル/ポルトガル)・トルコ語相当のMBROLA女性ボイスを使う
# 場合のみ必要。未インストールでも男性ボイス・他言語の女性ボイス(espeak-ng
# 内蔵のフォルマントバリアントで代替)は動作する(「多言語ボイス」参照)
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
python3 generate.py --count 5 --outdir ./out                        # デフォルト(tts)で5本
python3 generate.py --count 5 --mode glitch --outdir ./out_glitch    # グリッチ音方式
python3 generate.py --count 5 --mode random --outdir ./out_mixed     # 全方式からランダム
python3 generate.py --count 5 --voice random --outdir ./out_multilang  # 言語・性別もランダム
python3 generate.py --count 5 --repeat 3 --seed 42                   # 繰り返し回数・シード固定
python3 generate.py --count 3 --upload --privacy-status unlisted     # YouTubeへアップロード
```

### 主なオプション

| オプション | 説明 | デフォルト |
|---|---|---|
| `--count` | 生成する本数 | `3` |
| `--outdir` | 出力ディレクトリ | `./out` |
| `--mode` | `tts` / `tts_extreme` / `glitch` / `reverse` / `robot_voice` / `chorus` / `morse` / `random` | `tts` |
| `--voice` | [tts/tts_extreme/reverse/robot_voice専用] espeak-ngの声(`en`, `en-us` 等 / `random`=言語・性別ランダム) | `en` |
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
  001.mp4        完成動画(--upload時はvideo_idにリネームされる)
```

`--upload`時はアップロード成功後、完成動画が`{video_id}.mp4`にリネームされ
ます。`repost_shorts.py`が`upload_history.json`の`video_id`をキーにGitHub
Actionsアーティファクト内の該当ファイルを特定するためです(「Shorts→通常
動画への変換」・「ハマった罠」8番参照)。

## 多言語ボイス(`--voice random`)

土台の文字(母音中心)は変えず、espeak-ngが読み上げる**言語・性別**だけを
ランダムに変える機能です(`config.VOICE_LANGUAGES`)。`--voice random`で
以下19言語・男性/女性からランダムに選ばれます。

| 言語 | 男性 | 女性 | 単語の文字体系 |
|---|---|---|---|
| 英語 | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| フランス語 | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| ドイツ語 | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| ハンガリー語 | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| スウェーデン語 | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| ポルトガル語(ブラジル) | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| ポルトガル語(ポルトガル) | ○ | ○(MBROLA) | ラテン文字(Zalgo) |
| 中国語(標準語) | ○ | ○(フォルマント) | ラテン文字(Zalgo) |
| 広東語 | ○ | ○(フォルマント) | ラテン文字(Zalgo) |
| フィンランド語 | ○ | ○(フォルマント) | ラテン文字(Zalgo) |
| アイスランド語 | ○ | ○(フォルマント) | ラテン文字(Zalgo) |
| ベトナム語 | ○ | ○(フォルマント) | ラテン文字(Zalgo) |
| インドネシア語 | ○ | ○(フォルマント) | ラテン文字(Zalgo) |
| マレー語 | ○ | ○(フォルマント) | ラテン文字(Zalgo) |
| ルーマニア語 | ○ | ○(フォルマント) | ラテン文字(Zalgo) |
| ロシア語 | ○ | ○(フォルマント) | **キリル文字** |
| タイ語 | ○ | ○(フォルマント) | **タイ文字** |
| アラビア語 | ○ | ○(フォルマント) | **アラビア文字** |
| ヘブライ語 | ○ | ○(フォルマント) | **ヘブライ文字** |

女性ボイスは2種類。**MBROLA**(上記7言語のみ、`mbrola-*`パッケージが必要。
素の声よりやや低いため`-p`で補正、`config.FEMALE_VOICE_PITCH`)と、**フォル
マントバリアント**(残り12言語、`<voice>+f3`で追加パッケージ不要。f0が
108Hz→194Hzに上昇、MBROLA用ピッチ補正は重ねない。中国語のみ`cmn+f3`が必要、
「ハマった罠」11・13番)。

実在文字体系(ロシア語・タイ語・アラビア語・ヘブライ語)は少数派(4/19)の
ため、`--voice random`はまず`config.NATIVE_SCRIPT_VOICE_CHANCE`(デフォルト
30%)の確率で「実在文字体系 or ラテン文字」を決め、その中で言語を均等抽選
します(`generate.py _resolve_voice()`)。`generate.py`自体のデフォルトは
`en`固定ですが、`generate.yml`の`voice`入力デフォルトは`random`です。

### SEO関連の施策(いずれも`--upload`時)

- **現地語ハッシュタグ**: 選ばれた言語の「発音」を意味する現地語ハッシュ
  タグ(例: アラビア語`#نطق`)を説明文・タグに追加(`hashtag_word`)。英語は
  `#Pronunciation`があるため対象外。
- **タイトル・タグへの言語名追加**: 英語で「french pronunciation」と検索
  する層向けに、判明している言語ならタイトルに`in French?`、タグに`french
  pronunciation`を追加。英語自身は追加しない。
- **説明文への検索キーワード**: `tongue twister`・`language learners`を
  言語に関わらず常に追加。
- **視聴者属性ベースの現地語キーワード**(`config.AUDIENCE_REGION_PHRASES`):
  視聴者属性で上位のフィリピン・インドネシア・マレーシア向けフレーズを、
  動画のボイス言語と無関係に全動画へ追加。フィリピン語はespeak-ng非対応
  (「ハマった罠」14番)だがこちらは説明文のみなので影響なし。

### 実際の文字体系を使う言語

ロシア語・タイ語・アラビア語・ヘブライ語の4言語は単語自体をその言語の実際
の文字からランダム生成します(`random_script_word()`/`random_abugida_word()`)。
実在する単語ではなく文字をランダムに組み合わせた造語です。誤解を招かない
よう、`--upload`時は説明文と動画フレーム本体の両方に「実在の単語ではない」
旨を注記します(`is_native_script`引数、`frame_builder._sub_label()`。説明
欄だけでは伝わらなかった経緯は「ハマった罠」22番)。

文字体系の構造により2方式を使い分け: **`random_script_word()`**(クラス
ター方式、ロシア語・アラビア語・ヘブライ語。文字をランダムに選び連打する)
と**`random_abugida_word()`**(アブギダ方式、タイ語。子音字+母音記号で
音節を作る、詳細は「ハマった罠」12番)。アラビア語・ヘブライ語の文字プール
は`config._assigned_chars()`でUnicode範囲から機械的に構築しています。

## YouTubeへの自動アップロード

`--upload`は[YouTube Data API v3](https://developers.google.com/youtube/v3)
を使います。GitHub Actionsのようなブラウザ操作ができない環境向けに、事前
取得したOAuthリフレッシュトークンを使い回す方式です。

### 1. Google Cloud側の準備(初回のみ)

1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクトを作成し「YouTube Data API v3」を有効化。
2. 「OAuth同意画面」を設定(公開ステータスは「テスト」のままでよいが、その場合はアップロード先アカウントを「テストユーザー」に追加すること)。
3. 「認証情報」→「OAuthクライアントIDを作成」で種類は**デスクトップアプリ**を選択。

### 2. リフレッシュトークンの取得(初回のみ、ローカルで実行)

> **⚠️ 複数チャンネルを持つアカウントは要注意**: 実行時点でブラウザ上の
> YouTubeでアクティブなチャンネルに権限が発行されます。先にアップロード
> 先チャンネルへ切り替えてから、同じブラウザで実行してください。

```bash
pip install -r requirements-dev.txt
python3 get_youtube_refresh_token.py --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
```

認可後、`YOUTUBE_CLIENT_ID`/`YOUTUBE_CLIENT_SECRET`/`YOUTUBE_REFRESH_TOKEN`
に加え実際に認可されたチャンネル名・IDが標準出力に表示されます。意図した
チャンネルか必ず確認してください。

### 3. GitHub Secretsへの登録

| Secret名 | 必須 | 内容 |
|---|---|---|
| `YOUTUBE_CLIENT_ID` | ○ | OAuthクライアントID |
| `YOUTUBE_CLIENT_SECRET` | ○ | OAuthクライアントシークレット |
| `YOUTUBE_REFRESH_TOKEN` | ○ | 手順2で取得したリフレッシュトークン |
| `YOUTUBE_CHANNEL_ID` | 推奨 | アップロード先チャンネルID(`UC...`)。不一致ならアップロード前にエラーで止まる |
| `YOUTUBE_REFRESH_TOKEN_ISSUED_AT` | 推奨 | 手順2実行日(`YYYY-MM-DD`)。7日失効ルールの警告に使う |
| `YOUTUBE_SHORTS_PLAYLIST_ID` | 任意 | 設定するとShortsをこの再生リストに自動追加 |
| `YOUTUBE_REPOST_PLAYLIST_ID` | 任意 | 設定すると変換後の通常動画をこの再生リストに自動追加 |

### 4. 実行

- ローカル: `python3 generate.py --upload`(上記を環境変数にセット)
- GitHub Actions: Actionsタブ → **generate** → **Run workflow**。`upload`はデフォルト有効、`privacy_status`はデフォルト`public`。

### 5. リフレッシュトークンの失効監視

OAuth同意画面が「テスト」ステータスの場合、リフレッシュトークンは**発行
から7日で失効**します。`YOUTUBE_REFRESH_TOKEN_ISSUED_AT`を登録しておくと
`youtube_upload.get_youtube_client()`が経過日数をチェックし、5日経過で予告、
7日経過で警告をワークフローログに出します(`::warning::`、処理は止めない)。
再発行時は`get_youtube_refresh_token.py`を再実行し両方を更新してください。

### 6. APIクォータ使用量のログ

`--upload`/`repost_shorts.py`実行後、消費クォータ概算と残容量目安を実行
ログへ出力します(`youtube_upload.log_api_usage_summary()`)。

### 7. 再生リストへの自動追加(任意)

`YOUTUBE_SHORTS_PLAYLIST_ID`/`YOUTUBE_REPOST_PLAYLIST_ID`を設定する
と自動追加します(`add_to_playlist()`)。再生リスト自体はYouTube Studioで
事前に手動作成が必要です(URLの`list=`以降がID)。失敗しても動画本体は既に
公開済みなので警告のみで処理は続行します。

### 8. 概要欄の登録CTA

新規視聴者97%超・コア視聴者0.1%未満という偏りを踏まえ、全Shortsの概要欄
末尾に登録を促す一文を自動追加します。

### 9. 手動字幕とカテゴリ変更(SEO)

**カテゴリ**: `24`(Entertainment)から`26`(Howto & Style)に変更
(`config.YOUTUBE_CATEGORY_ID`、効果は未検証)。

**手動字幕**: ASRに任せると意味不明な文字起こしになるため、説明文と同趣旨
のキーワード付き固定テキストを1キューのSRT字幕として手動アップロードしま
す(`upload_caption()`)。

> **⚠️ `config.CAPTIONS_ENABLED = False`で現在無効化中**: 実機で断続的な
> 403 forbiddenを確認したため(「ハマった罠」21番)。有効化するには
> `True`に戻すこと。

> **⚠️ `captions.insert`は`youtube.force-ssl`スコープが必要**: 他のAPI
> 呼び出しとは別スコープです(「ハマった罠」19番)。有効化するには
> Google Cloud Console「OAuth同意画面」→「データアクセス」で
> `.../auth/youtube.force-ssl`を追加登録し、`get_youtube_refresh_token.py`
> を再実行してトークンを更新してください。

> **⚠️ クォータコストが大きい**: `captions.insert`は1回あたり**400
> units**(`videos.insert`の4倍)。日次上限(`config.DAILY_QUOTA_UNITS`、
> デフォルト10,000)に注意。

### 10. 運営者コメント・音声言語メタデータ・タイトルの日本語ローカライズ

**運営者コメント**: 字幕と同じキーワード付きテキストを運営者コメントとして
自動投稿(`post_comment()`、`config.COMMENT_ON_UPLOAD_ENABLED`でON/OFF、
デフォルトTrue)。「実在の単語ではない、ジョークだ」の注記を含みます
(説明欄・フレームより確実に読まれるため)。字幕と同じ`youtube.force-ssl`
スコープが必要で同様に不安定になりうる点は注意してください。ピン留め
専用APIは無いため、必要ならYouTube Studioから手動で行ってください。

**音声言語メタデータ**: `defaultAudioLanguage`に実際に読み上げた言語を設定
(glitch系は設定しない)。`defaultLanguage`は常に`"en"`。

**タイトルのローカライズ**: `localizations`フィールドで視聴者の表示言語ごと
にタイトルを出し分け(動画本体・音声・英語タイトルは不変)。追加スコープ・
クォータ消費は無し。

- **日本語**(`config.JAPANESE_TITLE_LOCALIZATION_ENABLED`、デフォルトTrue): 言語名の注記付き。
- **フィリピン語・インドネシア語・マレー語**(`config.EXTRA_TITLE_LOCALIZATION_ENABLED`、デフォルトTrue): `AUDIENCE_REGION_PHRASES`と同じフレーズを流用、誤訳リスクを避け言語名注記は無し。`config.EXTRA_TITLE_LOCALIZATIONS`にテンプレート追加で言語を増やせる。

いずれも、埋め込む単語がRTL文字(ヘブライ語・アラビア語)の場合に語順が
入れ替わる不具合(「ハマった罠」24番)への対策として、bidi isolate文字
(U+2068〜U+2069)で囲んでいます。

## カスタムサムネイル

動画本体のフレーム(キッカー+単語+モード注記+アイコン)とは別に、単語
だけを大きく表示したミニマルな16:9画像(`frame_builder.build_thumbnail()`)
を生成し`videos.thumbnails().set()`で設定します。タイトルはYouTube側が
一覧でテキスト表示するため、サムネイル画像に文言を重複させない設計です
(「ハマった罠」29番も参照)。

**制約**: カスタムサムネイル機能にはチャンネルの電話番号確認が必要です。
確認完了まで`config.CUSTOM_THUMBNAIL_ENABLED`はデフォルト`False`で、完了
後は`True`に切り替えるだけで有効化できます(コード変更不要)。失敗しても
動画本体は既に公開済みなので処理は継続します(`upload_thumbnail()`、
50 units)。

## Shorts→通常動画への変換

`upload_history.json`に記録された未変換のShortsを1本(`config.REPOST_MAX_PER_RUN`)、
動画本体をGitHub Actionsアーティファクトから取得し直し、横型(16:9)に
ピラーボックスした「通常動画」として、**元のShortsと同じタイトル・説明文
のまま**再アップロードします(`repost_shorts.py`、取得元の経緯は「ハマった
罠」8番)。

**なぜ1本ずつ別々に変換するのか**: 当初はShortsが10本たまるごとに1本の
結合動画にまとめていたが、再生数がほとんど伸びなかった。このチャンネルの
タイトル("How to Pronounce <word>")は「how to pronounce (記号/単語)」と
いう具体的な検索語との一致で再生数を得る性質が強く、10単語ぶんを1つの
タイトルにまとめると個々の単語の検索語に一致しなくなり、この強みを自ら
潰してしまっていた(類似フォーマットの他チャンネルが1記号1本・数秒の動画
で数百万再生を得ている実例を踏まえた判断)。そのため1本ずつ、Shortsと全く
同じタイトルを保ったまま変換する方式にした。

**なぜ横型への変換が必要か**: YouTubeのShorts判定はアスペクト比+尺のみで
機械的に決まるため、縦型のままでは短ければShorts扱いのままです。各クリップを
横型キャンバスにピラーボックス配置することで通常動画として扱われます。

**状態管理**: 変換済み(`converted_video_ids`)・諦めた動画(`skipped_video_ids`)
は`repost_state.json`に、アップロード履歴は`upload_history.json`に
記録しワークフロー末尾でコミットします(Actionsランナーは使い捨てのため)。
`uploaded_at`(ISO 8601)も各エントリに記録(古いエントリには無いため
`entry.get("uploaded_at")`で参照)。

**元Shorts⇔通常動画の相互リンク**: 変換成功後、元Shortsの概要欄に通常動画
へのリンクを、通常動画の概要欄に元Shortsへのリンクをそれぞれ追記し、検索で
どちらかにしか辿り着かなかった視聴者にもう片方への導線を示します
(`append_video_description()`、失敗しても他への影響なし)。

```bash
python3 repost_shorts.py --privacy-status unlisted --max-count 1
```

(認証は`--upload`と同じ環境変数に加え、アーティファクト取得用の
`GITHUB_TOKEN`[`actions:read`権限]・`GITHUB_REPOSITORY`が必要。GitHub
Actions内では自動設定されるためローカル実行時のみ指定)

## モード別パフォーマンス集計(`youtube_analytics.py`)

[YouTube Analytics API](https://developers.google.com/youtube/analytics)で
各Shortsの再生数・視聴維持率を取得し`upload_history.json`の`mode`と突き合
わせて集計します。投稿からの経過日数で正規化した1日あたり再生数
(`avg_views_per_day`)を主指標にしています(生の再生数だと新しい動画が
不利になるノイズが乗るため)。

```bash
python3 youtube_analytics.py                      # 過去28日(デフォルト)
python3 youtube_analytics.py --days 14
python3 youtube_analytics.py --days 90 --by-week   # 週別推移(長期の「飽き」傾向を見る)
python3 youtube_analytics.py --by-voice            # --voice randomの言語別集計
```

出力例:

```
=== モード別 再生数・視聴維持率集計(2026-08-22 〜 2026-09-19、対象87本) ===
  tts: 35本 / 1日あたり平均12.40回(単純平均210.5回, 視聴維持率38.2%)
  glitch: 18本 / 1日あたり平均7.10回(単純平均88.9回, 視聴維持率22.5%)
```

**必要な環境変数**: `--upload`と同じ3つに加え、`YOUTUBE_REFRESH_TOKEN`は
`yt-analytics.readonly`スコープを含めて**発行し直したもの**が必要です
(スコープは発行時に焼き付けられるため)。手順: (1) Cloud ConsoleでYouTube
Analytics APIを有効化 (2) OAuth同意画面にスコープ追加 (3)
`get_youtube_refresh_token.py`を再実行しトークン更新。`invalid_scope`エラー
が出る場合はリポジトリが古い可能性が高いので`git pull`してからやり直して
ください。GitHub Actionsからは`.github/workflows/analytics.yml`で実行でき
ます。Analytics APIのデータには1〜2日のラグがあります。

## 即時統計の確認(`youtube_quick_stats.py`)

`youtube_analytics.py`の1〜2日ラグを避け、投稿直後の初動を即時反映の値
(`videos.list(part=statistics)`)で確認します。

```bash
python3 youtube_quick_stats.py                # 過去24時間
python3 youtube_quick_stats.py --hours 6
```

経過日数による正規化は行わない軽量ツールです。モード間の公平な比較には
`youtube_analytics.py`を使ってください。環境変数・GitHub Actions
(`quick_stats.yml`)は共通です。

## 流入元の確認(`youtube_traffic_source.py`)

動画が伸びた理由(関連動画・フィード露出・検索・外部リンク)を
`insightTrafficSourceType`ディメンションで診断します。

```bash
python3 youtube_traffic_source.py --video-id mFGTwTBPy7Q --days 7
```

```
=== 動画 mFGTwTBPy7Q の流入元別再生数(合計1070回) ===
  関連動画のおすすめ(RELATED_VIDEO): 700回 (65.4%)
  YouTube内検索(YT_SEARCH): 200回 (18.7%)
```

同じAnalytics APIのため1〜2日のラグがあります。GitHub Actionsは
`traffic_source.yml`。なお実際の検索クエリ自体はAPIで取得できません
(`insightTrafficSourceDetail`は`YT_SEARCH`非対応、「ハマった罠」25番)。

## 日本語ローカライズが崩れて表示された動画の手動修正(`youtube_fix_localization.py`)

「ハマった罠」24番のbidi修正は新規アップロード分にしか効かないため、
修正前に公開した動画(ヘブライ語・アラビア語の回)を個別に直すツールです。

```bash
python3 youtube_fix_localization.py --video-ids ABC123,DEF456
```

タイトルの`「」`内(label)をbidi isolate文字で囲み直して`videos.update`
します。既に修正済み・`localizations.ja`が無い動画はスキップ。追加スコープ
不要。GitHub Actionsは`fix_localization.yml`。

## YouTubeチャンネル用アセット(アイコン・バナー)

```bash
python3 generate_channel_art.py --outdir ./assets
```

```
assets/
  icon.png    800x800   チャンネルアイコン(円形クロップ対応で中央に要素を収める)
  banner.png  2560x1440  チャンネルバナー(セーフエリア1546x423にタイトル・タグライン)
```

## ハマった罠(実装時のデバッグ記録)

後から追う人のための要点メモです。詳しいコード参照は各項目内のファイル/
関数名を参照してください。

1. **結合文字を積んでも「無音」にならないことがある**: ヘブライ語母音記号
   (`U+05B0`-`U+05BD`)等はespeak-ngが読み上げてしまう。`SAFE_COMBINING_BLOCKS`
   は実機で無音確認済みのコードポイントのみで構成。
2. **異なるブロックの結合文字を混ぜると読み上げが暴発する**: 個別に無音でも
   混在させると一部が読み上げられる。`_random_combining_stack()`は単一ブロック
   からのみ選ぶ。
3. **未割り当てコードポイントは「豆腐」になる**: `U+20D0`-`U+20FF`の一部。
   除外経緯は10番。
4. **フレーム画像はPILではなくブラウザで描く**: Zalgo結合文字は単一フォント
   に揃わないため、Chromium(Playwright)+HTML+fontconfigフォールバックを使用。
5. **動画尺は固定パディングしない**: `apad`は不自然な無音を生むため撤回。
   `finalize_audio()`が末尾フェード、`-shortest`で音声実長に追従。
6. **「ENCLOSING」系結合文字は豆腐ではないが表示が崩れる**: `U+20D0`-`U+20F0`
   のENCLOSING系(例`U+20E3`)は大きな図形で土台文字を覆う。最終的にブロック
   ごと除外(経緯は10番)。
7. **1つのGoogleアカウントに複数チャンネルがあると誤爆する**: APIはエラー
   を返さずアクティブだったチャンネルへ黙ってアップロードする。
   `YOUTUBE_CHANNEL_ID`設定で不一致時にエラー停止。
8. **Shorts→通常動画変換の取得はYouTubeではなくGitHub Actionsアーティファクト
   から**: 当初yt-dlpで再ダウンロードしていたが、ActionsランナーのIPが
   ボット判定される問題があった(別リポジトリで確認)。`generate.yml`が保存
   したアーティファクトをGitHub Actions APIで取得する方式に変更、`run_id`で
   対象runを特定。privacyStatusに関係なく取得可能になった利点もある。移行前
   のエントリ・90日超過分は変換対象外。
9. **同じブランチにsquash mergeを繰り返すと無関係な変更まで衝突扱いになる**:
   merge-baseが古いまま止まるため。対策: 新しい変更前に`git merge origin/main`。
10. **動画フレームは長らく「ほぼZalgoではない文字列」を表示していた**:
    `build_frame()`が`readable_label()`(結合文字を落とす)を誤って流用していた。
    `zalgo_display_word()`を新設し表示用/サイジング用を分離。この際に発覚:
    `U+20D0`-`U+20F0`ブロックが軒並み豆腐→ブロックごと除外、`U+1DFA`だけ
    結合しない→個別除外、深い結合スタックがキッカー文言と衝突→上下マージン
    追加+表示用に`max_marks_per_cluster`(デフォルト4)で切り詰め。
11. **中国語のMBROLA女性ボイス(`mb-cn1`)はパッケージ自体が壊れている**:
    存在しない`zh_phtrans`を参照しエラーになる(実際は`cmn_phtrans`)。13番の
    フォルマントバリアント方式で回避。
12. **タイ文字は子音字だけでは音節として成立しない**: `random_script_word()`
    は文字体系として不完全。専用の`random_thai_word()`(母音記号を70%の確率で
    付加)を実装、後に`random_abugida_word()`として一般化。
13. **MBROLA非対応言語の女性ボイスはespeak-ng内蔵の`+f3`で代替できる**:
    `<voice>+f3`でエラー無く合成可能、f0が108Hz→194Hzに上昇(MBROLA実測
    235Hzに近い)。中国語のみ`zh+f3`はNGで`cmn+f3`が必要。MBROLA用ピッチ補正
    (`-p`)と併用すると258Hzまで上がりすぎるため併用しない。
14. **フィリピン語はespeak-ngに存在しない、インドネシア語は存在する**:
    `fil`/`tl`は非対応。`id`は正常動作。フィリピン語の代替として近縁の
    マレー語(`ms`)を「マレー語として正直に」追加。
15. **YouTubeアナリティクスの地域データから未対応言語を洗い出す**: 視聴者
    上位国(トルコ・ブラジル・ポルトガル・ルーマニア)向けに追加、29言語に。
    トルコ語・ポルトガル語(ブラジル/ポルトガル)はMBROLA女性ボイスあり、
    ルーマニア語は`+f3`のみ。
16. **アナリティクスの裏付けが無い「珍しい文字体系」言語を9つ削除**: 29言語
    は出現頻度が薄すぎると判断。視聴地域の裏付けが無く役割が被っていた
    チェロキー語・タミル語・テルグ語・シンハラ語・ベンガル語・アルメニア語・
    アムハラ語・ジョージア語・ミャンマー語を削除、20言語に。
    `NATIVE_SCRIPT_VOICE_CHANCE`(30%)は値そのまま維持。
17. **`tts_extreme`は短い単語×速い読み上げが重なると一瞬のノイズになる**:
    実機200回試行で最短0.1秒(0.5秒未満43%)。`_stretch_to_min_duration()`
    で`TTS_EXTREME_MIN_DURATION_SECONDS`(0.6秒)未満なら`atempo`で引き伸ばす
    (`_atempo_chain_for_factor()`でチェーン)。修正後150回試行で0.5秒未満0件。
18. **「投稿本数を減らすべきか」の判断には経過日数の効果と長期トレンドの
    区別が要る**: `--by-week`(`summarize_by_week()`)で正規化済み指標を週別に
    並べ、右肩下がりなら「飽き」を疑う材料にする。
19. **`UPLOAD_SCOPES`に未付与のスコープを1つ混ぜただけでアップロード全体が
    止まった**: `youtube.force-ssl`を共有スコープに混ぜたところトークン
    リフレッシュ自体が`invalid_scope`で失敗し本番事故に。
    `get_youtube_client(scopes=None)`を該当関数だけに使う設計に修正。教訓:
    新しいスコープはそれを使う関数だけに絞る。
20. **`MODE_WEIGHTS`でglitchを下げた判断を実測で撤回した**: 主観で`2:2:1`に
    下げていたが、`--by-week`の2回の集計でいずれもglitchが最上位
    (9/21: 24.12>10.55>2.28、9/22: 57.26>37.11>6.09)。`1:1:1`に戻した。
21. **手動字幕(`captions.insert`)が断続的に403 forbiddenになり一時無効化
    した**: 3回中2回失敗。OAuth同意画面が未検証の制限付きスコープは断続的に
    拒否されるとみられる(確定原因ではない)。`config.CAPTIONS_ENABLED = False`
    で無効化。教訓: 1回成功しただけで直ったと判断しない。
22. **実在文字体系の「実在の単語ではない」注記は説明欄だけでは伝わらな
    かった**: 実際の話者から誤解コメントが付いた。動画フレーム自体
    (`_sub_label()`)にも注記を焼き込んで対応。
23. **`--mode glitch`が毎回似通って聞こえる問題をレイヤー重ね+テンポ密度の
    ランダム化で緩和した**: 2〜3レイヤーを`amix`で重ね、`high`/`low`の
    テンポ密度をランダム選択。
24. **タイトルの日本語ローカライズがRTL文字の回だけ語順が入れ替わって
    表示された**: Unicode双方向アルゴリズム(UAX #9)により`label`がRTL文字
    だと文字列全体の基準方向がRTL判定される。`label`をFirst Strong Isolate
    (U+2068〜U+2069)で囲んで解決。既存公開分は`youtube_fix_localization.py`
    で個別修正が必要。
25. **`insightTrafficSourceDetail`は`YT_SEARCH`では使えない**: 同じAPI・
    スコープで動くと想定したが`400 Bad Request`(プライバシー上の制限と
    みられる)。機能を撤回。教訓: ディメンション/フィルタの組み合わせ可否は
    実装前に確認が要る。
26. **トルコ語話者から繰り返し「本物のトルコ語ではない」指摘を受け言語
    プールから撤去した**: ジョーク注記を追加しても指摘が続いた(同じ視聴者
    のロシア語コメントは好意的だった)。教訓: 否定的な反応が繰り返される
    言語だけ個別に見直す。
27. **楔形文字・エジプト/アナトリア象形文字・線文字B表意文字は「絵のように
    見える」がespeak-ngで長大な音声になる**: Playwright+Notoフォントで
    5文字組み合わせると絵のような見た目になる一方、espeak-ngはコードポイント
    を桁ごとに読み上げ17〜18秒になる。単語の音に依存しない`glitch`モード
    専用に採用(`config.PICTOGRAPH_SCRIPTS`、`PICTOGRAPH_VISUAL_CHANCE`
    デフォルト0.4)。
28. **`reverse`/`robot_voice`/`chorus`/`morse`追加時に踏んだ3つの罠**:
    (1) リング変調(`amultiply`)はRMS音量が約20dB低下→`volume`+`alimiter`で
    補正(chorusのamixも同様)。(2) ヘブライ語ボイスはZalgo単語で他18言語
    (1.4〜2.6秒)の3倍(7.6〜7.7秒)になる→`CHORUS_VOICE_LANGUAGE_CODES`で
    ヘブライ語のみ除外。(3) モールス信号は標準速度だと1本15秒超→1ユニット
    0.015〜0.03秒にランダム化。chorus/morseは常に`random_zalgo_word()`を
    使用(言語不一致/符号表がラテン文字限定のため)。
29. **サムネイルの文字数ベースのフォントサイズ見積もりは楔形文字/
    ヒエログリフで大きくはみ出す**: ラテン文字前提の`_thumbnail_word_font_size()`
    は象形文字の実描画サイズに対応できずフレームから見切れた。実際の
    `scrollWidth`/`scrollHeight`を見て段階的に縮める`_shrink_word_to_fit()`
    に変更。
30. **Shorts10本の結合動画は再生数がほとんど伸びなかった**: 類似フォーマット
    の他チャンネル(1記号1本・数秒の動画で数百万再生)と見比べて、このチャン
    ネルのタイトル("How to Pronounce <word>")は検索語との完全一致で再生数を
    得る性質が強いと判断。10単語ぶんを1つのタイトルにまとめる結合動画は、
    個々の単語の検索語に一致しなくなりこの強みを自ら潰していた。`compile_shorts.py`
    (`COMPILATION_BATCH_SIZE`件たまるごとに結合)を廃止し、`repost_shorts.py`
    で1本ずつ元Shortsと同じタイトルのまま横型動画に変換する方式に置き換えた。

## プロジェクト構成

```
config.py                    全モジュール共通の設定・定数
word_generator.py            Zalgo風「発音不能な単語」の生成
tts_synth.py                  TTS(espeak-ng)による音声合成 [--mode tts / tts_extreme /
                               reverse / robot_voice / chorus]
glitch_synth.py               合成グリッチ音による音声生成 [--mode glitch]
morse_synth.py                モールス信号のビープ音による音声生成 [--mode morse]
audio_utils.py                繰り返し・パディング無しフェード・mp3変換
frame_builder.py              "How to Pronounce" フレーム画像・カスタムサムネイルの生成(Playwright)
video_builder.py              フレーム+音声 → mp4 の合成
youtube_upload.py             YouTube Data API v3への動画/サムネイルアップロード [--upload]
upload_history.py             アップロード成功履歴(upload_history.json)の読み書き
repost_state.py                Shorts→通常動画変換の状態(repost_state.json)管理
repost_shorts.py               Shortsを1本ずつ横型の通常動画に変換してアップロード
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
