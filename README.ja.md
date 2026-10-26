# Jev Triage for Splunk Enterprise Security（β版）

[English](README.md)

Splunk Enterprise Security の Finding を [TypeSafe Jev](https://docs.typesafe.ai) に送り、Finding ごとに
**Disposition の提案**（TP / FP / Benign / 判別不可）と **Urgency の提案**（Critical / High / Medium / Low）を表示する
Splunk アプリ（`TA-jev-triage`）です。選んだ LLM に提案を口語で説明させたり、提案を ES の Finding に Note として
書き込んだりできます。ES の項目は変更しません。判断は ES でアナリストが行います。

- トリアージ画面（React、Splunk UI Toolkit）: 一覧＋詳細ペイン、英語・日本語
- レスポンスアクション **Jev Triage**: 1件の Finding に、または検知のすべての Finding に
- SPL による情報収集（ID、資産、クラウドアカウントの挙動、結果、関連アラート）
- LLM は差し替え可能: Anthropic、Amazon Bedrock、OpenAI 互換、Google Gemini。Ollama のローカルモデルや
  Apple Foundation Models（macOS の `fm serve`）も使えます
- セカンドオピニオン: ES AI SOC Analyst の結果を Jev と並べて表示し、判断ガイドを Note として ES に書き込める
- トリアージ画面からまとめて再トリアージ
- 判定モデル: TypeSafe Jev（既定）、または条件付きでローカルの Cloudflare Clef 27B（llama.cpp、リファレンス参照）
- 自動実行での Jev・LLM の1日の上限
- Splunk Cloud 対応: AppInspect の Cloud 向け審査に合格し、Splunk Cloud で動作確認済み

## ドキュメント

| | 日本語 | English |
|---|---|---|
| クイックスタート | [docs/ja/quickstart.md](docs/ja/quickstart.md) | [docs/en/quickstart.md](docs/en/quickstart.md) |
| 導入ガイド | [docs/ja/install.md](docs/ja/install.md) | [docs/en/install.md](docs/en/install.md) |
| 利用ガイド | [docs/ja/user-guide.md](docs/ja/user-guide.md) | [docs/en/user-guide.md](docs/en/user-guide.md) |
| リファレンス | [docs/ja/reference.md](docs/ja/reference.md) | [docs/en/reference.md](docs/en/reference.md) |

## リポジトリの構成

| パス | 内容 |
|---|---|
| `app/TA-jev-triage/` | Splunk アプリ本体（このフォルダを `.spl` にまとめます） |
| `app/ui/` | React の画面のソース（`app/TA-jev-triage/appserver/static/pages/` にビルド） |
| `app/tests/` | 情報収集のオフライン用ヘルパー（SPL の記録・再生） |
| `poc/` | PoC: 質問セット、情報収集の各回、実行結果とレポート |
| `ground_truth_v*.csv` | 評価用の正解データ（BOTS v3 由来の Finding 33件）。現行は `v5` |
| `docs/` | β版のドキュメント（日本語・英語） |

配布用パッケージ（`TA-jev-triage-<版>.spl`）はリポジトリには入れず、GitHub の Releases に添付します。

## 状況

β版。Splunk Enterprise 10.4.2 ＋ Enterprise Security 8.7.1、および Splunk Cloud 10.4.2604 ＋ Enterprise Security 8.7.0
（ES AI SOC Analyst 有効）で検証済み。リリースノート: [docs/release-notes](docs/release-notes)。
評価データでの精度: Disposition 32/33、TP の見逃しなし、Urgency 完全一致 31/33・1段階以内 33/33。

## ライセンス

非公開のβ版です。許可なく再配布しないでください。
