"""Minimal System One client (stdlib only, so it runs on Splunk's bundled Python).

TypeSafe Jev is the default. Other servers that speak the same API (llama.cpp `/v1/systemone` with Kev or
Clef-Flash, Cloudflare Clef on Workers AI, ...) can be used through [jev] endpoint. For those, requests are made
"compatible": the state is sent as a JSON string, score levels and yes/no criteria are sent as plain text, and
answers are normalised to Jev's shape (score probabilities keyed "0".."n-1").
OpenAI's Decisions API (an endpoint ending in /v1/decisions) has its own shape: questions are converted to its
choice / score / predicate types and the answers back to Jev's shape."""
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


def is_openai_decisions(endpoint):
    return (urlparse(endpoint or "").path or "").rstrip("/").endswith("/decisions")


def _level_label(c, i):
    what = c.get("what") if isinstance(c, dict) else str(c)
    head = (what or "").split(":", 1)[0].strip()
    return head if head and len(head) <= 40 else "Level %d" % i


def openai_questions(questions):
    """Jev questions -> OpenAI Decisions questions (array)."""
    out = []
    for name, q in questions.items():
        t = q.get("type")
        if t == "choice":
            out.append({"type": "choice", "name": name, "instructions": q.get("instructions", ""),
                        "choices": [{"value": k, "description": v} for k, v in (q.get("criteria") or {}).items()]})
        elif t == "score":
            out.append({"type": "score", "name": name, "instructions": q.get("instructions", ""),
                        "levels": [{"label": _level_label(c, i), "description": _level_text(c)}
                                   for i, c in enumerate(q.get("criteria") or [])]})
        elif t == "noul":
            ins = q.get("instructions", "")
            if isinstance(q.get("criteria"), dict):
                ins = "%s (%s)" % (ins, "; ".join("%s if: %s" % (str(k).capitalize(), v) for k, v in q["criteria"].items()))
            out.append({"type": "predicate", "name": name, "instructions": ins})
    return out


def openai_answers(answers, questions):
    """OpenAI Decisions answers (array) -> Jev answers (dict by question name)."""
    out = {}
    for a in answers or []:
        name, t = a.get("name"), a.get("type")
        if t == "refusal":
            raise JevError("the model refused question %s" % name)
        if t == "predicate":
            out[name] = {"noul": float(a.get("probability", 0))}
        elif t == "choice":
            out[name] = {"choice": a.get("choice"), "confidence": float(a.get("confidence", 0)),
                         "probabilities": {str(p.get("value")): float(p.get("probability", 0)) for p in a.get("probabilities") or []}}
        elif t == "score":
            levels = (questions.get(name) or {}).get("criteria") or []
            labels = [_level_label(c, i) for i, c in enumerate(levels)]
            probs = {}
            for i, p in enumerate(a.get("probabilities") or []):
                v = p.get("value")
                idx = int(v) if str(v).isdigit() else (labels.index(p.get("label")) if p.get("label") in labels else i)
                probs[str(idx)] = float(p.get("probability", 0))
            out[name] = {"score": float(a.get("score", 0)), "confidence": float(a.get("confidence", 0)), "probabilities": probs}
    return out


def use_confidence(answers, field):
    """Servers whose `confidence` means something else (Laya: 1 - normalised entropy) also return a calibrated
    probability of the chosen answer, e.g. answer_confidence: use that one as `confidence` for the policy."""
    if not field or field == "confidence":
        return answers
    for a in (answers or {}).values():
        if isinstance(a, dict) and a.get(field) is not None:
            a["confidence_raw"] = a.get("confidence")
            a["confidence"] = a[field]
    return answers


def call(api_key, model, state, questions, timeout=30, retries=4, proxy=None, endpoint=None, extra=None,
         confidence_field=None):
    url = endpoint or API_URL
    native = is_typesafe(url)
    openai = is_openai_decisions(url)
    qs = questions if native or openai else compat_questions(questions)
    st = state if native or isinstance(state, str) else json.dumps(state, ensure_ascii=False)
    if openai:
        req_body = {"model": model, "input": st, "questions": openai_questions(questions)}
    else:
        req_body = {"model": model, "state": st, "questions": qs}
    if extra and not native:   # server-specific fields, e.g. Laya: {"max_len": 4096}
        req_body.update({k: v for k, v in extra.items() if k not in req_body})
    body = json.dumps(req_body).encode("utf-8")
    handlers = [urllib.request.HTTPSHandler(context=ssl.create_default_context())]
    if proxy and url.lower().startswith("https://"):
        handlers.append(urllib.request.ProxyHandler({"https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))   # plain http (local servers): never through a proxy
    opener = urllib.request.build_opener(*handlers)
    headers = {"Content-Type": "application/json", "User-Agent": "second_opinion_triage"}
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
                if openai:
                    out["answers"] = openai_answers(out["answers"], questions)
                    use_confidence(out["answers"], confidence_field)
                elif not native:
                    normalise_answers(out["answers"], qs)
                    use_confidence(out["answers"], confidence_field)
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
