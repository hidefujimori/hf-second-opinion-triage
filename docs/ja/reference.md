# リファレンス — HF Decision Model Triage and Second Opinion App（β版）

## 設定（`jev_triage.conf`）

通常は Setup 画面で変更します。既定値は `default/jev_triage.conf`、変更は `local/` に保存されます。

| スタンザ / キー | 既定 | 意味 |
|---|---|---|
| `[jev] endpoint` | `https://api.typesafe.ai/v1/systemone` | TypeSafe Jev、または同じ System One API の別サーバー（例: llama.cpp `http://<ホスト>:8081/v1/systemone`、API キーは任意）。TypeSafe 以外には質問を互換の形式で送ります（0.9.15） |
| `[jev] model` | `jev-1.13.0` | Jev のモデル（固定） |
| `[jev] display_name` | 空欄 | 画面・Note・ガイド・LLM への指示に出す判定モデルの名前。空欄 = モデル名から自動（`jev-*` → Jev、`clef-27b` → Clef 27B）。各結果は、その結果を作ったモデルの名前で表示 |
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

キー: `storage/passwords`、realm `second_opinion_triage`、名前は `typesafe_api_key`、`llm_api_key`、
`aws_access_key_id`、`aws_secret_access_key`。

## サーチコマンド

| コマンド | 用途 |
|---|---|
| `jevtriage [persist=true] [auto=true] [dryrun=true] [enrich=false] [ordercheck=false] [parallel=1-8] [timeout=秒]` | `` `jev_findings` `` の行をトリアージ |
| `jevtriage endpoint=<URL> model=<名前>` | 設定を変えずに別の判定モデルを評価（管理者のみ、保存しない、キーは送らない） |
| `jevtriage questions=<版 ID>\|default` | 指定した版の Jev の質問でトリアージ（管理者のみ、保存しない、サポートモードの試験で使用） |
| `jevprompt action=status\|support_on\|support_off\|get\|save\|test\|apply\|revert\|export\|import\|evalset_prompt` | Jev の質問のサポートモード（下記）。`status` 以外は管理者のみ |
| `jevguide [lang=en\|ja] [force=true] [persist=true]` | 判断ガイド（Jev と ES AI SOC Analyst の比較）を LLM で作成 |
| `jevexplain [lang=en\|ja] [force=true] [persist=true] [auto=true min_urgency=… dispositions=…]` | `jev_triage_latest` の行の LLM 説明 |
| `jevnote [lang=en\|ja] [force=true] [persist=true] [kind=guide]` | ES の Finding に Note を書く（提案、または判断ガイド） |
| `jevmigrate [action=plan\|run] [source=TA-jev-triage]` | 旧アプリ TA-jev-triage から設定・キー・KV のデータをコピー（管理者のみ。0.11.0 の名称変更後に1回） |
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
| KV ストア `jev_prompt_versions` | 編集した Jev の質問の版（サポートモード） |
| KV ストア `jev_prompt_state` | サポートモードの状態と、判定モデルごとの使用中の版 |
| index `jev_triage` sourcetype `jev:prompt:audit` | 誰が、いつ、なぜ、どの版でサポートモードの開始・保存・試験・適用・戻す・書き出し・読み込みを行ったか |
| index `cim_modactions` | Finding ごとのレスポンスアクションの状態（`action_name=jev_triage`） |
| ES の Note | 提案の文章。操作したユーザーの名前で書き込まれます |

## Jev の質問の編集（サポートモード、0.10.0 以降）

Jev に送る質問（`bin/jev_triage/questions.json`）には鍵がかかっています。サポートで文言を変える必要があるときは、
管理者（`edit_storage_passwords` または `admin_all_objects`）が **Setup >「プロンプト（サポート用）」** を開きます。

1. 理由と期限（既定 4 時間、最大 24 時間）を入れて **サポートモードを開始**。期限が来るか「サポートモードを終了」を押すと
   鍵が戻ります。適用済みの版はそのまま使われます。
2. 既定の質問か保存済みの版を元に **編集** して **下書きを保存**。変えられるのは文言だけです（`instructions`、選択肢の説明、
   Urgency の各段階の `what` と `examples`、yes/no の基準）。質問の名前と種類、選択肢のキー（`true_positive` など）、
   Urgency の4段階は、提案のルールが前提にしているため既定のままです。文言は英語（ASCII）のみ、上限は instructions 500 字、
   ほかの文 300 字、質問全体 6,000 字です。
