# TA-jev-triage 0.9.8 (prototype)

Triage Splunk Enterprise Security 8.7+ findings with TypeSafe Jev. Jev suggests a disposition
(TP / FP / Benign / Undetermined) and an urgency (low / medium / high / critical). Analysts make
the final decision in ES; this app does not change ES fields.

## Install (test environment)
1. Apps > Manage Apps > Install app from file > `TA-jev-triage-0.9.8.spl`, then restart Splunk.
2. Open the app. The first time, it opens **Setup** (also in the app menu and in Manage Apps > Set up).
   Enter the Jev API key, the LLM provider, model and key, and where your CloudTrail and endpoint data
   are; Save; then **Test connection**. Keys go to storage/passwords (realm TA-jev-triage) and are
   never shown again. Saving keys needs `admin_all_objects`.
   Alternatively, store the Jev API key from the command line (run on the Splunk server):
   ```
   curl -k -u admin https://localhost:8089/servicesNS/nobody/TA-jev-triage/storage/passwords \
     -d name=typesafe_api_key -d realm=TA-jev-triage -d password='<YOUR_KEY>'
   ```
3. The Splunk search head must reach `https://api.typesafe.ai`. If it needs a proxy, set
   `proxy = http://proxy:port` in `local/jev_triage.conf` under `[jev]`.

## Try it
- Dry run (enrichment + state only, no Jev call):
  `` `jev_findings` | head 3 | jevtriage dryrun=true | table event_id rule_name jev_state jev_enrich_errors ``
- Real run on 3 findings, stored:
  `` `jev_findings` | head 3 | jevtriage | `jev_persist` ``
- Dashboard: Jev Triage app > Jev Triage.
- Scheduled: enable saved search "Jev Triage - Untriaged Findings" (every 10 min, max 50 findings per run).

## Settings (`default/jev_triage.conf`, override in `local/`)
- `[jev]` model (pinned `jev-1.13.0`), confidence_threshold 0.60, escalation_floor 0.80,
  rollup_urgency_cap high, order_check true, timeout, proxy
- `[enrichment]` enabled, shared_entities (never used as join keys), max_facts
- SPL used for enrichment: `bin/jev_triage/enrichment_templates.json` (edit index names for your data)
- Questions sent to Jev: `bin/jev_triage/questions.json` (English, versioned)

## Stored results
- KV store `jev_triage_latest` (one row per event_id, used by the dashboard)
- index `jev_triage`, sourcetype `jev:triage:result` (full history)

## LLM explanation (0.2.0)
1. Set the provider and model in `local/jev_triage.conf`:
   ```
   [llm]
   provider = anthropic        # or openai (any OpenAI-compatible endpoint), bedrock, gemini
   model = <model id>
   endpoint =                  # optional base URL (openai-compatible / gateway)
   region =                    # bedrock only
   ```
   Google Gemini API with Gemma 4 (free tier is fine for testing):
   ```
   [llm]
   provider = gemini
   model = gemma-4-26b-a4b-it     # or gemma-4-31b-it
   thinking_level = minimal       # Gemma 4 thinks by default (~9 s); minimal makes it ~1 s
   ```
   Local LLMs (0.9.4) use provider `openai` (no key needed):
   ```
   [llm]
   provider = openai
   endpoint = http://<host>:11434/v1   # Ollama; Apple fm serve: http://<mac>:1976/v1, model = system
   model = gemma4:26b
   thinking_level = none               # sent as reasoning_effort; gpt-oss: low
   ```
   Key from Google AI Studio, stored as `llm_api_key`. The Splunk server must reach
   `generativelanguage.googleapis.com`. Note: on the free tier Google may use prompts to improve
   its products, so use test data only.
2. Store the credential in storage/passwords (realm TA-jev-triage):
   - anthropic / openai / gemini: name `llm_api_key`
   - bedrock: names `aws_access_key_id` and `aws_secret_access_key`
   ```
   curl -k -u admin https://localhost:8089/servicesNS/nobody/TA-jev-triage/storage/passwords \
     -d name=llm_api_key -d realm=TA-jev-triage -d password='<KEY>'
   ```
3. Dashboard: open a finding, click "Explain with LLM". Or in search:
   `` | `jev_explain("<event_id>")` ``
The explanation is cached per triage result and language. Text from logs is passed as data, and the
LLM is told not to change Jev's disposition or urgency.

