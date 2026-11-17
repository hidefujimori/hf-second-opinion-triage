"""REST endpoint /services/second_opinion_triage/call: calls the decision model and the LLM for this app's
search commands, so that analysts never receive the API keys.

The endpoint runs with the system session (restmap.conf passSystemAuth) and is allowed to users with the capability
jev_triage_run (role jev_triage_user). It reads the keys and the connection settings ([jev], [llm] in
jev_triage.conf) itself; the caller sends only what to ask (state and questions, or prompts) and gets back the
answers. The caller cannot choose the endpoint, model, proxy or key: evaluation of other models stays admin-only
and runs directly in the search commands.

Payload (JSON):
  {"kind": "jev", "state": {...}, "questions": {...}, "timeout": 30, "retries": 4}
  {"kind": "llm", "system": "...", "user": "...", "max_tokens": 600, "retries": 2}
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunk.persistconn.application import PersistentServerConnectionApplication  # noqa: E402
import splunk.rest as rest  # noqa: E402

from jev_triage import jev_client, llm  # noqa: E402
from jev_triage.settings import APP, JEV_SECRET, LLM_DEFAULTS  # noqa: E402

JEV_DEFAULTS = {"model": "jev-1.13.0", "timeout": "30", "proxy": "", "endpoint": "", "request_extra": "",
                "confidence_field": ""}


def _get(path, token, **query):
    q = dict(query, output_mode="json")
    resp, body = rest.simpleRequest(path, sessionKey=token, getargs=q, method="GET", raiseAllErrors=True)
    return json.loads(body)


def _keys(system_token):
    out = {}
    entries = _get("/servicesNS/nobody/%s/storage/passwords" % APP, system_token, count=0).get("entry", [])
    for e in sorted(entries, key=lambda x: 1 if ((x.get("content") or {}).get("realm") or "") == APP else 0):
        c = e.get("content") or {}
        realm = c.get("realm") or ""
        if realm == APP or (realm == "" and (e.get("acl") or {}).get("app") == APP):
            out[c.get("username")] = c.get("clear_password")
    return out


def _conf(system_token, stanza, defaults):
    out = dict(defaults)
    try:
        c = _get("/servicesNS/nobody/%s/configs/conf-jev_triage/%s" % (APP, stanza), system_token)["entry"][0]["content"]
        out.update({k: v for k, v in c.items() if not k.startswith("eai:") and v is not None and k in defaults})
    except Exception:
        pass
    return out


def _int(v, default, lo, hi):
    try:
        return max(lo, min(hi, int(float(v))))
    except (TypeError, ValueError):
        return default


def _jev(p, token):
    s = _conf(token, "jev", JEV_DEFAULTS)
    key = _keys(token).get(JEV_SECRET)
    endpoint = s["endpoint"] or None
    if not key and jev_client.is_typesafe(endpoint):
        return 400, {"error": "Jev API key not set: ask an admin to open Second Opinion Triage > Setup"}
    extra = json.loads(s["request_extra"]) if s["request_extra"] else None
    out = jev_client.call(key, s["model"], p["state"], p["questions"],
                          timeout=_int(p.get("timeout"), _int(s["timeout"], 30, 1, 600), 1, 600),
                          retries=_int(p.get("retries"), 4, 0, 4), proxy=s["proxy"] or None, endpoint=endpoint,
                          extra=extra, confidence_field=s["confidence_field"] or None)
    return 200, {"answers": out.get("answers"), "latency_ms": out.get("latency_ms"), "usage": out.get("usage"),
                 "model": s["model"]}


def _llm(p, token):
    cfg = _conf(token, "llm", LLM_DEFAULTS)
    keys = _keys(token)
    cfg["api_key"] = keys.get("llm_api_key", "")
    cfg["aws_access_key_id"] = keys.get("aws_access_key_id", "")
    cfg["aws_secret_access_key"] = keys.get("aws_secret_access_key", "")
    cfg["proxy"] = cfg.get("proxy") or None
    cfg["max_tokens"] = str(_int(p.get("max_tokens"), _int(cfg.get("max_tokens"), 600, 1, 4000), 1, 4000))
    text = llm.complete(cfg, str(p.get("system") or ""), str(p.get("user") or ""), retries=_int(p.get("retries"), 2, 0, 2))
    return 200, {"text": text, "model": "%s:%s" % (cfg.get("provider"), cfg.get("model"))}


class CallHandler(PersistentServerConnectionApplication):
    def __init__(self, command_line, command_arg):
        PersistentServerConnectionApplication.__init__(self)

    def handle(self, in_string):
        try:
            req = json.loads(in_string)
            token = req.get("system_authtoken")
            if not token or not (req.get("session") or {}).get("authtoken"):
                return {"status": 500, "payload": {"error": "no session"}}
            if (req.get("method") or "POST").upper() != "POST":
                return {"status": 405, "payload": {"error": "use POST"}}
            p = json.loads(req.get("payload") or "{}")
            kind = p.get("kind")
            if kind == "jev":
                if not isinstance(p.get("state"), (dict, str)) or not isinstance(p.get("questions"), dict):
                    return {"status": 400, "payload": {"error": "state and questions are required"}}
                status, body = _jev(p, token)
            elif kind == "llm":
                status, body = _llm(p, token)
            else:
                return {"status": 400, "payload": {"error": "kind must be jev or llm"}}
            return {"status": status, "payload": body}
        except (jev_client.JevError, llm.LLMError) as e:   # the provider's answer, never the key or the request
            return {"status": 502, "payload": {"error": str(e)[:500]}}
        except Exception as e:  # never echo the request (it carries tokens)
            sys.stderr.write("jev_call: %s\n" % type(e).__name__)
            return {"status": 500, "payload": {"error": "call failed: %s" % type(e).__name__}}
