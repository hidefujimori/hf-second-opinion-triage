# 利用ガイド — HF Decision Model Triage and Second Opinion App（β版）

Second Opinion Triage は、ES の Finding を、データから集めた情報と一緒に TypeSafe Jev に送り、
Jev が提案する **Disposition**（TP、FP、Benign、判別不可）と **Urgency**（Critical、High、Medium、Low）を表示します。
LLM に提案を口語で説明させることもできます。**ES の項目は変更しません**。最終的な Disposition と Urgency は ES でアナリストが設定します。

## トリアージ画面

- **絞り込み**（上部）: Finding の時刻、Jev の Disposition、Jev の Urgency、最低確信度、ES の状態（アナリスト判定済みか）、文字検索。
- **タイル**: Urgency 別・Disposition 別の件数、エラー、Jev とアナリストの最終判断の一致率。
  タイルを押すと一覧を絞り込み、もう一度押すと解除します。
- **一覧**: Urgency の高い順。Critical の行は左端が赤、High は橙です。
  再トリアージした Finding には小さな「再トリアージ」タグが付きます。
- **判断ガイド**（0.9.14）: ES AI と Jev の右に3列目として表示。2つを決まった表で比べ、推奨する対応・対応の目安とする Urgency・
  注意・確認の手順を示します。「LLM でガイドを作成」で食い違いの理由と判断の進め方を説明し、「ガイドを ES に Note として書く」で
  Finding に追記します。ES の値は変更しません。
- **ES AI SOC Analyst とのセカンドオピニオン**（0.9.13）: ES の AI トリアージの結果がある Finding は、一覧の「ES AI」列に
  ＝（一致）・≒（一部一致: Jev は判別不可だが同じ向き）・≠（不一致）で表示し、「ES AI との比較」で絞り込めます。
  行をクリックすると一覧の下に詳細が開き、左に ES AI、右に Jev を並べて表示します。ES AI が完了できなかった確認には印が付きます
  （見た目より少ない証拠で結論を出している可能性があります）。Jev は ES AI の結果を使いません。
- **まとめて再トリアージ**（0.9.12）: 行の左のチェックボックスで選び（見出しのチェックボックスで表示中をすべて選択）、
  「選択した Finding を再トリアージ」を押して確認します。一覧の上に進み具合と失敗の件数が表示されます。
  1件ずつの再トリアージと同じく、結果は置き換わり、説明は消去されます。
- **詳細ペイン**（行をクリック）: 確信度のバー付きの提案、判定ルールの注記、Jev の判断材料
  （エスカレーションが必要 / 想定内の管理者の操作 / 検知ロジックとの不一致 / 推定される攻撃の段階）、
  Jev に渡した情報、同じ対象の他のアラート、LLM の説明、操作ボタン。
- **言語**: 右上の *English / 日本語 (JA)* で、この画面と Splunk のメニューの言語を切り替えます
  （別のロケールで開き直します）。選んだ言語はブラウザに記憶されます。

ES から直接開くこともできます: Finding のメニュー（⋯）> **Open in Second Opinion Triage**。

### 詳細ペインの操作

| ボタン | 動作 |
|---|---|
| **LLM で説明** | 現在の提案の説明を LLM に作らせます（約5秒）。説明は保存され、**もう一度説明**で作り直せます |
| **ES に Note を書く** | 提案（と説明があれば説明）を ES の Finding に Note として書き込みます。1つの結果につき1回です。Note を書いたあとに説明を作った場合（**もう一度説明**で作り直した場合も）は、もう一度押すと説明だけを2件目の Note（「LLM の説明（追記）」）として追加します。それ以外は「書き込み済み」になります |
| **再トリアージ** | Jev にもう一度送り、結果を置き換えます。前の説明と Note の記録は前の結果のものなので消えます。ペインに「再トリアージ済み」と前回の結果が表示されます。説明が必要なら LLM にもう一度聞いてください |
| **ES で開く** | ES の Analyst Queue で Finding を開きます |

確信度: Jev が返す確率を、アプリが 0〜1 の確信度に変換したものです。
**確信度のしきい値**（既定 0.60）未満の Disposition は「判別不可」になります。