3. **試験**: 試験用の各 Finding を、使用中の版と下書きの両方でトリアージします（1件あたり Jev を4回、手動の利用として数えます）。
   `jev_eval_set.csv` があれば変更前後の正解数を表示し、**TP の見逃しが増える下書きは適用できません**。ない場合は直近に
   トリアージした33件で、変わった件を一覧にします。
4. **適用**（理由が必要）。新しいトリアージ結果に版が記録されます（例 `jev_questions =
   q-2026-10-06-r2a+c-20261026-153000`）。独自の質問を使っている間は、トリアージ画面の上部に表示が出ます。
   **既定に戻す** は、サポートモードが終了していても管理者ならいつでも使えます。

版は判定モデルごとです（保存したときの `[jev] model` の値。例 `jev-1.13.0`、`clef-27b`）。トリアージは使用中のモデル向けに
適用した版だけを使い、ほかのモデルは既定の質問のままです。試験は設定済みのエンドポイントで行うため、別のモデル向けの版は
`[jev]` をそのモデルに切り替えてから試験します。使用中の版が読めない、またはチェックに合わなくなった場合は既定の質問に
戻してトリアージを続け、理由を `jev_enrich_errors` に残します。

**書き出し・読み込み**: 「書き出し」で版を JSON（質問、モデル、元の版、ハッシュ、作成者、理由、試験結果）としてダウンロード
できます。別の環境で「読み込み」すると、ハッシュと構造を確認して下書きとして追加します。適用するには試験が必要です。
診断ファイルにも、使用中の版（書き出しと同じ形式）と直近30日の監査記録が入ります。

**試験の正解表（`jev_eval_set.csv`）**: 正解はお客様のデータで変わるため同梱していません。列
`finding_id,disposition,urgency,note`（disposition は `TP` / `FP` / `Benign` / `Undetermined`、urgency は
`low` / `medium` / `high` / `critical`）の CSV を作り、設定 > ルックアップ > ルックアップテーブルファイル（アプリ
second_opinion_triage）にアップロードしてください。作り始めるときは「正解表を作る LLM 用プロンプトを作成」で、直近にトリアージした
33件の事実（Jev に送った事実。Jev の回答は含みません）入りのプロンプトをコピーし、LLM に貼って、**全行を自分で確認してから**
CSV をアップロードします。自分でプロンプトを組み立てる場合は `bin/jev_triage/prompts/evalset_ja.txt`（英語は `_en`）を使えます。

## Jev 以外の判定モデル（条件付き、0.9.15 以降）

既定であり基準となるのは Jev です。同じ System One API の別サーバーを `[jev] endpoint`
（Setup 画面 > TypeSafe Jev > エンドポイント）に設定できます。これまでに十分な結果が出たのは次の1つだけです。

**Cloudflare Clef 27B**（`ggml-org/Clef-GGUF:Q4_K_M`、Apache 2.0）を llama.cpp の `/v1/systemone` で動かす場合、次の条件で使えます。

| 条件 | 内容 |
|---|---|
| サーバー | `/v1/systemone` と Clef に対応した新しい llama.cpp。`-b 4096 -ub 4096` で起動（入力全体が1回に入る大きさが必要） |
| Setup 画面 | エンドポイント `http://<ホスト>:<ポート>/v1/systemone`、モデル `clef-27b`、API キーは空（サーバーに `--api-key` を付けた場合はそのキー） |
| 判別不可の基準（確信度） | 0.60 ではなく **0.45**。Clef の確信度は Jev より低めに出る |
| ハードウェア | モデルは約 19 GB。24 GB 以上の NVIDIA GPU を推奨。48 GB の Apple Silicon Mac でも動くが1回約 20 秒: `[jev] parallel = 1`、`timeout = 180` にし、手動トリアージや少量向け |
| 確認 | 使う前に、自分の環境の正解付き Finding で精度を確かめること |

評価データ（BOTS v3 の Finding 33件、2026-10-26）:

| モデル | Disposition（基準） | 最有力の判定 | FP / Benign の区別 | Urgency（±1） | 1回の時間 |
|---|---|---|---|---|---|
| Jev jev-1.13.0 | 32/33（0.60） | 31/33 | できる | 31/33（33/33） | 約 0.15 秒 |
| Clef 27B Q4_K_M（Mac M4、48 GB） | 30/33（0.45）、23/33（0.60） | 32/33 | できる | 31/33（33/33） | 約 20 秒 |
| Clef-Flash 9B | 19/33（0.60） | 30/33（ほぼ全件 TP） | できない | 24/33 | 約 0.6 秒 |
| Kev-27B / 9B / 4B | 33件中 18 / 3 / 2 | 21 / 23 / 16 | 27B のみ | 28 / 15 / 15 | 27 / 0.9 / 0.5 秒 |

