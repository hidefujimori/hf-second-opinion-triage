# Installation guide — HF Decision Model Triage and Second Opinion App (beta)

## Requirements

| Item | Requirement |
|---|---|
| Splunk Enterprise Security | 8.7.1 or later |
| Splunk platform | Splunk Enterprise 10.x (tested on 10.4.2). Splunk Cloud Platform (Victoria experience): passes Splunk's automated app vetting (AppInspect, cloud checks); not yet tested on a live Cloud stack — see [Splunk Cloud notes](#splunk-cloud-notes) |
| Python | 3.13 or 3.9 (Splunk picks the newest available) |
| Network | Outbound HTTPS (443) from the search head(s) to `api.typesafe.ai`, and to your LLM endpoint if you use one. An HTTPS proxy can be set on the Setup page |
| Accounts | A TypeSafe Jev API key. Optional: an LLM API key (or AWS keys for Bedrock) |
| Deployment | Install on the search head(s) where ES runs (search head clusters: deploy from the deployer). Nothing is needed on indexers or forwarders, except the index below |

### Index

The app defines the index `jev_triage` (history of triage results). On a single instance it is
created by the app. In a distributed deployment create `jev_triage` on the indexers (or your
indexer cluster) yourself. The app works without it; only the history copy is missing.

## Install

### Splunk Enterprise

1. Apps > Manage Apps > **Install app from file**, choose `second_opinion_triage-<version>.spl`, Upload.
2. Restart Splunk when asked.
3. Upgrade: the same steps with **Upgrade app** checked. Settings and keys are kept.

### Splunk Cloud Platform (Victoria)

