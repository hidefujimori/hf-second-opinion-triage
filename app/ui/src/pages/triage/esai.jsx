// ES AI SOC Analyst (Mission Control "AI triage") results, shown next to Jev as a second opinion.
// Read only. Where the data lives (ES 8.7, checked on Splunk Cloud):
// - KV missioncontrol/mc_ai_analysis (lookup mc_ai_analysis_lookup): one record per finding,
//   incident_id = finding event_id; summary ends with a Markdown table (Determination / Severity / Confidence)
// - ES API public/v2/findings/{id}: ai_suggested_disposition_label (the value shown in the Analyst Queue)
// The texts are written by the ES agent: shown as plain text only, never used as instructions or as Jev input.
import { useEffect, useState } from 'react';
import { createRESTURL } from '@splunk/splunk-utils/url';
import { defaultFetchInit } from '@splunk/splunk-utils/fetch';
import { search } from '../../common/api';

const TABLE_ROW = (name) => new RegExp(`\\|\\s*(?:${name})\\s*\\|\\s*\\*{0,2}([^|*]+?)\\*{0,2}\\s*\\|`, 'i');

/** "True Positive - Suspicious Activity" -> TP; "Benign Positive - ..." -> Benign; "False Positive - ..." -> FP; else Undetermined */
export function aiCat(label) {
  const s = String(label || '').toLowerCase();
  if (!s) { return ''; }
  if (s.startsWith('true positive')) { return 'TP'; }
  if (s.startsWith('benign')) { return 'Benign'; }
  if (s.startsWith('false positive')) { return 'FP'; }
  return 'Undetermined';
}
const RAW = { true_positive: 'TP', false_positive: 'FP', benign: 'Benign', undetermined: 'Undetermined' };

/** agree | lean (Jev undetermined but leaning the same way) | disagree | none */
export function compare(jevDisp, jevRaw, ai) {
  if (!ai || !jevDisp) { return 'none'; }
  if (jevDisp === ai) { return 'agree'; }
  if (jevDisp === 'Undetermined' && RAW[jevRaw] === ai) { return 'lean'; }
  return 'disagree';
}

/** Pull Determination / Severity / Confidence out of the summary's Markdown table, and the text without the table. */
export function parseSummary(summary) {
  const s = String(summary || '');
  const pick = (re) => { const m = re.exec(s); return m ? m[1].trim() : ''; };
  return {
    disp: pick(TABLE_ROW('Determination|Investigation disposition')),
    sev: pick(TABLE_ROW('Severity')).toLowerCase(),
    conf: pick(TABLE_ROW('Confidence')),
    text: s.split('\n').filter((l) => !/^\s*\|/.test(l)).join('\n').trim(),
  };
}

