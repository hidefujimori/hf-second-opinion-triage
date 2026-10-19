// Decision guide rule table. Mirror of bin/jev_triage/guide.py verdict() - keep both in step.
import { aiCat } from './esai';

const URG = ['low', 'medium', 'high', 'critical'];
const RAW = { true_positive: 'TP', false_positive: 'FP', benign: 'Benign', undetermined: 'Undetermined' };
const NEG = ['FP', 'Benign'];
const fnum = (v, d) => { const n = parseFloat(v); return Number.isNaN(n) ? d : n; };

export function verdict(jevDisp, jevRaw, jevConf, jevUrg, aiLabel, aiSev = '', aiConf = '', aiFailed = 0) {
  const a = aiCat(aiLabel);
  const j = jevDisp || '';
  const cautions = [];
  if (a && aiFailed) { cautions.push('ai_failed_checks'); }
  if (fnum(jevConf, 1) < 0.6) { cautions.push('jev_low_conf'); }
  let pc = fnum(String(aiConf || '').replace('%', '').split(' ')[0], null);
  if (pc != null && pc <= 1) { pc *= 100; }
  if (pc != null && pc < 70) { cautions.push('ai_low_conf'); }
  const urg = [jevUrg, aiSev].filter((u) => URG.includes(u));
  const top = urg.length ? urg.reduce((x, y) => (URG.indexOf(y) > URG.indexOf(x) ? y : x)) : '';
  const low = urg.length ? urg.reduce((x, y) => (URG.indexOf(y) < URG.indexOf(x) ? y : x)) : '';
  if (!a) { return { key: 'no_ai', priority: '', action_urgency: jevUrg || '', cautions, checks: [] }; }
  let key; let prio;
  if (a === 'Undetermined') { key = 'ai_unsure'; prio = 'review'; } else if (j === 'TP' && a === 'TP') { key = 'both_tp'; prio = 'investigate'; } else if (NEG.includes(j) && NEG.includes(a)) { key = 'both_negative'; prio = 'close'; } else if ((j === 'TP' && NEG.includes(a)) || (NEG.includes(j) && a === 'TP')) { key = 'conflict'; prio = 'urgent_review'; } else if (j === 'Undetermined' && RAW[jevRaw] === a) { key = 'jev_unsure_same'; prio = 'review'; } else { key = 'jev_unsure_other'; prio = 'review'; }
  let checks = {
    both_tp: ['contain'], both_negative: ['confirm_reason'], conflict: ['compare_evidence', 'ai_failed'],
    jev_unsure_same: ['jev_missing', 'ai_failed'], jev_unsure_other: ['compare_evidence'], ai_unsure: ['jev_missing', 'compare_evidence'],
  }[key];
  if (!cautions.includes('ai_failed_checks')) { checks = checks.filter((c) => c !== 'ai_failed'); }
  let act;
  if (key === 'both_tp' || key === 'conflict') { act = top; } else if (key === 'both_negative' && urg.length) { act = low; } else { act = jevUrg || top; }
  return { key, priority: prio, action_urgency: act, cautions, checks };
}
