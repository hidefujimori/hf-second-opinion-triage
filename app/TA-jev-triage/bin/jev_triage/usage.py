"""Daily usage counters and limits for automatic runs (KV store collection jev_usage).

kinds: jev_auto, jev_manual (findings sent to Jev), llm_auto, llm_manual (LLM explanations).
Limits ([limits] in jev_triage.conf) apply to automatic runs only (detections through the
Adaptive Response queue, and the scheduled search). Manual actions are counted for display.
A day is the Splunk server's local calendar day. Counters are read-modify-write: findings processed
in parallel can pass a limit by up to the number of parallel workers.
"""
import json
import threading
import time

APP = "TA-jev-triage"
COLLECTION = "jev_usage"
_lock = threading.Lock()


def today():
    return time.strftime("%Y-%m-%d", time.localtime())


def parse_limit(v):
    """'' / None -> None (no limit); '0' -> 0 (none allowed); 'n' -> n."""
    if v is None or str(v).strip() == "":
        return None
    try:
        return max(0, int(float(v)))
    except ValueError:
        return None


def _path(key=None):
    p = "/servicesNS/nobody/%s/storage/collections/data/%s" % (APP, COLLECTION)
    # splunklib URL-encodes the path itself: do not pre-encode (":" would become %253A and never be found)
    return p + ("/" + key if key else "")


def get(service, kind, day=None):
    key = "%s:%s" % (day or today(), kind)
    try:
        resp = service.get(_path(key), output_mode="json")
        return int(float(json.loads(resp.body.read().decode("utf-8") or "{}").get("count", 0)))
    except Exception:   # 404: nothing counted yet today
        return 0


def _put(service, kind, count, day=None):
    day = day or today()
    doc = {"_key": "%s:%s" % (day, kind), "date": day, "kind": kind, "count": count, "updated": int(time.time())}
    service.post(_path() + "/batch_save", headers=[("Content-Type", "application/json")], body=json.dumps([doc]))


def take(service, kind, limit=None):
    """Count one use of `kind`. With a limit, return False (and count nothing) when today's count reached it."""
    with _lock:
        n = get(service, kind)
        if limit is not None and n >= limit:
            return False
        _put(service, kind, n + 1)
        return True


def limits(settings_stanza):
    return {"jev_auto": parse_limit(settings_stanza.get("jev_auto_daily")),
            "llm_auto": parse_limit(settings_stanza.get("llm_auto_daily"))}
