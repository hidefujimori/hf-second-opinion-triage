#!/usr/bin/env python
"""| jevqueue  —  work the Adaptive Response queue (KV store jev_triage_queue).

Run by the scheduled search "Second Opinion Triage - Response Queue" every minute. For each pending request
(one detection run, keyed by its sid):
- findings of that run indexed and the request is at least `settle` seconds old -> triage them,
  write ES Notes if asked, log success/failure to index=cim_modactions for each finding;
- no findings after `wait_seconds` -> give up and log a failure.
Done requests are removed after a day. Output: one row per request handled (for monitoring).
Options: settle=<seconds, default 30>
"""
import json
import logging
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib.searchcommands import Configuration, GeneratingCommand, Option, dispatch, validators  # noqa: E402

from jev_triage import respond  # noqa: E402

logger = respond.get_logger()


@Configuration()
class JevQueueCommand(GeneratingCommand):
    settle = Option(require=False, default=30, validate=validators.Integer(0, 600))

    def _status(self, req, msg, status, level):
        settings = {"sid": req.get("sid"), "search_name": req.get("search_name", ""), "app": req.get("app", ""),
                    "owner": req.get("owner", ""), "server_uri": req.get("server_uri", ""),
                    "session_key": self.service.token, "configuration": {}, "results_file": ""}
        modaction = respond.make_modaction(settings, logger)
        rows = [{"rid": r} for r in (req.get("rids") or "0").split(",")]
        respond.for_rows(modaction, rows, lambda: modaction.message(msg, status=status, level=level), logger)

    def generate(self):
        coll = self.service.kvstore[respond.QUEUE].data
        now = int(time.time())
        for req in coll.query():
            key = req.get("_key")
            if req.get("status") != "pending":
                if now - int(float(req.get("done_time") or 0)) > 86400:
                    coll.delete_by_id(key)
                continue
            sid = req.get("sid", "")
            age = now - int(float(req.get("queued_time") or now))
            wait = int(float(req.get("wait_seconds") or 300))
            where = "orig_sid=%s" % respond.q(sid)
            e, l = str(int(float(req.get("queued_time") or now)) - 86400), "now"
            out = {"sid": sid, "search_name": req.get("search_name"), "age_s": age}
            try:
                res = respond.oneshot(self.service, "search `jev_findings` | search %s | stats count" % where, e, l)
                n = int(float(res[0].get("count", 0))) if res else 0
                if n == 0:
                    if age < wait:
                        continue
                    msg, status, level = respond.summary(0, {}, "no findings for this run after %ss" % wait)
                elif age < self.settle and age < wait:
                    continue           # let the Finding action finish indexing
                else:
                    explain = None
                    if req.get("auto_explain") == "1":
                        explain = {"min_urgency": req.get("explain_min_urgency") or "high",
                                   "dispositions": req.get("explain_dispositions") or ""}
                    # detections are automatic runs: the daily limits apply
                    total, counts = respond.triage(self.service, where, e, l, req.get("write_note") == "1",
                                                   req.get("note_language") or "", auto=True, explain=explain)
                    msg, status, level = respond.summary(total, counts)
            except Exception as ex:
                msg, status, level = "jev_triage failed: %s" % str(ex)[:300], "failure", logging.ERROR
            logger.log(level, "mode=queue sid=%s %s", sid, msg)
            self._status(req, msg, status, level)
            req.update({"status": "done" if status == "success" else "failed", "done_time": now, "result": msg})
            coll.update(key, json.dumps({k: v for k, v in req.items() if not k.startswith("_") or k == "_key"}))
            out.update(status=req["status"], result=msg)
            yield out


dispatch(JevQueueCommand, sys.argv, sys.stdin, sys.stdout, __name__)
