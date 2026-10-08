"""Shared settings and secret loading (jev_triage.conf + storage/passwords, realm TA-jev-triage)."""
APP = "TA-jev-triage"
JEV_SECRET = "typesafe_api_key"
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
    """username -> clear password, only for this app's realm (or no realm)."""
    return {p.username: p.clear_password for p in service.storage_passwords if (p.realm or "") in (APP, "")}


def jev_api_key(service):
    key = secrets(service).get(JEV_SECRET)
    if not key:
        raise RuntimeError("Jev API key not set: open Jev Triage > Setup (or storage/passwords realm=%s name=%s)"
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
