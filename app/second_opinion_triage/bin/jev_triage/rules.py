"""Decision rules per decision model: the confidence threshold below which the disposition is Undetermined, and
whether the option-order check (a second call with the disposition options reversed) is used.

The values were tuned for each model on the 33 labelled findings (poc/decision-models/README.md):
  jev-* and other models: [jev] confidence_threshold / order_check (default 0.60, on; Jev 32/33)
  gpt-6-luna   0.50, order check off  (OpenAI Decisions: its answers change when options are reversed)
  clef         0.15, order check on   (Cloudflare Workers AI: low confidence values)
  clef-27b     0.45, order check on   (local Clef 27B Q4)
[jev] model_rules = off always uses [jev] confidence_threshold / order_check.
Override for one model in jev_triage.conf:  [model_rules:<model>]  confidence_threshold = ...  order_check = ..."""
import re

BUILT_IN = [
    (r"^gpt-6-luna", {"confidence_threshold": 0.50, "order_check": False}),
    (r"^clef$", {"confidence_threshold": 0.15, "order_check": True}),
    (r"^clef-27b", {"confidence_threshold": 0.45, "order_check": True}),
]


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "t", "on")


def rules_for(model, jev, override=None):
    """{confidence_threshold, order_check, source} for the model.
    jev = [jev] stanza (confidence_threshold, order_check, model_rules); override = [model_rules:<model>] stanza."""
    base = {"confidence_threshold": float(jev.get("confidence_threshold") or 0.60),
            "order_check": _truthy(jev.get("order_check", "true")), "source": "settings"}
    if str(jev.get("model_rules", "auto")).strip().lower() == "off":
        return base
    out = dict(base)
    for pat, r in BUILT_IN:
        if re.match(pat, (model or "").strip(), re.I):
            out.update(r, source="built-in")
            break
    o = {k: v for k, v in (override or {}).items() if v not in (None, "") and not str(k).startswith("eai:")}
    if "confidence_threshold" in o:
        out["confidence_threshold"] = float(o["confidence_threshold"])
        out["source"] = "model_rules:%s" % model
    if "order_check" in o:
        out["order_check"] = _truthy(o["order_check"])
        out["source"] = "model_rules:%s" % model
    return out


def describe(model, r):
    return "%s: threshold %.2f, order check %s (%s)" % (model, r["confidence_threshold"],
                                                         "on" if r["order_check"] else "off", r["source"])
