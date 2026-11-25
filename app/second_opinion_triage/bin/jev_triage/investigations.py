"""ES 8.7 investigations (KV missioncontrol/mc_incidents, the same collection ES uses for findings and investigations).

A finding record has notable_id = the finding's event_id and parent_incidents = the GUIDs of its investigations.
An investigation record has is_investigation = true, display_id (ES-00001 ...), status, disposition, assignee.
Read as the user running the search: users without read access to mc_incidents get nothing."""
import json
import re

KV = "/servicesNS/nobody/missioncontrol/storage/collections/data/mc_incidents"
GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
UNDECIDED = ("disposition:0", "disposition:6", "", None)
STATUS = {"0": "Unassigned", "1": "New", "2": "In Progress", "3": "Pending", "4": "Resolved", "5": "Closed"}


def _query(service, q, fields=None, limit=1000):
    params = {"query": json.dumps(q), "output_mode": "json", "limit": limit}
    if fields:
        params["fields"] = ",".join(fields)
    resp = service.get(KV, **params)
    return json.loads(resp.body.read().decode("utf-8") or "[]")


def get(service, ident):
    """Investigation by GUID or display id (ES-00002), or None."""
    ident = (ident or "").strip()
    if not ident:
        return None
    q = {"_key": ident} if GUID.match(ident) else {"display_id": ident}
    rows = [r for r in _query(service, q) if str(r.get("is_investigation")).lower() in ("true", "1")]
    return rows[0] if rows else None


def for_finding(service, event_id):
    """Investigations that contain this finding: list of dicts (guid, id, name, status, disposition, owner)."""
    rows = _query(service, {"notable_id": event_id}, ["_key", "parent_incidents"])
    guids = []
    for r in rows:
        p = r.get("parent_incidents") or []
        guids += p if isinstance(p, list) else [p]
    out = []
    for g in dict.fromkeys(guids):
        inv = get(service, g)
        if inv:
            out.append(view(inv))
    return out


def view(inv):
    return {"guid": inv.get("_key"), "id": inv.get("display_id") or inv.get("_key"), "name": inv.get("name") or "",
            "status": str(inv.get("status") or ""), "disposition": inv.get("disposition") or "",
            "owner": inv.get("assignee") or "", "urgency": inv.get("urgency") or "",
            "ai_suggested_disposition": inv.get("ai_suggested_disposition") or ""}


def children(service, guid):
    """Findings in an investigation: list of (incident id, event_id, name). event_id may be '' (not a notable)."""
    rows = _query(service, {"parent_incidents": guid}, ["_key", "notable_id", "name", "is_investigation"])
    return [(r.get("_key"), r.get("notable_id") or "", r.get("name") or "") for r in rows
            if str(r.get("is_investigation")).lower() not in ("true", "1")]


def contains(service, guid, event_id):
    return any(e == event_id for _, e, _ in children(service, guid))
