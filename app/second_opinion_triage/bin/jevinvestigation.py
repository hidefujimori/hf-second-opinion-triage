#!/usr/bin/env python
"""| jevinvestigation id=<ES-00002 | investigation GUID>  —  summary of the Jev results of all findings in an ES investigation.

One output row: inv_* fields (counts, highest urgency, ...). note=true writes the summary as a Note on the
investigation (ES public API, needs mc_investigation_write); llm=true adds a short LLM summary.
Findings without a Jev result: untriaged=count (only counted) or run (triaged now, up to [investigation] max_run);
the default comes from jev_triage.conf [investigation] untriaged (Setup).
force=true writes the Note again when the results have not changed since the last summary Note.
"""
import hashlib
import json
import os
import re
import sys
import time
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib import results  # noqa: E402
from splunklib.searchcommands import Configuration, GeneratingCommand, Option, dispatch, validators  # noqa: E402

from jev_triage import guide, investigations, invnote, modelname, remote, settings, usage  # noqa: E402

APP = "second_opinion_triage"
STORE = "/servicesNS/nobody/%s/storage/collections/data/jev_investigation_notes" % APP
LATEST = "/servicesNS/nobody/%s/storage/collections/data/jev_triage_latest" % APP
WORDS = {"en": "120 words", "ja": "300字"}
DEFAULTS = {"untriaged": "count", "max_run": "20"}


def _spl_q(v):
    return '"%s"' % str(v).replace("\\", "\\\\").replace('"', '\\"')


