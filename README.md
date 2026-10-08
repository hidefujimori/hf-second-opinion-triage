# Jev Triage for Splunk Enterprise Security (beta)

[日本語](README.ja.md)

A Splunk app (`TA-jev-triage`) that sends Splunk Enterprise Security findings to
[TypeSafe Jev](https://docs.typesafe.ai) and shows a **suggested disposition** (TP / FP / Benign /
Undetermined) and **suggested urgency** (Critical / High / Medium / Low) for each finding.
An LLM of your choice can explain a suggestion in plain language, and the suggestion can be
written to the ES finding as a Note. ES fields are never changed: analysts decide in ES.

- Triage page (React, Splunk UI Toolkit): list + detail pane, English / Japanese
- Adaptive response action **Jev Triage**: on one finding, or on every finding of a detection
- Context collection with SPL (identity, asset, cloud account behaviour, outcomes, related alerts)
- Pluggable LLM: Anthropic, Amazon Bedrock, OpenAI-compatible, Google Gemini
- Daily limits for automatic Jev and LLM use
- Splunk Cloud ready: passes AppInspect cloud vetting (not yet tested on a live Cloud stack)

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
| `app/TA-jev-triage/` | The Splunk app (package this folder as `.spl`) |
| `app/ui/` | Source of the React pages (built into `app/TA-jev-triage/appserver/static/pages/`) |
| `app/tests/` | Offline helpers for enrichment (record / replay SPL) |
| `poc/` | Proof of concept: question sets, enrichment rounds, runs and reports |
| `ground_truth_v*.csv` | Labelled evaluation set (33 findings from the BOTS v3 dataset); `v5` is current |
| `docs/` | Beta documentation (English and Japanese) |

Release packages (`TA-jev-triage-<version>.spl`) are attached to GitHub Releases, not committed.

## Status

Beta. Tested on Splunk Enterprise 10.4.2 with Enterprise Security 8.7.1.
Accuracy on the evaluation set: disposition 32/33, no true positive missed, urgency exact 31/33,
within one level 33/33.

## License

Private beta. Not for redistribution without permission.
