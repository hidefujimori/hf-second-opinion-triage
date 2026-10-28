#!/usr/bin/env python
"""| jevguide  —  decision guide: compare the Jev result with the ES AI SOC Analyst result and let an LLM
explain the comparison (why they differ, how to decide). Neither suggestion is changed.

Input: rows from the jev_triage_latest KV store. Reads the ES AI result itself (KV missioncontrol/mc_ai_analysis,
ES API public/v2/findings/{id}). Output: jev_guide, jev_guide_status, jev_guide_key, jev_guide_model, jev_guide_lang,
jev_guide_time, jev_guide_for (jev_time), jev_guide_ai_time (create_time of the ES AI result used), jev_guide_ms.
Typical use (dashboard button):
  | inputlookup jev_triage_latest where event_id="<id>" | jevguide persist=true lang=ja
Options: force=true (ignore a cached guide), lang=en|ja, persist=true
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib.searchcommands import Configuration, Option, StreamingCommand, dispatch, validators  # noqa: E402

from jev_triage import guide, llm, persist, settings, usage  # noqa: E402

WORDS = {"en": "180 words", "ja": "450字"}


@Configuration(local=True)
class JevGuideCommand(StreamingCommand):
    force = Option(require=False, validate=validators.Boolean(), default=False)
    lang = Option(require=False, default=None)
    persist = Option(require=False, validate=validators.Boolean(), default=False)

    def _system(self, lang):
        path = os.path.join(HERE, "jev_triage", "prompts", "guide_%s.txt" % lang)
        if not os.path.exists(path):
            path = os.path.join(HERE, "jev_triage", "prompts", "guide_en.txt")
        with open(path, encoding="utf-8") as fh:
            return fh.read().replace("{words}", WORDS.get(lang, "180 words"))

    def stream(self, records):
        for out in self._stream(records):
            if self.persist and out.get("event_id"):
                try:
                    persist.save_kv(self.service, [out])
                except Exception as e:
                    out["jev_persist_error"] = str(e)[:300]
            yield out

    def _stream(self, records):
        cfg = settings.llm_cfg(self.service, self.logger)
        # the guide is longer than an explanation: give the model a little more room
        cfg = dict(cfg, max_tokens=str(max(int(float(cfg.get("max_tokens") or 600)), 1000)))
        lang = (self.lang or cfg.get("language") or "en").lower()
        for rec in records:
            out = dict(rec)
            if rec.get("jev_status") != "ok":
                out["jev_guide_status"] = "skipped (no Jev result)"
                yield out
                continue
            arec, label = guide.ai_record(self.service, rec.get("event_id") or "")
            if not arec and not label:
                out["jev_guide_status"] = "skipped (no ES AI result)"
                yield out
                continue
            ai = guide.ai_view(arec, label)
            cached = (rec.get("jev_guide") and rec.get("jev_guide_for") == rec.get("jev_time") and rec.get("jev_guide_lang") == lang
                      and str(rec.get("jev_guide_ai_time") or "") == str(ai["time"]))
            if cached and not self.force:
                out["jev_guide_status"] = "cached"
                yield out
                continue
            v = guide.verdict(rec.get("jev_disposition"), rec.get("jev_disposition_raw"), rec.get("jev_disposition_confidence"),
                              rec.get("jev_urgency"), ai["label"], ai["severity"], ai["confidence"], len(ai["failed_checks"]))
            try:
                usage.take(self.service, "llm_manual")
            except Exception as e:   # counting must never stop the guide
                self.logger.warning("usage counter not updated: %s", e)
            try:
                t0 = time.time()
                out["jev_guide"] = llm.complete(cfg, self._system(lang), guide.prompt_user(rec, ai, v))
                out["jev_guide_status"] = "ok"
                out["jev_guide_key"] = v["key"]
                out["jev_guide_ms"] = int((time.time() - t0) * 1000)
                out["jev_guide_model"] = "%s:%s" % (cfg["provider"], cfg["model"])
                out["jev_guide_lang"] = lang
                out["jev_guide_time"] = int(time.time())
                out["jev_guide_for"] = rec.get("jev_time")
                out["jev_guide_ai_time"] = ai["time"]
            except Exception as e:
                out["jev_guide_status"] = "error: %s" % str(e)[:300]
            yield out


dispatch(JevGuideCommand, sys.argv, sys.stdin, sys.stdout, __name__)