@Configuration(type="reporting")
class JevInvestigationCommand(GeneratingCommand):
    id = Option(require=True)
    note = Option(require=False, validate=validators.Boolean(), default=False)
    llm = Option(require=False, validate=validators.Boolean(), default=False)
    force = Option(require=False, validate=validators.Boolean(), default=False)
    lang = Option(require=False, default=None)
    untriaged = Option(require=False, default=None, validate=validators.Set("count", "run"))

    def _get_json(self, path, **params):
        resp = self.service.get(path, output_mode="json", **params)
        return json.loads(resp.body.read().decode("utf-8") or "null")

    def _latest(self, ids):
        out = {}
        for i in range(0, len(ids), 50):
            part = ids[i:i + 50]
            rows = self._get_json(LATEST, query=json.dumps({"_key": {"$in": part}})) or []
            out.update({r.get("event_id") or r.get("_key"): r for r in rows})
        return out

    def _run(self, ids):
        """Triage findings that have no Jev result yet (same command as the Re-run button)."""
        times = [int(m.group(1)) for m in (re.search(r"@@time(\d+)", i) for i in ids) if m]
        kw = {"earliest_time": str(min(times) - 3600), "latest_time": str(max(times) + 3600)} \
            if len(times) == len(ids) else {"earliest_time": "0", "latest_time": "now"}
        spl = ("search `jev_findings` | search event_id IN (%s) | dedup event_id | jevtriage persist=true"
               " | table event_id jev_status" % ", ".join(_spl_q(i) for i in ids))
        stream = self.service.jobs.oneshot(spl, output_mode="json", count=0, **kw)
        return [r for r in results.JSONResultsReader(stream) if isinstance(r, dict)]

    def _summarize(self, inv, items, s, lang):   # not "_llm": splunklib keeps option "llm" in self._llm
        cfg = settings.llm_cfg(self.service, self.logger)
        path = os.path.join(HERE, "jev_triage", "prompts", "investigation_%s.txt" % lang)
        if not os.path.exists(path):
            path = os.path.join(HERE, "jev_triage", "prompts", "investigation_en.txt")
        with open(path, encoding="utf-8") as fh:
            system = fh.read().replace("{words}", WORDS.get(lang, "120 words"))
        jev_cfg = settings.stanza(self.service, "jev", {"model": "", "display_name": ""})
        system = modelname.localize(system, modelname.label(jev_cfg.get("model"), jev_cfg.get("display_name")))
        try:
            usage.take(self.service, "llm_manual")
        except Exception:
            pass
        user = ("<investigation_data>\n" + json.dumps(invnote.llm_input(inv, items, s), ensure_ascii=False, indent=1)
                + "\n</investigation_data>\n\nSummarize this investigation for the analyst.")
        return remote.complete(self.service, cfg, system, user), "%s:%s" % (cfg.get("provider"), cfg.get("model"))

    def generate(self):
        conf = settings.stanza(self.service, "investigation", DEFAULTS)
        lang = (self.lang or settings.stanza(self.service, "es_note", {"language": "en"}).get("language") or "en").lower()
        out = {"inv_status_msg": "", "inv_query": self.id}
        try:
            inv = investigations.get(self.service, self.id)
        except Exception as e:
            out["inv_status_msg"] = "error: cannot read investigations (%s)" % str(e)[:200]
            yield out
            return
        if not inv:
            out["inv_status_msg"] = "error: investigation not found"
            yield out
            return
        v = investigations.view(inv)
        out.update({"inv_guid": v["guid"], "inv_id": v["id"], "inv_name": v["name"], "inv_status": v["status"],
                    "inv_disposition": v["disposition"], "inv_owner": v["owner"]})
        kids = investigations.children(self.service, v["guid"])
        ids = [e for _, e, _ in kids if e]
        latest = self._latest(ids) if ids else {}
        mode = self.untriaged or (conf.get("untriaged") or "count")
        missing = [i for i in ids if i not in latest]
        out["inv_untriaged_mode"] = mode
        if mode == "run" and missing:
            try:
                lim = max(1, int(conf.get("max_run") or 20))
            except ValueError:
                lim = 20
            got = self._run(missing[:lim])
            out["inv_ran"] = len(got)
            out["inv_ran_ok"] = sum(1 for r in got if r.get("jev_status") == "ok")
            latest.update(self._latest(missing[:lim]))
        items = []
        for _, e, name in kids:
            rec = latest.get(e) if e else None
            arec, label = guide.ai_record(self.service, e) if (e and rec) else ({}, "")
            items.append({"event_id": e, "name": name, "rec": rec,
                          "ai_cat": guide.ai_cat(label or guide.parse_summary(arec.get("summary"))["disp"]) if (arec or label) else ""})
        s = invnote.aggregate(items)
        out.update({"inv_findings": s["n"], "inv_top_urgency": s["top"], "inv_tp": len(s["tp"]), "inv_undetermined": s["und"],
                    "inv_untriaged": s["untriaged"], "inv_errors": s["errors"], "inv_ai_disagree": s["ai_disagree"],
                    "inv_statement_conflict": s["conflict"],
                    "inv_dispositions": json.dumps(s["by_disp"], sort_keys=True), "inv_tp_findings": s["tp"]})
        if not self.note:
            out["inv_status_msg"] = "ok"
            yield out
            return
        mark = hashlib.sha1("|".join(sorted("%s:%s" % (e, (latest.get(e) or {}).get("jev_time", "")) for e in ids))
                            .encode("utf-8")).hexdigest()
        prev = {}
        try:
            prev = self._get_json("%s/%s" % (STORE, quote(v["guid"]))) or {}
        except Exception:
            prev = {}
        prev_llm = str(prev.get("llm")) == "1"
        if prev.get("note_for") == mark and (prev_llm or not self.llm) and not self.force:
            out.update({"inv_status_msg": "already written", "inv_note_id": prev.get("note_id", "")})
            yield out
            return
        llm_text = ""
        if self.llm:
            try:
                llm_text, out["inv_llm_model"] = self._summarize(inv, items, s, lang)
            except Exception as e:
                out["inv_llm_error"] = str(e)[:300]
        title, content = invnote.build(inv, s, lang, llm_text)
        try:
            path = "/servicesNS/nobody/missioncontrol/public/v2/investigations/%s/notes" % quote(v["guid"], safe="@")
            resp = self.service.post(path, headers=[("Content-Type", "application/json")],
                                     body=json.dumps({"title": title, "content": content}))
            body = json.loads(resp.body.read().decode("utf-8") or "{}")
            out["inv_note_id"] = body.get("id", "")
            out["inv_status_msg"] = "ok"
        except Exception as e:
            out["inv_status_msg"] = "error: %s" % str(e)[:300]
            yield out
            return
        doc = {"_key": v["guid"], "inv_id": v["id"], "note_id": out["inv_note_id"], "note_for": mark,
               "note_time": int(time.time()), "llm": "1" if llm_text else "0",
               "note_by": getattr(self.metadata.searchinfo, "username", "") or ""}
        try:
            self.service.post("%s/batch_save" % STORE, headers=[("Content-Type", "application/json")], body=json.dumps([doc]))
        except Exception as e:
            out["inv_persist_error"] = str(e)[:300]
        yield out


dispatch(JevInvestigationCommand, sys.argv, sys.stdin, sys.stdout, __name__)
