#!/usr/bin/env python
"""| jevtranslate id=<finding event_id> [scope=short|full] [lang=ja] [force=true]
Translate the ES AI SOC Analyst texts of a finding with the app's LLM (1.1).

scope=short: summary and justification; scope=full: also evidence, details and every check the agent ran.
The translation is stored in the KV collection jev_ai_translations (one per finding and language) and reused until
ES AI writes a new analysis; a full translation also serves a short request. It is never sent to the decision model.
Counted as a manual LLM use. Output: one row with status, scope, ai_time, model, ms and translation (JSON).
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib.searchcommands import Configuration, GeneratingCommand, Option, dispatch, validators  # noqa: E402

from jev_triage import guide, remote, settings, translate, usage  # noqa: E402


@Configuration(distributed=False)
class JevTranslateCommand(GeneratingCommand):
    id = Option(require=True)
    scope = Option(require=False, default="short", validate=validators.Set("short", "full"))
    lang = Option(require=False, default="ja", validate=validators.Set(*sorted(translate.LANGS)))
    force = Option(require=False, validate=validators.Boolean(), default=False)

    def generate(self):
        out = {"event_id": self.id, "lang": self.lang, "scope": self.scope}
        rec, _ = guide.ai_record(self.service, self.id)
        if not rec:
            out["status"] = "skipped (no ES AI result)"
            yield out
            return
        ai_time = str(rec.get("create_time") or "")
        old = translate.get(self.service, self.id, self.lang)
        covers = old.get("scope") == "full" or old.get("scope") == self.scope
        if old and str(old.get("ai_time")) == ai_time and covers and not self.force:
            out.update(status="cached", scope=old.get("scope"), ai_time=ai_time, model=old.get("model", ""),
                       translation=old.get("parts", "{}"), translated_by=old.get("user", ""), translated_at=old.get("time", ""))
            yield out
            return
        items = translate.parts(rec, self.scope)
        if not items:
            out["status"] = "skipped (nothing to translate)"
            yield out
            return
        cfg = settings.llm_cfg(self.service, self.logger)
        cfg = dict(cfg, max_tokens="2500")
        try:
            usage.take(self.service, "llm_manual")
        except Exception as e:   # counting must never stop the translation
            self.logger.warning("usage counter not updated: %s", e)
        t0 = time.time()

        def one(group):
            system, user = translate.prompt(self.lang, group)
            return translate.parse(remote.complete(self.service, cfg, system, user), group)

        got, errors = {}, []
        pieces = translate.split_long(items)
        for attempt in range(2):   # a second pass for pieces the model left out or that failed (busy LLM)
            todo = {k: v for k, v in pieces.items() if k not in got}
            if not todo:
                break
            groups = translate.chunks(todo)
            with ThreadPoolExecutor(max_workers=min(4, len(groups))) as pool:   # parts in parallel, each a short call
                for f in [pool.submit(one, g) for g in groups]:
                    try:
                        got.update(f.result())
                    except Exception as e:
                        errors.append(str(e)[:200])
        missing = [k for k in pieces if k not in got]
        if missing:
            out["missing"] = ",".join(missing)
            out["errors"] = " | ".join(errors[-3:])
        got = translate.join(got, pieces)
        got = {k: got[k] for k in items if k in got}   # display order
        if not got:
            out["status"] = "error: %s" % (errors[0] if errors else "the LLM answer could not be read")
            yield out
            return
        user_name = getattr(self._metadata.searchinfo, "username", "") or ""
        doc = {"_key": translate.key(self.id, self.lang), "event_id": self.id, "lang": self.lang, "scope": self.scope,
               "ai_time": ai_time, "parts": json.dumps(got, ensure_ascii=False),
               "model": "%s:%s" % (cfg.get("provider"), cfg.get("model")), "user": user_name, "time": int(time.time())}
        try:
            translate.save(self.service, doc)
            out["status"] = "ok" if not missing and len(got) == len(items) else \
                "ok (%d of %d parts translated; the rest is in English)" % (len(pieces) - len(missing), len(pieces))
        except Exception as e:
            out["status"] = "ok (not stored: %s)" % str(e)[:200]
        out.update(ai_time=ai_time, model=doc["model"], translation=doc["parts"], ms=int((time.time() - t0) * 1000),
                   translated_by=user_name, translated_at=doc["time"])
        yield out


dispatch(JevTranslateCommand, sys.argv, sys.stdin, sys.stdout, __name__)
