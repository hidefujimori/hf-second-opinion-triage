"""Versions of the Jev questions that support staff may edit (support mode).

The shipped questions.json is never changed. Edited versions are kept in the KV collection
jev_prompt_versions; which one is used is kept per decision model in jev_prompt_state
(key "active:questions:<model>"), together with the support-mode record (key "support_mode").

Only the wording may change: question names and types, choice keys, the number of score levels and the
yes/no criteria keys stay as shipped, because the policy (policy.py) depends on them."""
import base64
import copy
import hashlib
import json
import os
import re
import time

APP = "second_opinion_triage"
VERSIONS = "jev_prompt_versions"
STATE = "jev_prompt_state"
SUPPORT_KEY = "support_mode"
DEFAULT_HOURS = 4
MAX_HOURS = 24
MAX_INSTRUCTIONS = 500
MAX_TEXT = 300
MAX_EXAMPLES = 6
MAX_TOTAL = 6000
EXPORT_FORMAT = "jev-triage-questions/1"
AUDIT_SOURCETYPE = "jev:prompt:audit"
_ASCII = re.compile(r"^[\x20-\x7e]*$")
HERE = os.path.dirname(os.path.abspath(__file__))


class PromptError(Exception):
    pass


# ---------- default questions ----------
def load_default(name="questions.json"):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def canonical(questions):
    return json.dumps(questions, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_hash(questions):
    return hashlib.sha256(canonical(questions).encode("utf-8")).hexdigest()[:16]


# ---------- validation ----------
def _text(errs, where, v, limit, required=True):
    if not isinstance(v, str):
        errs.append("%s: must be text" % where)
        return
    if required and not v.strip():
        errs.append("%s: must not be empty" % where)
    if len(v) > limit:
        errs.append("%s: %d characters (max %d)" % (where, len(v), limit))
    if not _ASCII.match(v):
        errs.append("%s: English (ASCII) only - Jev is less accurate with other scripts" % where)


def validate(new, default):
    """Errors (list of text) for an edited questions dict compared with the shipped one."""
    errs = []
    if not isinstance(new, dict):
        return ["questions must be an object"]
    if list(new) != list(default):
        miss = [k for k in default if k not in new]
        extra = [k for k in new if k not in default]
        if miss or extra:
            errs.append("questions cannot be added or removed (missing: %s; extra: %s)" % (", ".join(miss) or "-", ", ".join(extra) or "-"))
        else:
            errs.append("question order must stay as shipped")
        return errs
    for name, d in default.items():
        q = new[name]
        if not isinstance(q, dict):
            errs.append("%s: must be an object" % name)
            continue
        if sorted(q) != sorted(d):
            errs.append("%s: fields must be %s" % (name, ", ".join(sorted(d))))
            continue
        if q.get("type") != d.get("type"):
            errs.append("%s: type cannot change (%s)" % (name, d.get("type")))
            continue
        _text(errs, "%s.instructions" % name, q.get("instructions"), MAX_INSTRUCTIONS)
        if "criteria" not in d:
            continue
        dc, qc = d["criteria"], q["criteria"]
        if isinstance(dc, dict):
            if not isinstance(qc, dict) or list(qc) != list(dc):
                errs.append("%s.criteria: keys and order must stay %s" % (name, ", ".join(dc)))
                continue
            for k in dc:
                _text(errs, "%s.criteria.%s" % (name, k), qc[k], MAX_TEXT)
        elif isinstance(dc, list):
            if not isinstance(qc, list) or len(qc) != len(dc):
                errs.append("%s.criteria: must keep %d levels" % (name, len(dc)))
                continue
            for i, (dl, ql) in enumerate(zip(dc, qc)):
                where = "%s.criteria[%d]" % (name, i)
                if isinstance(dl, dict):
                    if not isinstance(ql, dict) or sorted(ql) != sorted(dl):
                        errs.append("%s: fields must be %s" % (where, ", ".join(sorted(dl))))
                        continue
                    _text(errs, where + ".what", ql.get("what"), MAX_TEXT)
                    ex = ql.get("examples", [])
                    if not isinstance(ex, list) or len(ex) > MAX_EXAMPLES:
                        errs.append("%s.examples: a list of up to %d" % (where, MAX_EXAMPLES))
                        continue
                    for j, e in enumerate(ex):
                        _text(errs, "%s.examples[%d]" % (where, j), e, MAX_TEXT)
                else:
                    _text(errs, where, ql, MAX_TEXT)
    total = len(json.dumps(new))
    if total > MAX_TOTAL:
        errs.append("all questions: %d characters (max %d)" % (total, MAX_TOTAL))
    return errs


def diff(new, default):
    """[(path, old, new)] of the texts that differ."""
    out = []

    def walk(path, a, b):
        if isinstance(a, dict) and isinstance(b, dict):
            for k in a:
                if k in b:
                    walk("%s.%s" % (path, k) if path else k, a[k], b[k])
        elif isinstance(a, list) and isinstance(b, list):
            for i in range(max(len(a), len(b))):
                walk("%s[%d]" % (path, i), a[i] if i < len(a) else None, b[i] if i < len(b) else None)
        elif a != b:
            out.append((path, a, b))
    walk("", default, new)
    return out


# ---------- KV helpers ----------
def _path(coll, key=None):
    p = "/servicesNS/nobody/%s/storage/collections/data/%s" % (APP, coll)
    return p + ("/" + key if key else "")


def kv_query(service, coll, query=None, sort=None, limit=0):
    kw = {"output_mode": "json"}
    if query:
        kw["query"] = json.dumps(query)
    if sort:
        kw["sort"] = sort
    if limit:
        kw["limit"] = limit
    resp = service.get(_path(coll), **kw)
    return json.loads(resp.body.read().decode("utf-8") or "[]")


def kv_get(service, coll, key):
    rows = kv_query(service, coll, {"_key": key})
    return rows[0] if rows else None


def kv_save(service, coll, doc):
    service.post(_path(coll) + "/batch_save", headers=[("Content-Type", "application/json")], body=json.dumps([doc]))


def kv_delete(service, coll, key):
    service.delete(_path(coll), query=json.dumps({"_key": key}))


def active_key(model):
    return "active:questions:%s" % model


# ---------- support mode ----------
def support_state(service, now=None):
    now = now or time.time()
    d = kv_get(service, STATE, SUPPORT_KEY) or {}
    on = bool(d.get("active")) and float(d.get("expires_at") or 0) > now
    d["on"] = on
    d["remaining_s"] = int(float(d.get("expires_at") or 0) - now) if on else 0
    return d


# ---------- the version a triage uses ----------
def questions_for(service, model, default_set=None):
    """(qset, warning). qset = {"version": ..., "questions": ..., "custom": id or ""}.
    Falls back to the shipped questions (with a warning) when the active version cannot be used."""
    base = default_set or load_default()
    try:
        act = kv_get(service, STATE, active_key(model))
    except Exception as e:
        return dict(base, custom=""), "custom questions not read (%s); shipped questions used" % str(e)[:120]
    if not act or not act.get("version_id"):
        return dict(base, custom=""), ""
    vid = act["version_id"]
    try:
        v = kv_get(service, VERSIONS, vid)
        if not v:
            raise PromptError("version %s not found" % vid)
        q = json.loads(v["content"])
        if content_hash(q) != v.get("hash"):
            raise PromptError("version %s: content does not match its hash" % vid)
        errs = validate(q, base["questions"])
        if errs:
            raise PromptError("version %s: %s" % (vid, errs[0]))
    except Exception as e:
        return dict(base, custom=""), "custom questions %s not used (%s); shipped questions used" % (vid, str(e)[:160])
    return {"version": "%s+%s" % (v.get("base") or base.get("version"), vid), "questions": q, "custom": vid}, ""


# ---------- export / import ----------
def export_doc(v):
    return {"format": EXPORT_FORMAT, "id": v["_key"], "kind": v.get("kind", "questions"), "model": v.get("model"),
            "base": v.get("base"), "hash": v.get("hash"), "author": v.get("author"), "created": v.get("created"),
            "reason": v.get("reason"), "status": v.get("status"), "test": v.get("test"),
            "questions": json.loads(v["content"])}


def parse_import(text, default):
    try:
        d = json.loads(text)
    except ValueError as e:
        raise PromptError("not JSON: %s" % e)
    if not isinstance(d, dict) or d.get("format") != EXPORT_FORMAT:
        raise PromptError("not a Jev Triage questions export (format %s)" % EXPORT_FORMAT)
    if d.get("kind", "questions") != "questions":
        raise PromptError("kind %s cannot be imported by this version" % d.get("kind"))
    q = d.get("questions")
    if content_hash(q) != d.get("hash"):
        raise PromptError("the content does not match its hash (the file was changed after export)")
    errs = validate(q, default["questions"])
    if errs:
        raise PromptError("; ".join(errs[:5]))
    return d, q


def b64(s):
    return base64.b64decode(s.encode("ascii")).decode("utf-8")


def new_id(now=None):
    return time.strftime("c-%Y%m%d-%H%M%S", time.localtime(now or time.time()))


def audit(service, event):
    ev = dict(event, time=int(time.time()))
    service.post("/services/receivers/simple", body=json.dumps(ev), index="jev_triage",
                 sourcetype=AUDIT_SOURCETYPE, source="jevprompt")
