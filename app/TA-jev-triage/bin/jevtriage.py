#!/usr/bin/env python
"""| jevtriage  —  triage ES findings with TypeSafe Jev.

Input: findings from the `notable` macro (one row per finding).
Output: the same rows plus jev_* fields (suggested disposition/urgency, confidences, state sent, status).
Persist with: ... | jevtriage | outputlookup append=true key_field=event_id jev_triage_latest | collect index=jev_triage

Options:
  dryrun=true        build the state (with enrichment) but do not call Jev
  enrich=false       skip SPL enrichment
  ordercheck=false   skip the second call with reversed disposition options
  endpoint=<url> model=<name>   evaluation only (admins): use another System One server / model instead of
                     [jev] endpoint / model. No API key is sent to such an endpoint, and results cannot be persisted.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib import results  # noqa: E402
from splunklib.searchcommands import Configuration, Option, StreamingCommand, dispatch, validators  # noqa: E402

from jev_triage import __version__, jev_client, persist, policy, settings, state, usage  # noqa: E402
from jev_triage.enrich import Enricher, load_templates  # noqa: E402

APP = "TA-jev-triage"
SECRET_NAME = "typesafe_api_key"


@Configuration(local=True)
class JevTriageCommand(StreamingCommand):
    dryrun = Option(require=False, validate=validators.Boolean(), default=False)
    enrich = Option(require=False, validate=validators.Boolean(), default=None)
    ordercheck = Option(require=False, validate=validators.Boolean(), default=None)
    persist = Option(require=False, validate=validators.Boolean(), default=False)
    # auto=true: an automatic run (Adaptive Response queue, scheduled search): [limits] jev_auto_daily applies
    auto = Option(require=False, validate=validators.Boolean(), default=False)
    endpoint = Option(require=False, default=None)
    model = Option(require=False, default=None)

    def _settings(self):
        s = {"model": "jev-1.13.0", "questions_file": "questions.json", "confidence_threshold": "0.60",
             "escalation_floor": "0.80", "rollup_urgency_cap": "high", "order_check": "true",
             "timeout": "30", "proxy": "", "parallel": "4", "enrichment_enabled": "true", "endpoint": "",
             "shared_entities": "*.amazonaws.com,*.amazon.com,*.microsoft.com,*.office.com,*.google.com", "max_facts": "12"}
        try:
            conf = self.service.confs["jev_triage"]
            for stanza in ("jev", "enrichment"):
                for k, v in conf[stanza].content.items():
                    if not k.startswith("eai:") and v is not None:
                        s[k if stanza == "jev" or k != "enabled" else "enrichment_enabled"] = v
        except Exception as e:  # defaults are fine
            self.logger.warning("jev_triage.conf not read: %s", e)
        return s

    def _api_key(self):
        return settings.jev_api_key(self.service)

    def _run_spl(self, spl, earliest, latest):
        stream = self.service.jobs.oneshot(spl, earliest_time=earliest, latest_time=latest,
                                           output_mode="json", count=0)
        return [r for r in results.JSONResultsReader(stream) if isinstance(r, dict)]

    def _budget_ok(self):
        """Count this finding; False when the daily limit for automatic runs is reached."""
        try:
            if self.auto:
                return usage.take(self.service, "jev_auto", self._jev_limit)
            usage.take(self.service, "jev_manual")
        except Exception as e:   # counting must never stop triage
            self.logger.warning("usage counter not updated: %s", e)
        return True

    def _one(self, rec, ctx):
        s, qset, Q, Qrev, enricher, key, do_order, pool2 = ctx
        if not self.dryrun and not self._budget_ok():
            out = dict(rec)
            out.update({"jev_version": __version__, "jev_model": s["model"], "jev_time": int(time.time()),
                        "jev_status": "skipped",
                        "jev_error": "skipped (daily limit %s/day)" % self._jev_limit})
            return out
        out = dict(rec)
        out.update({"jev_version": __version__, "jev_model": s["model"], "jev_questions": qset.get("version"),
                    "jev_time": int(time.time())})
        try:
            t0 = time.time()
            facts, related = enricher.collect(rec) if enricher else ([], [])
            out["jev_enrich_ms"] = int((time.time() - t0) * 1000)
            st = state.build_state(rec, facts, related)
            out["jev_state"] = json.dumps(st, ensure_ascii=False)
            if enricher and enricher.errors:
                out["jev_enrich_errors"] = " | ".join(enricher.errors[-3:])
            if self.dryrun:
                out["jev_status"] = "dryrun"
                return out
            call = lambda q: jev_client.call(key, s["model"], st, q, timeout=int(s["timeout"]), proxy=s["proxy"] or None,
                                             endpoint=s["endpoint"] or None)
            # forward and reversed-option calls run at the same time
            f_rev = pool2.submit(call, Qrev) if do_order else None
            res = call(Q)
            rev = f_rev.result() if f_rev else None
            out.update(policy.decide(res["answers"], rev["answers"] if rev else None, state.is_rollup(rec),
                                     float(s["confidence_threshold"]), float(s["escalation_floor"]),
                                     s["rollup_urgency_cap"] or None))
            out["jev_answers"] = json.dumps(res["answers"])
            out["jev_latency_ms"] = res.get("latency_ms")
            out["jev_input_tokens"] = (res.get("usage") or {}).get("input_tokens", 0) + ((rev or {}).get("usage") or {}).get("input_tokens", 0)
            out["jev_status"] = "ok"
        except Exception as e:  # one bad finding must not stop the batch
            out["jev_status"] = "error"
            out["jev_error"] = str(e)[:500]
        return out

    def _save(self, outs):
        """persist=true: store in the KV store and index here (no outputlookup/collect in the search)."""
        if self.persist and not self.dryrun:
            for o in outs:
                for f in persist.CLEARED_ON_TRIAGE:
                    o.setdefault(f, "")
            try:
                persist.mark_rerun(self.service, outs, getattr(self._metadata.searchinfo, "username", "") or "")
            except Exception as e:  # history only; never block saving the new result
                self.logger.warning("previous result not read: %s", e)
            try:
                persist.save_kv(self.service, outs)
            except Exception as e:
                for o in outs:
                    o["jev_persist_error"] = str(e)[:300]
            try:   # history copy; needs edit_tcp (receivers/simple), so a failure here is only reported
                persist.index_events(self.service, outs)
            except Exception as e:
                for o in outs:
                    o["jev_index_error"] = str(e)[:300]
        return outs

    def stream(self, records):
        s = self._settings()
        truthy = lambda v: str(v).lower() in ("1", "true", "yes")
        do_enrich = truthy(s["enrichment_enabled"]) if self.enrich is None else self.enrich
        do_order = truthy(s["order_check"]) if self.ordercheck is None else self.ordercheck
        with open(os.path.join(HERE, "jev_triage", s["questions_file"]), encoding="utf-8") as fh:
            qset = json.load(fh)
        Q = qset["questions"]
        Qrev = policy.reversed_disposition(Q)
        enricher = Enricher(self._run_spl, load_templates(), s["shared_entities"].split(","), int(s["max_facts"])) if do_enrich else None
        if self.endpoint or self.model:   # evaluation of another decision model
            if not settings.can_admin(self.service):
                raise RuntimeError("endpoint= / model= are for admins (edit_storage_passwords or admin_all_objects)")
            if self.persist or self.auto:
                raise RuntimeError("endpoint= / model= are for evaluation: persist=true and auto=true are not allowed")
            if self.endpoint and not str(self.endpoint).lower().startswith(("http://", "https://")):
                raise RuntimeError("endpoint must start with http:// or https://")
        configured = s["endpoint"] or jev_client.API_URL
        if self.endpoint:
            s["endpoint"] = self.endpoint
        if self.model:
            s["model"] = self.model
        if self.dryrun:
            key = None
        elif self.endpoint and self.endpoint != configured:
            key = None   # never send the stored key to an endpoint given in the search
        else:
            key = settings.jev_api_key(self.service, required=jev_client.is_typesafe(s["endpoint"] or None))
        self._jev_limit = usage.limits(settings.stanza(self.service, "limits", settings.LIMIT_DEFAULTS))["jev_auto"]
        try:
            workers = max(1, min(8, int(s.get("parallel") or 4)))
        except ValueError:
            workers = 4
        # findings are processed `workers` at a time (SPL searches and Jev calls overlap); output keeps input order
        with ThreadPoolExecutor(max_workers=workers) as pool, ThreadPoolExecutor(max_workers=workers) as pool2:
            ctx = (s, qset, Q, Qrev, enricher, key, do_order, pool2)
            batch = []
            for rec in records:
                batch.append(rec)
                if len(batch) >= workers * 4:
                    for out in self._save(list(pool.map(lambda r: self._one(r, ctx), batch))):
                        yield out
                    batch = []
            if batch:
                for out in self._save(list(pool.map(lambda r: self._one(r, ctx), batch))):
                    yield out
        if enricher:
            self.logger.info("jevtriage enrichment: %d SPL searches, %d reused", enricher.spl_calls, enricher.memo_hits)


dispatch(JevTriageCommand, sys.argv, sys.stdin, sys.stdout, __name__)
