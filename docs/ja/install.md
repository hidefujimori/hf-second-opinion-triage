# 導入ガイド — Jev Triage（β版）

## 前提条件

| 項目 | 条件 |
|---|---|
| Splunk Enterprise Security | 8.7.1 以降 |
| Splunk プラットフォーム | Splunk Enterprise 10.x（10.4.2 で検証）。Splunk Cloud Platform（Victoria）: Splunk の自動審査（AppInspect の Cloud 向けチェック）は合格。実際の Cloud 環境では未検証 — [Splunk Cloud での注意](#splunk-cloud-での注意)を参照 |
| Python | 3.13 または 3.9（Splunk が使える新しい方を選びます） |
| ネットワーク | 検索ヘッドから `api.typesafe.ai` への外向き HTTPS（443）。LLM を使う場合はその接続先も。HTTPS プロキシは Setup 画面で設定可能 |
| アカウント | TypeSafe Jev の API キー。任意で LLM の API キー（Bedrock の場合は AWS のキー） |
| 配置 | ES が動く検索ヘッドに入れます（検索ヘッドクラスタは deployer から配布）。インデクサやフォワーダには不要（下記の index を除く） |

### index

アプリは index `jev_triage`（トリアージ結果の履歴）を定義しています。シングル構成ではアプリが作成します。
分散構成ではインデクサ（またはインデクサクラスタ）に `jev_triage` を作成してください。
なくてもアプリは動きますが、履歴のコピーが残りません。

## インストール

### Splunk Enterprise

1. Apps > Manage Apps > **Install app from file** で `TA-jev-triage-<版>.spl` を選び、Upload します。
2. 求められたら Splunk を再起動します。
3. 更新の場合も同じ手順で **Upgrade app** にチェックを入れます。設定とキーは引き継がれます。

### Splunk Cloud Platform（Victoria）

1. `sc_admin` で Apps > Manage Apps > **Upload App** から `.spl` を選びます。
2. Splunk が自動審査を行います。現在の Cloud 向けチェックでは失敗 0、エラー 0、手動確認 0 です。
   いくつか警告が残ります（[リファレンス](reference.md#既知の制限β版)を参照）。

## 設定（Setup 画面）

アプリを開くと、初回は **Setup** 画面が開きます。以後はメニューの **Setup** から開きます。

| 区分 | 設定する内容 |
|---|---|
| TypeSafe Jev | **Jev の API キー**。モデルは指示がない限り変更しません。プロキシは任意 |
| Enrichment（情報収集） | データの場所: **CloudTrail のデータ**（マクロ `jev_cloudtrail`）と**エンドポイントのプロセスデータ**（マクロ `jev_endpoint`）。実際の index 名を指定します（`index=*` は遅い） |
| LLM による説明 | 任意。**プロバイダ**（`anthropic`、`openai` = OpenAI 互換の任意のサーバー、`bedrock`、`gemini`）、**モデル**、キー、必要ならエンドポイント / リージョン / プロキシ |
| ES の Finding への Note | Note の言語（`en` / `ja`） |
| 自動実行の上限 | 自動の Jev トリアージと自動の LLM 説明の1日の上限（[利用ガイド](user-guide.md#自動実行の上限)を参照） |

**保存**を押し、**接続テスト**を押します。表で Jev（LLM を設定した場合は LLM も）が `ok` になれば完了です。
設定は次の検索から反映され、再起動は不要です。

> Google Gemini の無料枠を使う場合、Google がプロンプトを製品改善に使うことがあります。テストデータだけで使ってください。

## 権限

| 誰が | 必要なもの |
|---|---|
| Setup を行う管理者 | `admin_all_objects` または `edit_storage_passwords`（Splunk Cloud では `sc_admin`） |
| アプリを使うアナリスト（ボタン、手動のレスポンスアクション） | アプリに含まれる **`jev_triage_user`** ロール（`list_storage_passwords` を持つ）。付与したあと Setup 画面で一度**保存**を押し、キーをこのロールに共有します。アナリストが読めるのは Jev / LLM のキーだけで、他の資格情報は読めません |
| ES の Finding への Note 書き込み | `mc_investigation_write`（ES の `ess_analyst`、`ess_admin` が持っています） |
| **再トリアージ**ボタンでの index `jev_triage` への履歴の書き込み | `edit_tcp`。なければ KV ストアだけを更新します |
| レスポンスアクションを付けた検知 | 検知の所有者（通常は `nobody` → `splunk-system-user`）で動くため、追加の権限は不要です |

KV ストアのコレクション `jev_triage_latest` と `jev_usage` には、`admin`、`sc_admin`、`ess_admin`、
`ess_analyst`、`jev_triage_user` が書き込めます。

## Splunk Cloud での注意

確認済み: AppInspect の Cloud 向け審査に合格（報告書: `appinspect_cloud_<版>.json`）。
実際の Cloud 環境では未確認のため、次の点について結果を教えてください。

- Cloud の検索ヘッドから `api.typesafe.ai` と LLM の接続先への外向き HTTPS
  （止められている場合は Splunk サポートに相談するか、Admin Config Service を使います）
- index `jev_triage`（必要なら Admin Config Service で作成）
- `sc_admin` で Setup 画面からキーを保存できるか
- Cloud 上の ES での Note とレスポンスアクションの状況表示

## アンインストール

アプリを無効化または削除します（Apps > Manage Apps）。必要なら index `jev_triage` と、
保存したキー（REST の `storage/passwords`、realm `TA-jev-triage`）も削除します。
ES の Finding に書き込んだ Note は残ります。
