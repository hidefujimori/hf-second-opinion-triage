[jev_triage]
param.write_note = <bool>
* Also write the suggestion as a Note on the ES finding (default 0).
param.note_language = en|ja|<empty>
* Note language; empty uses [es_note] language in jev_triage.conf.
param.auto_explain = <bool>
* Also ask the LLM for an explanation (default 0). From detections, at most [limits] llm_auto_daily
  per day (jev_triage.conf); ad hoc runs on a finding are not limited.
param.explain_min_urgency = low|medium|high|critical
* Explain only findings with this Jev urgency or higher (default high).
param.explain_dispositions = <comma-separated list>
* Explain only these Jev dispositions: TP, FP, Benign, Undetermined (default TP,Undetermined). Empty = all.
param.wait_seconds = <int>
* When run from a detection: how long the queue waits for the findings of that run (30-1800, default 300).
