#!/usr/bin/env python
"""| jevnote  —  write the Jev suggestion (and the LLM explanation, if present) as a Note on the ES finding.

Input: rows from the jev_triage_latest KV store. Uses the ES public API:
  POST /servicesNS/nobody/missioncontrol/public/v2/investigations/{finding_id}/notes
Output: jev_note_status, jev_note_id, jev_note_time, jev_note_for, jev_note_expl_for (one note per triage result;
an explanation made after that Note is added as a second, explanation-only Note; force=true writes again).
Typical use:  | `jev_note("<event_id>")`
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

from jev_triage import note, persist  # noqa: E402


@Configuration(local=True)
class JevNoteCommand(StreamingCommand):
    force = Option(require=False, validate=validators.Boolean(), default=False)
    lang = Option(require=False, default=None)
    persist = Option(require=False, validate=validators.Boolean(), default=False)

    def _default_lang(self):   # not "_lang": splunklib keeps the value of option "lang" in self._lang
        try:
            return self.service.confs["jev_triage"]["es_note"].content.get("language") or "en"
        except Exception:
            return "en"

    def stream(self, records):
        return _persisting(self, self._stream(records))

    def _stream(self, records):
        lang = (self.lang or self._default_lang()).lower()
        for rec in records:
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
            title, content = note.build_explanation(rec, lang) if only_expl else note.build(rec, lang)
            # splunklib URL-encodes the path itself; '@' must stay as is (pre-encoding gives %2540 -> 404)
            path = "/servicesNS/nobody/missioncontrol/public/v2/investigations/%s/notes" % quote(fid, safe="@")
            try:
                resp = self.service.post(path, headers=[("Content-Type", "application/json")],
                                         body=json.dumps({"title": title, "content": content}))
                body = json.loads(resp.body.read().decode("utf-8") or "{}")
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
