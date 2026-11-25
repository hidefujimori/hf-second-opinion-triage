#!/usr/bin/env python
"""| jevnote  —  write the Jev suggestion (and the LLM explanation, if present) as a Note on the ES finding.

Input: rows from the jev_triage_latest KV store. Uses the ES public API:
  POST /servicesNS/nobody/missioncontrol/public/v2/investigations/{finding_id}/notes
Output: jev_note_status, jev_note_id, jev_note_time, jev_note_for, jev_note_expl_for (one note per triage result;
an explanation made after that Note is added as a second, explanation-only Note; force=true writes again).
Typical use:  | `jev_note("<event_id>")`
kind=guide writes the decision guide (Jev vs ES AI SOC Analyst) instead: jev_note_guide_status / _id / _time / _for.
target=<ES-00002 | investigation GUID> writes the suggestion on an investigation that contains the finding instead of the
finding itself (always written; output jev_note_target_status / jev_note_target_id, the finding's Note records are kept).
Requires mc_investigation_write for the user running the search.
"""
import json
import os
import sys
import time
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib.searchcommands import Configuration, Option, StreamingCommand, dispatch, validators  # noqa: E402

from jev_triage import conditions, guide, investigations, modelname, note, persist, settings  # noqa: E402


@Configuration(local=True)
class JevNoteCommand(StreamingCommand):
    force = Option(require=False, validate=validators.Boolean(), default=False)
    lang = Option(require=False, default=None)
    persist = Option(require=False, validate=validators.Boolean(), default=False)
    kind = Option(require=False, default="suggestion", validate=validators.Set("suggestion", "guide"))
    target = Option(require=False, default=None)

    def _default_lang(self):   # not "_lang": splunklib keeps the value of option "lang" in self._lang
        try:
            return self.service.confs["jev_triage"]["es_note"].content.get("language") or "en"
        except Exception:
            return "en"

    def stream(self, records):
        if self.target:   # the finding's KV record is not changed (save_kv replaces whole records)
            return self._stream(records)
        return _persisting(self, self._stream(records))

    def _labels(self, lang):
        """Statement id -> label in the Note's language (built-in and admin-defined statements)."""
        if not hasattr(self, "_stmt_labels"):
            try:
                self._stmt_labels = conditions.all_statements(self.service)
            except Exception:
                self._stmt_labels = conditions.BUILTIN
        key = "label_ja" if lang == "ja" else "label_en"
        return {c["id"]: c.get(key) or c.get("label_en") or c["id"] for c in self._stmt_labels}

    def _post(self, fid, title, content):
        # splunklib URL-encodes the path itself; '@' must stay as is (pre-encoding gives %2540 -> 404)
        path = "/servicesNS/nobody/missioncontrol/public/v2/investigations/%s/notes" % quote(fid, safe="@")
        resp = self.service.post(path, headers=[("Content-Type", "application/json")],
                                 body=json.dumps({"title": title, "content": content}))
        return json.loads(resp.body.read().decode("utf-8") or "{}")

    def _guide(self, records, lang):
        """kind=guide: the decision guide (Jev vs ES AI, and the LLM guide when there is one) as a Note."""
        jev_cfg = settings.stanza(self.service, "jev", {"model": "", "display_name": ""})
        for rec in records:
            rec = dict(rec, jev_model_label=modelname.for_record(rec, jev_cfg))
            out = dict(rec)
            if rec.get("jev_status") != "ok":
                out["jev_note_guide_status"] = "skipped (no Jev result)"
                yield out
                continue
            arec, label = guide.ai_record(self.service, rec.get("event_id") or "")
            if not arec and not label:
                out["jev_note_guide_status"] = "skipped (no ES AI result)"
                yield out
                continue
            ai = guide.ai_view(arec, label)
            has_llm = bool(rec.get("jev_guide")) and rec.get("jev_guide_for") == rec.get("jev_time")
            mark = "%s|%s|%s" % (rec.get("jev_time"), ai["time"], rec.get("jev_guide_time") if has_llm else "")
            if rec.get("jev_note_guide_for") == mark and not self.force:
                out["jev_note_guide_status"] = "already written"
                yield out
                continue
            v = guide.verdict(rec.get("jev_disposition"), rec.get("jev_disposition_raw"), rec.get("jev_disposition_confidence"),
                              rec.get("jev_urgency"), ai["label"], ai["severity"], ai["confidence"], len(ai["failed_checks"]))
            title, content = guide.note_text(rec, ai, v, lang)
            try:
                body = self._post(rec.get("event_id") or "", title, content)
                out["jev_note_guide_status"] = "ok"
                out["jev_note_guide_id"] = body.get("id", "")
                out["jev_note_guide_time"] = int(time.time())
                out["jev_note_guide_for"] = mark
            except Exception as e:
                out["jev_note_guide_status"] = "error: %s" % str(e)[:300]
            yield out

    def _to_investigation(self, records, lang, jev_cfg):
        """target=: the suggestion Note on an investigation that contains the finding."""
        try:
            inv = investigations.get(self.service, self.target)
        except Exception as e:
            inv, err = None, "error: cannot read investigations (%s)" % str(e)[:200]
        else:
            err = "error: investigation not found"
        for rec in records:
            rec = dict(rec, jev_model_label=modelname.for_record(rec, jev_cfg))
            out = {"event_id": rec.get("event_id")}   # nothing of the finding's own Note records is changed
            if not inv:
                out["jev_note_target_status"] = err
            elif rec.get("jev_status") != "ok":
                out["jev_note_target_status"] = "skipped (no Jev result)"
            elif not investigations.contains(self.service, inv["_key"], rec.get("event_id") or ""):
                out["jev_note_target_status"] = "error: the finding is not in %s" % (inv.get("display_id") or inv["_key"])
            else:
                title, content = note.build(rec, lang, self._labels(lang))
                try:
                    body = self._post(inv["_key"], "%s — %s" % (title, rec.get("rule_name") or rec.get("event_id")), content)
                    out["jev_note_target_status"] = "ok"
                    out["jev_note_target_id"] = body.get("id", "")
                    out["jev_note_target"] = inv.get("display_id") or inv["_key"]
                except Exception as e:
                    out["jev_note_target_status"] = "error: %s" % str(e)[:300]
            yield out

    def _stream(self, records):
        lang = (self.lang or self._default_lang()).lower()
        if self.kind == "guide":
            for out in self._guide(records, lang):
                yield out
            return
        jev_cfg = settings.stanza(self.service, "jev", {"model": "", "display_name": ""})
        if self.target:
            for out in self._to_investigation(records, lang, jev_cfg):
                yield out
            return
        for rec in records:
            rec = dict(rec, jev_model_label=modelname.for_record(rec, jev_cfg))
            out = dict(rec)
            if rec.get("jev_status") != "ok":
                out["jev_note_status"] = "skipped (no Jev result)"
                yield out
                continue
            only_expl = False
            if rec.get("jev_note_for") == rec.get("jev_time") and rec.get("jev_note_id") and not self.force:
                if note.explanation_in_note(rec):
                    out["jev_note_status"] = "already written"
                    yield out
                    continue
                only_expl = True   # the Note was written before the explanation: add the explanation
            fid = rec.get("event_id") or ""
            title, content = note.build_explanation(rec, lang) if only_expl else note.build(rec, lang, self._labels(lang))
            try:
                body = self._post(fid, title, content)
                out["jev_note_status"] = "ok (explanation added)" if only_expl else "ok"
                out["jev_note_id"] = body.get("id", "")
                out["jev_note_expl_for"] = rec.get("jev_explain_time") if note.has_explanation(rec) else ""
                out["jev_note_time"] = int(time.time())
                out["jev_note_for"] = rec.get("jev_time")
            except Exception as e:
                out["jev_note_status"] = "error: %s" % str(e)[:300]
            yield out


def _persisting(cmd, gen):
    """persist=true: write each changed row back to the KV store (instead of | outputlookup)."""
    for out in gen:
        if cmd.persist and out.get("event_id"):
            try:
                persist.save_kv(cmd.service, [out])
            except Exception as e:
                out["jev_persist_error"] = str(e)[:300]
        yield out


dispatch(JevNoteCommand, sys.argv, sys.stdin, sys.stdout, __name__)
