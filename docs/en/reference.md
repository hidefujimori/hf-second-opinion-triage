# Reference — HF Decision Model Triage and Second Opinion App (beta)

## Settings (`jev_triage.conf`)

Normally changed on the Setup page. Defaults are in `default/jev_triage.conf`; changes go to `local/`.

| Stanza / key | Default | Meaning |
|---|---|---|
| `[jev] endpoint` | `https://api.typesafe.ai/v1/systemone` | TypeSafe Jev, or another server with the same System One API (e.g. llama.cpp `http://<host>:8081/v1/systemone`; API key optional). Questions are sent in a compatible form to non-TypeSafe servers (0.9.15) |
| `[jev] model` | `jev-1.13.0` | Jev model (pinned) |
| `[jev] confidence_threshold` | 0.60 | Below this the disposition is Undetermined |
| `[jev] escalation_floor` | 0.80 | If Jev's "should be escalated" is at or above this, urgency is at least High |
| `[jev] rollup_urgency_cap` | high | Highest urgency for risk / finding-group roll-ups |
| `[jev] order_check` | true | Ask a second time with the options reversed; disagreement → Undetermined |
| `[jev] timeout`, `parallel`, `proxy` | 30, 4, — | Request timeout (s), findings processed at the same time (1–8), HTTPS proxy |
| `[enrichment] enabled`, `max_facts`, `shared_entities` | true, 12, `*.amazonaws.com,…` | Context collection; patterns never used as join keys |
| `[llm] provider`, `model`, `endpoint`, `region`, `thinking_level`, `max_tokens`, `timeout`, `language`, `proxy` | anthropic, —, —, —, —, 600, 60, en, — | LLM for explanations. `thinking_level`: gemini → thinkingLevel (`minimal` for Gemma 4); openai → reasoning_effort (Ollama: `none` for gemma4 / qwen3, `low` for gpt-oss). OpenAI-compatible requests always send `stream: false` |
| `[es_note] language` | en | Language of Notes |
| `[limits] llm_auto_daily` | 100 | Automatic LLM explanations per day (empty = no limit) |
| `[limits] jev_auto_daily` | empty | Findings sent to Jev per day by automatic runs |

Macros: `jev_cloudtrail` (CloudTrail data), `jev_endpoint` (endpoint process data),
`jev_findings` (findings source, `` `notable` ``).

Keys: `storage/passwords`, realm `second_opinion_triage`, names `typesafe_api_key`, `llm_api_key`,
`aws_access_key_id`, `aws_secret_access_key`.

## Search commands

| Command | Use |
|---|---|
| `jevtriage [persist=true] [auto=true] [dryrun=true] [enrich=false] [ordercheck=false] [parallel=1-8] [timeout=s]` | Triage rows of `` `jev_findings` `` |
| `jevtriage endpoint=<url> model=<name>` | Evaluate another decision model without changing settings (admins; not saved; no key sent) |
| `jevtriage questions=<version id>\|default` | Triage with a given version of the Jev questions (admins; not saved; used by the support-mode test) |
| `jevprompt action=status\|support_on\|support_off\|get\|save\|test\|apply\|revert\|export\|import\|evalset_prompt` | Support mode for the Jev questions (see below). Everything but `status` is for admins |
| `jevguide [lang=en\|ja] [force=true] [persist=true]` | Decision guide (Jev vs ES AI SOC Analyst) written by the LLM |
| `jevexplain [lang=en\|ja] [force=true] [persist=true] [auto=true min_urgency=… dispositions=…]` | LLM explanation of rows of `jev_triage_latest` |
| `jevnote [lang=en\|ja] [force=true] [persist=true] [kind=guide]` | Write a Note on the ES finding (the suggestion, or the decision guide) |
| `jevmigrate [action=plan\|run] [source=TA-jev-triage]` | Copy settings, keys and KV data from the old app TA-jev-triage (admins; once, after the 0.11.0 rename) |
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
| KV store `jev_prompt_versions` | Edited versions of the Jev questions (support mode) |
| KV store `jev_prompt_state` | Support mode on/off and the version in use per decision model |
| index `jev_triage` sourcetype `jev:prompt:audit` | Who started support mode, saved, tested, applied, reverted, exported or imported which version, when and why |
| index `cim_modactions` | Response-action status per finding (`action_name=jev_triage`) |
| ES Notes | Text of the suggestion, written by the user who triggered it |

