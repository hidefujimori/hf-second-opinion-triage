#!/usr/bin/env python
"""| jevmigrate  —  copy settings and data from the old app TA-jev-triage (before 0.11.0) into this app.

The app was renamed in 0.11.0 (TA-jev-triage -> second_opinion_triage). Splunk treats it as a new app, so its
settings, API keys and KV store data start empty. Run this once, as an admin, while the old app is still installed
and enabled, then disable or remove the old app:

  | jevmigrate                 (action=plan: show what would be copied, change nothing)
  | jevmigrate action=run      (copy)

Copied: jev_triage.conf values that differ from this app's, the macros jev_cloudtrail / jev_endpoint / jev_findings,
the stored API keys (names only are shown), the KV collections jev_triage_latest, jev_usage, jev_prompt_versions and
jev_prompt_state, and whether the two scheduled searches are enabled. Not copied: the lookup jev_eval_set.csv
(upload it again) and the queue of pending response-action requests. Index jev_triage is shared by both apps.
Running it again updates the copies (KV records are upserted by key); nothing is deleted.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib.searchcommands import Configuration, GeneratingCommand, Option, dispatch, validators  # noqa: E402

from jev_triage import settings  # noqa: E402

NEW = settings.APP
OLD_DEFAULT = "TA-jev-triage"
COLLECTIONS = ("jev_triage_latest", "jev_usage", "jev_prompt_versions", "jev_prompt_state")
MACROS = ("jev_cloudtrail", "jev_endpoint", "jev_findings")
SAVED = ("Jev Triage - Untriaged Findings", "Jev Triage - Response Queue")
KEY_READ = "admin,sc_admin,jev_triage_user"
KEY_WRITE = "admin,sc_admin"


def _q(s):
    """splunklib URL-encodes the path itself: pass names as they are (encoding here would double-encode)."""
    return s


@Configuration(distributed=False)
class JevMigrateCommand(GeneratingCommand):
    action = Option(require=False, default="plan", validate=validators.Set("plan", "run"))
    source = Option(require=False, default=OLD_DEFAULT)

    def _get(self, path, **kw):
        kw.setdefault("output_mode", "json")
        resp = self.service.get(path, **kw)
        return json.loads(resp.body.read().decode("utf-8") or "null")

    def _entries(self, path, **kw):
        return (self._get(path, count=0, **kw) or {}).get("entry") or []

    def _row(self, item, status, detail="", count=""):
        return {"item": item, "status": status, "detail": detail, "count": count}

    # ----- pieces -----
    def _conf(self, run):
        old = {e["name"]: e["content"] for e in self._entries("/servicesNS/nobody/%s/configs/conf-jev_triage" % self.source)}
        new = {e["name"]: e["content"] for e in self._entries("/servicesNS/nobody/%s/configs/conf-jev_triage" % NEW)}
        rows = []
        for stanza, content in sorted(old.items()):
            diff = {k: v for k, v in content.items()
                    if not k.startswith("eai:") and k not in ("disabled",) and v is not None
                    and str(v) != str((new.get(stanza) or {}).get(k))}
            if not diff:
                continue
            if run:
                self.service.post("/servicesNS/nobody/%s/configs/conf-jev_triage/%s" % (NEW, _q(stanza)), **diff)
            shown = ", ".join("%s=%s" % (k, "***" if k in ("endpoint", "proxy") else v) for k, v in sorted(diff.items()))
            rows.append(self._row("setting [%s]" % stanza, "copied" if run else "to copy", shown[:300], len(diff)))
        return rows or [self._row("settings", "same", "jev_triage.conf values are the same")]

    def _macros(self, run):
        rows = []
        for m in MACROS:
            try:
                old = self._entries("/servicesNS/nobody/%s/configs/conf-macros/%s" % (self.source, m))[0]["content"]["definition"]
                new = self._entries("/servicesNS/nobody/%s/configs/conf-macros/%s" % (NEW, m))[0]["content"]["definition"]
            except Exception as e:
                rows.append(self._row("macro %s" % m, "error", str(e)[:200]))
                continue
            if old == new:
                rows.append(self._row("macro %s" % m, "same", ""))
                continue
            if run:
                self.service.post("/servicesNS/nobody/%s/configs/conf-macros/%s" % (NEW, m), definition=old)
            rows.append(self._row("macro %s" % m, "copied" if run else "to copy", old[:200]))
        return rows

    def _keys(self, run):
        rows = []
        old = [e for e in self._entries("/servicesNS/nobody/%s/storage/passwords" % self.source)
               if (e["content"].get("realm") or "") == self.source]
        have = {e["content"].get("username") for e in self._entries("/servicesNS/nobody/%s/storage/passwords" % NEW)
                if (e["content"].get("realm") or "") == NEW}
        for e in old:
            name = e["content"].get("username")
            if name in have:
                rows.append(self._row("API key %s" % name, "kept", "already set in this app"))
                continue
            if run:
                self.service.post("/servicesNS/nobody/%s/storage/passwords" % NEW, name=name, realm=NEW,
                                  password=e["content"].get("clear_password") or "")
                try:
                    # a new credential is owned by the user who created it: change its ACL in that user's namespace
                    owner = getattr(self._metadata.searchinfo, "username", "") or "nobody"
                    self.service.post("/servicesNS/%s/%s/configs/conf-passwords/%s/acl" % (owner, NEW, "credential:%s:%s:" % (NEW, name)),
                                      sharing="app", owner="nobody", **{"perms.read": KEY_READ, "perms.write": KEY_WRITE})
                except Exception as x:
                    rows.append(self._row("API key %s" % name, "copied", "ACL not set: %s" % str(x)[:150]))
                    continue
            rows.append(self._row("API key %s" % name, "copied" if run else "to copy", "value never shown"))
        return rows or [self._row("API keys", "none", "no keys in the old app")]

    def _kv(self, run):
        rows = []
        for c in COLLECTIONS:
            base_old = "/servicesNS/nobody/%s/storage/collections/data/%s" % (self.source, c)
            try:
                docs, skip = [], 0
                while True:
                    part = self._get(base_old, limit=1000, skip=skip) or []
                    docs.extend(part)
                    if len(part) < 1000:
                        break
                    skip += 1000
            except Exception as e:
                rows.append(self._row("KV %s" % c, "error", str(e)[:200]))
                continue
            for d in docs:
                d.pop("_user", None)
            if run and docs:
                path = "/servicesNS/nobody/%s/storage/collections/data/%s/batch_save" % (NEW, c)
                for i in range(0, len(docs), 500):
                    self.service.post(path, headers=[("Content-Type", "application/json")], body=json.dumps(docs[i:i + 500]))
            rows.append(self._row("KV %s" % c, ("copied" if run else "to copy") if docs else "empty", "", len(docs)))
        return rows

    def _saved(self, run):
        rows = []
        for name in SAVED:
            try:
                old = self._entries("/servicesNS/nobody/%s/saved/searches/%s" % (self.source, _q(name)))[0]["content"]
                new = self._entries("/servicesNS/nobody/%s/saved/searches/%s" % (NEW, _q(name)))[0]["content"]
            except Exception as e:
                rows.append(self._row("scheduled search %s" % name, "error", str(e)[:200]))
                continue
            od, nd = str(old.get("disabled")) in ("1", "true", "True"), str(new.get("disabled")) in ("1", "true", "True")
            if od == nd:
                rows.append(self._row("scheduled search %s" % name, "same", "disabled" if od else "enabled"))
                continue
            if run:
                self.service.post("/servicesNS/nobody/%s/saved/searches/%s/%s" % (NEW, _q(name), "disable" if od else "enable"))
            rows.append(self._row("scheduled search %s" % name, "copied" if run else "to copy", "disabled" if od else "enabled"))
        return rows

    def generate(self):
        if not settings.can_admin(self.service):
            raise RuntimeError("jevmigrate is for admins (edit_storage_passwords or admin_all_objects)")
        try:
            app = self._entries("/services/apps/local/%s" % _q(self.source))[0]["content"]
        except Exception:
            yield self._row("old app", "not found", "%s is not installed: nothing to copy" % self.source)
            return
        run = self.action == "run"
        if str(app.get("disabled")).lower() in ("1", "true"):
            yield self._row("old app", "disabled",
                            "%s %s is disabled: enable it (Apps > Manage Apps > Enable), run this again, then disable it"
                            % (self.source, app.get("version")))
            return
        yield self._row("old app", "found", "%s %s" % (self.source, app.get("version")))
        for part in (self._conf, self._macros, self._keys, self._kv, self._saved):
            try:
                for r in part(run):
                    yield r
            except Exception as e:
                yield self._row(part.__name__.strip("_"), "error", str(e)[:300])
        yield self._row("lookup jev_eval_set.csv", "manual", "not copied: upload it again in this app if you use it")
        if run:
            yield self._row("next", "todo", "disable or remove %s, then restart Splunk; check Setup and run a connection test" % self.source,
                            time.strftime("%Y-%m-%d %H:%M"))


dispatch(JevMigrateCommand, sys.argv, sys.stdin, sys.stdout, __name__)
