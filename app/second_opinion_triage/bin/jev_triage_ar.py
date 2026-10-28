#!/usr/bin/env python
"""Adaptive Response / alert action "jev_triage".

- Ad hoc on a finding (Analyst Queue > Run adaptive response): rows have event_id -> triage now.
- From a detection, next to the "Finding" action: Splunk runs a search's actions one after another and the
  findings may not exist yet (the Finding action can run after this one). The session key of an action is
  logged out when the action ends, so no background work can use it. The action therefore only puts a
  request in the KV store queue `jev_triage_queue`; the scheduled search "Jev Triage - Response Queue"
  (| jevqueue, every minute) triages the findings of that run once they are indexed.
Status per finding goes to index=cim_modactions (Splunk_SA_CIM), which ES shows on the finding.
"""
import csv
import gzip
import json
import logging
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib import client  # noqa: E402

from jev_triage import respond  # noqa: E402

logger = respond.get_logger()


def service_from(payload):
    m = re.match(r"^(https?)://([^:/]+):(\d+)", payload.get("server_uri", "https://127.0.0.1:8089"))
    scheme, host, port = (m.group(1), m.group(2), int(m.group(3))) if m else ("https", "127.0.0.1", 8089)
    return client.Service(scheme=scheme, host=host, port=port, token=payload["session_key"],
                          owner="nobody", app=respond.APP)


def read_rows(path):
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            return list(csv.DictReader(fh))
    except Exception:
        return []


def config(payload):
    cfg = payload.get("configuration") or {}
    yes = lambda v: str(v).lower() in ("1", "true", "yes")
    write_note = yes(cfg.get("write_note", "0"))
    lang = (cfg.get("note_language") or "").strip().lower()
    try:
        wait = max(30, min(1800, int(cfg.get("wait_seconds") or 300)))
    except ValueError:
        wait = 300
    explain = None
    if yes(cfg.get("auto_explain", "0")):
        explain = {"min_urgency": (cfg.get("explain_min_urgency") or "high").strip().lower(),
                   "dispositions": (cfg.get("explain_dispositions") or "").strip()}
    return write_note, lang, wait, explain


def adhoc(payload, rows, modaction):
    write_note, lang, _, explain = config(payload)
    ids = sorted({r["event_id"] for r in rows if r.get("event_id")})
    e, l = respond.window_from_ids(ids)
    where = "event_id IN (%s)" % ", ".join(respond.q(i) for i in ids[:200])
    # ad hoc = an analyst's action: counted, but not limited
    total, counts = respond.triage(service_from(payload), where, e, l, write_note, lang, auto=False, explain=explain)
    msg, status, level = respond.summary(total, counts)
    logger.log(level, "mode=adhoc sid=%s %s", payload.get("sid"), msg)
    respond.for_rows(modaction, rows, lambda: modaction.message(msg, status=status, level=level), logger)
    return 0 if status == "success" else 2


def enqueue(payload, rows, modaction):
    write_note, lang, wait, explain = config(payload)
    sid = payload.get("sid", "")
    rec = {"_key": re.sub(r"[^A-Za-z0-9_.-]", "_", sid)[:200], "sid": sid,
           "search_name": payload.get("search_name", ""), "app": payload.get("app", ""),
           "owner": payload.get("owner", ""), "server_uri": payload.get("server_uri", ""),
           "rids": ",".join(str(r.get("rid", i)) for i, r in enumerate(rows)) or "0",
           "write_note": "1" if write_note else "0", "note_language": lang, "wait_seconds": wait,
           "auto_explain": "1" if explain else "0",
           "explain_min_urgency": (explain or {}).get("min_urgency", ""),
           "explain_dispositions": (explain or {}).get("dispositions", ""),
           "queued_time": int(time.time()), "status": "pending"}
    coll = service_from(payload).kvstore[respond.QUEUE].data
    try:
        coll.insert(json.dumps(rec))
    except Exception:   # same sid queued again: replace
        coll.update(rec["_key"], json.dumps(rec))
    logger.info("mode=detection sid=%s queued (%s rows)", sid, len(rows))
    respond.for_rows(modaction, rows, lambda: modaction.message(
        "queued: the findings of this run are triaged within a few minutes", status="working",
        level=logging.INFO), logger)
    return 0


def main():
    # alert.execute.cmd.arg.0 passes --execute; refuse anything else (e.g. --setup, or a manual run)
    if len(sys.argv) < 2 or sys.argv[1] != "--execute":
        sys.stderr.write("FATAL Unsupported execution mode (expected --execute flag)\n")
        sys.exit(1)
    payload = json.loads(sys.stdin.read())
    rows = read_rows(payload.get("results_file", ""))
    modaction = respond.make_modaction(payload, logger)
    # ES lists a response action on a finding from the "Invoking modular action" record
    # (eventtype cim_modaction_invocation) that ModularAction.invoke() writes for each result row.
    respond.for_rows(modaction, rows, lambda: modaction.invoke(), logger)
    try:
        if any(r.get("event_id") for r in rows):
            sys.exit(adhoc(payload, rows, modaction))
        sys.exit(enqueue(payload, rows, modaction))
    except SystemExit:
        raise
    except Exception as e:
        logger.exception("jev_triage action failed")
        respond.for_rows(modaction, rows, lambda: modaction.message(
            "jev_triage failed: %s" % str(e)[:300], status="failure", level=logging.ERROR), logger)
        sys.exit(3)


if __name__ == "__main__":
    main()
