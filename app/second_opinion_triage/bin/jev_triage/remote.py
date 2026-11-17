"""Search-command side of /services/second_opinion_triage/call (see bin/jev_call.py).

Users who cannot read the stored keys (analysts: role jev_triage_user) ask the app's endpoint to call the decision
model or the LLM; the keys stay inside splunkd. Admins call the providers directly (also needed for evaluation
options such as endpoint= or usekey=)."""
import json

PATH = "/services/second_opinion_triage/call"


class RemoteError(Exception):
    pass


def _post(service, payload):
    try:
        resp = service.post(PATH, body=json.dumps(payload), headers=[("Content-Type", "application/json")])
        return json.loads(resp.body.read().decode("utf-8"))
    except Exception as e:
        body = getattr(e, "body", None)
        msg = None
        try:
            raw = body.read() if hasattr(body, "read") else body
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", "replace")
            data = json.loads(raw) if raw else {}
            msg = data.get("error") or ((data.get("messages") or [{}])[0].get("text"))
        except Exception:
            pass
        status = getattr(e, "status", "")
        raise RemoteError("app endpoint%s: %s" % (" HTTP %s" % status if status else "", msg or str(e)[:300]))


def jev(service, state, questions, timeout=30, retries=4):
    out = _post(service, {"kind": "jev", "state": state, "questions": questions, "timeout": timeout, "retries": retries})
    if "answers" not in out:
        raise RemoteError("app endpoint: no answers")
    return out


def llm(service, system, user, max_tokens=None, retries=2):
    out = _post(service, {"kind": "llm", "system": system, "user": user, "max_tokens": max_tokens, "retries": retries})
    return (out.get("text") or "").strip()


def complete(service, cfg, system, user, retries=2):
    """LLM answer: directly when this user could read the LLM key (cfg carries it), otherwise through the endpoint."""
    if cfg.get("api_key") or (cfg.get("aws_access_key_id") and cfg.get("aws_secret_access_key")):
        from jev_triage import llm as _llm
        return _llm.complete(cfg, system, user, retries=retries)
    return llm(service, system, user, max_tokens=cfg.get("max_tokens"), retries=retries)
