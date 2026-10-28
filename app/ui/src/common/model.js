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
