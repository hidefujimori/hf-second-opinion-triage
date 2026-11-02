"""Collect context for one finding with SPL and phrase it as short English facts for Jev.

Rules learned in the PoC:
- shared resources (cloud service endpoints such as *.amazonaws.com) are never used as join keys;
- for change alerts, find the actor and pass the actor's own state (identity, cloud behaviour, workstation)."""
import fnmatch
import ipaddress
import json
import os
import re
import threading

from .state import _mv, _one, is_rollup

HERE = os.path.dirname(os.path.abspath(__file__))
KNOWN_CATEGORIES = {"employee", "contractor", "service_account", "privileged", "default", "vendor", "shared", "admin"}


def load_templates(path=None):
    with open(path or os.path.join(HERE, "enrichment_templates.json"), encoding="utf-8") as fh:
        return {k: v for k, v in json.load(fh).items() if not k.startswith("_")}


def esc(v):
    return str(v).replace("\\", "\\\\").replace('"', '\\"')


def is_ip(v):
    try:
        ipaddress.ip_address(v)
        return True
    except ValueError:
        return False


def is_url(v):
    """URLs and paths (e.g. a console sign-in URL in dest) are not hosts."""
    return "://" in str(v) or "/" in str(v)


AUTH_ACTIONS = {"success", "failure", "error"}   # CIM values of Authentication.action


GD_TYPE = re.compile(r"^[A-Za-z]+:[A-Za-z0-9]+/[A-Za-z0-9.!_-]+$")   # GuardDuty finding type, e.g. Recon:EC2/PortProbeUnprotectedPort
LOOKALIKE = str.maketrans({"0": "o", "1": "l", "i": "l", "|": "l", "3": "e", "5": "s", "$": "s", "@": "a"})


# Networks of hosting and cloud providers (rented servers, VPNs), from the ASN organisation name
HOSTING = ("digitalocean", "leaseweb", "ovh", "hetzner", "linode", "akamai connected cloud", "vultr", "choopa",
           "contabo", "m247", "scaleway", "online s.a.s", "hostinger", "ionos", "godaddy", "web2objects", "datacamp",
           "hostwinds", "colocrossing", "quadranet", "psychz", "tencent", "alibaba", "oracle", "google", "microsoft",
           "amazon")


def network_kind(org):
    o = str(org or "").lower()
    if "amazon" in o:
        return "an AWS network (AWS services, EC2 instances: the organisation's own or anyone's)"
    if any(h in o for h in HOSTING):
        return "a hosting or cloud provider network (rented servers, VPN exits)"
    return ""   # no label for other networks: "not a hosting provider" read as reassurance in earlier tests


def lookalike_key(name):
    """frothly, fr0thly and fr0thIy give the same key."""
    return str(name).lower().translate(LOOKALIKE).replace("rn", "m")


def short(host):
    return str(host).split(".")[0]


