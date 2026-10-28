"""Decision guide: Jev and the ES AI SOC Analyst side by side, turned into a suggested course of action.

The rule table (verdict) is deterministic and mirrored in ui/src/pages/triage/guide.js - keep both in step.
The LLM only explains the comparison (why the two differ, what to check); it never changes either suggestion.
ES AI texts are written by another AI agent from log data: they are passed as data and never followed."""
import json

from . import note

URG = ["low", "medium", "high", "critical"]
RAW = {"true_positive": "TP", "false_positive": "FP", "benign": "Benign", "undetermined": "Undetermined"}
NEG = ("FP", "Benign")


def ai_cat(label):
    s = (label or "").strip().lower()
    if not s:
        return ""
    if s.startswith("true positive"):
        return "TP"
    if s.startswith("benign"):
        return "Benign"
    if s.startswith("false positive"):
        return "FP"
    return "Undetermined"


def parse_summary(summary):
    """Determination / Severity / Confidence from the Markdown table at the end of the ES AI summary."""
    import re
    s = summary or ""

    def pick(name):
        m = re.search(r"\|\s*(?:%s)\s*\|\s*\**([^|*]+?)\**\s*\|" % name, s, re.I)
        return m.group(1).strip() if m else ""
    return {"disp": pick("Determination|Investigation disposition"), "sev": pick("Severity").lower(),
            "conf": pick("Confidence"),
            "text": "\n".join(l for l in s.splitlines() if not l.strip().startswith("|")).strip()}


