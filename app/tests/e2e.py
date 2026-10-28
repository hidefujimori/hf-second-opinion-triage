"""End-to-end through the app's own modules: replayed enrichment + real Jev calls + policy."""
import sys, os, json, csv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "second_opinion_triage", "bin"))
from jev_triage import jev_client, policy, state
from jev_triage.enrich import Enricher
import replay
key = [l.split("=",1)[1].strip() for l in open(os.path.join(os.path.dirname(__file__), "..", "..", ".env")) if l.startswith("TYPESAFE_API_KEY=")][0]
Q = json.load(open(os.path.join(os.path.dirname(__file__), "..", "second_opinion_triage", "bin", "jev_triage", "questions.json")))["questions"]
gt = {r["n"]: r for r in csv.DictReader(open(os.path.join(os.path.dirname(__file__), "..", "..", "ground_truth_v3.csv"), encoding="utf-8"))}
R = replay.records()
for n in map(int, sys.argv[1].split(",")):
    f = R[n]; facts, rel = Enricher(replay.run).collect(f); st = state.build_state(f, facts, rel)
    a = jev_client.call(key, "jev-1.13.0", st, Q); b = jev_client.call(key, "jev-1.13.0", st, policy.reversed_disposition(Q))
    d = policy.decide(a["answers"], b["answers"], state.is_rollup(f))
    g = gt[str(n)]
    print("#%-2d truth %-8s %-7s | app %-12s %-8s conf %.2f %s" % (n, g["disposition"], g["urgency"], d["jev_disposition"], d["jev_urgency"], d["jev_disposition_confidence"], d["jev_policy"]))