## Notes on ES findings (0.3.0)
`| jevnote` writes the suggestion (and the LLM explanation if one exists for the current result) as a
Note on the ES finding, through the ES public API (`/public/v2/investigations/{id}/notes`).
One Note per triage result; `force=true` writes again. Needs `mc_investigation_write`.
- Dashboard: "Write Note to ES" in the finding detail
- Search: `` | `jev_note("<event_id>")` `` or `` | `jev_note("<event_id>", "ja")` ``
- Note language: `[es_note] language = en | ja` in `local/jev_triage.conf`

## Japanese (0.3.0)
- Dashboard "Jev トリアージ" (`jev_triage_ja`): Japanese labels; Explain and Note in Japanese
- LLM template `bin/jev_triage/prompts/explain_ja.txt`; `` | `jev_explain("<event_id>", "ja")` ``
- Jev itself always receives English input.

## Data locations
Enrichment reads CloudTrail and endpoint process data through two macros. Point them at your indexes
in `local/macros.conf` (defaults search `index=*`, which is slow):
- `jev_cloudtrail` (default `index=* sourcetype=aws:cloudtrail`)
- `jev_endpoint` (default `index=*`)

## Changes in 0.2.0
- `| jevexplain` command, `jev_explain(1)` macro, Explain button on the dashboard
- Roll-up findings (risk / finding group) use the time window of their contributing detections
- Cloud accounts are compared with their own previous 30 days (new source IP addresses)
- Index results with `_time` = triage time; index locations via macros

## Changes in 0.4.0
- Setup page (`jev_setup`): Jev / enrichment / LLM / Note settings, keys, data-location macros
- `| jevcheck [target=jev|llm|all]`: connection test (one tiny request each; never prints keys)

## Changes in 0.5.0
- Faster: findings are processed in parallel (`[jev] parallel`, default 4), the same enrichment search is
  run once per run and reused, and the two Jev calls per finding run at the same time
- Cloud accounts: AWS service principals and "AWS Internal" are not counted as source IP addresses;
  CloudTrail `readOnly` decides read vs change
- Roll-ups on a shared object (e.g. ec2.amazonaws.com): the changes behind the risk score and their actors
  are passed to Jev
- New field `jev_enrich_ms` (enrichment time per finding)

## Changes in 0.5.1
- Cloud accounts: a fact for mass instance launches (10 or more / 50 or more RunInstances)

## Adaptive Response "Jev Triage" (0.6.0)
- **On a finding (ad hoc):** ES Analyst Queue > finding > Run adaptive response action > Jev Triage.
  The finding is triaged right away; the result shows on the Jev Triage dashboard.
- **On a detection:** add the "Jev Triage" response action next to "Finding". Splunk runs a search's
  actions one after another (the Finding action may run after this one), and an action's session ends
  with the action. So the action only queues a request (KV store `jev_triage_queue`); the scheduled
  search **"Jev Triage - Response Queue"** (`| jevqueue`, every minute, enabled by default) triages the
  findings of that run once they are indexed, usually within 1-2 minutes. Keep it enabled if you use
  the action on detections.
- Options: `Write ES Note` (default No), `Note language`, `Explain with LLM` (default No),
  `Explain only urgency at least` (default High), `Explain only dispositions` (default TP,Undetermined),
  `Wait for findings (s)` (queue only, default 300).
- Status per finding is logged to `index=cim_modactions` (`action_name=jev_triage`), so ES shows it;
  details in `$SPLUNK_HOME/var/log/splunk/jev_triage_modalert.log`.
- The action runs as the detection owner (or the analyst, ad hoc); that user needs access to the
  app's keys (storage/passwords) and, for Notes, `mc_investigation_write`.

## Dashboard (0.7.0)
- "Jev Triage" / "Jev トリアージ": findings list on the left, detail pane on the right (click a row).
  Colored urgency (Critical red, High orange, Medium yellow, Low blue) and disposition; summary tiles
  filter the list. `?event_id=<finding id>` opens a finding directly (used by "Open in Jev Triage" in ES).
- Explain / Write Note / Re-run run `jevexplain|jevnote|jevtriage persist=true`: the commands store
  the result themselves (KV store batch_save, and for re-runs a JSON event in index=jev_triage,
  sourcetype `jev:triage:json`). No outputlookup/collect, so Splunk does not ask to confirm a risky search.
  The index copy needs `edit_tcp`; without it only the KV store is updated.

