"""Store results from inside the search commands (KV store + index) through the REST API.

Dashboards use `... | jevtriage persist=true` instead of `| outputlookup` / `| collect`, which are
"risky" SPL commands: Splunk asks the user to confirm searches that contain them."""
import json

APP = "TA-jev-triage"
COLLECTION = "jev_triage_latest"
INDEX = "jev_triage"
SOURCETYPE = "jev:triage:json"
KV_FIELDS = ("event_id rule_name rule_title security_domain urgency src dest user risk_object jev_status jev_error "
             "jev_enrich_errors jev_disposition jev_disposition_raw jev_disposition_confidence jev_es_disposition "
             "jev_urgency jev_urgency_score jev_urgency_confidence jev_escalate jev_admin_activity jev_logic_mismatch "
             "jev_tactic jev_policy jev_state jev_answers jev_model jev_questions jev_version jev_time jev_latency_ms "
             "jev_enrich_ms jev_input_tokens jev_explanation jev_explain_status jev_explain_model jev_explain_lang "
             "jev_explain_time jev_explain_for jev_explain_ms jev_note_status jev_note_id jev_note_time jev_note_for jev_note_expl_for jev_prev_time jev_prev_disposition jev_prev_urgency jev_prev_had_explanation jev_rerun_count jev_rerun_by").split()
NUMERIC = {"jev_time", "jev_disposition_confidence", "jev_urgency_score", "jev_explain_time", "jev_prev_time", "jev_rerun_count"}
# a new triage result replaces the old explanation and note record (they belong to the old result)
CLEARED_ON_TRIAGE = [f for f in KV_FIELDS if f.startswith("jev_explain") or f.startswith("jev_note")]


def _num(v):
    """Numbers for the typed KV fields; whole numbers stay integers so jev_time compares equal to
    jev_explain_for / jev_note_for (stored as text) after a round trip."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return int(f) if f.is_integer() else f


def kv_doc(rec):
    doc = {"_key": rec.get("_key") or rec.get("event_id")}
    for f in KV_FIELDS:
        v = rec.get(f)
        if v is None or v == "":
            continue
        doc[f] = _num(v) if f in NUMERIC else v
    return doc


def save_kv(service, recs):
    """Upsert by _key (batch_save)."""
    docs = [kv_doc(r) for r in recs if r.get("event_id")]
    if not docs:
        return 0
    path = "/servicesNS/nobody/%s/storage/collections/data/%s/batch_save" % (APP, COLLECTION)
    service.post(path, headers=[("Content-Type", "application/json")], body=json.dumps(docs))
    return len(docs)


def index_events(service, recs):
    """One JSON event per result in index=jev_triage (history); jev_answers is left out like `jev_persist`."""
    n = 0
    for r in recs:
        ev = {k: v for k, v in kv_doc(r).items() if k not in ("_key", "jev_answers")}
        # with body=..., splunklib puts the other keyword arguments in the URL query
        service.post("/services/receivers/simple", body=json.dumps(ev), index=INDEX, sourcetype=SOURCETYPE, source="jevtriage")
        n += 1
    return n


def mark_rerun(service, outs, user=""):
    """Re-run from the dashboard: remember the previous result on the new one, so the page can say
    that the finding was triaged again and that the old explanation / Note record were cleared."""
    ids = [o.get("event_id") for o in outs if o.get("event_id")]
    if not ids:
        return
    path = "/servicesNS/nobody/%s/storage/collections/data/%s" % (APP, COLLECTION)
    resp = service.get(path, query=json.dumps({"event_id": {"$in": ids}}), output_mode="json")
    old = {d.get("event_id"): d for d in json.loads(resp.body.read().decode("utf-8") or "[]")}
    for o in outs:
        p = old.get(o.get("event_id"))
        if not p or o.get("jev_status") != "ok":
            continue
        o["jev_prev_time"] = p.get("jev_time", "")
        o["jev_prev_disposition"] = p.get("jev_disposition", "")
        o["jev_prev_urgency"] = p.get("jev_urgency", "")
        o["jev_prev_had_explanation"] = "1" if p.get("jev_explanation") else "0"
        o["jev_rerun_count"] = int(_num(p.get("jev_rerun_count") or 0) or 0) + 1
        o["jev_rerun_by"] = user