## Editing the Jev questions (support mode, 0.10.0+)

The questions sent to Jev (`bin/jev_triage/questions.json`) are locked. When support needs to change their wording,
an admin (`edit_storage_passwords` or `admin_all_objects`) opens **Setup > Prompts (support)**:

1. **Start support mode** with a reason and a time limit (default 4 hours, at most 24). The lock comes back when the
   time is up or someone clicks *End support mode*. Versions already applied stay in use.
2. **Edit** from the shipped questions or from a saved version, and **Save draft**. Only the texts can change:
   `instructions`, the choice descriptions, the urgency levels (`what`, `examples`) and the yes/no criteria.
   Question names and types, the choice keys (`true_positive` …) and the four urgency levels stay as shipped,
   because the suggestion rules depend on them. Texts must be English (ASCII); limits: 500 characters for
   instructions, 300 for other texts, 6,000 for all questions.
3. **Test**: every test finding is triaged with the version in use and with the draft (Jev is called 4 times per
   finding; counted as manual use). With `jev_eval_set.csv` the result shows correct dispositions and urgencies
   before and after; **a draft that misses more TP findings cannot be applied**. Without it, the last 33 triaged
   findings are used and the changes are listed.
4. **Apply** (reason required). New triage results record the version, e.g. `jev_questions =
   q-2026-10-06-r2a+c-20261026-153000`, and the triage page shows a banner while custom questions are in use.
   **Back to shipped** is always available to admins, also when support mode is off.

Versions belong to a decision model (the `[jev] model` value when they are saved, e.g. `jev-1.13.0` or `clef-27b`).
Triage uses only the version applied for the model in use; other models keep the shipped questions. A test runs
on the configured endpoint, so a version for another model is tested after switching `[jev]` to that model.
If the version in use cannot be read or no longer passes the checks, triage falls back to the shipped questions
and records the reason in `jev_enrich_errors`.

**Export / import**: *Export* downloads a version as JSON (questions, model, base, hash, author, reason, test result).
*Import* on another environment checks the hash and the structure and adds it as a draft, which must be tested
before it can be applied. The diagnostics file includes the versions in use (in the export format) and the last
30 days of the audit log.

