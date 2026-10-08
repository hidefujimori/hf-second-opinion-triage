#!/usr/bin/env python3
"""Jev triage PoC: send ES findings to Jev and compare with reviewed ground truth.

Usage:
  python3 run_poc.py --dry-run          # build states only, no API calls
  python3 run_poc.py                    # call Jev for all findings
  python3 run_poc.py --only 1,6,14      # call Jev for selected finding numbers

API key: environment variable TYPESAFE_API_KEY, or a line TYPESAFE_API_KEY=... in ../.env
"""
import argparse, csv, ipaddress, json, os, re, sys, time
from collections import Counter, defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
CONF_THRESHOLD = 0.60          # disposition confidence below this -> undetermined
ESCALATION_FLOOR = 0.80        # requires_escalation >= this -> urgency at least high
AGG_CAP = None                 # round 4: max urgency level index for roll-up findings (2 = high)
LEVELS = ["low", "medium", "high", "critical"]
GT_DISP = {"TP": "true_positive", "FP": "false_positive", "Benign": "benign", "判別不可": "undetermined"}
TAG = {"true_positive": "TP", "false_positive": "FP", "benign": "Benign", "undetermined": "Undetermined"}


# ---------- state building (numbers and dates are turned into named buckets in code) ----------
def volume_bucket(n):
    if n is None: return None
    n = int(n)
    if n <= 5: return "very low (1-5)"
    if n <= 20: return "low (6-20)"
    if n <= 200: return "medium (21-200)"
    if n <= 1000: return "high (201-1000)"
    return "very high (over 1000)"

def risk_band(s):
    if s is None: return None
    s = float(s)
    return "low (under 100)" if s < 100 else "elevated (100-199)" if s < 200 else "high (200 or more)"

def ip_scope(v):
    try:
        ip = ipaddress.ip_address(v)
        return "internal" if ip.is_private else "external, internet"
    except ValueError:
        return None

def entity(v):
    if isinstance(v, list): return [entity(x) for x in v]
    scope = ip_scope(v)
    return f"{v} ({scope})" if scope else v

READ_ONLY = re.compile(r"^(Describe|Get|List)")

def build_state(f):
    kind = {"notable": "single detection",
            "risk_event": "risk aggregation (risk threshold exceeded for one entity)",
            "finding_group": "finding group (several findings on one entity)"}[f["notable_type"]]
    if kind == "single detection" and "Risk Threshold" in f["rule_title"]:
        kind = "risk aggregation (risk threshold exceeded for one entity)"
    desc = f["description"].replace(" in the BOTS v3 dataset window", "")
    desc = re.sub(r" at \d{9,10}(\.\d+)?", "", desc)  # epoch timestamps: dates are handled in code, not by Jev
    asset_known = None
    if "(asset is_expected=false)" in desc:
        desc = desc.replace(" (asset is_expected=false)", "")
        asset_known = "no - source is not in the asset inventory"
    s = {
        "alert_type": kind,
        "detection": f["rule_title"],
        "description": desc,
        "security_domain": f["security_domain"],
        "rule_severity": f.get("severity"),
    }
    for k in ("src", "dest", "user", "dvc"):
        if f.get(k): s[k] = entity(f[k])
    if f.get("app"): s["application"] = f["app"]
    if f.get("users"): s["usernames_tried"] = f["users"]
    if f.get("command"): s["change_operation"] = f["command"]
    if f.get("count") is not None: s["event_volume"] = volume_bucket(f["count"])
    if f.get("user_count"): s["distinct_usernames"] = volume_bucket(f["user_count"])
    if f.get("region_count"): s["cloud_regions_used"] = "many (10 or more)" if f["region_count"] >= 10 else "few"
    if f.get("api_calls"):
        writes = [c for c in f["api_calls"] if not READ_ONLY.match(c)]
        s["api_call_types"] = "read-only calls only" if not writes else "includes changes: " + ", ".join(writes)
    if f.get("risk_object"): s["risk_object"] = entity(f["risk_object"])
    if f.get("risk_object_type"): s["risk_object_type"] = f["risk_object_type"]
    if f.get("risk_score") is not None: s["risk_score_band"] = risk_band(f["risk_score"])
    if f.get("contributing"): s["contributing_detections"] = f["contributing"]
    if asset_known: s["asset_in_inventory"] = asset_known
    if ENRICH:
        facts = []
        keys = []
        for k in ("user", "src", "dest", "dvc", "risk_object"):
            v = f.get(k)
            keys += v if isinstance(v, list) else ([v] if v else [])
        for k in keys:
            for fact in ENRICH["entities"].get(k, []):
                if fact not in facts: facts.append(fact)
        for fact in ENRICH["by_change"].get(f.get("command", ""), []):
            facts.append(fact)
        if facts: s["context_from_siem"] = facts
        others = sorted({o["rule_title"] for o in ALL if o is not f and o["notable_type"] == "notable"
                         and not o["rule_title"].startswith(("BOTS - Risk", "Risk"))
                         and set(keys) & set(_ents(o))} - {f["rule_title"]})
        if others: s["other_alerts_on_same_entity"] = others
    return s