def _f(v, d=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def verdict(jev_disp, jev_raw, jev_conf, jev_urg, ai_label, ai_sev="", ai_conf="", ai_failed=0):
    """-> dict(key, priority, action_urgency, cautions[list of keys], checks[list of keys])
    key: no_ai | both_tp | both_negative | conflict | jev_unsure_same | jev_unsure_other | ai_unsure"""
    a = ai_cat(ai_label)
    j = jev_disp or ""
    cautions = []
    if a and ai_failed:
        cautions.append("ai_failed_checks")
    if _f(jev_conf, 1) < 0.6:
        cautions.append("jev_low_conf")
    pc = _f((ai_conf or "").rstrip("%").split(" ")[0], None)
    if pc is not None and pc <= 1:
        pc *= 100
    if pc is not None and pc < 70:
        cautions.append("ai_low_conf")
    urg = [u for u in (jev_urg, ai_sev) if u in URG]
    top = max(urg, key=URG.index) if urg else ""
    if not a:
        return {"key": "no_ai", "priority": "", "action_urgency": jev_urg or "", "cautions": cautions, "checks": []}
    if a == "Undetermined":
        key, prio = "ai_unsure", "review"
    elif j == "TP" and a == "TP":
        key, prio = "both_tp", "investigate"
    elif j in NEG and a in NEG:
        key, prio = "both_negative", "close"
    elif (j == "TP" and a in NEG) or (j in NEG and a == "TP"):
        key, prio = "conflict", "urgent_review"
    elif j == "Undetermined" and RAW.get(jev_raw) == a:
        key, prio = "jev_unsure_same", "review"
    else:
        key, prio = "jev_unsure_other", "review"
    checks = {"both_tp": ["contain"], "both_negative": ["confirm_reason"], "conflict": ["compare_evidence", "ai_failed"],
              "jev_unsure_same": ["jev_missing", "ai_failed"], "jev_unsure_other": ["compare_evidence"],
              "ai_unsure": ["jev_missing", "compare_evidence"]}[key]
    if "ai_failed_checks" not in cautions:
        checks = [c for c in checks if c != "ai_failed"]
    act = top if key in ("both_tp", "conflict") else (min(urg, key=URG.index) if key == "both_negative" and urg else (jev_urg or top))
    return {"key": key, "priority": prio, "action_urgency": act, "cautions": cautions, "checks": checks}


def ai_record(service, event_id):
    """Latest ES AI analysis for a finding (KV missioncontrol/mc_ai_analysis) and the AQ label, or ({}, "")."""
    rec, label = {}, ""
    try:
        resp = service.get("/servicesNS/nobody/missioncontrol/storage/collections/data/mc_ai_analysis",
                           query=json.dumps({"incident_id": event_id}), output_mode="json")
        recs = json.loads(resp.body.read().decode("utf-8") or "[]")
        recs.sort(key=lambda r: _f(r.get("create_time"), 0), reverse=True)
        rec = recs[0] if recs else {}
    except Exception:
        rec = {}
    try:
        from urllib.parse import quote
        resp = service.get("/servicesNS/nobody/missioncontrol/public/v2/findings/%s" % quote(event_id, safe="@"), output_mode="json")
        label = (json.loads(resp.body.read().decode("utf-8") or "{}") or {}).get("ai_suggested_disposition_label", "") or ""
    except Exception:
        label = ""
    return rec, label


def ai_view(rec, label):
    """What we use from the ES AI record."""
    p = parse_summary(rec.get("summary"))
    tools = rec.get("tools") if isinstance(rec.get("tools"), list) else []
    failed = [t for t in tools if isinstance(t, dict) and t.get("status") == "failed"]
    return {"label": label or p["disp"], "severity": p["sev"], "confidence": p["conf"], "summary": p["text"],
            "justification": rec.get("justification") or "", "failed_checks": failed,
            "time": rec.get("create_time") or ""}


def clip(s, n):
    s = (s or "").replace("**", "").replace("`", "")
    return s if len(s) <= n else s[:n] + " …"


def prompt_user(rec, ai, v):
    try:
        st = json.loads(rec.get("jev_state") or "{}")
    except ValueError:
        st = {}
    try:
        ans = json.loads(rec.get("jev_answers") or "{}")
    except ValueError:
        ans = {}
    probs = {k: round(x, 2) for k, x in (ans.get("disposition", {}).get("probabilities") or {}).items()}
    jev = {"disposition": rec.get("jev_disposition"), "disposition_confidence": rec.get("jev_disposition_confidence"),
           "disposition_probabilities": probs, "urgency": rec.get("jev_urgency"), "policy_notes": rec.get("jev_policy") or "none",
           "context_from_siem": st.get("context_from_siem") or []}
    es_ai = {"disposition": ai["label"], "severity": ai["severity"], "confidence": ai["confidence"],
             "summary": clip(ai["summary"], 1200), "justification": clip(ai["justification"], 1800),
             "checks_that_failed": [clip("%s: %s" % (t.get("purpose") or t.get("app_name") or "", "; ".join(t.get("errors") or [])), 240)
                                    for t in ai["failed_checks"][:5]]}
    alert = {k: st.get(k) for k in ("alert_type", "detection", "description", "security_domain", "rule_severity", "user", "src", "dest", "risk_object") if st.get(k)}
    return ("<alert_data>\n" + json.dumps({"alert": alert, "jev": jev}, ensure_ascii=False, indent=1) + "\n</alert_data>\n"
            + "<es_ai_data>\n" + json.dumps(es_ai, ensure_ascii=False, indent=1) + "\n</es_ai_data>\n"
            + "<comparison>\n" + json.dumps(v, ensure_ascii=False) + "\n</comparison>\n\n"
            + "Write the decision guide for the analyst.")


# ---- Note text ----
L = {
    "en": {"title": "Second Opinion Triage decision guide (Jev vs ES AI SOC Analyst)", "jev": "Jev", "ai": "ES AI", "conf": "confidence",
           "verdict": "Comparison", "action": "Suggested course of action", "urg": "Suggested urgency to act on",
           "caution": "Cautions", "guide": "Guide (LLM)",
           "foot": "Suggestion only: neither Jev nor the ES AI changed the finding. Set the final disposition and urgency in ES. Generated by Second Opinion Triage."},
    "ja": {"title": "セカンドオピニオン 判断ガイド（Jev と ES AI SOC Analyst の比較）", "jev": "Jev", "ai": "ES AI", "conf": "確信度",
           "verdict": "比較", "action": "推奨する対応", "urg": "対応の目安とする Urgency",
           "caution": "注意", "guide": "ガイド（LLM）",
           "foot": "提案のみです。Jev も ES AI も Finding の値は変えていません。最終的な Disposition と Urgency は ES で設定してください。Second Opinion Triage により作成。"},
}
VERDICT = {
    "en": {"both_tp": "Both say True Positive", "both_negative": "Both say not a threat (FP / Benign)",
           "conflict": "They disagree (threat vs not a threat)", "jev_unsure_same": "Jev undetermined, leaning the same way as ES AI",
           "jev_unsure_other": "Jev undetermined, leaning a different way from ES AI", "ai_unsure": "ES AI undetermined",
           "no_ai": "No ES AI result"},
    "ja": {"both_tp": "両方が TP（真陽性）", "both_negative": "両方が脅威ではない（FP / Benign）",
           "conflict": "食い違い（脅威 と 脅威ではない）", "jev_unsure_same": "Jev は判別不可だが ES AI と同じ向き",
           "jev_unsure_other": "Jev は判別不可で ES AI と違う向き", "ai_unsure": "ES AI が判別不可", "no_ai": "ES AI の判定なし"},
}
ACTION = {
    "en": {"investigate": "Start the investigation / response with priority", "close": "Candidate for closing after a quick check of the reason",
           "urgent_review": "Review by a person first: check the evidence on both sides", "review": "Decide by a person: check what is missing", "": "-"},
    "ja": {"investigate": "優先して調査・対応を始める", "close": "理由を簡単に確認したうえでクローズ候補",
           "urgent_review": "最優先で人が確認: 両方の根拠を見比べる", "review": "人が判断: 足りない情報を確認する", "": "-"},
}
CAUTION = {
    "en": {"ai_failed_checks": "Some ES AI checks failed: its conclusion may rest on less evidence",
           "jev_low_conf": "Jev's confidence is low", "ai_low_conf": "ES AI's confidence is low"},
    "ja": {"ai_failed_checks": "ES AI の確認の一部が失敗しており、少ない証拠で結論を出している可能性がある",
           "jev_low_conf": "Jev の確信度が低い", "ai_low_conf": "ES AI の確信度が低い"},
}


def note_text(rec, ai, v, lang="en"):
    from . import modelname
    lang = lang if lang in L else "en"
    name = rec.get("jev_model_label") or modelname.label(rec.get("jev_model"))
    t = modelname.localize(L[lang], name)
    VERDICT_ = {lang: modelname.localize(VERDICT[lang], name)}
    CAUTION_ = {lang: modelname.localize(CAUTION[lang], name)}
    lines = ["%s: %s" % (t["verdict"], VERDICT_[lang][v["key"]]),
             "- %s: %s / %s (%s %s)" % (t["jev"], note.DISP.get(lang, note.DISP["en"]).get(rec.get("jev_disposition"), rec.get("jev_disposition")), (rec.get("jev_urgency") or "").capitalize(), t["conf"], rec.get("jev_disposition_confidence")),
             "- %s: %s / %s (%s %s)" % (t["ai"], ai.get("label") or "-", (ai.get("severity") or "-").capitalize(), t["conf"], ai.get("confidence") or "-"),
             "%s: %s" % (t["action"], ACTION[lang][v["priority"]])]
    if v.get("action_urgency"):
        lines.append("%s: %s" % (t["urg"], v["action_urgency"].capitalize()))
    if v["cautions"]:
        lines.append("%s: %s" % (t["caution"], " / ".join(CAUTION_[lang][c] for c in v["cautions"])))
    if rec.get("jev_guide") and rec.get("jev_guide_for") == rec.get("jev_time"):
        lines += ["", "%s:" % t["guide"], rec["jev_guide"]]
    lines += ["", t["foot"]]
    return t["title"], "\n".join(lines)