const plain = (s) => String(s || '').replace(/\*\*/g, '').replace(/`/g, '');

function relEpoch(t) {
  const m = /^-(\d+)([hd])$/.exec(t || '');
  if (!m) { return 0; }
  return Math.floor(Date.now() / 1000) - parseInt(m[1], 10) * (m[2] === 'h' ? 3600 : 86400);
}

/** event_id -> {disp, cat, sev, conf, time} for the list. Empty when ES AI triage is not there (or not readable). */
export async function loadAiIndex(time) {
  const since = time === '0' ? 0 : relEpoch(time) - 86400;  // results come shortly after the finding
  try {
    const rows = await search('| inputlookup mc_ai_analysis_lookup'
      + ` | where like(incident_id, "%@@notable@@%") AND tonumber(create_time) >= ${since}`
      + ' | rex field=summary "\\|\\s*(?:Determination|Investigation disposition)\\s*\\|\\s*\\*{0,2}(?<ai_disp>[^|*]+?)\\*{0,2}\\s*\\|"'
      + ' | rex field=summary "\\|\\s*Severity\\s*\\|\\s*\\*{0,2}(?<ai_sev>[^|*]+?)\\*{0,2}\\s*\\|"'
      + ' | rex field=summary "\\|\\s*Confidence\\s*\\|\\s*\\*{0,2}(?<ai_conf>[^|*]+?)\\*{0,2}\\s*\\|"'
      + ' | sort 0 - create_time | dedup incident_id | table incident_id ai_disp ai_sev ai_conf create_time');
    const out = {};
    rows.forEach((r) => {
      out[r.incident_id] = { disp: r.ai_disp || '', cat: aiCat(r.ai_disp), sev: (r.ai_sev || '').toLowerCase(), conf: r.ai_conf || '', time: r.create_time };
    });
    return out;
  } catch (e) {
    return {};
  }
}

async function getJson(url) {
  const res = await fetch(url, defaultFetchInit);
  if (!res.ok) { const err = new Error(`HTTP ${res.status}`); err.status = res.status; throw err; }
  return res.json();
}

/** Full ES AI record for one finding: {rec, label} ; rec null when there is none. */
function useAiRecord(id) {
  const [st, setSt] = useState({ loading: true, rec: null, label: '', err: '' });
  useEffect(() => {
    let live = true;
    setSt({ loading: true, rec: null, label: '', err: '' });
    const kv = createRESTURL('storage/collections/data/mc_ai_analysis', { app: 'missioncontrol', owner: 'nobody' })
      + `?output_mode=json&query=${encodeURIComponent(JSON.stringify({ incident_id: id }))}`;
    const fu = `${createRESTURL(`public/v2/findings/${encodeURIComponent(id)}`, { app: 'missioncontrol', owner: 'nobody' })}?output_mode=json`;
    Promise.allSettled([getJson(kv), getJson(fu)]).then(([a, b]) => {
      if (!live) { return; }
      const recs = a.status === 'fulfilled' && Array.isArray(a.value) ? a.value : [];
      recs.sort((x, y) => (parseFloat(y.create_time) || 0) - (parseFloat(x.create_time) || 0));
      const f = b.status === 'fulfilled' ? b.value || {} : {};
      const label = f.ai_suggested_disposition_label || '';
      const err = a.status === 'rejected' && a.reason && a.reason.status !== 404 ? a.reason.message : '';
      setSt({ loading: false, rec: recs[0] || null, label, err });
    });
    return () => { live = false; };
  }, [id]);
  return st;
}

function Sec({ title, children }) { return <div className="jev-sec"><h3>{title}</h3>{children}</div>; }

export function EsAiColumn({ T, id, Badge, Chip, onData }) {
  const { loading, rec, label, err } = useAiRecord(id);
  const p = parseSummary(rec && rec.summary);
  const dispLabel = label || p.disp;
  const cat = aiCat(dispLabel);
  useEffect(() => { if (!loading) { onData({ cat, sev: p.sev, conf: p.conf, label: dispLabel, has: !!(rec || label) }); } },
    [loading, cat, p.sev, p.conf, dispLabel, rec, label]);  // eslint-disable-line react-hooks/exhaustive-deps
  const tools = (rec && Array.isArray(rec.tools)) ? rec.tools : [];
  const failed = tools.filter((t) => t && t.status === 'failed');
  return (
    <div className="jev-col jev-esai">
      <div className="jev-col-head">{T.aiTitle}{rec && rec.create_time ? <span className="sub"> · {new Date(parseFloat(rec.create_time) * 1000).toLocaleString()}</span> : null}</div>
      <div className="jev-pane-body">
        {loading && <div className="sub">{T.loading}</div>}
        {!loading && !rec && !label && <p className="jev-explain placeholder">{err ? `${T.aiErr} (${err})` : T.aiNone}</p>}
        {!loading && (rec || label) && (
          <>
            <Sec title={`${T.sugDisp} / ${T.sugUrg}`}>
              <div className="jev-verdict">
                <div className="jev-vbox"><div className="sub">{T.sugDisp}</div><div className="big"><Chip d={cat} T={T} /></div>
                  <div className="sub">{dispLabel}</div></div>
                <div className="jev-vbox"><div className="sub">{T.aiSev}</div><div className="big"><Badge u={p.sev} T={T} /></div>
                  <div className="sub">{p.conf ? `${T.confidence} ${p.conf}` : ''}</div></div>
              </div>
              <div className="jev-status">{T.aiNote}</div>
            </Sec>
            {p.text && <Sec title={T.aiSummary}><div className="jev-explain">{plain(p.text)}</div></Sec>}
            {rec && rec.justification && <Sec title={T.aiWhy}><details><summary>{T.show}</summary><div className="jev-explain">{plain(rec.justification)}</div></details></Sec>}
            {rec && rec.evidence && <Sec title={T.aiEvidence}><details><summary>{T.show}</summary><div className="jev-explain">{plain(rec.evidence)}</div></details></Sec>}
            {tools.length > 0 && (
              <Sec title={`${T.aiTools} (${tools.length}${failed.length ? ` · ${T.aiFailed} ${failed.length}` : ''})`}>
                <ul className="jev-facts jev-tools">
                  {tools.map((t, i) => (
                    <li key={i} className={t.status === 'failed' ? 'bad' : ''}>
                      <span className={`st ${t.status || ''}`}>{t.status === 'failed' ? '⚠' : t.status === 'success' ? '✓' : '–'}</span>{' '}
                      {plain(t.purpose || t.app_name || '').slice(0, 220)}
                      {t.status === 'no_results' && <span className="sub"> ({T.aiNoResults})</span>}
                      {t.status === 'failed' && t.errors && <div className="sub">{plain([].concat(t.errors).join(' / ')).slice(0, 200)}</div>}
                    </li>))}
                </ul>
                {failed.length > 0 && <div className="jev-status">{T.aiFailedHint}</div>}
              </Sec>)}
            {rec && rec.view_details && <Sec title={T.aiDetails}><details><summary>{T.show}</summary><div className="jev-explain">{plain(rec.view_details)}</div></details></Sec>}
          </>)}
      </div>
    </div>
  );
}