class Enricher(object):
    def __init__(self, run, templates=None, shared=("*.amazonaws.com", "*.amazon.com", "*.microsoft.com", "*.office.com", "*.google.com"), max_facts=12):
        """run(spl, earliest, latest) -> list[dict]"""
        self.run = run
        self.t = templates or load_templates()
        self.shared = [p.strip() for p in shared if p.strip()]
        self.max_facts = max_facts
        self._memo = {}          # (spl, earliest, latest) -> rows; shared by all findings in one run
        self._lock = threading.Lock()
        self._tl = threading.local()
        self.spl_calls = 0
        self.memo_hits = 0

    @property
    def errors(self):
        """Errors of the finding being collected in this thread."""
        if not hasattr(self._tl, "errors"):
            self._tl.errors = []
        return self._tl.errors

    @errors.setter
    def errors(self, value):
        self._tl.errors = value

    # ---- helpers ----
    def _q(self, name, value, earliest, latest, **extra):
        # SPL field=value matching is case-insensitive, so lower-case the value: same entity -> same cached search
        value = str(value).lower()
        sh = value if is_ip(value) else short(value)
        spl = self.t[name].replace("{value}", esc(value)).replace("{short}", esc(sh))
        for k, v in extra.items():
            spl = spl.replace("{%s}" % k, v)
        key = (spl, str(earliest), str(latest))
        with self._lock:
            if key in self._memo:
                self.memo_hits += 1
                return self._memo[key]
        try:
            rows = self.run(spl, earliest, latest)
        except Exception as e:  # enrichment must never stop triage
            self.errors.append("%s: %s" % (name, e))
            return []
        with self._lock:
            self._memo[key] = rows
            self.spl_calls += 1
        return rows

    def is_shared(self, v):
        return any(fnmatch.fnmatch(str(v).lower(), p.lower()) for p in self.shared)

    # ---- fact builders ----
    def identity_facts(self, user, who="this account"):
        rows = self._q("identity", user.lower(), "0", "now")
        if not rows:
            return ["identity: %s is not in the identity inventory" % user], []
        r = rows[0]
        vals = [_one(r.get(k)) or "" for k in ("category", "bunit", "priority")]
        cat = next((v for v in vals if v.lower() in KNOWN_CATEGORIES), None)
        dept = next((v for v in vals if v and v.lower() not in KNOWN_CATEGORIES
                     and v.lower() not in ("false", "true", "low", "medium", "high", "critical")), None)
        prio = next((v for v in vals if v.lower() in ("low", "medium", "high", "critical")), None)
        watch = str(_one(r.get("watchlist")) or "").lower() == "true"
        cat_txt = {"service_account": "service account", "employee": "regular employee"}.get((cat or "").lower(), cat or "user")
        parts = ["identity: %s is a %s" % (user, cat_txt)]
        if dept:
            parts.append("department %s" % dept)
        if prio:
            parts.append("priority %s" % prio)
        parts.append("on the watchlist" if watch else "not on the watchlist")
        facts = [", ".join(parts)]
        if (cat or "").lower() == "employee":
            facts.append("%s is a named personal account, not a default, shared, or vendor account" % user)
        return facts, _mv(r.get("hosts"))

    def cloud_origin_facts(self, user, e, l):
        """How the account came to exist and whether its name imitates another one (rare, strong signals).
        Tested and left out: console sign-ins with or without MFA, the kind of API client and the number of active days
        lowered correct verdicts (a legitimate employee without MFA, an attacker's script looking like automation)."""
        facts = []
        try:
            ef = float(e)
            e7, e1 = str(int(ef - 7 * 86400)), str(int(ef - 86400))
        except (TypeError, ValueError):
            ef, e7, e1 = None, "-8d", "-2d"
        u = str(user)
        if "/" not in u and u.lower() != "root":
            rows = self._q("cloud_user_origin", u, e7, l)
            r = rows[0] if rows else {}
            if r.get("created"):
                created = float(_one(r.get("created")))
                actor, atype, aip = _one(r.get("actor")) or "unknown", _one(r.get("actor_type")) or "", _one(r.get("actor_ip")) or ""
                who = {"AssumedRole": "a role session (%s)" % actor, "IAMUser": "the user %s" % actor,
                       "Root": "the root account"}.get(atype, actor)
                when = ("during this period" if ef is None or created >= ef
                        else "%d day(s) before this period" % max(1, int((ef - created) // 86400)))
                frm = ("from %s" % aip) if is_ip(aip) else "through an AWS service"
                facts.append("the account %s was created %s by %s %s" % (u, when, who, frm))
                ev = set(_mv(r.get("events")))
                given = []
                if "CreateLoginProfile" in ev:
                    given.append("a console password")
                if "CreateAccessKey" in ev:
                    given.append("an access key")
                if _mv(r.get("groups")):
                    given.append("membership in group %s" % ", ".join(_mv(r.get("groups"))[:3]))
                pols = _mv(r.get("policies")) + _mv(r.get("inline_policies"))
                if pols:
                    given.append("policies %s" % ", ".join(p.split("/")[-1] for p in pols[:3]))
                if given:
                    facts.append("the new account was then given %s" % ", ".join(given))
            known = self._q("cloud_users_known", "", e1, l)
            names = _mv(known[0].get("users")) if known else []
            twins = [n for n in names if n != u and n.lower() != u.lower() and lookalike_key(n) == lookalike_key(u)]
            if twins:
                facts.append("the user name %s closely resembles another account in the same logs, %s (look-alike characters such as 0/o or I/l)" % (u, twins[0]))
        return facts

    def win_actor_facts(self, user, e, l):
        """What the same person did on Windows in the period: log clearing, account deletion and creation, group changes."""
        rows = self._q("win_actor", user, e, l)
        if not rows:
            return []
        r = rows[0]
        n = lambda k: int(float(_one(r.get(k)) or 0))
        facts = []
        if n("cleared_hosts"):
            facts.append("the same user cleared the Windows Security event log on %d host(s) in this period" % n("cleared_hosts"))
        if n("deleted"):
            names = _mv(r.get("deleted_users"))
            facts.append("the same user deleted %d user account(s) on %d host(s) in this period: %s%s" % (
                n("deleted"), n("deleted_hosts"), ", ".join(names[:6]), ", ..." if len(names) > 6 else ""))
        if n("created"):
            facts.append("the same user created %d user account(s) in this period" % n("created"))
        if n("group_adds"):
            g = _mv(r.get("groups"))
            facts.append("the same user added %d account(s) to security groups%s" % (n("group_adds"), (" (" + ", ".join(g[:3]) + ")") if g else ""))
        return facts

    def guardduty_facts(self, gtype, e, l):
        rows = self._q("guardduty_detail", gtype, e, l)
        if not rows or not _one(rows[0].get("sev")):
            return []
        r = rows[0]
        facts = []
        sev = float(_one(r.get("sev")) or 0)
        facts.append("GuardDuty rated this finding severity %s (%s)" % (
            ("%g" % sev), "high" if sev >= 7 else "medium" if sev >= 4 else "low"))
        ports = _mv(r.get("ports"))
        if ports:
            facts.append("the instance was probed on port %s by %d different remote address(es); GuardDuty counted %s probes" % (
                ", ".join(ports[:3]), int(float(_one(r.get("remote_ips")) or 0)), _one(r.get("count")) or "several"))
            orgs = _mv(r.get("probe_orgs"))
            if orgs:
                facts.append("probing addresses belong to: %s" % ", ".join(orgs[:3]))
        if _mv(r.get("api_org")):
            facts.append("the API call%s came from an address of %s%s" % (
                (" " + ", ".join(_mv(r.get("api"))[:2])) if _mv(r.get("api")) else "", ", ".join(_mv(r.get("api_org"))[:2]),
                (" in " + ", ".join(_mv(r.get("api_country"))[:2])) if _mv(r.get("api_country")) else ""))
        return facts

    def cloud_user_facts(self, user, e, l):
        rows = self._q("cloud_user", user, e, l)
        if not rows or int(float(rows[0].get("count") or 0)) == 0:
            return []
        r = rows[0]
        facts = []
        # baseline: the same account in the 30 days before the detection window
        try:
            be, bl = str(int(float(e)) - 30 * 86400), str(int(float(e)))
        except (TypeError, ValueError):
            be, bl = "-37d", "-7d"
        base = self._q("cloud_user_baseline", user, be, bl)
        now_ips = set(_mv(r.get("ip_list")))
        if base and int(float(base[0].get("count") or 0)) > 0:
            new = now_ips - set(_mv(base[0].get("ip_list")))
            facts.append("compared with the previous 30 days: %s" % (
                "all source IP addresses were seen before for this account" if not new
                else "%d of %d source IP addresses are new for this account" % (len(new), len(now_ips))))
        else:
            facts.append("baseline comparison not available: no stored records for this account in the previous 30 days (this says nothing about whether the account was active)")
        ips = int(float(r.get("source_ips") or 0))
        regions = int(float(r.get("regions") or 0))
        writes = int(float(r.get("write_calls") or 0))
        if ips == 0:
            facts.append("cloud API calls came only through cloud services, not from a client IP address")
        else:
            facts.append("cloud API calls came from %s source IP address%s" % ("one fixed" if ips == 1 else str(ips) + " different", "" if ips == 1 else "es"))
        if ips and _mv(r.get("via_services")):
            facts.append("some calls were made by cloud services on the account's behalf")
        launches = int(float(r.get("launches") or 0))
        if launches >= 50:
            facts.append("the account launched a very large number of cloud instances (50 or more)")
        elif launches >= 10:
            facts.append("the account launched many cloud instances (10 or more)")
        if regions >= 10:
            facts.append("activity spans many cloud regions (10 or more)")
        mfa_writes = int(float(_one(r.get("mfa_writes")) or 0))
        mfa_own = str(_one(r.get("mfa_for_other")) or "0") != "1"
        if writes == 0:
            facts.append("calls are read-only (Describe, Get, List)")
        elif writes <= mfa_writes and mfa_own:
            facts.append("calls include changes, but the only changes were setting up MFA for its own user")
        else:
            facts.append("calls include changes, not only reads")
        iam = _mv(r.get("iam_changes"))
        if iam:
            facts.append("the account made identity changes: " + ", ".join(iam))
        grants = _mv(r.get("priv_grants"))
        if grants:
            admin = str(_one(r.get("admin_grant")) or "0") == "1"
            own = str(_one(r.get("self_grant")) or "0") == "1"
            facts.append("the account changed permissions: %s%s%s" % (
                ", ".join(grants[:4]),
                "; it attached full administrator permissions (AdministratorAccess or IAMFullAccess)" if admin else "",
                "; it gave permissions to its own user" if own else ""))
        mfa_off = _mv(r.get("mfa_removed"))
        if mfa_off:
            facts.append("the account removed or deactivated an MFA device: " + ", ".join(mfa_off))
        mfa_on = _mv(r.get("mfa_setup"))
        if mfa_on:
            try:
                after = float(_one(r.get("first_mfa"))) >= float(_one(r.get("first_login")))
            except (TypeError, ValueError):
                after = False
            facts.append("%s the account enrolled an MFA device for %s (%s), so later sign-ins can require MFA" % (
                "after signing in," if after else "during this period", "its own user" if mfa_own else "another user", ", ".join(mfa_on)))
        facts += self.ip_peer_facts(user, now_ips, e, l)
        return facts

    def ip_peer_facts(self, user, ips, e, l):
        """Is the source IP address used only by this account, or shared (office NAT, proxy, lab)?"""
        ips = sorted(ip for ip in ips if is_ip(ip))
        if not ips or len(ips) > 5:
            return []
        rows = self._q("cloud_ip_peers", user, e, l, ips=", ".join('"%s"' % esc(ip) for ip in ips))
        if not rows:
            return []
        r = rows[0]
        num = lambda k: int(float(_one(r.get(k)) or 0))
        n, logins, mfa, failed = num("other_accounts"), num("other_logins"), num("other_mfa_logins"), num("failed_logins")
        addr = "that address" if len(ips) == 1 else "those addresses"
        if n == 0:
            return []  # tested: "no other account" reads as reassurance and lowered TP confidence (0.9.11 regression run)
        fact = "%s also used the same source IP address%s in this period" % (
            "one other cloud account" if n == 1 else
            "several other cloud accounts (2 to 9)" if n < 10 else "many other cloud accounts (10 or more)",
            "" if len(ips) == 1 else "es")
        if logins:
            fact += "; %s of those accounts signed in with MFA" % ("all" if mfa >= logins else "some" if mfa else "none")
        fact += "; there were %s from %s" % ("no failed sign-ins" if failed == 0 else "failed sign-ins", addr)
        return [fact]

    def workstation_facts(self, hosts, e, l, owner_label):
        facts = []
        for h in hosts[:2]:
            rows = self._q("endpoint_powershell", h, e, l)
            if rows and int(float(rows[0].get("suspicious") or 0)) > 0:
                facts.append("%s workstation %s shows hidden, base64 encoded PowerShell launchers, a sign the workstation may be compromised" % (owner_label, h.upper()))
        return facts

    def host_facts(self, host, e, l):
        facts = []
        rows = self._q("asset", host.lower(), "0", "now")
        if rows:
            r = rows[0]
            facts.append("asset: %s in the inventory (category %s, priority %s)" % (host, _one(r.get("category")) or "unknown", _one(r.get("priority")) or "unknown"))
        else:
            facts.append("asset: %s is not in the asset inventory" % host)
        ps = self._q("endpoint_powershell", host, e, l)
        if ps and int(float(ps[0].get("total") or 0)) > 0:
            if int(float(ps[0].get("suspicious") or 0)) > 0:
                facts.append("PowerShell command lines on %s include hidden windows or base64 encoded commands" % host)
            else:
                facts.append("PowerShell command lines on %s show no encoded or hidden commands" % host)
        return facts

    def asn_org(self, ip):
        """Organisation of the address from the ASN data of Enterprise Security (threat intelligence source
        maxmind_geoip_asn_ipv4). Without that data (not ES, source disabled) say nothing and record no error."""
        if getattr(self, "_no_asn", False):
            return ""
        n = len(self.errors)
        rows = self._q("ip_asn", ip, "-1m", "now")
        if len(self.errors) > n:
            del self.errors[n:]
            self._no_asn = True
            return ""
        return _one(rows[0].get("autonomous_system_organization")) if rows else ""

    def ip_intel_facts(self, ip):
        """Threat intelligence of Enterprise Security (ip_intel: downloaded feeds, local lists, TIM exports).
        Only a match is reported; no match and no ES (no ip_intel) say nothing."""
        if getattr(self, "_no_intel", False):
            return []
        n = len(self.errors)
        rows = self._q("ip_intel", ip, "-1m", "now")
        if len(self.errors) > n:
            del self.errors[n:]
            self._no_intel = True
            return []
        r = rows[0] if rows else {}
        if not int(float(_one(r.get("count")) or 0)):
            return []
        src_names = _mv(r.get("sources"))
        desc = [d for d in _mv(r.get("descriptions")) if d][:2]
        return ["%s is listed in the threat intelligence of Enterprise Security: %s%s%s" % (
            ip, ", ".join(src_names[:3]) or "a threat list", (" (" + "; ".join(desc) + ")") if desc else "",
            (", weight %s" % _one(r.get("weight"))) if _one(r.get("weight")) else "")]

    def src_facts(self, src, domain, e, l):
        facts = []
        if is_ip(src) and ipaddress.ip_address(src).is_global:
            loc = self._q("ip_location", src, "-1m", "now")
            country = _one(loc[0].get("Country")) if loc else ""
            org = self.asn_org(src)
            facts += self.ip_intel_facts(src)
            if country or org:
                facts.append("source %s%s%s" % (
                    src, (" is located in %s" % country) if country else "",
                    ("%s belongs to %s%s" % (";" if country else "", org, (", " + network_kind(org)) if network_kind(org) else "")) if org else ""))
        if is_ip(src) and ipaddress.ip_address(src).is_private:
            if not self._q("asset", src, "0", "now"):
                facts.append("asset: source %s is not in the asset inventory" % src)
        if domain == "access":
            rows = self._q("auth_outcome", src, e, l)
            acts = {(_one(r.get("action")) or "").lower(): int(float(r.get("count") or 0)) for r in rows}
            # only when the data model uses the CIM values; e.g. action="ConsoleLogin" says nothing about the outcome
            if acts and set(acts) & AUTH_ACTIONS:
                ok = acts.get("success", 0)
                facts.append("authentication outcome: no successful login from %s" % src if ok == 0
                             else "authentication outcome: %s had successful logins" % src)
        if domain == "network":
            rows = self._q("traffic_outcome", src, e, l)
            acts = {(_one(r.get("action")) or ""): int(float(r.get("count") or 0)) for r in rows}
            if acts.get("blocked"):
                allowed = acts.get("allowed", 0)
                facts.append("traffic outcome: the firewall blocked connections from %s; %s" % (
                    src, "no connections were explicitly allowed" if not allowed else "some other connections were allowed"))
        return facts

    def actor_facts(self, command, e, l):
        rows = self._q("change_actor", command, e, l)
        if not rows:
            return []
        facts = []
        r = rows[0]
        actor = _one(r.get("actor"))
        ua = (_one(r.get("userAgent")) or "").lower()
        how = "through the cloud web console" if "signin" in ua or "console" in ua else "through an API client"
        facts.append("actor of %s: %s %s" % (command, actor, how))
        idf, hosts = self.identity_facts(actor)
        facts += idf
        facts += self.cloud_user_facts(actor, e, l)
        facts += self.workstation_facts(hosts, e, l, "the actor's own")
        return facts

    def related(self, f, ents, e, l):
        ents = [x for x in ents if not self.is_shared(x)]
        if not ents:
            return []
        clauses = " OR ".join('user="{0}" OR src="{0}" OR dest="{0}" OR risk_object="{0}"'.format(esc(x)) for x in ents[:5])
        rows = self._q("related_alerts", "", e, l, clauses=clauses, event_id=esc(_one(f.get("event_id")) or ""))
        own = _one(f.get("rule_name")) or ""
        rules = [x for x in (_mv(rows[0].get("rules")) if rows else []) if x != own and "Risk Threshold" not in x and "Finding Group" not in x]
        return rules[:8]

    def rollup_window(self, f, ents):
        """Roll-up findings search the risk index in their own window; use the window of the
        contributing detections instead, so enrichment looks at the time the activity happened."""
        ents = [x for x in ents if not self.is_shared(x)]
        if not ents:
            return None
        clauses = " OR ".join('user="{0}" OR src="{0}" OR dest="{0}" OR risk_object="{0}"'.format(esc(x)) for x in ents[:5])
        try:
            t = float(_one(f.get("_time")) or 0)
            re_, rl = (str(int(t - 7 * 86400)), str(int(t + 3600))) if t else ("-7d", "now")
        except ValueError:
            re_, rl = "-7d", "now"
        rows = self._q("rollup_window", "", re_, rl, clauses=clauses)
        if rows and rows[0].get("e") and rows[0].get("l") and int(float(rows[0].get("count") or 0)) > 0:
            e, l = int(float(rows[0]["e"])), int(float(rows[0]["l"]))
            return str(e), str(min(l, e + 7 * 86400))  # never search more than 7 days for one finding
        return None

    def rollup_contributor_facts(self, obj, f):
        """Roll-ups on a shared object (e.g. ec2.amazonaws.com): the object itself tells nothing, so look at the
        changes that raised its risk and at the people who made them."""
        try:
            t = float(_one(f.get("_time")) or 0)
            re_, rl = (str(int(t - 7 * 86400)), str(int(t + 3600))) if t else ("-7d", "now")
        except ValueError:
            re_, rl = "-7d", "now"
        rows = self._q("rollup_contributors", obj, re_, rl)
        cmds = _mv(rows[0].get("commands")) if rows else []
        if not cmds:
            return []
        facts = ["the risk score comes from these changes: %s" % ", ".join(cmds[:6])]
        for c in cmds[:4]:
            w = self._q("change_window", c, re_, rl)
            if w and w[0].get("e") and w[0].get("l") and int(float(w[0].get("count") or 0)) > 0:
                e, l = int(float(w[0]["e"])), int(float(w[0]["l"]))
                facts += self.actor_facts(c, str(e), str(min(l, e + 7 * 86400)))
        return facts

    # ---- main ----
    def collect(self, f):
        self.errors = []
        e = _one(f.get("info_min_time")) or "-24h"
        l = _one(f.get("info_max_time")) or "now"
        domain = (_one(f.get("security_domain")) or "").lower()
        facts = []
        users = _mv(f.get("user"))
        if (_one(f.get("risk_object_type")) or "") == "user":
            users += _mv(f.get("risk_object"))
        hosts = [h for h in _mv(f.get("dest")) if not is_ip(h) and not is_url(h) and not self.is_shared(h)]
        if (_one(f.get("risk_object_type")) or "") == "system" and not is_ip(_one(f.get("risk_object")) or "x"):
            hosts += [h for h in _mv(f.get("risk_object")) if not self.is_shared(h)]
        srcs = [s for s in _mv(f.get("src")) if is_ip(s)]
        if (_one(f.get("risk_object_type")) or "") == "system":
            srcs += [s for s in _mv(f.get("risk_object")) if is_ip(s)]
        nt = (_one(f.get("notable_type")) or "")
        limit = self.max_facts
        if nt == "risk_event" or "Risk Threshold" in (_one(f.get("rule_title")) or "") or _one(f.get("detection_type")) == "fbd":
            win = self.rollup_window(f, list(dict.fromkeys(users + hosts + srcs)))
            if win:
                e, l = win
        sig = _one(f.get("signature")) or ""
        if GD_TYPE.match(sig):
            facts += self.guardduty_facts(sig, e, l)
        for u in dict.fromkeys(users):
            idf, ws = self.identity_facts(u)
            facts += idf
            facts += self.cloud_origin_facts(u, e, l)
            facts += self.cloud_user_facts(u, e, l)
            facts += self.win_actor_facts(u, e, l)
            facts += self.workstation_facts(ws, e, l, "this user's own")
        missing = []
        for h in dict.fromkeys(hosts):
            for x in self.host_facts(h, e, l):
                if x == "asset: %s is not in the asset inventory" % h:
                    missing.append(h)   # one line for all of them, so they do not crowd out other facts
                else:
                    facts.append(x)
        if len(missing) == 1:
            facts.append("asset: %s is not in the asset inventory" % missing[0])
        elif missing:
            facts.append("asset: none of the %d hosts are in the asset inventory (%s%s)" % (
                len(missing), ", ".join(missing[:4]), ", ..." if len(missing) > 4 else ""))
        for s in dict.fromkeys(srcs):
            facts += self.src_facts(s, domain or "access", e, l)
        if f.get("command"):
            facts += self.actor_facts(_one(f.get("command")), e, l)
        if is_rollup(f):
            ro = _one(f.get("risk_object")) or _one(f.get("src")) or ""
            if ro and self.is_shared(ro):
                extra = self.rollup_contributor_facts(ro, f)
                if extra:
                    facts = extra + facts
                    limit = self.max_facts + 6   # several actors behind one roll-up

        ents = list(dict.fromkeys(users + hosts + srcs))
        try:
            t = float(_one(f.get("_time")) or 0)
            re_, rl = (str(int(t - 7 * 86400)), str(int(t + 86400))) if t else ("-7d", "now")
        except ValueError:
            re_, rl = "-7d", "now"
        related = self.related(f, ents, re_, rl)
        facts = list(dict.fromkeys(facts))[: limit]
        return facts, related
