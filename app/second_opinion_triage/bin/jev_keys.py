"""REST endpoint /services/second_opinion_triage/keys: hands this app's own keys to its search commands.

Analysts used to need list_storage_passwords to read the Jev / LLM keys, but that capability also lets a user read
every credential whose ACL is read=* (other apps', the system's). This endpoint runs with the system session
(restmap.conf passSystemAuth) and returns only this app's keys, to users with the capability jev_triage_run
(role jev_triage_user). The evaluation keys (alt_api_key, alt_api_key_2) are returned to admins only.
"""
import json
import sys

from splunk.persistconn.application import PersistentServerConnectionApplication
import splunk.rest as rest

APP = "second_opinion_triage"
FOR_USERS = ("typesafe_api_key", "llm_api_key", "aws_access_key_id", "aws_secret_access_key")
FOR_ADMINS = ("alt_api_key", "alt_api_key_2")


def _get(path, token, **query):
    q = dict(query, output_mode="json")
    resp, body = rest.simpleRequest(path, sessionKey=token, getargs=q, method="GET", raiseAllErrors=True)
    return json.loads(body)


def _is_admin(user_token):
    try:
        caps = _get("/services/authentication/current-context", user_token)["entry"][0]["content"].get("capabilities") or []
        return "admin_all_objects" in caps or "edit_storage_passwords" in caps
    except Exception:
        return False


def _keys(system_token):
    out = {}
    entries = _get("/servicesNS/nobody/%s/storage/passwords" % APP, system_token, count=0).get("entry", [])
    for e in sorted(entries, key=lambda x: 1 if ((x.get("content") or {}).get("realm") or "") == APP else 0):
        c = e.get("content") or {}
        realm = c.get("realm") or ""
        if realm == APP or (realm == "" and (e.get("acl") or {}).get("app") == APP):
            out[c.get("username")] = c.get("clear_password")
    return out


class KeysHandler(PersistentServerConnectionApplication):
    def __init__(self, command_line, command_arg):
        PersistentServerConnectionApplication.__init__(self)

    def handle(self, in_string):
        try:
            req = json.loads(in_string)
            system_token = req.get("system_authtoken")
            user_token = (req.get("session") or {}).get("authtoken")
            if not system_token or not user_token:
                return {"status": 500, "payload": {"error": "no session"}}
            keys = _keys(system_token)
            names = FOR_USERS + (FOR_ADMINS if _is_admin(user_token) else ())
            return {"status": 200, "payload": {"keys": {k: keys[k] for k in names if keys.get(k)}}}
        except Exception as e:  # never echo the request (it carries tokens)
            sys.stderr.write("jev_keys: %s\n" % type(e).__name__)
            return {"status": 500, "payload": {"error": "keys not read: %s" % type(e).__name__}}
