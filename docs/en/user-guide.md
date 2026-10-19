# User guide — Jev Triage (beta)

Jev Triage sends each ES finding, with context collected from your data, to TypeSafe Jev and
shows Jev's **suggested disposition** (TP, FP, Benign, Undetermined) and **suggested urgency**
(Critical, High, Medium, Low). An LLM can explain a suggestion in plain language.
**ES fields are never changed** — analysts set the final disposition and urgency in ES.

## The Jev Triage page

- **Filters** (top): finding time, Jev disposition, Jev urgency, minimum confidence, ES status
  (decided by an analyst or not), and a text search.
- **Tiles**: counts per urgency and disposition, errors, and the agreement between Jev and the
  analysts' final dispositions. Click a tile to filter the list; click again to clear it.
- **List**: highest urgency first. Critical rows have a red edge, High rows an orange one.
  A small **re-run** tag marks findings that were triaged again.
- **Re-run several findings at once** (0.9.12): tick the check boxes on the left of the rows (the box in the
  header selects all shown rows), then *Re-run triage for selected* and confirm. Progress and the number of
  failures are shown above the list. As with the single button, each result is replaced and its explanation cleared.
- **Detail pane** (click a row): the suggestion with confidence bars, policy notes, Jev's signals
  (should be escalated / expected admin activity / detection logic mismatch / likely tactic),
  the context sent to Jev, other alerts on the same entity, the LLM explanation, and the actions.
- **Language**: *English / 日本語 (JA)* at the top right switches this page and Splunk's menus
  (the page reopens under the other locale). Your choice is remembered in the browser.

From ES you can open a finding directly: finding menu (⋯) > **Open in Jev Triage**.

### Actions in the detail pane

| Button | What it does |
|---|---|
| **Explain with LLM** | Asks the LLM to explain the current suggestion (about 5 s). The text is kept; **Explain again** makes a new one |
| **Write Note to ES** | Adds the suggestion (and the explanation, if there is one) as a Note on the ES finding. One Note per result. If you make the explanation after the Note was written (or make a new one with **Explain again**), pressing the button again adds the explanation as a second Note ("LLM explanation (added)"); otherwise it says *already written* |
| **Re-run triage** | Sends the finding to Jev again and replaces the result. The old explanation and Note record are cleared (they belonged to the old result); the pane shows *Triaged again* with the previous result. Ask the LLM again if you need an explanation |
| **Open in ES** | Opens the finding in the ES Analyst Queue |

Confidence: Jev returns probabilities; the app turns them into a confidence between 0 and 1.
Below the **confidence threshold** (default 0.60) the disposition is *Undetermined*.

## Adaptive response action "Jev Triage"

### On one finding (manual)

ES Analyst Queue > finding > **Run adaptive response action** > **Jev Triage**. The finding is
triaged at once. ES shows the action and its status on the finding.

### On a detection (automatic)

Edit the detection and add **Jev Triage** next to the **Finding** action. Splunk runs a search's
actions one after another, so Jev Triage only queues a request; the scheduled search
**Jev Triage - Response Queue** (every minute, enabled by default) triages the findings of that
run once they are indexed — usually within 1–2 minutes. Keep that search enabled.

### Options

| Option | Default | Meaning |
|---|---|---|
| Write ES Note | No | Also write the Note |
| Note language | App default | `en` / `ja`. *App default* = **Note language** on the Setup page. Automatic explanations use the same language, so they match the Note |
| Explain with LLM | No | Also ask the LLM for an explanation (uses tokens) |
| Explain only urgency at least | High | Only findings with this urgency or higher get an automatic explanation |
| Explain only dispositions | TP,Undetermined | Only these dispositions get one. Empty = all |
| Wait for findings (s) | 300 | Detections only: how long the queue waits for the findings of a run |

## Limits for automatic runs

Setup page > **Limits for automatic runs**. The limits apply only to **automatic** runs
(detections through the response action, and the scheduled search *Jev Triage - Untriaged
Findings*). Manual actions (buttons, the response action run by hand on a finding) are counted
but never limited.

| Setting | Default | When reached |
|---|---|---|
| LLM explanations per day (automatic) | 100 | No automatic explanation (`skipped (daily limit N/day)`). Triage and the Note still run; the pane says the explanation can be made with *Explain with LLM* |
| Jev triage per day (automatic) | empty = no limit | The finding is stored as *skipped* and picked up again later (scheduled search) or with *Re-run triage* |

Empty = no limit, 0 = none per day. A day is the Splunk server's local calendar day. The Setup
page shows today's counts (automatic and manual). Findings processed in parallel can pass a
limit by up to the number of parallel findings (default 4).

If you run a local LLM, leave the LLM limit empty.

## Scheduled searches

| Search | Default | Purpose |
|---|---|---|
| Jev Triage - Response Queue | enabled, every minute | Works the queue of the response action (needed for detections) |
| Jev Triage - Untriaged Findings | disabled | Every 10 minutes, triages up to 50 findings of the last 24 h that have no Jev result |

## Good to know

- Jev receives English text built from the finding and from facts collected with SPL
  (identity, asset, cloud account behaviour, authentication / traffic outcome, PowerShell on the
  host, related alerts). Shared services such as `*.amazonaws.com` are never used to join data.
- The LLM receives the same facts plus Jev's suggestion. It is told not to change the suggestion
  and to treat text from logs as data.
- Accuracy in our test (33 findings from the BOTS v3 dataset): disposition 32/33, no true positive
  missed, urgency exact 31/33 and within one level 33/33. Your data will differ — treat the
  results as suggestions and tell us where they are wrong.
