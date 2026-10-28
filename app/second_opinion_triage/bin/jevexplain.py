#!/usr/bin/env python
"""| jevexplain  —  plain-language explanation of a Jev triage result, written by an LLM.

Input: rows from the jev_triage_latest KV store (needs jev_state, jev_answers, jev_disposition ...).
Output: jev_explanation, jev_explain_status, jev_explain_model, jev_explain_lang, jev_explain_time, jev_explain_for.
Typical use (dashboard Explain button):
  | inputlookup jev_triage_latest where event_id="<id>" | jevexplain | outputlookup append=true key_field=_key jev_triage_latest
Options: force=true (ignore cached explanation), lang=en|ja (default from jev_triage.conf [llm] language)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib.searchcommands import Configuration, Option, StreamingCommand, dispatch, validators  # noqa: E402

from jev_triage import llm, persist, settings, usage  # noqa: E402

APP = "second_opinion_triage"
WORDS = {"en": "120 words", "ja": "300字"}


@Configuration(local=True)
class JevExplainCommand(StreamingCommand):
    force = Option(require=False, validate=validators.Boolean(), default=False)
    lang = Option(require=False, default=None)
    persist = Option(require=False, validate=validators.Boolean(), default=False)
    # Automatic explanations (Adaptive Response): only findings that match the rules below, and at most
    # [limits] llm_auto_daily per day. Manual use (the Explain button) is not limited.
    auto = Option(require=False, validate=validators.Boolean(), default=False)
    min_urgency = Option(require=False, default=None, validate=validators.Set("low", "medium", "high", "critical"))
    dispositions = Option(require=False, default=None)   # e.g. "TP,Undetermined"

    def _cfg(self):
        return settings.llm_cfg(self.service, self.logger)

    def _prompt(self, lang, rec):
        path = os.path.join(HERE, "jev_triage", "prompts", "explain_%s.txt" % lang)
        if not os.path.exists(path):
            path = os.path.join(HERE, "jev_triage", "prompts", "explain_en.txt")
        with open(path, encoding="utf-8") as fh:
            system = fh.read().replace("{words}", WORDS.get(lang, "120"))
        try:
            st = json.loads(rec.get("jev_state") or "{}")
        except ValueError:
            st = {}
        try:
            ans = json.loads(rec.get("jev_answers") or "{}")
        except ValueError:
            ans = {}
        probs = {k: round(v, 2) for k, v in (ans.get("disposition", {}).get("probabilities") or {}).items()}
        suggestion = {
            "disposition": rec.get("jev_disposition"), "disposition_confidence": rec.get("jev_disposition_confidence"),
            "disposition_probabilities": probs, "urgency": rec.get("jev_urgency"),
            "escalate_probability": rec.get("jev_escalate"), "expected_admin_activity_probability": rec.get("jev_admin_activity"),
            "detection_logic_mismatch_probability": rec.get("jev_logic_mismatch"), "attack_tactic": rec.get("jev_tactic"),
            "policy_notes": rec.get("jev_policy") or "none",
        }
        user = ("<alert_data>\n" + json.dumps({"alert": st, "jev_suggestion": suggestion}, ensure_ascii=False, indent=1)
                + "\n</alert_data>\n\nExplain the Jev suggestion for this alert.")
        return system, user

    URG = ["low", "medium", "high", "critical"]

    def _rule_skip(self, rec):
        """Reason not to explain this finding automatically, or None."""
        if self.min_urgency and (rec.get("jev_urgency") or "low") in self.URG \
                and self.URG.index(rec.get("jev_urgency") or "low") < self.URG.index(self.min_urgency):
            return "skipped (urgency below %s)" % self.min_urgency
        if self.dispositions:
            allowed = [d.strip() for d in self.dispositions.split(",") if d.strip()]
            if allowed and rec.get("jev_disposition") not in allowed:
                return "skipped (disposition not in %s)" % ",".join(allowed)
        return None

    def _budget(self):
        """None if this explanation may run, else the reason it may not."""
        try:
            if self.auto:
                lim = usage.limits(settings.stanza(self.service, "limits", settings.LIMIT_DEFAULTS))["llm_auto"]
                if not usage.take(self.service, "llm_auto", lim):
                    return "skipped (daily limit %s/day)" % lim
            else:
                usage.take(self.service, "llm_manual")
        except Exception as e:   # counting must never stop the explanation
            self.logger.warning("usage counter not updated: %s", e)
        return None

    def stream(self, records):
        return _persisting(self, self._stream(records))

    def _stream(self, records):
        cfg = self._cfg()
        lang = (self.lang or cfg.get("language") or "en").lower()
        for rec in records:
            out = dict(rec)
            cached = rec.get("jev_explanation") and rec.get("jev_explain_for") == rec.get("jev_time") and rec.get("jev_explain_lang") == lang
            if cached and not self.force:
                out["jev_explain_status"] = "cached"
                yield out
                continue
            if rec.get("jev_status") != "ok":
                out["jev_explain_status"] = "skipped (no Jev result)"
                yield out
                continue
            reason = self._rule_skip(rec) or self._budget()
            if reason:
                out["jev_explain_status"] = reason
                yield out
                continue
            try:
                system, user = self._prompt(lang, rec)
                t0 = time.time()
                out["jev_explanation"] = llm.complete(cfg, system, user)
                out["jev_explain_status"] = "ok"
                out["jev_explain_ms"] = int((time.time() - t0) * 1000)
                out["jev_explain_model"] = "%s:%s" % (cfg["provider"], cfg["model"])
                out["jev_explain_lang"] = lang
                out["jev_explain_time"] = int(time.time())
                out["jev_explain_for"] = rec.get("jev_time")
            except Exception as e:
                out["jev_explain_status"] = "error: %s" % str(e)[:300]
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


dispatch(JevExplainCommand, sys.argv, sys.stdin, sys.stdout, __name__)
