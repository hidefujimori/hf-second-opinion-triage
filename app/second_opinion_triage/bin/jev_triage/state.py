"""Turn an ES finding (fields from the `notable` macro) into the English state sent to Jev.
Numbers, counts and dates are converted to named buckets here, never sent raw (Jev 1.13 guidance)."""
import ipaddress
import re

READ_ONLY = re.compile(r"^(Describe|Get|List)")
EPOCH = re.compile(r" at \d{9,10}(\.\d+)?")


def _mv(v):
    if v is None or v == "":
        return []
    return v if isinstance(v, list) else [v]


def _one(v):
    m = _mv(v)
    return m[0] if m else None


def volume_bucket(n):
    try:
        n = int(float(n))
    except (TypeError, ValueError):
        return None
    if n <= 5:
        return "very low (1-5)"
    if n <= 20:
        return "low (6-20)"
    if n <= 200:
        return "medium (21-200)"
    if n <= 1000:
        return "high (201-1000)"
    return "very high (over 1000)"


def risk_band(s):
    try:
        s = float(s)
    except (TypeError, ValueError):
        return None
    return "low (under 100)" if s < 100 else "elevated (100-199)" if s < 200 else "high (200 or more)"


def ip_scope(v):
    try:
        return "internal" if ipaddress.ip_address(v).is_private else "external, internet"
    except ValueError:
        return None


def entity(v):
    scope = ip_scope(v)
    return "%s (%s)" % (v, scope) if scope else v


def alert_type(f):
    nt = _one(f.get("notable_type")) or "notable"
    if nt == "risk_event" and _one(f.get("detection_type")) == "fbd":
        return "finding group (several findings on one entity)"
    if nt == "risk_event" or "Risk Threshold" in (_one(f.get("rule_title")) or ""):
        return "risk aggregation (risk threshold exceeded for one entity)"
    return "single detection"


def is_rollup(f):
    return alert_type(f) != "single detection"


def entities(f):
    """Entity values used for enrichment joins (user, src, dest, dvc, risk_object)."""
    out = []
    for k in ("user", "src", "dest", "dvc", "risk_object"):
        for v in _mv(f.get(k)):
            if v not in out:
                out.append(v)
    return out


# Fields the detection itself wrote (the correlation search's result row, kept in the finding's _raw), minus ES
# bookkeeping and the fields already used above. They carry what the rule author chose to show (ports, ACL grants,
# the created user, the GuardDuty title ...). Off by default (details=true turns it on): measured, the rule's own
# wording ("probed by a known malicious host", created user names) pulled benign findings towards true positive.
RAW_KEY = re.compile(r'(?:^|, )([A-Za-z_][A-Za-z0-9_.]*)="')
META = {"search_name", "app_name", "count", "firstTime", "lastTime", "severity", "user", "src", "dest", "dvc",
        "events", "users", "user_count", "regions", "command", "app", "sources", "risk_message", "risk_object",
        "risk_object_type", "risk_score", "vendor_account", "index", "dataset", "gd_severity", "urgency", "owner",
        "status", "disposition", "rule_title", "rule_name", "rule_description", "security_domain", "event_hash",
        "savedsearch_description", "contributing_events_search", "entity", "entity_type", "all_risk_objects"}
META_PREFIX = ("info_", "orig_", "source_", "date_", "_", "annotations", "drilldown", "risk_", "mitre", "analytic_story")
MAX_DETAILS, MAX_VALUE, MAX_TOTAL = 8, 160, 900
NUM = re.compile(r"^-?\d+(\.\d+)?$")


def _ascii(v):
    return re.sub(r"[^\x20-\x7e]", "", str(v)).strip()


def _ip_permissions(o):
    out = []
    for it in (o.get("items") if isinstance(o, dict) else o) or []:
        proto = it.get("ipProtocol", "")
        fp, tp = it.get("fromPort"), it.get("toPort")
        port = "all ports" if proto in ("-1", -1) else ("%s/%s" % (proto, fp) if fp == tp else "%s/%s-%s" % (proto, fp, tp))
        cidrs = [r.get("cidrIp") for r in ((it.get("ipRanges") or {}).get("items") or []) if r.get("cidrIp")]
        cidrs += [r.get("cidrIpv6") for r in ((it.get("ipv6Ranges") or {}).get("items") or []) if r.get("cidrIpv6")]
        out.append("%s from %s" % (port, ", ".join(cidrs) or "other security groups"))
    return "; ".join(out)


