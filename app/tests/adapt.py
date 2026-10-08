import json, os
SNAP = os.path.join(os.path.dirname(__file__), "..", "..", "poc", "findings_snapshot.jsonl")
def records():
    out = {}
    for l in open(SNAP, encoding="utf-8"):
        f = json.loads(l)
        r = {"event_id": f["event_id"], "rule_title": f["rule_title"], "rule_name": f["rule_title"],
             "rule_description": f["description"], "security_domain": f["security_domain"], "severity": f.get("severity"),
             "notable_type": "risk_event" if f["notable_type"] in ("risk_event", "finding_group") else "notable",
             "info_min_time": "1534752000", "info_max_time": "1534896000", "_time": "1788236883"}
        if f["notable_type"] == "finding_group": r["detection_type"] = "fbd"
        for k in ("src", "dest", "user", "dvc", "app", "users", "command", "count", "user_count", "risk_object", "risk_object_type", "risk_score"):
            if f.get(k) is not None: r[k] = f[k]
        if f.get("api_calls"): r["events"] = f["api_calls"]
        if f.get("region_count"): r["regions"] = ["r%d" % i for i in range(f["region_count"])]
        if f.get("contributing"): r["orig_source"] = f["contributing"]
        out[f["n"]] = r
    return out
