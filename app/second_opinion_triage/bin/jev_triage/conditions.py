"""Analyst statements for re-triaging a finding (1.1).

An analyst who knows something the SIEM does not (an approved change, the account owner confirmed it, ...) can
re-triage a finding with one or more of these statements. They go to the decision model in their own state field,
`analyst_statements`, apart from the facts collected from the SIEM, and every attempt is recorded with the result.

Built-in statements ship with the app; admins can add their own on the Setup page (KV collection jev_conditions).
The model reads English (ASCII) only, so every statement has an English text; the labels are what the page shows.
"""
import json
import re

APP = "second_opinion_triage"
COLLECTION = "jev_conditions"
MAX_PER_RUN = 3
MAX_TEXT = 240
ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")

BUILTIN = [
    {"id": "approved_change", "label_en": "Approved change or maintenance",
     "label_ja": "承認済みの変更・作業",
     "text": "The analyst confirmed that this activity was an approved, planned change or maintenance task."},
    {"id": "owner_confirmed", "label_en": "Confirmed with the account owner",
     "label_ja": "本人に確認済み",
     "text": "The analyst confirmed with the account owner that they performed this activity themselves."},
    {"id": "authorized_test", "label_en": "Authorized security test",
     "label_ja": "承認済みのセキュリティテスト",
     "text": "The analyst confirmed that this activity is an authorized security test (penetration test, red team "
             "exercise or vulnerability scanner)."},
    {"id": "internal_source", "label_en": "Source is our own network",
     "label_ja": "送信元は自組織のネットワーク",
     "text": "The analyst confirmed that the source address belongs to the organization (office, VPN or the "
             "organization's own cloud)."},
    {"id": "known_compromised", "label_en": "Account or host known to be compromised",
     "label_ja": "侵害が分かっているアカウント・ホスト",
     "text": "The analyst knows that this account or host is already compromised by an attacker."},
    {"id": "part_of_incident", "label_en": "Part of an incident being handled",
     "label_ja": "対応中のインシデントの一部",
     "text": "The analyst confirmed that this alert is part of a security incident that is already being handled."},
]


def validate(c):
    """Problems with a custom statement (empty list when it is fine)."""
    errs = []
    if not ID_RE.match(str(c.get("id") or "")):
        errs.append("id: lower-case letters, digits and _ (2-40 characters, starting with a letter)")
    text = str(c.get("text") or "").strip()
    if not text:
        errs.append("text is required")
    elif len(text) > MAX_TEXT:
        errs.append("text: at most %d characters" % MAX_TEXT)
    elif any(ord(ch) > 126 or (ord(ch) < 32) for ch in text):
        errs.append("text: English (ASCII) only - the decision model reads English")
    if not str(c.get("label_en") or c.get("label_ja") or "").strip():
        errs.append("a label is required")
    if any(b["id"] == c.get("id") for b in BUILTIN):
        errs.append("id is used by a built-in statement")
    return errs


def custom(service):
    try:
        resp = service.get("/servicesNS/nobody/%s/storage/collections/data/%s" % (APP, COLLECTION), output_mode="json")
        rows = json.loads(resp.body.read().decode("utf-8") or "[]")
    except Exception:
        return []
    out = []
    for r in rows:
        c = {k: r.get(k, "") for k in ("id", "label_en", "label_ja", "text")}
        c["id"] = c["id"] or r.get("_key", "")
        if str(r.get("enabled", "1")) in ("0", "false") or validate(c):
            continue
        c["custom"] = True
        out.append(c)
    return out


def all_statements(service):
    return BUILTIN + custom(service)


def resolve(service, ids):
    """The statements for a comma-separated list of ids (raises on unknown ids or too many)."""
    wanted = [i.strip() for i in str(ids or "").split(",") if i.strip()]
    if not wanted:
        return []
    if len(wanted) > MAX_PER_RUN:
        raise ValueError("at most %d statements per re-triage" % MAX_PER_RUN)
    known = {c["id"]: c for c in all_statements(service)}
    missing = [i for i in wanted if i not in known]
    if missing:
        raise ValueError("unknown statement: %s" % ", ".join(missing))
    return [known[i] for i in dict.fromkeys(wanted)]


NEGATIVE = ("benign", "false_positive")


def compare(base, dec):
    """Fields that keep the result without statements (`base`, from policy.decide) beside the one with them.

    A conflict is flagged when the facts alone pointed to a real attack (true_positive, raw answer) but the
    statements moved the result away from TP (to benign, false positive or undetermined): Jev does not weigh the
    statements against the facts, so a person must."""
    raw_b = base.get("jev_disposition_raw")
    conflict = raw_b == "true_positive" and dec.get("jev_disposition") != "TP"
    note = "with analyst statements; without them: %s (%s %.2f)" % (
        base.get("jev_disposition"), raw_b, float(base.get("jev_disposition_confidence") or 0))
    if conflict:
        note += " - the facts alone point to a true positive"
    policy = dec.get("jev_policy") or ""
    return {"jev_base_disposition": base.get("jev_disposition"), "jev_base_disposition_raw": raw_b,
            "jev_base_confidence": base.get("jev_disposition_confidence"), "jev_base_urgency": base.get("jev_urgency"),
            "jev_statement_conflict": "1" if conflict else "0",
            "jev_policy": (policy + " / " if policy else "") + note}