## ES から1クリックで実行:「Run Second Opinion Triage」（0.11.0）

Enterprise Security で Finding のメニューを開き、**Run Second Opinion Triage**（ワークフローアクション）を選びます。
新しいタブでトリアージ画面が開き、確認を1回出したあと、Setup >「**手動実行**」の既定値（LLM の説明を作るか、
ES に Note を書くか）でトリアージします。結果は一覧の下に開きます。
**Open in Second Opinion Triage** は、実行せずに Finding を開くだけです。

## レスポンスアクション「Second Opinion Triage」

### 1件の Finding に対して（手動）

ES の Analyst Queue > Finding > **Run adaptive response action** > **Second Opinion Triage**。すぐにトリアージされ、
ES の Finding にアクションと状態が表示されます。

### 検知に付ける（自動）

検知を編集し、**Finding** アクションと並べて **Second Opinion Triage** を追加します。Splunk は1つの検索のアクションを
順番に実行するため、Second Opinion Triage は依頼を受け付けるだけです。定期検索 **Second Opinion Triage - Response Queue**
（毎分、既定で有効）が、その実行の Finding が登録されたあとにトリアージします（通常1〜2分）。
この定期検索は有効のままにしてください。

### オプション

| オプション | 既定 | 意味 |
|---|---|---|
| Write ES Note | No | Note も書き込む |
| Note language | アプリの既定 | `en` / `ja`。「アプリの既定」は Setup 画面の **Note の言語**。自動説明も同じ言語で作るので、Note と言語がそろいます |
| Explain with LLM | No | LLM の説明も作る（トークンを使います） |
| Explain only urgency at least | High | この Urgency 以上の Finding だけ自動で説明する |
| Explain only dispositions | TP,Undetermined | この Disposition だけ自動で説明する。空欄 = すべて |
| Wait for findings (s) | 300 | 検知の場合だけ: その実行の Finding を待つ時間 |

## 自動実行の上限

Setup 画面 > **自動実行の上限**。上限がかかるのは**自動**実行だけです（レスポンスアクションを付けた検知と、
定期検索 *Second Opinion Triage - Untriaged Findings*）。手動の操作（ボタン、Finding に手動で実行したレスポンスアクション）は
件数に数えますが、制限はしません。

| 設定 | 既定 | 上限に達したとき |
|---|---|---|
| LLM 説明 / 日（自動） | 100 | 自動説明を作りません（`skipped (daily limit N/day)`）。トリアージと Note は続けます。ペインに「LLM で説明」で作れる旨を表示します |
| トリアージ / 日（自動） | 空欄 = 無制限 | Finding を「未トリアージ（skipped）」として記録し、後で定期検索か**再トリアージ**で処理します |

空欄 = 無制限、0 = 1日0件です。1日は Splunk サーバーの現地時間で区切ります。Setup 画面に本日の件数
（自動・手動）を表示します。並行処理しているため、上限を最大で同時処理数（既定4）だけ超えることがあります。

ローカルの LLM を使う場合は、LLM の上限は空欄にしてください。

## 定期検索

| 検索 | 既定 | 用途 |
|---|---|---|
| Second Opinion Triage - Response Queue | 有効、毎分 | レスポンスアクションの依頼を処理（検知で使う場合に必要） |
| Second Opinion Triage - Untriaged Findings | 無効 | 10分ごとに、過去24時間で Jev の結果がない Finding を最大50件トリアージ |

## 知っておいてほしいこと

- Jev に送るのは、Finding と SPL で集めた情報（ID、資産、クラウドアカウントの挙動、認証・通信の結果、
  ホストの PowerShell、関連アラート）から作った英語の文章です。`*.amazonaws.com` のような共有サービスで
  データを結び付けることはしません。
- LLM には同じ情報と Jev の提案を渡します。提案を変えないこと、ログ中の文字列はデータとして扱うことを指示しています。
- 私たちの検証（BOTS v3 データの Finding 33件）での精度: Disposition 32/33、TP の見逃しなし、
  Urgency 完全一致 31/33・1段階以内 33/33。実際のデータでは結果が変わります。提案として扱い、外れていた点を教えてください。