def _acl(o):
    grants = o.get("Grant") if isinstance(o, dict) else None
    if isinstance(grants, dict):
        grants = [grants]
    out = []
    for g in grants or []:
        ge = g.get("Grantee") or {}
        uri = ge.get("URI") or ""
        who = ("everyone (AllUsers)" if uri.endswith("/AllUsers") else "any AWS account (AuthenticatedUsers)"
               if uri.endswith("/AuthenticatedUsers") else "log delivery" if uri.endswith("/LogDelivery")
               else ge.get("DisplayName") or ge.get("ID", "")[:12] or "a grantee")
        out.append("%s %s" % (who, g.get("Permission", "")))
    return "grants: " + ", ".join(out) if out else ""


def _json_value(v):
    import json
    try:
        o = json.loads(v)
    except (TypeError, ValueError):
        return None
    if isinstance(o, dict) and ("items" in o and o["items"] and "ipProtocol" in str(o["items"][0])):
        return _ip_permissions(o)
    if isinstance(o, dict) and "Grant" in o:
        return _acl(o)
    if isinstance(o, dict):   # flat key=value of the scalar leaves
        leaves = ["%s=%s" % (k, o[k]) for k in o if not isinstance(o[k], (dict, list))]
        return ", ".join(leaves) or None
    return None


def detection_output(f):
    """Short "name: value" lines for the fields the detection wrote, or []."""
    raw = _one(f.get("_raw")) or ""
    keys = []
    for k in RAW_KEY.findall(raw):
        if k in keys or k in META or k.startswith(META_PREFIX):
            continue
        keys.append(k)
    out, total = [], 0
    for k in keys:
        vals = [_ascii(v) for v in _mv(f.get(k)) if _ascii(v)]
        if not vals:
            continue
        if len(vals) == 1 and vals[0][:1] in "{[":
            text = _json_value(vals[0])
            if not text:
                continue
        elif len(vals) == 1 and NUM.match(vals[0]):
            text = volume_bucket(vals[0]) or vals[0]
        else:
            text = ", ".join(vals[:5]) + (" (and %d more)" % (len(vals) - 5) if len(vals) > 5 else "")
        line = "%s: %s" % (k.replace("_", " "), _ascii(text)[:MAX_VALUE])
        if total + len(line) > MAX_TOTAL:
            break
        out.append(line)
        total += len(line)
        if len(out) >= MAX_DETAILS:
            break
    return out


def build_state(f, facts=None, related=None, risk_band_on=False, details_on=False):
    desc = _one(f.get("rule_description")) or _one(f.get("orig_rule_description")) or ""
    desc = EPOCH.sub("", desc)
    s = {
        "alert_type": alert_type(f),
        "detection": _one(f.get("rule_title")) or _one(f.get("rule_name")) or _one(f.get("search_name")),
        "description": desc,
        "security_domain": _one(f.get("security_domain")),
        "rule_severity": _one(f.get("severity")),
    }
    for k in ("src", "dest", "user", "dvc"):
        vals = [entity(v) for v in _mv(f.get(k))]
        if vals:
            s[k] = vals[0] if len(vals) == 1 else vals[:10]
    if f.get("app"):
        s["application"] = _one(f.get("app"))
    if f.get("users"):
        s["usernames_tried"] = _mv(f.get("users"))[:10]
    if f.get("command"):
        s["change_operation"] = _one(f.get("command"))
    if f.get("count"):
        s["event_volume"] = volume_bucket(_one(f.get("count")))
    if f.get("user_count"):
        s["distinct_usernames"] = volume_bucket(_one(f.get("user_count")))
    regions = _mv(f.get("regions"))
    if regions:
        s["cloud_regions_used"] = "many (10 or more)" if len(regions) >= 10 else "few"
    events = _mv(f.get("events"))
    if events:
        writes = [c for c in events if not READ_ONLY.match(c)]
        s["api_call_types"] = "read-only calls only" if not writes else "includes changes: " + ", ".join(writes[:10])
    if f.get("risk_object"):
        s["risk_object"] = entity(_one(f.get("risk_object")))
    if f.get("risk_object_type"):
        s["risk_object_type"] = _one(f.get("risk_object_type"))
    # risk_score: the running total ES adds up for the entity when the finding is shown (later detections included,
    # old 100/200 scale). Off by default: the band made the model doubt true positives (measured).
    if risk_band_on and f.get("risk_score"):
        s["risk_score_band"] = risk_band(_one(f.get("risk_score")))
    contrib = _mv(f.get("orig_source")) or _mv(f.get("sources")) or _mv(f.get("risk_message"))
    if contrib:
        s["contributing_detections"] = contrib[:10]
    if details_on:
        det = detection_output(f)
        if det:
            s["detection_output"] = det
    if facts:
        s["context_from_siem"] = facts
    if related:
        s["other_alerts_on_same_entity"] = related
    return {k: v for k, v in s.items() if v not in (None, "", [])}
