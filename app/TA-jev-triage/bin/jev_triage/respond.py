"""Shared code for the Adaptive Response action (jev_triage_ar.py) and its queue (| jevqueue)."""
import json
import logging
import os
import re
import sys

from splunklib import results

APP = "TA-jev-triage"
ACTION = "jev_triage"
QUEUE = "jev_triage_queue"
SPLUNK_HOME = os.environ.get("SPLUNK_HOME", "/opt/splunk")
_cim = os.path.join(SPLUNK_HOME, "etc", "apps", "Splunk_SA_CIM", "lib")
if _cim not in sys.path:
    sys.path.append(_cim)
try:  # Common Action Model helper shipped with Splunk_SA_CIM (present with ES)
    from cim_actions import ModularAction  # noqa: E402
except Exception:  # pragma: no cover
    ModularAction = None


def get_logger():
    if ModularAction:
        return ModularAction.setup_logger("jev_triage_modalert")
    lg = logging.getLogger("jev_triage_modalert")
    if not lg.handlers:
        try:
            h = logging.FileHandler(os.path.join(SPLUNK_HOME, "var", "log", "splunk", "jev_triage_modalert.log"))
        except Exception:
            h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        lg.addHandler(h)
        lg.setLevel(logging.INFO)
    return lg


def q(v):
    return '"%s"' % str(v).replace("\\", "\\\\").replace('"', '\\"')


def oneshot(svc, spl, earliest, latest):
    """Rows of a oneshot search. A FATAL/ERROR message (e.g. a failing command) raises instead of
    looking like an empty result."""
    stream = svc.jobs.oneshot(spl, earliest_time=earliest, latest_time=latest, output_mode="json", count=0)
    rows, errors = [], []
    for r in results.JSONResultsReader(stream):
        if isinstance(r, dict):
            rows.append(r)
        elif isinstance(r, results.Message) and r.type in ("FATAL", "ERROR"):
            errors.append(r.message)
    if errors and not rows:
        raise RuntimeError("search failed: " + " | ".join(errors)[:400])
    return rows


def window_from_ids(ids):
    """event_id '<uuid>@@notable@@time<epoch>' carries the finding time; search around it."""
    ts = [int(m.group(1)) for i in ids for m in [re.search(r"@@time(\d+)", i)] if m]
    if ts:
        return str(min(ts) - 3600), str(max(ts) + 3600)
    return "-30d", "now"


def triage(svc, where, e, l, write_note=False, lang="", auto=False, explain=None):
    """Triage the findings matching `where`; returns (total, counts by jev_status / explain / note status).

    auto=True: an automatic run (detection through the queue): the daily limits in [limits] apply.
    explain: None, or {"min_urgency": "high", "dispositions": "TP,Undetermined"} to add LLM explanations
    (before the Note, so the Note includes them)."""
    steps = " | jevtriage%s" % (" auto=true" if auto else "")
    if explain:
        steps += " | jevexplain%s%s%s%s" % (
            " auto=true" if auto else "",
            " lang=%s" % lang if lang in ("en", "ja") else "",
            " min_urgency=%s" % explain["min_urgency"] if explain.get("min_urgency") in ("low", "medium", "high", "critical") else "",
            " dispositions=%s" % q(explain["dispositions"]) if explain.get("dispositions") else "")
    if write_note:
        # jevnote before jev_persist: the note fields are stored together with the result
        steps += " | jevnote%s" % (" lang=%s" % lang if lang in ("en", "ja") else "")
    spl = ("search `jev_findings` | search %s | dedup event_id%s | `jev_persist`"
           " | eval jev_note_status=coalesce(jev_note_status, \"-\"), jev_explain_status=coalesce(jev_explain_status, \"-\")"
           " | stats count by jev_status jev_explain_status jev_note_status") % (where, steps)
    counts, total = {}, 0

    def add(k, n):
        counts[k] = counts.get(k, 0) + n

    for r in oneshot(svc, spl, e, l):
        n = int(float(r.get("count", 0)))
        total += n
        add(r.get("jev_status", "?"), n)
        es = r.get("jev_explain_status", "-")
        if explain and es != "-":
            add("explain " + es[:60], n)
        ns = r.get("jev_note_status", "-")
        if write_note and ns != "-":
            add("note " + ns[:40], n)
    return total, counts


def summary(total, counts, problem=None):
    detail = ", ".join("%s=%d" % kv for kv in sorted(counts.items()))
    if problem:
        return problem, "failure", logging.WARNING
    if total and counts.get("ok", 0) + counts.get("skipped", 0) == total:
        return "triaged %d finding(s) (%s)" % (total, detail), "success", logging.INFO
    return "triaged %d finding(s) with problems (%s)" % (total, detail), "failure", logging.WARNING


def make_modaction(settings, logger):
    if not ModularAction:
        return None
    try:
        return ModularAction(json.dumps(settings), logger, ACTION)
    except Exception as e:
        logger.warning("cim_actions not usable: %s", e)
        return None


def for_rows(modaction, rows, fn, logger):
    """Call fn() once per result row (rid) so ES ties each record to its finding."""
    if not modaction:
        return
    for num, row in enumerate(rows or [{}]):
        try:
            row = dict(row)
            row.setdefault("rid", str(num))
            modaction.update(row)
            fn()
        except Exception as e:  # never fail because of status logging
            logger.warning("status record not written: %s", e)