def _ents(o):
    out = []
    for k in ("user", "src", "dest", "dvc", "risk_object"):
        v = o.get(k); out += v if isinstance(v, list) else ([v] if v else [])
    return out

ENRICH, ALL = None, []


# ---------- Jev call ----------
def load_key():
    k = os.environ.get("TYPESAFE_API_KEY")
    env = os.path.join(HERE, "..", ".env")
    if not k and os.path.exists(env):
        for line in open(env):
            if line.strip().startswith("TYPESAFE_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not k: sys.exit("TYPESAFE_API_KEY not set (env var or ../.env)")
    return k

def call_jev(key, state, questions, retries=4):
    import requests
    body = {"model": MODEL, "state": state, "questions": questions}
    for attempt in range(retries + 1):
        t0 = time.time()
        r = requests.post(API_URL, json=body, timeout=30,
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        ms = int((time.time() - t0) * 1000)
        if r.status_code in (429, 529) and attempt < retries:
            time.sleep(2 ** attempt); continue
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:300]}", "latency_ms": ms}
        out = r.json(); out["latency_ms"] = ms
        return out
    return {"error": "retries exhausted"}


# ---------- policy ----------
def decide(ans, ans_rev, is_agg=False):
    d = ans["disposition"]
    disp, conf = d["choice"], d["confidence"]
    reasons = []
    if conf < CONF_THRESHOLD:
        reasons.append(f"low confidence {conf:.2f}"); disp = "undetermined"
    if ans_rev and ans_rev["disposition"]["choice"] != d["choice"]:
        reasons.append(f"order check disagreed ({ans_rev['disposition']['choice']})"); disp = "undetermined"
    u = ans["urgency"]
    lvl = int(max(u["probabilities"].items(), key=lambda kv: kv[1])[0])
    esc = ans["requires_escalation"]["noul"]
    if esc >= ESCALATION_FLOOR and lvl < 2:
        reasons.append(f"escalation {esc:.2f} raised urgency"); lvl = 2
    if AGG_CAP is not None and is_agg and lvl > AGG_CAP:
        reasons.append(f"roll-up capped at {LEVELS[AGG_CAP]}"); lvl = AGG_CAP
    return disp, LEVELS[lvl], reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--no-order-check", action="store_true")
    ap.add_argument("--questions", default="jev_questions_r2a.json")
    ap.add_argument("--gt", default="ground_truth_v3.csv")
    ap.add_argument("--enrich", default="", help="enrichment json (round 3)")
    ap.add_argument("--agg-cap", default="", help="cap urgency of roll-up findings, e.g. high (round 4)")
    ap.add_argument("--rescore", default="", help="re-score an existing results_*.jsonl against --gt without calling Jev")
    a = ap.parse_args()

    global ENRICH, ALL, AGG_CAP
    findings = [json.loads(l) for l in open(os.path.join(HERE, "findings_snapshot.jsonl"), encoding="utf-8")]
    ALL = list(findings)
    if a.agg_cap: AGG_CAP = LEVELS.index(a.agg_cap)
    if a.enrich: ENRICH = json.load(open(os.path.join(HERE, a.enrich), encoding="utf-8"))
    if a.only:
        keep = {int(x) for x in a.only.split(",")}
        findings = [f for f in findings if f["n"] in keep]
    qset = json.load(open(os.path.join(HERE, a.questions), encoding="utf-8"))
    Q = qset["questions"]
    Qrev = {"disposition": dict(Q["disposition"], criteria=dict(reversed(list(Q["disposition"]["criteria"].items()))))}
    gt = {r["event_id"]: r for r in csv.DictReader(open(os.path.join(HERE, "..", a.gt), encoding="utf-8"))}

    if a.rescore:
        rows = []
        for line in open(os.path.join(HERE, a.rescore), encoding="utf-8"):
            d = json.loads(line); r = d["row"]; g = gt[[k for k in gt if gt[k]["n"] == str(d["n"])][0]]
            r["gt_disp"], r["gt_urg"] = GT_DISP[g["disposition"]], g["urgency"].lower(); rows.append(r)
        stamp = os.path.basename(a.rescore)[len("results_"):-len(".jsonl")] + "_rescored_" + a.gt.split("_")[-1].split(".")[0]
        write_report(rows, stamp, qset["version"] + " (rescored)"); return

    if a.dry_run:
        for f in findings:
            st = build_state(f)
            print(f"#{f['n']}", json.dumps(st, ensure_ascii=False))
        approx = sum(len(json.dumps(build_state(f))) for f in findings) // 4 + len(findings) * len(json.dumps(Q)) // 4
        print(f"\n{len(findings)} findings, ~{approx} input tokens for the main calls (rough estimate)")
        return

    key = load_key()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + qset["version"].split("-")[-1] + ("_" + os.path.splitext(a.enrich)[0].replace("enrichment", "enr") if a.enrich else "") + ("_cap" if a.agg_cap else "")
    raw_path = os.path.join(HERE, f"results_{stamp}.jsonl")
    rows = []
    with open(raw_path, "w", encoding="utf-8") as raw:
        for f in findings:
            st = build_state(f)
            res = call_jev(key, st, Q)
            rev = None if a.no_order_check or "error" in res else call_jev(key, st, Qrev)
            g = gt[f["event_id"]]
            row = {"n": f["n"], "rule": f["rule_title"], "gt_disp": GT_DISP[g["disposition"]], "gt_urg": g["urgency"].lower(),
                   "label_confidence": g["label_confidence"]}
            if "error" in res:
                row.update(status="error", error=res["error"])
            else:
                ans = res["answers"]
                disp, urg, why = decide(ans, rev.get("answers") if rev and "answers" in rev else None, st["alert_type"] != "single detection")
                row.update(status="ok", jev_disp=disp, jev_disp_raw=ans["disposition"]["choice"],
                           disp_conf=round(ans["disposition"]["confidence"], 3), jev_urg=urg,
                           urg_score=round(ans["urgency"]["score"], 2), urg_conf=round(ans["urgency"]["confidence"], 3),
                           escalate=round(ans["requires_escalation"]["noul"], 3),
                           admin=round(ans["expected_admin_activity"]["noul"], 3),
                           mismatch=round(ans["detection_logic_mismatch"]["noul"], 3),
                           tactic=ans["attack_tactic"]["choice"], policy=" / ".join(why),
                           latency_ms=res["latency_ms"], tokens=res.get("usage", {}).get("input_tokens"))
            raw.write(json.dumps({"n": f["n"], "state": st, "response": res, "order_check": rev, "row": row}, ensure_ascii=False) + "\n")
            rows.append(row)
            print(f"#{f['n']:>2} {row.get('jev_disp', row.get('status')):>15} {row.get('jev_urg', ''):>8}  (truth {row['gt_disp']}/{row['gt_urg']})")
    write_report(rows, stamp, qset["version"])


