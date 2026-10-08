"""Minimal TypeSafe System One client (stdlib only, so it runs on Splunk's bundled Python)."""
import json
import ssl
import time
import urllib.error
import urllib.request

API_URL = "https://api.typesafe.ai/v1/systemone"


class JevError(Exception):
    pass


def call(api_key, model, state, questions, timeout=30, retries=4, proxy=None):
    body = json.dumps({"model": model, "state": state, "questions": questions}).encode("utf-8")
    handlers = [urllib.request.HTTPSHandler(context=ssl.create_default_context())]
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(API_URL, data=body, method="POST", headers={
            "Authorization": "Bearer " + api_key, "Content-Type": "application/json",
            "User-Agent": "TA-jev-triage/0.1"})
        t0 = time.time()
        try:
            with opener.open(req, timeout=timeout) as r:
                out = json.loads(r.read().decode("utf-8"))
                out["latency_ms"] = int((time.time() - t0) * 1000)
                return out
        except urllib.error.HTTPError as e:
            last = "HTTP %s: %s" % (e.code, e.read()[:300].decode("utf-8", "replace"))
            if e.code in (429, 529) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise JevError(last)
        except (urllib.error.URLError, OSError) as e:
            last = str(e)
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
    raise JevError(last or "retries exhausted")
