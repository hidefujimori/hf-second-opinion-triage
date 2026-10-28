#!/usr/bin/env python
"""| jevprompt  —  support mode for the Jev questions (edit, test, apply, revert, export, import).

The shipped questions (bin/jev_triage/questions.json) never change. Edited versions are kept in the KV store and
one version per decision model can be put in use. Everything except action=status needs an admin
(edit_storage_passwords or admin_all_objects); save / import / test / apply also need support mode to be on.

  | jevprompt action=status
  | jevprompt action=support_on reason="..." hours=4        (1-24)
  | jevprompt action=support_off
  | jevprompt action=get id=<version id>|default
  | jevprompt action=save model=<model> reason="..." content=<base64 of the questions JSON>
  | jevprompt action=test id=<version id> [days=90] [limit=33]
  | jevprompt action=apply id=<version id> reason="..."
  | jevprompt action=revert model=<model> reason="..."
  | jevprompt action=export id=<version id>
  | jevprompt action=import reason="..." content=<base64 of an exported file>
  | jevprompt action=evalset_prompt lang=ja|en [limit=33]
Each change is written to index=jev_triage sourcetype=jev:prompt:audit.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib import results  # noqa: E402
from splunklib.searchcommands import Configuration, GeneratingCommand, Option, dispatch, validators  # noqa: E402

from jev_triage import prompts_store as ps, settings  # noqa: E402

ACTIONS = ("status", "support_on", "support_off", "get", "save", "test", "apply", "revert", "export", "import",
           "evalset_prompt")
DISP = {"tp": "TP", "true_positive": "TP", "fp": "FP", "false_positive": "FP", "benign": "Benign",
        "benign_positive": "Benign", "undetermined": "Undetermined", "unknown": "Undetermined",
        "\u5224\u5225\u4e0d\u53ef": "Undetermined"}
LEVELS = ("low", "medium", "high", "critical")


def _disp(v):
    return DISP.get(str(v or "").strip().lower().replace(" ", "_").replace("-", "_"), "")


@Configuration(distributed=False)
class JevPromptCommand(GeneratingCommand):
    action = Option(require=True, validate=validators.Set(*ACTIONS))
    id = Option(require=False, default=None)
    model = Option(require=False, default=None)
    reason = Option(require=False, default="")
    content = Option(require=False, default=None)
    hours = Option(require=False, default=ps.DEFAULT_HOURS, validate=validators.Integer(1, ps.MAX_HOURS))
    days = Option(require=False, default=90, validate=validators.Integer(1, 3650))
    limit = Option(require=False, default=33, validate=validators.Integer(1, 200))
    lang = Option(require=False, default="en", validate=validators.Set("en", "ja"))

    # ----- helpers -----
    def _user(self):
        return getattr(self._metadata.searchinfo, "username", "") or ""

    def _jev(self):
        return settings.stanza(self.service, "jev", {"model": "jev-1.13.0", "questions_file": "questions.json"})

    def _default(self):
        return ps.load_default(self._jev().get("questions_file") or "questions.json")

    def _need_admin(self):
        if not settings.can_admin(self.service):
            raise RuntimeError("jevprompt action=%s is for admins (edit_storage_passwords or admin_all_objects)" % self.action)

    def _need_support(self):
        if not ps.support_state(self.service)["on"]:
            raise RuntimeError("support mode is off: start it first (Setup > Prompts (support))")

    def _need_reason(self):
        if not str(self.reason or "").strip():
            raise RuntimeError("reason= is required")

    def _audit(self, what, **kw):
        ev = dict(action=what, user=self._user(), reason=self.reason or "", **kw)
        try:
            ps.audit(self.service, ev)
        except Exception as e:   # needs edit_tcp; the change itself is already stored
            self.logger.warning("audit event not written: %s", e)
            return str(e)[:200]
        return ""

    def _version(self, vid):
        v = ps.kv_get(self.service, ps.VERSIONS, vid or "")
        if not v:
            raise RuntimeError("version %s not found" % vid)
        return v

    def _row(self, v):
        t = json.loads(v.get("test") or "{}")
        return {"row": "version", "id": v["_key"], "kind": v.get("kind"), "model": v.get("model"), "base": v.get("base"),
                "status": v.get("status"), "author": v.get("author"), "created": v.get("created"), "reason": v.get("reason"),
                "hash": v.get("hash"), "imported_from": v.get("imported_from", ""), "tested": "1" if v.get("test_hash") == v.get("hash") else "0",
                "test_blocked": "1" if t.get("blocked") else "0", "test_summary": t.get("summary", ""), "test": v.get("test", "")}

    def _new_version(self, q, model, base, extra=None):
        errs = ps.validate(q, self._default()["questions"])
        if errs:
            raise RuntimeError("not saved: " + "; ".join(errs[:8]))
        vid = ps.new_id()
        while ps.kv_get(self.service, ps.VERSIONS, vid):
            time.sleep(1)
            vid = ps.new_id()
        doc = {"_key": vid, "kind": "questions", "model": model, "base": base, "content": json.dumps(q),
               "hash": ps.content_hash(q), "author": self._user(), "created": int(time.time()),
               "reason": self.reason, "status": "draft",
               "diff": json.dumps(ps.diff(q, self._default()["questions"]))}
        doc.update(extra or {})
        ps.kv_save(self.service, ps.VERSIONS, doc)
        return doc

    # ----- actions -----
    def a_status(self):
        jev = self._jev()
        sup = ps.support_state(self.service)
        yield {"row": "state", "model_in_use": jev.get("model"), "default_version": self._default().get("version"),
               "support_on": "1" if sup["on"] else "0", "support_by": sup.get("enabled_by", ""),
               "support_expires": sup.get("expires_at", ""), "support_remaining_s": sup["remaining_s"],
               "support_reason": sup.get("reason", ""), "can_edit": "1" if settings.can_admin(self.service) else "0"}
        for a in ps.kv_query(self.service, ps.STATE, {"kind": "questions"}):
            if a.get("version_id"):
                yield {"row": "active", "model": a.get("model"), "id": a.get("version_id"),
                       "applied_by": a.get("applied_by"), "applied_at": a.get("applied_at")}
        for v in ps.kv_query(self.service, ps.VERSIONS, sort="created:-1", limit=200):
            r = self._row(v)
            r.pop("test", None)
            yield r

    def a_support_on(self):
        self._need_admin()
        self._need_reason()
        now = int(time.time())
        doc = {"_key": ps.SUPPORT_KEY, "active": True, "enabled_by": self._user(), "enabled_at": now,
               "expires_at": now + int(self.hours) * 3600, "reason": self.reason}
        ps.kv_save(self.service, ps.STATE, doc)
        warn = self._audit("support_on", hours=int(self.hours), expires_at=doc["expires_at"])
        yield {"status": "ok", "support_on": "1", "expires_at": doc["expires_at"], "audit_error": warn}

    def a_support_off(self):
        self._need_admin()
        d = ps.kv_get(self.service, ps.STATE, ps.SUPPORT_KEY) or {"_key": ps.SUPPORT_KEY}
        d.update(active=False, ended_by=self._user(), ended_at=int(time.time()))
        d.pop("_user", None)
        ps.kv_save(self.service, ps.STATE, d)
        warn = self._audit("support_off")
        yield {"status": "ok", "support_on": "0", "audit_error": warn}

    def a_get(self):
        self._need_admin()
        d = self._default()
        if not self.id or self.id == "default":
            yield {"id": "default", "base": d.get("version"), "content": json.dumps(d["questions"])}
            return
        v = self._version(self.id)
        r = self._row(v)
        r.update(content=v["content"], diff=v.get("diff", ""))
        yield r

    def a_save(self):
        self._need_admin()
        self._need_support()
        self._need_reason()
        if not self.content:
            raise RuntimeError("content= (base64 of the questions JSON) is required")
        try:
            q = json.loads(ps.b64(self.content))
        except Exception as e:
            raise RuntimeError("content is not base64 of JSON: %s" % e)
        if isinstance(q, dict) and "questions" in q and isinstance(q["questions"], dict):
            q = q["questions"]
        model = self.model or self._jev().get("model")
        doc = self._new_version(q, model, self._default().get("version"))
        warn = self._audit("save", id=doc["_key"], model=model, hash=doc["hash"], changes=len(json.loads(doc["diff"])))
        yield {"status": "ok", "id": doc["_key"], "model": model, "hash": doc["hash"],
               "changes": len(json.loads(doc["diff"])), "audit_error": warn}

    def a_import(self):
        self._need_admin()
        self._need_support()
        self._need_reason()
        if not self.content:
            raise RuntimeError("content= (base64 of the exported file) is required")
        try:
            meta, q = ps.parse_import(ps.b64(self.content), self._default())
        except ps.PromptError as e:
            raise RuntimeError("not imported: %s" % e)
        model = self.model or meta.get("model") or self._jev().get("model")
        doc = self._new_version(q, model, meta.get("base") or self._default().get("version"),
                                {"imported_from": "%s (%s, %s)" % (meta.get("id"), meta.get("author"), meta.get("hash"))})
        if (meta.get("base") or "") != (self._default().get("version") or ""):
            doc["base_warning"] = "exported from base %s; this app ships %s" % (meta.get("base"), self._default().get("version"))
        warn = self._audit("import", id=doc["_key"], model=model, hash=doc["hash"], imported_from=meta.get("id"))
        yield {"status": "ok", "id": doc["_key"], "model": model, "hash": doc["hash"],
               "warning": doc.get("base_warning", ""), "audit_error": warn}

    def a_export(self):
        self._need_admin()
        v = self._version(self.id)
        yield {"id": v["_key"], "filename": "jev-questions-%s-%s.json" % (v.get("model"), v["_key"]),
               "export": json.dumps(ps.export_doc(v), indent=2)}

    # --- test ---
    def _oneshot(self, spl, earliest="0"):
        stream = self.service.jobs.oneshot(spl, earliest_time=earliest, latest_time="now", output_mode="json", count=0)
        rows, fatal = [], []
        for r in results.JSONResultsReader(stream):
            if isinstance(r, dict):
                rows.append(r)
            elif isinstance(r, results.Message) and r.type in ("FATAL", "ERROR"):
                fatal.append(r.message)
        if fatal and not rows:
            raise RuntimeError("search failed: %s" % " ".join(fatal)[:400])
        return rows

    def _targets(self):
        """(ids, truth by id, source)."""
        try:
            rows = self._oneshot("| inputlookup jev_eval_set.csv | head 500")
        except Exception:
            rows = []
        truth = {}
        for r in rows:
            fid = (r.get("finding_id") or r.get("event_id") or "").strip()
            if fid:
                truth[fid] = {"disposition": _disp(r.get("disposition")), "urgency": str(r.get("urgency") or "").strip().lower()}
        if truth:
            return list(truth), truth, "jev_eval_set"
        rows = self._oneshot("| inputlookup jev_triage_latest | where isnotnull(jev_time) | sort - jev_time | head %d | table event_id" % int(self.limit))
        return [r["event_id"] for r in rows if r.get("event_id")], {}, "recent"

    def _run(self, ids, qid, model):
        quoted = ", ".join('"%s"' % i.replace('"', '') for i in ids)
        spl = ("search `jev_findings` | search event_id IN (%s) | dedup event_id | jevtriage questions=\"%s\" model=\"%s\""
               " | table event_id rule_name jev_status jev_error jev_enrich_errors jev_disposition jev_urgency jev_disposition_confidence" % (quoted, qid, model))
        return {r["event_id"]: r for r in self._oneshot(spl, "-%dd" % int(self.days))}

    def a_test(self):
        self._need_admin()
        self._need_support()
        v = self._version(self.id)
        model = v.get("model")
        if model != self._jev().get("model"):
            raise RuntimeError("version %s is for model %s, but [jev] model is %s: the test uses the configured endpoint, "
                               "so set the endpoint and model for %s first" % (v["_key"], model, self._jev().get("model"), model))
        act = ps.kv_get(self.service, ps.STATE, ps.active_key(model)) or {}
        cur_id = act.get("version_id") or "default"
        if cur_id == v["_key"]:
            cur_id = "default"
        ids, truth, source = self._targets()
        if not ids:
            raise RuntimeError("no findings to test with (no jev_eval_set.csv and no triage results yet)")
        t0 = time.time()
        # one after the other: two runs at once (each with its own enrichment searches) can hit the search
        # head's limit of concurrent searches and lose facts, which makes the comparison meaningless
        cur = self._run(ids, cur_id, model)
        new = self._run(ids, v["_key"], model)
        changes, n, err, enrich_err = [], 0, 0, 0
        score = {"cur_disp": 0, "new_disp": 0, "cur_urg": 0, "new_urg": 0, "cur_tp_miss": 0, "new_tp_miss": 0, "lost_tp": 0}
        for i in ids:
            a, b = cur.get(i), new.get(i)
            if not a or not b:
                continue
            n += 1
            if a.get("jev_enrich_errors") or b.get("jev_enrich_errors"):
                enrich_err += 1
            if b.get("jev_status") != "ok" or a.get("jev_status") != "ok":
                err += 1
                continue
            t = truth.get(i, {})
            if t.get("disposition"):
                score["cur_disp"] += a.get("jev_disposition") == t["disposition"]
                score["new_disp"] += b.get("jev_disposition") == t["disposition"]
                if t["disposition"] == "TP":
                    score["cur_tp_miss"] += a.get("jev_disposition") != "TP"
                    score["new_tp_miss"] += b.get("jev_disposition") != "TP"
            if t.get("urgency") in LEVELS:
                score["cur_urg"] += a.get("jev_urgency") == t["urgency"]
                score["new_urg"] += b.get("jev_urgency") == t["urgency"]
            if a.get("jev_disposition") == "TP" and b.get("jev_disposition") != "TP":
                score["lost_tp"] += 1
            if (a.get("jev_disposition"), a.get("jev_urgency")) != (b.get("jev_disposition"), b.get("jev_urgency")):
                changes.append({"event_id": i, "rule_name": b.get("rule_name") or a.get("rule_name"),
                                "cur": "%s / %s" % (a.get("jev_disposition"), a.get("jev_urgency")),
                                "new": "%s / %s" % (b.get("jev_disposition"), b.get("jev_urgency")),
                                "truth": "%s / %s" % (t.get("disposition") or "-", t.get("urgency") or "-") if t else ""})
        has_truth = bool(truth)
        blocked = has_truth and score["new_tp_miss"] > score["cur_tp_miss"]
        warnings = []
        if err:
            warnings.append("%d findings failed in one of the runs" % err)
        if enrich_err:
            blocked = True
            warnings.append("%d findings had enrichment errors in one of the runs (the comparison is not reliable; "
                            "test again when the search head is less busy)" % enrich_err)
        if has_truth and score["new_disp"] < score["cur_disp"]:
            warnings.append("fewer correct dispositions (%d -> %d)" % (score["cur_disp"], score["new_disp"]))
        if has_truth and score["new_urg"] < score["cur_urg"]:
            warnings.append("fewer correct urgencies (%d -> %d)" % (score["cur_urg"], score["new_urg"]))
        if score["lost_tp"]:
            warnings.append("%d findings are no longer TP" % score["lost_tp"])
        if n == 0:
            blocked = True
            warnings.append("none of the findings could be tested")
        summary = "%s: %d findings, %d changed" % (source, n, len(changes))
        if has_truth:
            summary += ", disposition %d->%d, urgency %d->%d, TP missed %d->%d" % (
                score["cur_disp"], score["new_disp"], score["cur_urg"], score["new_urg"], score["cur_tp_miss"], score["new_tp_miss"])
        test = {"time": int(time.time()), "by": self._user(), "against": cur_id, "source": source, "n": n, "errors": err,
                "enrich_errors": enrich_err, "truth": has_truth, "score": score, "changes": changes[:100], "blocked": blocked, "warnings": warnings,
                "summary": summary, "seconds": int(time.time() - t0)}
        v["test"] = json.dumps(test)
        v["test_hash"] = v.get("hash")
        if v.get("status") == "draft":
            v["status"] = "tested"
        v.pop("_user", None)
        ps.kv_save(self.service, ps.VERSIONS, v)
        warn = self._audit("test", id=v["_key"], model=model, summary=summary, blocked=blocked)
        yield {"status": "ok", "id": v["_key"], "blocked": "1" if blocked else "0", "summary": summary,
               "warnings": " | ".join(warnings), "test": json.dumps(test), "audit_error": warn}

    def a_apply(self):
        self._need_admin()
        self._need_support()
        self._need_reason()
        v = self._version(self.id)
        if v.get("test_hash") != v.get("hash"):
            raise RuntimeError("version %s has not been tested" % v["_key"])
        t = json.loads(v.get("test") or "{}")
        if t.get("blocked"):
            raise RuntimeError("version %s cannot be applied: %s" % (v["_key"], t.get("summary")))
        errs = ps.validate(json.loads(v["content"]), self._default()["questions"])
        if errs:
            raise RuntimeError("version %s: %s" % (v["_key"], errs[0]))
        model = v.get("model")
        old = ps.kv_get(self.service, ps.STATE, ps.active_key(model)) or {}
        if old.get("version_id") and old["version_id"] != v["_key"]:
            try:
                o = self._version(old["version_id"])
                o["status"] = "tested"
                o.pop("_user", None)
                ps.kv_save(self.service, ps.VERSIONS, o)
            except Exception:
                pass
        ps.kv_save(self.service, ps.STATE, {"_key": ps.active_key(model), "kind": "questions", "model": model,
                                            "version_id": v["_key"], "applied_by": self._user(),
                                            "applied_at": int(time.time()), "reason": self.reason})
        v["status"] = "active"
        v.pop("_user", None)
        ps.kv_save(self.service, ps.VERSIONS, v)
        warn = self._audit("apply", id=v["_key"], model=model, previous=old.get("version_id") or "default",
                           warnings=t.get("warnings"))
        yield {"status": "ok", "id": v["_key"], "model": model, "previous": old.get("version_id") or "default", "audit_error": warn}

    def a_revert(self):
        self._need_admin()
        self._need_reason()
        model = self.model or self._jev().get("model")
        old = ps.kv_get(self.service, ps.STATE, ps.active_key(model)) or {}
        if old.get("version_id"):
            ps.kv_delete(self.service, ps.STATE, ps.active_key(model))
            try:
                o = self._version(old["version_id"])
                o["status"] = "tested"
                o.pop("_user", None)
                ps.kv_save(self.service, ps.VERSIONS, o)
            except Exception:
                pass
        warn = self._audit("revert", model=model, previous=old.get("version_id") or "default")
        yield {"status": "ok", "model": model, "previous": old.get("version_id") or "default", "audit_error": warn}

    def a_evalset_prompt(self):
        self._need_admin()
        with open(os.path.join(HERE, "jev_triage", "prompts", "evalset_%s.txt" % self.lang), encoding="utf-8") as fh:
            tpl = fh.read()
        rows = self._oneshot("| inputlookup jev_triage_latest | where isnotnull(jev_state) | sort - jev_time | head %d"
                             " | table event_id rule_name urgency jev_state" % int(self.limit))
        lines = []
        for r in rows:
            st = (r.get("jev_state") or "")[:1500]
            lines.append(json.dumps({"finding_id": r.get("event_id"), "rule_name": r.get("rule_name"),
                                     "es_urgency": r.get("urgency"), "facts": st}, ensure_ascii=False))
        yield {"count": len(lines), "prompt": tpl.replace("{findings}", "\n".join(lines))}

    def generate(self):
        # splunklib takes the output fields from the first row: give every row the same fields
        rows = list(getattr(self, "a_" + self.action)())
        keys = []
        for r in rows:
            keys.extend(k for k in r if k not in keys)
        for r in rows:
            yield {k: r.get(k, "") for k in keys}


dispatch(JevPromptCommand, sys.argv, sys.stdin, sys.stdout, __name__)
