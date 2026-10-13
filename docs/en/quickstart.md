# Quick start — Jev Triage for Splunk Enterprise Security (beta)

About 15 minutes from install to the first suggestion. For details see the
[Installation guide](install.md), the [User guide](user-guide.md) and the [Reference](reference.md).

> **Beta.** Jev Triage *suggests* a disposition and an urgency for ES findings. It never changes
> ES fields. Analysts make the final decision in Enterprise Security.

## What you need

- Splunk Enterprise Security **8.7.1 or later** (tested: Splunk Enterprise 10.4.2 + ES 8.7.1)
- A **TypeSafe Jev API key** (https://docs.typesafe.ai)
- Outbound HTTPS from the search head to `api.typesafe.ai`
- Optional: an LLM for plain-language explanations (Anthropic, Amazon Bedrock, OpenAI-compatible,
  or Google Gemini) and its API key — or a local one on your network (Ollama, Apple Foundation
  Models on a Mac); see [Optional: a local LLM](#optional-a-local-llm)
- An admin account (Splunk Cloud: `sc_admin`)

## 1. Install the app

- **Splunk Enterprise:** Apps > Manage Apps > **Install app from file** > choose
  `TA-jev-triage-<version>.spl` > Upload, then restart Splunk.
- **Splunk Cloud Platform (Victoria):** Apps > Manage Apps > **Upload App**. The app is vetted
  automatically (no restart needed).

## 2. Enter the keys (Setup page)

Open the app **Jev Triage**. The first time it opens **Setup** (later: menu **Setup**).

1. **TypeSafe Jev > Jev API key**: paste the key.
2. **LLM explanation** (optional): choose the **Provider**, enter the **Model** and the **API key**.
   For a local LLM see [Optional: a local LLM](#optional-a-local-llm).
3. **Enrichment**: point **CloudTrail data** and **Endpoint process data** at your indexes
   (for example `index=aws sourcetype=aws:cloudtrail`). The default `index=*` works but is slow.
4. Click **Save**, then **Test connection**. Both rows should say `ok`. Until you save, the page
   shows *Not saved yet* above the buttons.

Keys are stored in Splunk's encrypted credential store and are never shown again.

### Optional: a local LLM

Explanations can come from a model inside your network, so no prompt leaves it. The servers below
speak the OpenAI API, so the **Provider** is `openai` and the **API key** stays empty.

> **The Splunk search head calls the LLM, not your browser.** In the Endpoint, `localhost` means the
> Splunk server itself. A model running on your own PC or Mac (Ollama, vLLM, LM Studio, `fm serve`)
> is used only if the Splunk server can reach that machine over the network: start the server so it
> listens on the network (not only on localhost), and enter that machine's IP address or host name.
> A fixed address avoids breaking the setting when it changes. Automatic explanations from the
> response action use the same path.

**Apple Foundation Models on a Mac (`fm serve`)**

1. On the Mac (macOS 27 with Apple Intelligence turned on), start the server so other machines can
   reach it, and leave the Terminal window open:
   ```
   fm serve --host 0.0.0.0 --port 1976
   ```
   If the macOS firewall is on, allow incoming connections for `fm`.
2. Check from the Splunk search head: `curl http://<mac-ip>:1976/v1/models` lists the model `system`.
3. On the Setup page:

   | Field | Value |
   |---|---|
   | Provider | `openai` |
   | Model | `system` |
   | Endpoint | `http://<mac-ip>:1976/v1` — with `http://`, the port and `/v1` |
   | Thinking level | empty |
   | LLM API key | empty |

4. **Save**, then **Test connection**.

The Mac must stay awake with `fm serve` running, and a fixed IP address helps. `fm serve` has no
authentication: anyone who can reach the port can use it, so limit it with a firewall.

**Ollama**

Start Ollama so it listens on the network (`OLLAMA_HOST=0.0.0.0`), then set Provider `openai`,
Endpoint `http://<host>:11434/v1`, the Model name as Ollama lists it (for example `gemma4:26b`),
and Thinking level `none` (`low` for `gpt-oss`).

**vLLM and other OpenAI-compatible servers**

Endpoint `http://<host>:<port>/v1` (vLLM: port 8000 by default; if it listens only on localhost, start it with `--host 0.0.0.0`),
Model = the served model name (vLLM: `curl http://<host>:8000/v1/models`). If the model thinks
and answers come back empty, set Thinking level (sent as `reasoning_effort`) or raise Max tokens.

More models, timings and troubleshooting: [Installation guide > Local LLMs](install.md#local-llms-ollama-apple-foundation-models).

## 3. Let analysts use it

Add the role **`jev_triage_user`** to your analyst roles (Settings > Roles > *your analyst role* >
Inheritance). Then click **Save** once more on the Setup page, so the stored keys are shared with
that role. Admins need nothing extra.

## 4. Triage findings

- **One finding:** in ES Analyst Queue, open a finding > **Run adaptive response action** >
  **Jev Triage** > Run. The result appears in the app within seconds.
- **Every new finding of a detection:** edit the detection (correlation search) and add the
  response action **Jev Triage** next to **Finding**. Results appear 1–2 minutes after each run.
- **Findings you already have:** enable the scheduled search *Jev Triage - Untriaged Findings*
  (Settings > Searches, reports, and alerts), or open a finding in the app and click **Re-run triage**.

## 5. Look at the results

Open **Jev Triage** (app home). The list shows each finding with the suggested urgency
(Critical red, High orange, Medium yellow, Low blue) and disposition (TP, FP, Benign,
Undetermined). Click a row to open the details on the right:

- **Explain with LLM** — a plain-language explanation of the suggestion
- **Write Note to ES** — adds the suggestion (and the explanation) as a Note on the ES finding
- **Open in ES** — back to the finding in Enterprise Security

Switch **English / 日本語 (JA)** at the top right.

## Next steps

- Automatic LLM explanations and daily limits: [User guide > Limits](user-guide.md#limits-for-automatic-runs)
- Permissions, settings and troubleshooting: [Reference](reference.md)
