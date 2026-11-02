"""Shared settings and secret loading (jev_triage.conf + storage/passwords, realm second_opinion_triage)."""
APP = "second_opinion_triage"
JEV_SECRET = "typesafe_api_key"
ALT_SECRET = "alt_api_key"   # evaluation of another decision model (jevtriage usekey=alt), e.g. Cloudflare
ALT2_SECRET = "alt_api_key_2"   # a second one (usekey=alt2), e.g. OpenAI
LLM_SECRETS = ("llm_api_key", "aws_access_key_id", "aws_secret_access_key")

LIMIT_DEFAULTS = {"jev_auto_daily": "", "llm_auto_daily": "100"}

LLM_DEFAULTS = {"provider": "anthropic", "model": "", "endpoint": "", "region": "", "max_tokens": "600",
                "timeout": "60", "language": "en", "proxy": "", "thinking_level": ""}


def stanza(service, name, defaults=None, logger=None):
    out = dict(defaults or {})
    try:
        for k, v in service.confs["jev_triage"][name].content.items():
            if not k.startswith("eai:") and v is not None:
                out[k] = v
    except Exception as e:
        if logger:
            logger.warning("[%s] stanza not read: %s", name, e)
    return out


def secrets(service):
    """username -> clear password for this app's realm.

    The keys are shared at app level, so a search started from another app (e.g. Search & Reporting) does not see
    them in its own namespace: read them in this app's namespace whatever app the search runs in."""
    import json
    try:
        resp = service.get("storage/passwords", owner="-", app=APP, count=0, output_mode="json")
        entries = json.loads(resp.body.read().decode("utf-8")).get("entry", [])
    except Exception:
        return {p.username: p.clear_password for p in service.storage_passwords if (p.realm or "") in (APP, "")}
    out = {}
    # entries without a realm only when they belong to this app; this app's realm wins
    for e in sorted(entries, key=lambda x: 1 if ((x.get("content") or {}).get("realm") or "") == APP else 0):
        c = e.get("content") or {}
        realm = c.get("realm") or ""
        if realm == APP or (realm == "" and ((e.get("acl") or {}).get("app") == APP)):
            out[c.get("username")] = c.get("clear_password")
    return out


def jev_api_key(service, required=True):
    """The key stored for [jev]. Not required for a local System One server (e.g. llama.cpp without --api-key)."""
    key = secrets(service).get(JEV_SECRET)
    if not key and required:
        raise RuntimeError("Jev API key not set: open Second Opinion Triage > Setup (or storage/passwords realm=%s name=%s)"
                           % (APP, JEV_SECRET))
    return key


def llm_cfg(service, logger=None):
    cfg = stanza(service, "llm", LLM_DEFAULTS, logger)
    sec = secrets(service)
    cfg["api_key"] = sec.get("llm_api_key", "")
    cfg["aws_access_key_id"] = sec.get("aws_access_key_id", "")
    cfg["aws_secret_access_key"] = sec.get("aws_secret_access_key", "")
    cfg["proxy"] = cfg.get("proxy") or None
    return cfg


def can_admin(service):
    """The current user may change the app's settings (same rule as the Setup page)."""
    try:
        import json
        resp = service.get("/services/authentication/current-context", output_mode="json")
        caps = json.loads(resp.body.read().decode("utf-8"))["entry"][0]["content"].get("capabilities") or []
        return "admin_all_objects" in caps or "edit_storage_passwords" in caps
    except Exception:
        return False
