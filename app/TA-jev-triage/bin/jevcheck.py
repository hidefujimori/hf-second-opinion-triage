#!/usr/bin/env python
"""| jevcheck  —  connection test for the Setup page. Never outputs secrets.

Options: target=jev|llm|all (default all)
Output: one row per target: target, key_set, status (ok|error|not_configured), detail, latency_ms
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib.searchcommands import Configuration, GeneratingCommand, Option, dispatch, validators  # noqa: E402

from jev_triage import __version__, jev_client, llm, settings  # noqa: E402

PING_STATE = {"alert": "connectivity test from the Splunk app TA-jev-triage", "note": "no security event"}
PING_Q = {"is_test": {"type": "noul", "instructions": "This message is a connectivity test."}}


def _short(e):
    return str(e).replace("\n", " ")[:300]


@Configuration(distributed=False)
class JevCheckCommand(GeneratingCommand):
    target = Option(require=False, default="all", validate=validators.Set("jev", "llm", "all"))

    def _jev(self):
        row = {"target": "jev", "version": __version__}
        sec = settings.secrets(self.service)
        s = settings.stanza(self.service, "jev", {"model": "jev-1.13.0", "timeout": "30", "proxy": ""})
        row["key_set"] = "yes" if sec.get(settings.JEV_SECRET) else "no"
        row["model"] = s["model"]
        if row["key_set"] == "no":
            row.update(status="not_configured", detail="Jev API key is not set")
            return row
        t0 = time.time()
        try:
            out = jev_client.call(sec[settings.JEV_SECRET], s["model"], PING_STATE, PING_Q,
                                  timeout=int(s["timeout"]), retries=1, proxy=s["proxy"] or None)
            ok = "is_test" in (out.get("answers") or {})
            row.update(status="ok" if ok else "error",
                       detail="Jev answered" if ok else "unexpected response")
        except Exception as e:
            row.update(status="error", detail=_short(e))
        row["latency_ms"] = int((time.time() - t0) * 1000)
        return row

    def _llm(self):
        cfg = settings.llm_cfg(self.service, self.logger)
        row = {"target": "llm", "version": __version__, "model": "%s / %s" % (cfg.get("provider"), cfg.get("model") or "-")}
        if (cfg.get("provider") or "").lower() == "bedrock":
            row["key_set"] = "yes" if cfg["aws_access_key_id"] and cfg["aws_secret_access_key"] else "no"
        else:
            row["key_set"] = "yes" if cfg["api_key"] else "no"
        if row["key_set"] == "no" or not cfg.get("model"):
            row.update(status="not_configured",
                       detail="LLM credential is not set" if row["key_set"] == "no" else "LLM model is not set")
            return row
        cfg["max_tokens"] = "40"
        t0 = time.time()
        try:
            text = llm.complete(cfg, "You are a connectivity test. Reply with the single word OK.", "ping", retries=1)
            row.update(status="ok", detail="LLM answered: %s" % text[:40])
        except Exception as e:
            row.update(status="error", detail=_short(e))
        row["latency_ms"] = int((time.time() - t0) * 1000)
        return row

    def generate(self):
        if self.target in ("jev", "all"):
            yield self._jev()
        if self.target in ("llm", "all"):
            yield self._llm()


dispatch(JevCheckCommand, sys.argv, sys.stdin, sys.stdout, __name__)