1. As `sc_admin`: Apps > Manage Apps > **Upload App**, choose the `.spl` file.
2. Splunk runs the automated vetting. The app passes the current cloud checks with 0 failures,
   0 errors and 0 manual checks; a few warnings remain (see [Reference](reference.md#known-limitations)).

## Moving from TA-jev-triage (versions before 0.11.0)

0.11.0 renamed the app from `TA-jev-triage` to `second_opinion_triage`. Splunk treats it as a new app, so its settings,
API keys and stored results start empty. Move them once:

1. Keep the old app installed and enabled, and install the new app (upgrade is not possible across the rename).
2. Restart Splunk, open the new app's Setup page and find **Move from TA-jev-triage** at the top.
3. *Check what will be copied*, then *Copy now* (admins; the same as `| jevmigrate action=run`).
   Copied: settings, macros, API keys (values are never shown), the KV store data (results, usage, versions of the
   Jev questions, support-mode state) and whether the scheduled searches are enabled.
   Not copied: the lookup `jev_eval_set.csv` (upload it again) and pending response-action requests.
4. Disable or remove `TA-jev-triage` and restart Splunk. While both apps are enabled, both run their scheduled searches.
5. Open Setup again, check the values and run *Test connection*. Update correlation searches or bookmarks that link to
   `/app/TA-jev-triage/...` (the response action keeps its name `jev_triage`).

Index `jev_triage` is shared by both apps, so the history stays.

## Configure (Setup page)

Open the app. The first time it opens **Setup**; later use the menu **Setup**.

| Section | What to set |
|---|---|
| TypeSafe Jev | **Jev API key**. Keep the pinned model unless told otherwise. Optional proxy |
| Enrichment | Where your data is: **CloudTrail data** (macro `jev_cloudtrail`) and **Endpoint process data** (macro `jev_endpoint`). Use real index names; `index=*` is slow |
| LLM explanation | Optional. **Provider** (`anthropic`, `openai` = any OpenAI-compatible server, `bedrock`, `gemini`), **Model**, key(s), optional endpoint / region / proxy |
| Notes on ES findings | Language of the Notes (`en` / `ja`) |
| Limits for automatic runs | Daily limits for automatic Jev triage and automatic LLM explanations (see the [User guide](user-guide.md#limits-for-automatic-runs)) |

Click **Save**, then **Test connection**: the table must show `ok` for Jev (and for the LLM if
you set one). Settings apply to the next search; no restart is needed. While there are unsaved
changes the page says *Not saved yet* above the buttons, and Test connection waits until you save.

> If you use Google's free Gemini tier, Google may use the prompts to improve its products. Use
> it only with test data.

### Local LLMs (Ollama, Apple Foundation Models)

Prompts stay inside your network. Use **Provider** `openai` and point **Endpoint** at the server;
the API key can stay empty.

| Server | Endpoint | Model | Thinking level |
|---|---|---|---|
| Ollama | `http://<host>:11434/v1` | e.g. `gemma4:26b`, `gpt-oss:20b`, `qwen2.5:14b-instruct` | `none` for gemma4 / qwen3, `low` for gpt-oss, empty for models that do not think |
| Apple Foundation Models (macOS 27, `fm serve --host 0.0.0.0 --port 1976`) | `http://<mac>:1976/v1` | `system` | empty |

- Write the endpoint with `http://` and the port, ending in `/v1` (not just the host name; Setup
  refuses an endpoint without `http://` or `https://`).
- The Splunk search head must reach the server. Ollama listens only on localhost unless
  `OLLAMA_HOST=0.0.0.0` is set; `fm serve` needs `--host 0.0.0.0`.
- Thinking models can spend all of **Max tokens** on thinking and return nothing. The app then
  reports `empty answer … set thinking_level …`; set **Thinking level** as in the table (gpt-oss
  cannot stop thinking, `low` keeps it short) or raise **Max tokens**.
- `fm serve` and Ollama have no authentication: anyone on the network who can reach the port can use
  them. Limit access with a firewall.
- Only one LLM key is stored. If a key is saved (for example from Gemini), it is also sent to the
  local server, which ignores it; remove it on the Setup page if you do not want that.
- Tested (0.9.4–0.9.5, 3 findings, English and Japanese): Ollama `gemma4:26b` (none) about 3 s,
  `gpt-oss:20b` (low) 2–4 s, `qwen2.5:14b-instruct` 4–7 s; Apple `fm serve` about 5 s.

## Permissions

| Who | Needs |
|---|---|
| Admin who runs Setup | `admin_all_objects` or `edit_storage_passwords` (Splunk Cloud: `sc_admin`) |
| Analysts using the app (buttons, ad hoc response action) | the role **`jev_triage_user`** (shipped with the app; it has `list_storage_passwords`). After giving it, click **Save** on the Setup page once so the keys are shared with this role. Analysts can only read the Jev / LLM keys, not other credentials |
| Writing Notes to ES findings | `mc_investigation_write` (ES roles `ess_analyst`, `ess_admin` have it) |
| History copy in index `jev_triage` from the **Re-run triage** button | `edit_tcp`. Without it only the KV store is updated |
| Detections with the response action | They run as the detection owner (usually `nobody` → `splunk-system-user`), which already has the needed rights |

The KV store collections `jev_triage_latest` and `jev_usage` are writable by `admin`, `sc_admin`,
`ess_admin`, `ess_analyst` and `jev_triage_user`.

## Splunk Cloud notes

Checked: the app passes AppInspect cloud vetting (report: `appinspect_cloud_<version>.json`).
Not yet verified on a real Cloud stack — please report what you see:

- outbound HTTPS from the Cloud search head to `api.typesafe.ai` and to the LLM endpoint
  (if blocked, ask Splunk Support / use the Admin Config Service);
- the `jev_triage` index (create it with the Admin Config Service if needed);
- `sc_admin` saving keys on the Setup page;
- ES Notes and adaptive-response status in ES on Cloud.

## Uninstall

Disable or remove the app (Apps > Manage Apps). Then, if you want, delete the index
`jev_triage`, and the stored keys (Settings > ... or REST `storage/passwords`, realm `second_opinion_triage`).
Notes already written to ES findings stay.