## Re-run triage (0.7.1)
Re-run replaces the result. The LLM explanation and the Note record belong to the old result and are
cleared; the new result keeps `jev_prev_time`, `jev_prev_disposition`, `jev_prev_urgency`,
`jev_prev_had_explanation`, `jev_rerun_count` and `jev_rerun_by`, and the detail pane says that the
finding was triaged again and that the explanation must be requested again.

## Limits for automatic runs (0.9.0)
LLM explanations cost tokens, so automatic use is limited. Setup page > "Limits for automatic runs"
(`[limits]` in jev_triage.conf):
- `llm_auto_daily` (default 100): LLM explanations made automatically per day. They are made only when
  the response action has "Explain with LLM" on, and only for findings that match its urgency /
  disposition rules. Over the limit: no explanation (status "skipped (daily limit N/day)"); triage and Note
  still run, and the detail pane says that the explanation can be made with "Explain with LLM".
- `jev_auto_daily` (default empty = no limit): findings sent to Jev per day by automatic runs. Over the
  limit the finding is stored with status "skipped" and picked up again later.
- Automatic = detections through the response-action queue and the scheduled search "Jev Triage -
  Untriaged Findings" (`jevtriage auto=true`, `jevexplain auto=true`). Manual actions (dashboard buttons,
  ad hoc response action on a finding) are counted but not limited.
- Counters: KV store `jev_usage`, one record per day (server local date) and kind
  (jev_auto, jev_manual, llm_auto, llm_manual); today's numbers are shown on the Setup page.
  Findings processed in parallel can pass a limit by up to `[jev] parallel`.

## Local LLMs (0.9.4, 0.9.5)
- Ollama and Apple Foundation Models (macOS 27 `fm serve`) work through provider `openai`
  (see "LLM explanation" above and docs/en/install.md > Local LLMs).
- OpenAI-compatible requests send `stream: false` (fm serve streams by default).
- `thinking_level` is also used for `openai` and sent as `reasoning_effort`: Ollama gemma4 / qwen3
  need `none`; gpt-oss cannot stop thinking, use `low`. The Setup page shows the field for openai too
  (options: empty, none, minimal, low).
- An empty answer is an error ("empty answer … set thinking_level …") instead of an empty `ok`;
  `<think>` blocks are removed.
- 0.9.5: help text and error message say `low` for gpt-oss (0.9.4 said `none`).
- 0.9.6: the endpoint and proxy must start with http:// or https:// (Setup refuses to save otherwise;
  the LLM call reports it clearly). Setup shows "Not saved yet. Click Save, then Test connection."
  above the buttons (kept in view while scrolling) when something changed, Test connection waits until
  you save, and the browser asks before leaving the page with unsaved changes.
- 0.9.7: response action with "Write ES Note" + "Explain with LLM" and Note language "App default": the
  explanation is written in the Note language ([es_note] language) instead of [llm] language, so a
  Japanese Note no longer carries an English explanation.

## Explanation added to an existing Note (0.9.8)
- If the Note for the current result was written before the LLM explanation, "Write Note to ES" now adds
  the explanation as a second Note ("Jev triage suggestion — LLM explanation (added)") instead of saying
  "already written". New KV field `jev_note_expl_for` = `jev_explain_time` of the explanation in the Note
  (older records: the Note had the explanation if it was made before the Note). A new explanation
  ("Explain again") can be added the same way.

## UI (0.8.0)
- The Jev Triage page and the Setup page are React pages built with Splunk UI Toolkit
  (`@splunk/react-ui`, `@splunk/react-page`). One page for both languages: switch English / 日本語 (JA)
  at the top right. The switch opens the same page under the en-US / ja-JP locale, so Splunk's own
  menus change language too; the choice is remembered in the browser (default English). Light and dark themes follow the user's Splunk theme.
- Source: `../ui/src` (outside the app package). Build output: `appserver/static/pages/<view>.js`
  (`jev_triage.js`, `jev_setup.js`; `jev_triage_ja.js` is a copy for the old Japanese view name).
  The views use Splunk's built-in template `pages/splunk_ui_app.html` (no custom Mako templates,
  which are deprecated as of Splunk 10.4).
- Build: copy `ui/package.json` and `ui/webpack.config.js` to a build folder, `npm install`, then
  `UI_SRC=<ui/src> APP_DIR=<TA-jev-triage> npx webpack --mode production`.

## Not in this prototype
Japanese labels in the policy-note column.
