# Installation guide — Jev Triage (beta)

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

1. Apps > Manage Apps > **Install app from file**, choose `TA-jev-triage-<version>.spl`, Upload.
2. Restart Splunk when asked.
3. Upgrade: the same steps with **Upgrade app** checked. Settings and keys are kept.

### Splunk Cloud Platform (Victoria)

1. As `sc_admin`: Apps > Manage Apps > **Upload App**, choose the `.spl` file.
2. Splunk runs the automated vetting. The app passes the current cloud checks with 0 failures,
   0 errors and 0 manual checks; a few warnings remain (see [Reference](reference.md#known-limitations)).

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
you set one). Settings apply to the next search; no restart is needed.

> If you use Google's free Gemini tier, Google may use the prompts to improve its products. Use
> it only with test data.

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
`jev_triage`, and the stored keys (Settings > ... or REST `storage/passwords`, realm `TA-jev-triage`).
Notes already written to ES findings stay.
