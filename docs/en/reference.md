# Reference — Jev Triage (beta)

## Settings (`jev_triage.conf`)

Normally changed on the Setup page. Defaults are in `default/jev_triage.conf`; changes go to `local/`.

| Stanza / key | Default | Meaning |
|---|---|---|
| `[jev] model` | `jev-1.13.0` | Jev model (pinned) |
| `[jev] confidence_threshold` | 0.60 | Below this the disposition is Undetermined |
| `[jev] escalation_floor` | 0.80 | If Jev's "should be escalated" is at or above this, urgency is at least High |
| `[jev] rollup_urgency_cap` | high | Highest urgency for risk / finding-group roll-ups |
| `[jev] order_check` | true | Ask a second time with the options reversed; disagreement → Undetermined |
| `[jev] timeout`, `parallel`, `proxy` | 30, 4, — | Request timeout (s), findings processed at the same time (1–8), HTTPS proxy |
| `[enrichment] enabled`, `max_facts`, `shared_entities` | true, 12, `*.amazonaws.com,…` | Context collection; patterns never used as join keys |
| `[llm] provider`, `model`, `endpoint`, `region`, `thinking_level`, `max_tokens`, `timeout`, `language`, `proxy` | anthropic, —, —, —, —, 600, 60, en, — | LLM for explanations |
| `[es_note] language` | en | Language of Notes |
| `[limits] llm_auto_daily` | 100 | Automatic LLM explanations per day (empty = no limit) |
| `[limits] jev_auto_daily` | empty | Findings sent to Jev per day by automatic runs |

Macros: `jev_cloudtrail` (CloudTrail data), `jev_endpoint` (endpoint process data),
`jev_findings` (findings source, `` `notable` ``).

Keys: `storage/passwords`, realm `TA-jev-triage`, names `typesafe_api_key`, `llm_api_key`,
`aws_access_key_id`, `aws_secret_access_key`.

## Search commands

| Command | Use |
|---|---|
| `jevtriage [persist=true] [auto=true] [dryrun=true] [enrich=false] [ordercheck=false]` | Triage rows of `` `jev_findings` `` |
| `jevexplain [lang=en\|ja] [force=true] [persist=true] [auto=true min_urgency=… dispositions=…]` | LLM explanation of rows of `jev_triage_latest` |
| `jevnote [lang=en\|ja] [force=true] [persist=true]` | Write a Note on the ES finding |
| `jevcheck [target=jev\|llm\|all]` | Connection test (never prints keys) |
| `jevqueue` | Works the response-action queue (scheduled) |

Examples:
```
`jev_findings` | head 3 | jevtriage dryrun=true | table event_id jev_state
| inputlookup jev_triage_latest where event_id="<id>" | jevexplain lang=ja
| jevcheck
```

## Stored data

| Where | What |
|---|---|
| KV store `jev_triage_latest` | Latest result per finding (suggestion, state sent, answers, explanation, Note record, re-run info) |
| KV store `jev_usage` | Daily counters (`jev_auto`, `jev_manual`, `llm_auto`, `llm_manual`) |
| KV store `jev_triage_queue` | Requests from detections; done requests are removed after a day |
| index `jev_triage` | History (`jev:triage:result` from automatic runs, `jev:triage:json` from Re-run) |
| index `cim_modactions` | Response-action status per finding (`action_name=jev_triage`) |
| ES Notes | Text of the suggestion, written by the user who triggered it |

## Data sent outside Splunk

- **To TypeSafe Jev** (`api.typesafe.ai`): an English description of the finding (rule, fields,
  bucketed counts) and the facts collected by enrichment (account / host names, categories,
  outcomes). No raw events.
- **To the LLM** (only when explaining): the same description plus Jev's suggestion.
- Nothing is sent when you only open the page.

## Troubleshooting

| Symptom | Check |
|---|---|
| Test connection fails | Network / proxy to `api.typesafe.ai` or the LLM; key stored (Setup shows *stored*) |
| Analysts get "API key not found" | Give them the `jev_triage_user` role, then click **Save** on Setup once |
| Response action shows *failure* | `index=cim_modactions action_name=jev_triage`, and `index=_internal source=*jev_triage_modalert.log` |
| Detection runs but nothing is triaged | Is *Jev Triage - Response Queue* enabled? Look at `jev_usage` limits (status *skipped*) |
| Command errors | The job's search.log (Job Inspector) — look for `ChunkedExternProcessor` |
| Slow triage | Point the enrichment macros at real indexes; lower `[jev] parallel` if the search head is busy |

## Known limitations (beta)

- Tested on Splunk Enterprise 10.4.2 + ES 8.7.1 only. Splunk Cloud: vetting passes; behaviour on
  a live stack not yet verified (see the [Installation guide](install.md#splunk-cloud-notes)).
- The pages use Splunk's built-in page template (`pages/splunk_ui_app.html`); older Splunk 9.x
  versions were not tested.
- AppInspect warnings that remain: the Response Queue runs every minute (by design), the bundled
  Splunk SDK for Python is 2.1.1 (3.x needs Python 3.13 only), the UI bundle contains SplunkJS
  layout code from `@splunk/react-page`.
- Daily limits can be passed by up to the number of findings processed in parallel.
- Running the response action by hand repeatedly on the same finding with *Write ES Note* on adds
  a new Note each time (each run is a new result).
- Accuracy figures come from 33 BOTS v3 findings; real data will differ.

## Building from source

The pages are React (Splunk UI Toolkit). Source: `app/ui`. Build:

```
cp app/ui/package.json app/ui/webpack.config.js <build-folder>/
cd <build-folder> && npm install
UI_SRC=<repo>/app/ui/src APP_DIR=<repo>/app/TA-jev-triage npx webpack --mode production
cp <repo>/app/TA-jev-triage/appserver/static/pages/jev_triage.js <repo>/app/TA-jev-triage/appserver/static/pages/jev_triage_ja.js
```

Package: `tar --exclude='__pycache__' --exclude='*.LICENSE.txt' -czf TA-jev-triage-<version>.spl -C app TA-jev-triage`.
Vet: `splunk-appinspect inspect TA-jev-triage-<version>.spl --mode precert --included-tags cloud`.
