# HF Decision Model Triage and Second Opinion App（パブリックβ）

[English](README.md)

Splunk® Enterprise Security の Finding に、ES AI SOC Analyst（Triage agent）と並べて使うセカンドオピニオンを出す
Splunk アプリ（`second_opinion_triage`、旧 `TA-jev-triage`）です。Finding を判定モデル（既定は
[TypeSafe Jev](https://docs.typesafe.ai)、互換のモデルも可）に送り、Finding ごとに
**Disposition の提案**（TP / FP / Benign / 判別不可）と **Urgency の提案**（Critical / High / Medium / Low）を表示します。選んだ LLM に提案を口語で説明させたり、提案を ES の Finding に Note として
書き込んだりできます。ES の項目は変更しません。判断は ES でアナリストが行います。

- トリアージ画面（React、Splunk UI Toolkit）: 一覧＋詳細ペイン、英語・日本語
- ES の Finding のメニューに **Run Second Opinion Triage**: Setup の既定値で1クリック実行
- レスポンスアクション **Second Opinion Triage**: 1件の Finding に、または検知のすべての Finding に
- SPL による情報収集（ID、資産、クラウドアカウントの挙動、結果、関連アラート）
- LLM は差し替え可能: Anthropic、Amazon Bedrock、OpenAI 互換、Google Gemini。Ollama のローカルモデルや
  Apple Foundation Models（macOS の `fm serve`）も使えます
- セカンドオピニオン: ES AI SOC Analyst の結果を Jev と並べて表示し、判断ガイドを Note として ES に書き込める
- トリアージ画面からまとめて再トリアージ
- 判定モデル: TypeSafe Jev（既定）、または条件付きでローカルの Cloudflare Clef 27B（llama.cpp、リファレンス参照）
- 自動実行での Jev・LLM の1日の上限
- サポートモード（0.10.0）: 管理者が期限付きで Jev の質問の文言を判定モデルごとに編集できる（版管理、適用前の試験、書き出し・読み込み、監査ログ）
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
| `app/second_opinion_triage/` | Splunk アプリ本体（このフォルダを `.spl` にまとめます） |
| `app/ui/` | React の画面のソース（`app/second_opinion_triage/appserver/static/pages/` にビルド） |
| `app/tests/` | 情報収集のオフライン用ヘルパー（SPL の記録・再生） |
| `poc/` | PoC: 質問セット、情報収集の各回、実行結果とレポート |
| `ground_truth_v*.csv` | 評価用の正解データ（BOTS v3 由来の Finding 33件）。現行は `v5` |
| `docs/` | β版のドキュメント（日本語・英語） |

配布用パッケージ（`second_opinion_triage-<版>.spl`）はリポジトリには入れず、GitHub の Releases に添付します。

## 状況

パブリックβ（最新: [v0.11.5-beta](docs/release-notes/v0.11.5-beta.md)）。Splunk Enterprise 10.4.2 ＋ Enterprise Security 8.7.1、
および Splunk Cloud 10.4 ＋ Enterprise Security 8.7.0 / 8.7.1（ES AI SOC Analyst 有効）で検証済み。リリースノート: [docs/release-notes](docs/release-notes)。
評価データでの精度: Disposition 32/33、TP の見逃しなし、Urgency 完全一致 31/33・1段階以内 33/33。

## Splunk の外に送るデータ

検索ヘッドは、各 Finding の事実を判定モデル（別のエンドポイントを設定しない限り TypeSafe Jev）に送ります。説明やガイドを
求めたときは、設定した LLM にも送ります。API キーは各自で用意し、利用料金は各プロバイダから請求されます。詳しくは
[リファレンス](docs/ja/reference.md) の「Splunk の外に送るデータ」を参照してください。

## TA-jev-triage からの移行

0.11.0 でアプリ名を変更しました（`TA-jev-triage` → `second_opinion_triage`）。新しいアプリを旧アプリと並べて導入し、
Setup >「TA-jev-triage からの移行」で設定・キー・結果をコピーしてから、旧アプリを無効化または削除してください。
手順は [インストール](docs/ja/install.md) を参照してください。

## サポート

パブリックβの間、作者がベストエフォートで対応します。質問・不具合・要望は [GitHub Issues](../../issues) へ
（Setup > サポートの診断ファイルを添付してください）。セキュリティの問題は [SECURITY.md](SECURITY.md) を参照してください。

## ライセンス

[Apache License 2.0](LICENSE)。同梱しているほかのソフトウェアは [NOTICE](NOTICE) を参照してください。
TypeSafe と Jev はその所有者の商標、Splunk は Splunk LLC の商標です。本アプリは個人の独立したプロジェクトで、
TypeSafe および Splunk とは提携・承認の関係にありません。
