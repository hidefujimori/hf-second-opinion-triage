# HF Decision Model Triage and Second Opinion App (public beta)

[日本語](README.ja.md)

A second opinion for findings in Splunk® Enterprise Security, for use alongside the ES AI SOC Analyst
(Triage agent). The app (`second_opinion_triage`, formerly `TA-jev-triage`) sends findings to a decision model —
[TypeSafe Jev](https://docs.typesafe.ai) by default, or a compatible model — and shows a **suggested disposition** (TP / FP / Benign /
Undetermined) and **suggested urgency** (Critical / High / Medium / Low) for each finding.
An LLM of your choice can explain a suggestion in plain language, and the suggestion can be
written to the ES finding as a Note. ES fields are never changed: analysts decide in ES.

- Triage page (React, Splunk UI Toolkit): list + detail pane, English / Japanese
- **Run Second Opinion Triage** in the menu of an ES finding: one click, with the defaults set on the Setup page
- Adaptive response action **Second Opinion Triage**: on one finding, or on every finding of a detection
- Context collection with SPL (identity, asset, cloud account behaviour, outcomes, related alerts)
- Pluggable LLM: Anthropic, Amazon Bedrock, OpenAI-compatible, Google Gemini — including local
  models on Ollama and Apple Foundation Models (macOS `fm serve`)
- Second opinion: the ES AI SOC Analyst result next to Jev's, with a decision guide that can be written to ES as a Note
- Bulk re-run from the triage page
- Decision model: TypeSafe Jev (default), or conditionally a local Cloudflare Clef 27B on llama.cpp (see the Reference)
- Daily limits for automatic Jev and LLM use
- Support mode (0.10.0): admins can edit the wording of the Jev questions for a limited time, per decision model, with versioning, a test before applying, export / import and an audit log
- Splunk Cloud: passes AppInspect cloud vetting and runs on Splunk Cloud

## Documentation

| | English | 日本語 |
|---|---|---|
| Quick start | [docs/en/quickstart.md](docs/en/quickstart.md) | [docs/ja/quickstart.md](docs/ja/quickstart.md) |
| Installation | [docs/en/install.md](docs/en/install.md) | [docs/ja/install.md](docs/ja/install.md) |
| User guide | [docs/en/user-guide.md](docs/en/user-guide.md) | [docs/ja/user-guide.md](docs/ja/user-guide.md) |
| Reference | [docs/en/reference.md](docs/en/reference.md) | [docs/ja/reference.md](docs/ja/reference.md) |

## Repository layout

| Path | Contents |
|---|---|
| `app/second_opinion_triage/` | The Splunk app (package this folder as `.spl`) |
| `app/ui/` | Source of the React pages (built into `app/second_opinion_triage/appserver/static/pages/`) |
| `app/tests/` | Offline helpers for enrichment (record / replay SPL) |
| `poc/` | Proof of concept: question sets, enrichment rounds, runs and reports |
| `ground_truth_v*.csv` | Labelled evaluation set (33 findings from the BOTS v3 dataset); `v5` is current |
| `docs/` | Beta documentation (English and Japanese) |

Release packages (`second_opinion_triage-<version>.spl`) are attached to GitHub Releases, not committed.

## Status

Beta. Tested on Splunk Enterprise 10.4.2 with Enterprise Security 8.7.1, and on Splunk Cloud 10.4.2604 with
Enterprise Security 8.7.0 (ES AI SOC Analyst enabled). Release notes: [docs/release-notes](docs/release-notes).
Accuracy on the evaluation set: disposition 32/33, no true positive missed, urgency exact 31/33,
within one level 33/33.

## Data sent outside Splunk

The search head sends the facts of each finding to the decision model (TypeSafe Jev unless you configure another
endpoint) and, when someone asks for an explanation or a guide, to the LLM you configure. You need your own API keys,
and their use is billed by those providers. See [Data sent outside Splunk](docs/en/reference.md).

## Moving from TA-jev-triage

0.11.0 renamed the app (`TA-jev-triage` → `second_opinion_triage`). Install the new app next to the old one, open
Setup > *Move from TA-jev-triage* and copy the settings, keys and results, then disable or remove the old app.
See [Installation](docs/en/install.md).

## Support

Public beta, supported by the author on a best-effort basis: [GitHub Issues](../../issues) for questions, bugs and
ideas (attach the diagnostics file from Setup > Support). Security problems: see [SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE). Third-party components: [NOTICE](NOTICE).
TypeSafe and Jev are trademarks of their owner; Splunk is a trademark of Splunk LLC. This is an independent project,
not affiliated with or endorsed by TypeSafe or Splunk.
