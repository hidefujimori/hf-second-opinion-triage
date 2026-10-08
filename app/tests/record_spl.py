import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "TA-jev-triage", "bin"))
from jev_triage.enrich import Enricher
from adapt import records
R = records(); log = []
def run(spl, e, l): log.append({"spl": spl, "earliest": e, "latest": l}); return []
for n in map(int, sys.argv[1].split(",")):
    log.append({"finding": n}); Enricher(run).collect(R[n])
print(json.dumps(log, indent=1))
