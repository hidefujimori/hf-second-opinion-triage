"""Turn Jev answers into the suggested ES values. All thresholds come from jev_triage.conf."""
LEVELS = ["low", "medium", "high", "critical"]
TAGS = {"true_positive": "TP", "false_positive": "FP", "benign": "Benign", "undetermined": "Undetermined"}
# ES 8.x standard dispositions (configurable in jev_triage.conf [es_mapping])
ES_DISPOSITION = {"true_positive": "disposition:1", "benign": "disposition:2",
                  "false_positive": "disposition:3", "undetermined": "disposition:6"}


def reversed_disposition(questions):
    d = dict(questions["disposition"])
    d["criteria"] = dict(reversed(list(d["criteria"].items())))
    return {"disposition": d}


def decide(ans, ans_rev, rollup, conf_threshold=0.60, escalation_floor=0.80, rollup_cap="high"):
    reasons = []
    d = ans["disposition"]
    disp, conf = d["choice"], float(d["confidence"])
    if conf < conf_threshold:
        reasons.append("low confidence %.2f" % conf)
        disp = "undetermined"
    if ans_rev is not None and ans_rev["disposition"]["choice"] != d["choice"]:
        reasons.append("option-order check disagreed (%s)" % ans_rev["disposition"]["choice"])
        disp = "undetermined"
    probs = ans["urgency"]["probabilities"]
    lvl = int(max(probs.items(), key=lambda kv: kv[1])[0])
    esc = float(ans.get("requires_escalation", {}).get("noul", 0))
    if esc >= escalation_floor and lvl < 2:
        reasons.append("escalation %.2f raised urgency" % esc)
        lvl = 2
    if rollup and rollup_cap and lvl > LEVELS.index(rollup_cap):
        reasons.append("roll-up capped at %s" % rollup_cap)
        lvl = LEVELS.index(rollup_cap)
    return {
        "jev_disposition": TAGS[disp],
        "jev_disposition_raw": d["choice"],
        "jev_disposition_confidence": round(conf, 3),
        "jev_es_disposition": ES_DISPOSITION[disp],
        "jev_urgency": LEVELS[lvl],
        "jev_urgency_score": round(float(ans["urgency"]["score"]), 2),
        "jev_urgency_confidence": round(float(ans["urgency"]["confidence"]), 3),
        "jev_escalate": round(esc, 3),
        "jev_admin_activity": round(float(ans.get("expected_admin_activity", {}).get("noul", 0)), 3),
        "jev_logic_mismatch": round(float(ans.get("detection_logic_mismatch", {}).get("noul", 0)), 3),
        "jev_tactic": ans.get("attack_tactic", {}).get("choice"),
        "jev_policy": " / ".join(reasons),
    }