def write_report(rows, stamp, qver):
    ok = [r for r in rows if r["status"] == "ok"]
    csv_path = os.path.join(HERE, f"results_{stamp}.csv")
    keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)
    n = len(ok) or 1
    disp_ok = sum(r["jev_disp"] == r["gt_disp"] for r in ok)
    urg_ok = sum(r["jev_urg"] == r["gt_urg"] for r in ok)
    urg_near = sum(abs(LEVELS.index(r["jev_urg"]) - LEVELS.index(r["gt_urg"])) <= 1 for r in ok)
    tp = [r for r in ok if r["gt_disp"] == "true_positive"]
    tp_missed = [r for r in tp if r["jev_disp"] in ("false_positive", "benign")]
    und = sum(r["jev_disp"] == "undetermined" for r in ok)
    conf = defaultdict(Counter)
    for r in ok: conf[r["gt_disp"]][r["jev_disp"]] += 1
    order = ["true_positive", "false_positive", "benign", "undetermined"]
    L = [f"# Jev PoC result {stamp}", "",
         f"model {MODEL}, questions {qver}, confidence threshold {CONF_THRESHOLD}, findings {len(rows)} (errors {len(rows) - len(ok)})", "",
         "| metric | value |", "| --- | --- |",
         f"| Disposition match | {disp_ok}/{len(ok)} ({disp_ok / n:.0%}) |",
         f"| TP missed (Jev said FP or Benign) | {len(tp_missed)}/{len(tp)} |",
         f"| Undetermined share | {und}/{len(ok)} ({und / n:.0%}) |",
         f"| Urgency exact match | {urg_ok}/{len(ok)} ({urg_ok / n:.0%}) |",
         f"| Urgency within 1 level | {urg_near}/{len(ok)} ({urg_near / n:.0%}) |", "",
         "Disposition confusion (rows = ground truth, columns = Jev):", "",
         "| truth \\ Jev | " + " | ".join(TAG[o] for o in order) + " |", "| --- |" + " --- |" * len(order)]
    for g in order:
        L.append(f"| {TAG[g]} | " + " | ".join(str(conf[g][o]) for o in order) + " |")
    L += ["", "| # | rule | truth | Jev | disp conf | truth urg | Jev urg | policy |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if r["status"] != "ok":
            L.append(f"| {r['n']} | {r['rule']} | {TAG[r['gt_disp']]} | ERROR | | {r['gt_urg']} | | {r.get('error','')[:60]} |"); continue
        mark = "" if r["jev_disp"] == r["gt_disp"] else " ✗"
        L.append(f"| {r['n']} | {r['rule']} | {TAG[r['gt_disp']]} | {TAG[r['jev_disp']]}{mark} | {r['disp_conf']} | {r['gt_urg']} | {r['jev_urg']} | {r['policy']} |")
    md = os.path.join(HERE, f"report_{stamp}.md")
    open(md, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"\nreport: {md}\ncsv:    {csv_path}")


if __name__ == "__main__":
    main()