**Test answers (`jev_eval_set.csv`)**: not shipped, because the answers depend on your data. Create a CSV with the
columns `finding_id,disposition,urgency,note` (disposition `TP` / `FP` / `Benign` / `Undetermined`, urgency
`low` / `medium` / `high` / `critical`) and upload it in Settings > Lookups > Lookup table files, app second_opinion_triage.
To start it, *Make LLM prompt for test answers* copies a prompt with the facts of the last 33 triaged findings
(the same facts sent to Jev, not Jev's answers); paste it into an LLM, **check every row yourself**, then upload
the CSV. The prompt is in `bin/jev_triage/prompts/evalset_en.txt` (and `_ja`) if you prefer to build it yourself.

## Decision models other than Jev (conditional, 0.9.15+)

Jev is the default and the reference. Another server with the same System One API can be set as
`[jev] endpoint` (Setup page > TypeSafe Jev > Endpoint). Only one has been found good enough so far:

**Cloudflare Clef 27B** (`ggml-org/Clef-GGUF:Q4_K_M`, Apache 2.0) served by llama.cpp `/v1/systemone` — usable when:

| Condition | Value |
|---|---|
| Server | llama.cpp with `/v1/systemone` and Clef support (recent build), started with `-b 4096 -ub 4096` (the batch must hold the whole input) |
| Setup page | Endpoint `http://<host>:<port>/v1/systemone`, Model `clef-27b`, API key empty (or the server's `--api-key`) |
| Confidence threshold | **0.45** instead of 0.60: Clef's confidence runs lower than Jev's |
| Hardware | ~19 GB model: an NVIDIA GPU with 24 GB or more is recommended. A 48 GB Apple Silicon Mac works but takes ~20 s per call: set `[jev] parallel = 1` and `timeout = 180`, and use it for manual triage or small volumes only |
| Check | Re-check accuracy with your own labelled findings before relying on it |

Evaluation set (33 BOTS v3 findings, 2026-10-26):

| Model | Disposition (threshold) | Most likely choice | FP / Benign told apart | Urgency (±1) | Time per call |
|---|---|---|---|---|---|
| Jev jev-1.13.0 | 32/33 (0.60) | 31/33 | yes | 31/33 (33/33) | ~0.15 s |
| Clef 27B Q4_K_M (Mac M4, 48 GB) | 30/33 (0.45), 23/33 (0.60) | 32/33 | yes | 31/33 (33/33) | ~20 s |
| Clef-Flash 9B | 19/33 (0.60) | 30/33 (almost all TP) | no | 24/33 | ~0.6 s |
| Kev-27B / 9B / 4B | 18 / 3 / 2 of 33 | 21 / 23 / 16 | 27B only | 28 / 15 / 15 | 27 / 0.9 / 0.5 s |

Clef 27B missed the same finding as Jev (#5) and the same two urgencies (#22, #32). The 0.45 threshold was chosen on
the same 33 findings, so treat it as a starting point. Not recommended: Clef-Flash, Kev (any size).
With a local server no finding data leaves your network for the decision (the LLM explanation is configured separately).
Set-up files for tests: `tools/local-decision/` in the repository; details: `poc/decision-models/README.md`.

## Data sent outside Splunk

- **To TypeSafe Jev** (`api.typesafe.ai`): an English description of the finding (rule, fields,
  bucketed counts) and the facts collected by enrichment (account / host names, categories,
  outcomes). No raw events.
- **To the LLM** (only when explaining): the same description plus Jev's suggestion.
- With a local decision model (`[jev] endpoint` on your own server) the description goes to that server instead of TypeSafe.
- Nothing is sent when you only open the page.

## Troubleshooting

When you ask for help, attach the diagnostics file: **Setup > Support > Make diagnostics file**. It holds
versions, settings, a connection test, recent errors and the app logs of the last 24 hours. It never
contains API keys, and the endpoint and proxy hosts are hidden.

| Symptom | Check |
|---|---|
| Test connection fails | Network / proxy to `api.typesafe.ai` or the LLM; key stored (Setup shows *stored*) |
| Explanation fails with `The read operation timed out` | The LLM did not answer within Timeout (busy server, thinking model, model loading). The app tries once more; then raise Timeout or try later |
| Explanation fails with `unknown url type` or `endpoint must start with http://` | Endpoint is missing `http://` (and the port / `/v1`), e.g. `http://<host>:11434/v1` |
| Explanation fails with `empty answer … thinking` | A thinking model used up Max tokens: set Thinking level (`none`, or `low` for gpt-oss) or raise Max tokens |
| Analysts get "API key not found" | Give them the `jev_triage_user` role, then click **Save** on Setup once |
| Response action shows *failure* | `index=cim_modactions action_name=jev_triage`, and `index=_internal source=*jev_triage_modalert.log` |
| Detection runs but nothing is triaged | Is *Second Opinion Triage - Response Queue* enabled? Look at `jev_usage` limits (status *skipped*) |
| Command errors | The job's search.log (Job Inspector) — look for `ChunkedExternProcessor` |
| Slow triage | Point the enrichment macros at real indexes; lower `[jev] parallel` if the search head is busy |

## Known limitations (beta)

- Tested on Splunk Enterprise 10.4.2 + ES 8.7.1 and Splunk Cloud 10.4.2604 + ES 8.7.0 (see the
  [Installation guide](install.md#splunk-cloud-notes)).
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
UI_SRC=<repo>/app/ui/src APP_DIR=<repo>/app/second_opinion_triage npx webpack --mode production
cp <repo>/app/second_opinion_triage/appserver/static/pages/jev_triage.js <repo>/app/second_opinion_triage/appserver/static/pages/jev_triage_ja.js
```

Package: `tar --exclude='__pycache__' --exclude='*.LICENSE.txt' -czf second_opinion_triage-<version>.spl -C app second_opinion_triage`.
Vet: `splunk-appinspect inspect second_opinion_triage-<version>.spl --mode precert --included-tags cloud`.
