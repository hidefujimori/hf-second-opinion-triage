// Display name of the decision model that produced a result (same rules as bin/jev_triage/modelname.py).
// Texts say "Jev"; they are shown with the name of the model that made the result.
const JEV = /\bJev\b/g;

export function modelLabel(model, cfg = {}) {
  const configured = (cfg.model || '').trim();
  const m = (model || configured || '').trim();
  if (cfg.display_name && (!m || m === configured)) { return cfg.display_name.trim(); }
  if (!m || /^jev([-_.]|$)/i.test(m)) { return 'Jev'; }
  const words = m.split(/[-_\s/]+/).filter(Boolean).map((w) => {
    if (/^\d+(\.\d+)?[bkm]$/i.test(w)) { return w.toUpperCase(); }
    if (/^[\d.]+$/.test(w)) { return w; }
    return w.charAt(0).toUpperCase() + w.slice(1);
  });
  return words.join(' ') || 'Jev';
}

export function localize(T, name) {
  if (!name || name === 'Jev') { return T; }
  const out = {};
  Object.keys(T).forEach((k) => { out[k] = typeof T[k] === 'string' ? T[k].replace(JEV, name) : T[k]; });
  return out;
}

// Decision rules per model (same as bin/jev_triage/rules.py): threshold and option-order check.
const BUILT_IN_RULES = [
  [/^gpt-6-luna/i, { confidence_threshold: 0.50, order_check: false }],
  [/^clef$/i, { confidence_threshold: 0.15, order_check: true }],
  [/^clef-27b/i, { confidence_threshold: 0.45, order_check: true }],
];

export function rulesFor(model, jev = {}) {
  const truthy = (v) => /^(1|true|yes|t|on)$/i.test(String(v == null ? 'true' : v).trim());
  const base = { confidence_threshold: Number(jev.confidence_threshold || 0.6), order_check: truthy(jev.order_check), source: 'settings' };
  if (String(jev.model_rules || 'auto').toLowerCase() === 'off') { return base; }
  const hit = BUILT_IN_RULES.find(([re]) => re.test((model || '').trim()));
  return hit ? { ...base, ...hit[1], source: 'built-in' } : base;
}
