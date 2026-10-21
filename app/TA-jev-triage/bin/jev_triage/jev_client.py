"""Minimal System One client (stdlib only, so it runs on Splunk's bundled Python).

TypeSafe Jev is the default. Other servers that speak the same API (llama.cpp `/v1/systemone` with Kev or
Clef-Flash, Cloudflare Clef on Workers AI, ...) can be used through [jev] endpoint. For those, requests are made
"compatible": the state is sent as a JSON string, score levels and yes/no criteria are sent as plain text, and
answers are normalised to Jev's shape (score probabilities keyed "0".."n-1")."""
import json
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

API_URL = "https://api.typesafe.ai/v1/systemone"


class JevError(Exception):
    pass


def is_typesafe(endpoint):
    return (urlparse(endpoint or API_URL).hostname or "").lower().endswith("typesafe.ai")


def _level_text(c):
    if isinstance(c, dict):
        ex = c.get("examples") or []
        return "%s%s" % (c.get("what") or c.get("label") or "", (" (e.g. %s)" % "; ".join(ex)) if ex else "")
    return str(c)


def compat_questions(questions):
    """Jev-specific question details as plain text, for other System One servers."""
    out = {}
    for name, q in questions.items():
        q = dict(q)
        if q.get("type") == "score" and isinstance(q.get("criteria"), list):
            q["criteria"] = [_level_text(c) for c in q["criteria"]]
        elif q.get("type") == "noul" and isinstance(q.get("criteria"), dict):
            crit = q.pop("criteria")
            extra = "; ".join("%s if: %s" % (str(k).capitalize(), v) for k, v in crit.items())
            q["instructions"] = "%s (%s)" % (q.get("instructions", ""), extra)
        out[name] = q
    return out


def normalise_answers(answers, questions):
    """Score probabilities keyed by level index ("0".."n-1"), as Jev returns them."""
    for name, a in (answers or {}).items():
        q = questions.get(name) or {}
        if q.get("type") != "score" or not isinstance(a, dict):
            continue
        probs = a.get("probabilities")
        levels = q.get("criteria") or []
        texts = [_level_text(c) for c in levels]
        if isinstance(probs, list):
            a["probabilities"] = {str(i): float(p.get("probability", 0) if isinstance(p, dict) else p) for i, p in enumerate(probs)}
        elif isinstance(probs, dict) and probs and not all(str(k).isdigit() for k in probs):
            legend = a.get("legend")
            order = [str(x) for x in legend] if isinstance(legend, list) else texts
            idx = {k: i for i, k in enumerate(order)}
            a["probabilities"] = {str(idx.get(str(k), i)): float(v) for i, (k, v) in enumerate(probs.items())}
    return answers


def call(api_key, model, state, questions, timeout=30, retries=4, proxy=None, endpoint=None):
    url = endpoint or API_URL
    native = is_typesafe(url)
    qs = questions if native else compat_questions(questions)
    st = state if native or isinstance(state, str) else json.dumps(state, ensure_ascii=False)
    body = json.dumps({"model": model, "state": st, "questions": qs}).encode("utf-8")
    handlers = [urllib.request.HTTPSHandler(context=ssl.create_default_context())]
    if proxy and url.lower().startswith("https://"):
        handlers.append(urllib.request.ProxyHandler({"https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))   # plain http (local servers): never through a proxy
    opener = urllib.request.build_opener(*handlers)
    headers = {"Content-Type": "application/json", "User-Agent": "TA-jev-triage"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        t0 = time.time()
        try:
            with opener.open(req, timeout=timeout) as r:
                out = json.loads(r.read().decode("utf-8"))
                if "answers" not in out and isinstance(out.get("result"), dict):   # Cloudflare Workers AI wraps the answer
                    out = out["result"]
                if "answers" not in out:
                    raise JevError("no answers in the response: %s" % json.dumps(out)[:200])
                if not native:
                    normalise_answers(out["answers"], qs)
                out["latency_ms"] = int((time.time() - t0) * 1000)
                return out
        except urllib.error.HTTPError as e:
            last = "HTTP %s: %s" % (e.code, e.read()[:300].decode("utf-8", "replace"))
            if e.code in (429, 503, 529) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise JevError(last)
        except (urllib.error.URLError, OSError) as e:
            last = str(e)
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
    raise JevError(last or "retries exhausted")
