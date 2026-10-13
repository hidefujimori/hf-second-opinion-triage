"""Pluggable LLM providers for the explanation (stdlib only).
provider = anthropic | openai | bedrock | gemini   (openai = any OpenAI-compatible endpoint incl. Ollama and Apple fm serve; gemini = Google Gemini API incl. Gemma 4)"""
import datetime
import hashlib
import hmac
import json
import ssl
import time
import urllib.parse
import urllib.request


class LLMError(Exception):
    pass


def _check_url(url, what="endpoint"):
    if not url.lower().startswith(("http://", "https://")):
        raise LLMError("%s must start with http:// or https:// (e.g. http://<host>:11434/v1), got %r" % (what, url))


def _post(url, body, headers, timeout, proxy=None):
    _check_url(url)
    handlers = [urllib.request.HTTPSHandler(context=ssl.create_default_context())]
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise LLMError("HTTP %s: %s" % (e.code, e.read()[:300].decode("utf-8", "replace")))
    except (urllib.error.URLError, OSError) as e:
        raise LLMError(str(e))


def _anthropic(cfg, system, user):
    url = (cfg.get("endpoint") or "https://api.anthropic.com").rstrip("/") + "/v1/messages"
    out = _post(url, {"model": cfg["model"], "max_tokens": int(cfg.get("max_tokens", 600)),
                      "system": system, "messages": [{"role": "user", "content": user}]},
                {"x-api-key": cfg["api_key"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
                int(cfg.get("timeout", 60)), cfg.get("proxy"))
    return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")


def _openai(cfg, system, user):
    """OpenAI Chat Completions and compatible servers (Ollama, vLLM, LM Studio, Apple `fm serve`, gateways).
    stream=false is sent explicitly: some servers (Apple fm serve) stream by default.
    thinking_level -> reasoning_effort (Ollama: "none" turns thinking off for gemma4 / qwen3; gpt-oss cannot
    turn it off, use "low";
    otherwise the thinking can use up max_tokens and leave an empty answer)."""
    base = (cfg.get("endpoint") or "https://api.openai.com/v1").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = "Bearer " + cfg["api_key"]
    body = {"model": cfg["model"], "max_tokens": int(cfg.get("max_tokens", 600)), "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    level = (cfg.get("thinking_level") or "").strip()
    if level:
        body["reasoning_effort"] = level
    timeout = int(cfg.get("timeout", 60))
    try:
        out = _post(base + "/chat/completions", body, headers, timeout, cfg.get("proxy"))
    except LLMError as e:
        if "reasoning" in str(e).lower() and "reasoning_effort" in body:
            body.pop("reasoning_effort")
            out = _post(base + "/chat/completions", body, headers, timeout, cfg.get("proxy"))
        else:
            raise
    choice = (out.get("choices") or [{}])[0]
    text = _strip_think((choice.get("message") or {}).get("content") or "")
    if not text:
        hint = ""
        if (choice.get("message") or {}).get("reasoning") or (choice.get("message") or {}).get("reasoning_content"):
            hint = "; the model spent max_tokens on thinking - set thinking_level = none (gemma4, qwen3) or low (gpt-oss), or raise max_tokens"
        raise LLMError("empty answer (finish_reason %s%s)" % (choice.get("finish_reason"), hint))
    return text


def _strip_think(text):
    """Drop <think>...</think> blocks that some local models put in the answer."""
    while "<think>" in text and "</think>" in text:
        a, b = text.index("<think>"), text.index("</think>")
        if b < a:
            break
        text = text[:a] + text[b + len("</think>"):]
    if "</think>" in text:          # opening tag eaten by the chat template
        text = text.split("</think>", 1)[1]
    return text.strip()


def _sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _bedrock(cfg, system, user):
    """Bedrock Converse API with SigV4 (no boto3 needed)."""
    region = cfg.get("region") or "us-east-1"
    host = "bedrock-runtime.%s.amazonaws.com" % region
    path = "/model/%s/converse" % urllib.parse.quote(cfg["model"], safe="")
    body = json.dumps({"system": [{"text": system}], "messages": [{"role": "user", "content": [{"text": user}]}],
                       "inferenceConfig": {"maxTokens": int(cfg.get("max_tokens", 600))}}).encode("utf-8")
    now = datetime.datetime.utcnow()
    amz_date, date = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_uri = urllib.parse.quote(path, safe="/-_.~%")
    signed_headers = "content-type;host;x-amz-date"
    canonical = "\n".join(["POST", canonical_uri, "", "content-type:application/json", "host:" + host,
                           "x-amz-date:" + amz_date, "", signed_headers, payload_hash])
    scope = "%s/%s/bedrock/aws4_request" % (date, region)
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _sign(_sign(_sign(_sign(("AWS4" + cfg["aws_secret_access_key"]).encode(), date), region), "bedrock"), "aws4_request")
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-Amz-Date": amz_date, "Host": host,
               "Authorization": "AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (cfg["aws_access_key_id"], scope, signed_headers, sig)}
    out = _post("https://%s%s" % (host, path), body, headers, int(cfg.get("timeout", 60)), cfg.get("proxy"))
    return "".join(c.get("text", "") for c in out["output"]["message"]["content"])


def _gemini(cfg, system, user):
    """Google Gemini API (also serves Gemma 4: gemma-4-31b-it, gemma-4-26b-a4b-it).
    Gemma 4 thinks by default (slow); thinking_level = minimal turns it off. If the model rejects
    the thinking setting or system instructions (older Gemma), retry without them."""
    base = (cfg.get("endpoint") or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    url = "%s/models/%s:generateContent" % (base, urllib.parse.quote(cfg["model"], safe="-._"))
    headers = {"x-goog-api-key": cfg["api_key"], "Content-Type": "application/json"}
    gen = {"maxOutputTokens": int(cfg.get("max_tokens", 600))}
    level = (cfg.get("thinking_level") or "").strip()
    if level:
        gen["thinkingConfig"] = {"thinkingLevel": level}
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}], "generationConfig": gen}
    timeout = int(cfg.get("timeout", 60))
    try:
        out = _post(url, body, headers, timeout, cfg.get("proxy"))
    except LLMError as e:
        msg = str(e).lower()
        if "thinking" in msg and "thinkingConfig" in gen:
            gen.pop("thinkingConfig")
            out = _post(url, body, headers, timeout, cfg.get("proxy"))
        elif "instruction" in msg and "not enabled" in msg:
            body.pop("systemInstruction")
            body["contents"][0]["parts"][0]["text"] = system + "\n\n" + user
            out = _post(url, body, headers, timeout, cfg.get("proxy"))
        else:
            raise
    cands = out.get("candidates") or []
    if not cands:
        raise LLMError("no candidates (prompt feedback: %s)" % json.dumps(out.get("promptFeedback", {}))[:200])
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text:
        raise LLMError("empty answer (finishReason %s)" % cands[0].get("finishReason"))
    return text


PROVIDERS = {"anthropic": _anthropic, "openai": _openai, "bedrock": _bedrock, "gemini": _gemini}


def complete(cfg, system, user, retries=2):
    fn = PROVIDERS.get((cfg.get("provider") or "").lower())
    if not fn:
        raise LLMError("unknown provider %r (anthropic | openai | bedrock | gemini)" % cfg.get("provider"))
    if not cfg.get("model"):
        raise LLMError("[llm] model is not set in jev_triage.conf")
    last = None
    for attempt in range(retries + 1):
        try:
            return fn(cfg, system, user).strip()
        except LLMError as e:
            last = e
            if any(c in str(e) for c in ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 529")) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            if "timed out" in str(e).lower() and attempt == 0:   # a busy server: try once more
                continue
            raise
    raise last
