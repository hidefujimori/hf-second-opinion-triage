# リファレンス — Jev Triage（β版）

## 設定（`jev_triage.conf`）

通常は Setup 画面で変更します。既定値は `default/jev_triage.conf`、変更は `local/` に保存されます。

| スタンザ / キー | 既定 | 意味 |
|---|---|---|
| `[jev] model` | `jev-1.13.0` | Jev のモデル（固定） |
| `[jev] confidence_threshold` | 0.60 | これ未満の Disposition は判別不可 |
| `[jev] escalation_floor` | 0.80 | Jev の「エスカレーションが必要」がこれ以上なら Urgency を High 以上に |
| `[jev] rollup_urgency_cap` | high | リスク集約・Finding グループの Urgency の上限 |
| `[jev] order_check` | true | 選択肢を逆順にしてもう一度聞き、食い違えば判別不可 |
| `[jev] timeout`, `parallel`, `proxy` | 30, 4, — | タイムアウト（秒）、同時に処理する Finding 数（1〜8）、HTTPS プロキシ |
| `[enrichment] enabled`, `max_facts`, `shared_entities` | true, 12, `*.amazonaws.com,…` | 情報収集。結合キーに使わないパターン |
| `[llm] provider`, `model`, `endpoint`, `region`, `thinking_level`, `max_tokens`, `timeout`, `language`, `proxy` | anthropic, —, —, —, —, 600, 60, en, — | 説明に使う LLM。`thinking_level`: gemini → thinkingLevel（Gemma 4 は `minimal`）、openai → reasoning_effort（Ollama の gemma4・qwen3 は `none`、gpt-oss は `low`）。OpenAI 互換には常に `stream: false` を送ります |
| `[es_note] language` | en | Note の言語 |
| `[limits] llm_auto_daily` | 100 | 自動の LLM 説明の1日の上限（空欄 = 無制限） |
| `[limits] jev_auto_daily` | 空欄 | 自動実行で Jev に送る Finding の1日の上限 |

マクロ: `jev_cloudtrail`（CloudTrail のデータ）、`jev_endpoint`（エンドポイントのプロセスデータ）、
`jev_findings`（Finding の取得元、`` `notable` ``）。

キー: `storage/passwords`、realm `TA-jev-triage`、名前は `typesafe_api_key`、`llm_api_key`、
`aws_access_key_id`、`aws_secret_access_key`。

## サーチコマンド

| コマンド | 用途 |
|---|---|
| `jevtriage [persist=true] [auto=true] [dryrun=true] [enrich=false] [ordercheck=false]` | `` `jev_findings` `` の行をトリアージ |
| `jevexplain [lang=en\|ja] [force=true] [persist=true] [auto=true min_urgency=… dispositions=…]` | `jev_triage_latest` の行の LLM 説明 |
| `jevnote [lang=en\|ja] [force=true] [persist=true]` | ES の Finding に Note を書く |
| `jevcheck [target=jev\|llm\|all]` | 接続テスト（キーは出力しません） |
| `jevqueue` | レスポンスアクションの依頼を処理（定期検索で使用） |

例:
```
`jev_findings` | head 3 | jevtriage dryrun=true | table event_id jev_state
| inputlookup jev_triage_latest where event_id="<id>" | jevexplain lang=ja
| jevcheck
```

## 保存されるデータ

| 場所 | 内容 |
|---|---|
| KV ストア `jev_triage_latest` | Finding ごとの最新の結果（提案、送った情報、回答、説明、Note の記録、再トリアージの情報） |
| KV ストア `jev_usage` | 日ごとの件数（`jev_auto`、`jev_manual`、`llm_auto`、`llm_manual`） |
| KV ストア `jev_triage_queue` | 検知からの依頼。完了した依頼は1日後に削除 |
| index `jev_triage` | 履歴（自動実行は `jev:triage:result`、再トリアージは `jev:triage:json`） |
| index `cim_modactions` | Finding ごとのレスポンスアクションの状態（`action_name=jev_triage`） |
| ES の Note | 提案の文章。操作したユーザーの名前で書き込まれます |

## Splunk の外に送るデータ

- **TypeSafe Jev**（`api.typesafe.ai`）へ: Finding の英語の説明（ルール、項目、区分に変換した件数）と、
  情報収集で得た事実（アカウント名・ホスト名、分類、結果）。生のイベントは送りません。
- **LLM** へ（説明するときだけ）: 同じ説明と Jev の提案。
- 画面を開くだけでは何も送りません。

## トラブルシューティング

| 症状 | 確認すること |
|---|---|
| 接続テストが失敗する | `api.typesafe.ai` や LLM への通信・プロキシ、キーが保存済みか（Setup に「保存済み」と出るか） |
| 説明が `empty answer … thinking` で失敗する | 思考するモデルが最大トークン数を使い切っています。Thinking level を設定する（`none`、gpt-oss は `low`）か、最大トークン数を増やす |
| アナリストで「API key not found」 | `jev_triage_user` ロールを付与し、Setup 画面で一度**保存**を押す |
| レスポンスアクションが failure | `index=cim_modactions action_name=jev_triage` と `index=_internal source=*jev_triage_modalert.log` |
| 検知は動くがトリアージされない | *Jev Triage - Response Queue* が有効か。`jev_usage` の上限（状態が skipped） |
| コマンドのエラー | ジョブの search.log（Job Inspector）で `ChunkedExternProcessor` を探す |
| トリアージが遅い | 情報収集のマクロを実際の index に向ける。検索ヘッドが混んでいれば `[jev] parallel` を下げる |

## 既知の制限（β版）

- 検証は Splunk Enterprise 10.4.2 ＋ ES 8.7.1 のみ。Splunk Cloud は審査合格、実環境での動作は未検証
  （[導入ガイド](install.md#splunk-cloud-での注意)を参照）。
- 画面は Splunk 標準のページテンプレート（`pages/splunk_ui_app.html`）を使います。Splunk 9.x 系では未検証です。
- 残っている AppInspect の警告: Response Queue が毎分動く（意図どおり）、同梱の Splunk SDK for Python が 2.1.1
  （3.x は Python 3.13 専用）、画面のバンドルに `@splunk/react-page` の SplunkJS のレイアウト処理が含まれる。
- 並行処理のため、1日の上限を最大で同時処理数だけ超えることがあります。
- *Write ES Note* をオンにして同じ Finding に手動でレスポンスアクションを繰り返すと、そのたびに Note が増えます（毎回が新しい結果のため）。
- 精度の数値は BOTS v3 の Finding 33件での結果です。実際のデータでは変わります。

## ソースからのビルド

画面は React（Splunk UI Toolkit）です。ソースは `app/ui`。ビルド手順は[英語版](../en/reference.md#building-from-source)と同じです。
