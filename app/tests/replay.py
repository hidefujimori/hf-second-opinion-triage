"""Run the app's enrichment with SPL results replayed from cache.json; unknown SPL goes to pending.json."""
import sys, os, json, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "TA-jev-triage", "bin"))
from jev_triage.enrich import Enricher
from jev_triage import state
from adapt import records
CACHE = os.path.join(os.path.dirname(__file__), "cache.json")
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
pending = {}
def key(spl, e, l): return hashlib.sha1(("%s|%s|%s" % (spl, e, l)).encode()).hexdigest()[:12]
def run(spl, e, l):
    k = key(spl, e, l)
    if k in cache: return cache[k]
    pending[k] = {"spl": spl, "earliest": e, "latest": l}; return []
R = records(); out = {}
for n in map(int, sys.argv[1].split(",")):
    facts, rel = Enricher(run).collect(R[n]); out[n] = state.build_state(R[n], facts, rel)
json.dump(pending, open(os.path.join(os.path.dirname(__file__), "pending.json"), "w"), indent=1)
if "--show" in sys.argv:
    for n, s in out.items(): print(n, json.dumps({k: s.get(k) for k in ("context_from_siem", "other_alerts_on_same_entity")}, ensure_ascii=False))
print("pending:", len(pending))
for k, v in pending.items(): print(k, v["earliest"], v["latest"], v["spl"])
