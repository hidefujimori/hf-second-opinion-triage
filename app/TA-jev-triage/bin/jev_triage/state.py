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


def build_state(f, facts=None, related=None):
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
    if f.get("risk_score"):
        s["risk_score_band"] = risk_band(_one(f.get("risk_score")))
    contrib = _mv(f.get("orig_source")) or _mv(f.get("sources")) or _mv(f.get("risk_message"))
    if contrib:
        s["contributing_detections"] = contrib[:10]
    if facts:
        s["context_from_siem"] = facts
    if related:
        s["other_alerts_on_same_entity"] = related
    return {k: v for k, v in s.items() if v not in (None, "", [])}