Clef 27B が外した Finding（#5）と Urgency の2件（#22、#32）は Jev と同じでした。基準 0.45 は同じ33件で決めた値なので、
出発点として扱ってください。推奨しない: Clef-Flash、Kev（全サイズ）。
ローカルのサーバーなら、判定のために Finding の情報がネットワークの外に出ることはありません（LLM の説明は別の設定です）。
検証用の資材はリポジトリの `tools/local-decision/`、詳細は `poc/decision-models/README.md`。

## Splunk の外に送るデータ

- **TypeSafe Jev**（`api.typesafe.ai`）へ: Finding の英語の説明（ルール、項目、区分に変換した件数）と、
  情報収集で得た事実（アカウント名・ホスト名、分類、結果）。生のイベントは送りません。
- **LLM** へ（説明するときだけ）: 同じ説明と Jev の提案。
- ローカルの判定モデル（自前のサーバーを `[jev] endpoint` に設定）を使う場合、説明は TypeSafe ではなくそのサーバーに送ります。
- 画面を開くだけでは何も送りません。

## トラブルシューティング

問い合わせの際は診断ファイルを添えてください: **Setup > サポート > 診断ファイルを作成**。版、設定、接続テスト、
最近のエラー、直近24時間のアプリのログが入ります。API キーは含まれず、エンドポイントとプロキシのホスト名は伏せられます。

| 症状 | 確認すること |
|---|---|
| 接続テストが失敗する | `api.typesafe.ai` や LLM への通信・プロキシ、キーが保存済みか（Setup に「保存済み」と出るか） |
| 説明が `The read operation timed out` で失敗する | LLM がタイムアウト内に応答しなかった（混雑、思考するモデル、モデルの読み込み中）。アプリは1回だけやり直します。続く場合はタイムアウトを延ばすか、時間をおいて実行 |
| 説明が `unknown url type` や `endpoint must start with http://` で失敗する | エンドポイントに `http://`（とポート・`/v1`）がありません。例: `http://<ホスト>:11434/v1` |
| 説明が `empty answer … thinking` で失敗する | 思考するモデルが最大トークン数を使い切っています。Thinking level を設定する（`none`、gpt-oss は `low`）か、最大トークン数を増やす |
| アナリストで「API key not found」 | `jev_triage_user` ロールを付与し、Setup 画面で一度**保存**を押す |
| レスポンスアクションが failure | `index=cim_modactions action_name=jev_triage` と `index=_internal source=*jev_triage_modalert.log` |
| 検知は動くがトリアージされない | *Second Opinion Triage - Response Queue* が有効か。`jev_usage` の上限（状態が skipped） |
| コマンドのエラー | ジョブの search.log（Job Inspector）で `ChunkedExternProcessor` を探す |
| トリアージが遅い | 情報収集のマクロを実際の index に向ける。検索ヘッドが混んでいれば `[jev] parallel` を下げる |

## 既知の制限（β版）

- 検証は Splunk Enterprise 10.4.2 ＋ ES 8.7.1、および Splunk Cloud 10.4.2604 ＋ ES 8.7.0
  （[導入ガイド](install.md#splunk-cloud-での注意)を参照）。
- 画面は Splunk 標準のページテンプレート（`pages/splunk_ui_app.html`）を使います。Splunk 9.x 系では未検証です。
- 残っている AppInspect の警告: Response Queue が毎分動く（意図どおり）、同梱の Splunk SDK for Python が 2.1.1
  （3.x は Python 3.13 専用）、画面のバンドルに `@splunk/react-page` の SplunkJS のレイアウト処理が含まれる。
- 並行処理のため、1日の上限を最大で同時処理数だけ超えることがあります。
- *Write ES Note* をオンにして同じ Finding に手動でレスポンスアクションを繰り返すと、そのたびに Note が増えます（毎回が新しい結果のため）。
- 精度の数値は BOTS v3 の Finding 33件での結果です。実際のデータでは変わります。

## ソースからのビルド

画面は React（Splunk UI Toolkit）です。ソースは `app/ui`。ビルド手順は[英語版](../en/reference.md#building-from-source)と同じです。
