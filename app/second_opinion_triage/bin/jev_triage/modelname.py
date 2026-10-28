"""Display name of the decision model that produced a result.

Texts in the pages, Notes, guides and LLM prompts say "Jev"; they are shown with the name of the model that made
the result instead (stored per result as jev_model), so results from Clef, Kev, ... are not labelled "Jev".
[jev] display_name overrides the automatic name for the configured model."""
import re

_JEV = re.compile(r"\bJev\b")


def label(model, display_name="", configured=""):
    model = (model or configured or "").strip()
    if display_name and (not model or model == (configured or "").strip()):
        return display_name.strip()
    if not model or re.match(r"(?i)^jev([-_.]|$)", model):
        return "Jev"
    words = [w for w in re.split(r"[-_\s/]+", model) if w]
    out = []
    for w in words:
        if re.match(r"(?i)^\d+(\.\d+)?[bkm]$", w):      # 27b -> 27B
            out.append(w.upper())
        elif re.match(r"^[\d.]+$", w) or w.lower() in ("q4", "q8", "gguf"):
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out) or "Jev"


def localize(obj, name):
    """Copy of a text table with "Jev" replaced by the model's display name."""
    if not name or name == "Jev":
        return obj
    if isinstance(obj, str):
        return _JEV.sub(name, obj)
    if isinstance(obj, dict):
        return {k: localize(v, name) for k, v in obj.items()}
    if isinstance(obj, list):
        return [localize(v, name) for v in obj]
    return obj


def for_record(rec, jev_cfg):
    """Display name for one result; jev_cfg = the [jev] stanza (model, display_name)."""
    return label(rec.get("jev_model"), (jev_cfg or {}).get("display_name", ""), (jev_cfg or {}).get("model", ""))
