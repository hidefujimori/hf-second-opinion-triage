# クイックスタート — HF Decision Model Triage and Second Opinion App（β版）

インストールから最初の提案が出るまで、約15分です。詳しくは[導入ガイド](install.md)、
[利用ガイド](user-guide.md)、[リファレンス](reference.md)を参照してください。

> **β版です。** Jev Triage は ES の Finding に対して Disposition と Urgency を**提案**します。
> ES の項目は変更しません。最終的な判断は Enterprise Security でアナリストが行います。

## 必要なもの

- Splunk Enterprise Security **8.7.1 以降**（検証済み: Splunk Enterprise 10.4.2 ＋ ES 8.7.1）
- **TypeSafe Jev の API キー**（https://docs.typesafe.ai）
- 検索ヘッドから `api.typesafe.ai` への外向き HTTPS 通信
- 任意: 口語の説明を作る LLM（Anthropic、Amazon Bedrock、OpenAI 互換、Google Gemini）とその API キー。
  社内ネットワークのローカル LLM（Ollama、Mac の Apple Foundation Models）も使えます（[任意: ローカルの LLM](#任意-ローカルの-llm)）
- 管理者アカウント（Splunk Cloud では `sc_admin`）

## 1. アプリを入れる

- **Splunk Enterprise:** Apps > Manage Apps > **Install app from file** で
  `second_opinion_triage-<版>.spl` を選んで Upload し、Splunk を再起動します。
- **Splunk Cloud Platform（Victoria）:** Apps > Manage Apps > **Upload App**。自動で審査され、再起動は不要です。

## 2. キーを入れる（Setup 画面）

アプリ **Jev Triage** を開きます。初回は **Setup** 画面が開きます（以後はメニューの **Setup**）。

1. **TypeSafe Jev > Jev の API キー** にキーを貼り付けます。
2. **LLM による説明**（任意）: **プロバイダ**を選び、**モデル**と **API キー**を入れます。
   ローカルの LLM は[任意: ローカルの LLM](#任意-ローカルの-llm)を参照してください。
3. **Enrichment（情報収集）**: **CloudTrail のデータ**と**エンドポイントのプロセスデータ**を実際の index に
   向けます（例: `index=aws sourcetype=aws:cloudtrail`）。既定の `index=*` でも動きますが遅くなります。
4. **保存**を押し、**接続テスト**を押します。両方の行が `ok` になれば完了です。保存するまでは、ボタンの上に
   「変更はまだ保存されていません」と表示されます。

キーは Splunk の暗号化された資格情報ストアに保存され、保存後は表示されません。

### 任意: ローカルの LLM

説明を社内ネットワーク内のモデルで作れば、プロンプトは外に出ません。下のサーバーはどれも OpenAI 互換の API なので、
**プロバイダ**は `openai`、**API キー**は空欄にします。

> **LLM を呼ぶのはブラウザではなく Splunk の検索ヘッドです。** エンドポイントに `localhost` と書くと Splunk サーバー
> 自身を指します。自分の PC や Mac で動かしているモデル（Ollama、vLLM、LM Studio、`fm serve`）は、Splunk サーバーから
> ネットワーク経由で届く場合だけ使えます。サーバーを localhost だけでなくネットワークで待ち受けるように起動し、
> そのマシンの IP アドレスかホスト名を入れてください。アドレスが変わると設定が使えなくなるので、固定がおすすめです。
> レスポンスアクションからの自動説明も同じ経路を使います。

**Mac の Apple Foundation Models（`fm serve`）**

1. Mac（macOS 27、Apple Intelligence がオン）で、他のマシンから届くようにサーバーを起動し、ターミナルは開いたままにします。
   ```
   fm serve --host 0.0.0.0 --port 1976
   ```
   macOS のファイアウォールがオンの場合は、`fm` への着信接続を許可してください。
2. Splunk の検索ヘッドから確認します: `curl http://<MacのIP>:1976/v1/models` でモデル `system` が表示されれば OK です。
3. Setup 画面で次のように設定します。

   | 項目 | 値 |
   |---|---|
   | プロバイダ | `openai` |
   | モデル | `system` |
   | エンドポイント | `http://<MacのIP>:1976/v1`（`http://`、ポート、`/v1` まで書く） |
   | Thinking level | 空欄（なし） |
   | LLM の API キー | 空欄 |

4. **保存**を押し、**接続テスト**を押します。

Mac はスリープさせず、`fm serve` を動かしたままにしてください。IP アドレスは固定がおすすめです。`fm serve` には認証が
ないため、ポートに届く人は誰でも使えます。ファイアウォールで制限してください。

**Ollama**

Ollama をネットワークで待ち受けるように起動し（`OLLAMA_HOST=0.0.0.0`）、プロバイダ `openai`、エンドポイント
`http://<ホスト>:11434/v1`、モデルは Ollama に表示される名前（例: `gemma4:26b`）、Thinking level は `none`
（`gpt-oss` は `low`）にします。

**vLLM などの OpenAI 互換サーバー**

エンドポイント `http://<ホスト>:<ポート>/v1`（vLLM の既定は 8000。localhost だけで待ち受けている場合は `--host 0.0.0.0` で起動）、モデルは提供している
モデル名（vLLM: `curl http://<ホスト>:8000/v1/models` で確認）。思考するモデルで回答が空になる場合は、
Thinking level（`reasoning_effort` として送信）を設定するか、最大トークン数を増やしてください。

他のモデル、速度、トラブルシューティング: [導入ガイド > ローカルの LLM](install.md#ローカルの-llmollamaapple-foundation-models)

### 任意: Jev の代わりにローカルの判定モデル

推奨は Jev です。Finding の情報をネットワークの外に出せない場合は、自前の llama.cpp サーバーで動かす
**Cloudflare Clef 27B** を、条件付きで Jev の代わりに使えます。Setup > TypeSafe Jev で、エンドポイント
`http://<ホスト>:<ポート>/v1/systemone`、モデル `clef-27b`、判別不可の基準 **0.45** にし、24 GB 以上の GPU を用意します
（48 GB の Mac でも動きますが遅いため、同時実行数 1、タイムアウト 180）。ほかに試したローカルのモデル（Clef-Flash、Kev）は推奨しません。
条件と結果: [リファレンス > Jev 以外の判定モデル](reference.md#jev-以外の判定モデル条件付き0915-以降)。

## 3. アナリストが使えるようにする

アナリストのロールに **`jev_triage_user`** ロールを追加します（設定 > ロール > *アナリストのロール* > 継承）。
そのあと Setup 画面でもう一度**保存**を押して、保存済みのキーをこのロールに共有します。管理者は追加の設定は不要です。

## 4. Finding をトリアージする

- **1件だけ:** ES の Analyst Queue で Finding を開き、**Run adaptive response action** >
  **Jev Triage** > 実行。数秒でアプリに結果が出ます。
- **検知の新しい Finding すべて:** 検知（相関検索）を編集し、**Finding** アクションと並べて
  レスポンスアクション **Jev Triage** を追加します。検知の実行から1〜2分で結果が出ます。
- **既存の Finding:** 定期検索 *Jev Triage - Untriaged Findings* を有効にするか
  （設定 > サーチ、レポート、アラート）、アプリで Finding を開いて**再トリアージ**を押します。

## 5. 結果を見る

**Jev Triage**（アプリのホーム）を開きます。一覧には Finding ごとに、提案された Urgency
（Critical 赤、High 橙、Medium 黄、Low 青）と Disposition（TP、FP、Benign、判別不可）が表示されます。
行をクリックすると右側に詳細が開きます。

- **LLM で説明** — 提案を口語で説明します
- **ES に Note を書く** — 提案（と説明）を ES の Finding に Note として書き込みます
- **ES で開く** — Enterprise Security の Finding に戻ります

右上の **English / 日本語 (JA)** で言語を切り替えます。

## 次に読むもの

- LLM の自動説明と1日の上限: [利用ガイド > 自動実行の上限](user-guide.md#自動実行の上限)
- 権限、設定項目、トラブルシューティング: [リファレンス](reference.md)
