# クイックスタート — Jev Triage for Splunk Enterprise Security（β版）

インストールから最初の提案が出るまで、約15分です。詳しくは[導入ガイド](install.md)、
[利用ガイド](user-guide.md)、[リファレンス](reference.md)を参照してください。

> **β版です。** Jev Triage は ES の Finding に対して Disposition と Urgency を**提案**します。
> ES の項目は変更しません。最終的な判断は Enterprise Security でアナリストが行います。

## 必要なもの

- Splunk Enterprise Security **8.7.1 以降**（検証済み: Splunk Enterprise 10.4.2 ＋ ES 8.7.1）
- **TypeSafe Jev の API キー**（https://docs.typesafe.ai）
- 検索ヘッドから `api.typesafe.ai` への外向き HTTPS 通信
- 任意: 口語の説明を作る LLM（Anthropic、Amazon Bedrock、OpenAI 互換、Google Gemini）とその API キー
- 管理者アカウント（Splunk Cloud では `sc_admin`）

## 1. アプリを入れる

- **Splunk Enterprise:** Apps > Manage Apps > **Install app from file** で
  `TA-jev-triage-<版>.spl` を選んで Upload し、Splunk を再起動します。
- **Splunk Cloud Platform（Victoria）:** Apps > Manage Apps > **Upload App**。自動で審査され、再起動は不要です。

## 2. キーを入れる（Setup 画面）

アプリ **Jev Triage** を開きます。初回は **Setup** 画面が開きます（以後はメニューの **Setup**）。

1. **TypeSafe Jev > Jev の API キー** にキーを貼り付けます。
2. **LLM による説明**（任意）: **プロバイダ**を選び、**モデル**と **API キー**を入れます。
3. **Enrichment（情報収集）**: **CloudTrail のデータ**と**エンドポイントのプロセスデータ**を実際の index に
   向けます（例: `index=aws sourcetype=aws:cloudtrail`）。既定の `index=*` でも動きますが遅くなります。
4. **保存**を押し、**接続テスト**を押します。両方の行が `ok` になれば完了です。

キーは Splunk の暗号化された資格情報ストアに保存され、保存後は表示されません。

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
