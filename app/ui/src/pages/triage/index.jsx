import { useCallback, useEffect, useMemo, useState } from 'react';
import layout from '@splunk/react-page/18';
import { getUserTheme } from '@splunk/splunk-utils/themes';
import Button from '@splunk/react-ui/Button';
import Select from '@splunk/react-ui/Select';
import Text from '@splunk/react-ui/Text';
import Message from '@splunk/react-ui/Message';
import { createURL } from '@splunk/splunk-utils/url';
import { search, q } from '../../common/api';
import { useLang, fmt, ensureLocale } from '../../common/i18n';
import { injectCss } from '../../common/styles';
import LangSwitch from '../../common/LangSwitch';
import { TEXT } from './text';

const URG = ['critical', 'high', 'medium', 'low'];
const DISP = ['TP', 'FP', 'Benign', 'Undetermined'];

const LIST_SPL = 'search `notable`'
  + ' | lookup jev_triage_latest event_id OUTPUT jev_status jev_error jev_disposition jev_disposition_confidence jev_es_disposition'
  + ' jev_urgency jev_urgency_confidence jev_escalate jev_tactic jev_policy jev_time jev_rerun_count'
  + ' | where isnotnull(jev_status)'
  + ' | eval analyst_decided=if(disposition_default="false" OR status_label IN ("Resolved","Closed"), 1, 0)'
  + ' | eval agree=case(analyst_decided=0, null(), jev_es_disposition=disposition, 1, true(), 0)'
  + ' | eval entity=coalesce(user, src, dest, risk_object)'
  + ' | table _time event_id rule_name security_domain entity urgency disposition_label status_label analyst_decided agree'
  + ' jev_status jev_error jev_disposition jev_disposition_confidence jev_urgency jev_urgency_confidence jev_escalate jev_tactic jev_policy jev_time jev_rerun_count'
  + ' | head 1000';

// ---------- small helpers ----------
const num = (v) => { const n = parseFloat(v); return Number.isNaN(n) ? null : n; };
const mv = (v) => (v == null ? [] : Array.isArray(v) ? v : [v]);
const epochFromId = (id) => { const m = /@@time(\d+)/.exec(id || ''); return m ? parseInt(m[1], 10) : null; };
// t: epoch seconds ("1788238033" / 1788238033) or an ISO time string ("2026-09-01T13:27:13.000+09:00")
function fmtTime(t) {
  if (t == null || t === '') { return ''; }
  if (/^\d+(\.\d+)?$/.test(String(t))) { return new Date(parseFloat(t) * 1000).toLocaleString(); }
  const d = new Date(t);
  return Number.isNaN(d.getTime()) ? String(t) : d.toLocaleString();
}
function urlParam(name) {
  const m = new RegExp(`[?&]${name.replace('.', '\\.')}=([^&]*)`).exec(window.location.search);
  return m ? decodeURIComponent(m[1].replace(/\+/g, ' ')) : null;
}

function Badge({ u, T }) {
  const k = (u || '').toLowerCase();
  return <span className={`jev-badge ${URG.includes(k) ? k : 'none'}`}>{k ? (T[k] || k) : '–'}</span>;
}
function Chip({ d, status, T }) {
  if (status === 'error') { return <span className="jev-chip error">error</span>; }
  return <span className={`jev-chip ${DISP.includes(d) ? d : 'none'}`}>{d ? (T[d] || d) : '–'}</span>;
}
function Meter({ v, wide, hot }) {
  const n = num(v);
  let cls = 'jev-meter';
  if (wide) { cls += ' wide'; }
  if (hot && n >= 0.8) { cls += ' hot'; } else if (hot && n >= 0.5) { cls += ' warm'; }
  const w = n == null ? 0 : Math.round(Math.max(0, Math.min(1, n)) * 100);
  return <span className={cls}><i style={{ width: `${w}%` }} /></span>;
}
function Conf({ v, wide, hot, label }) {
  const n = num(v);
  return <span className="jev-conf"><Meter v={v} wide={wide} hot={hot} /><span>{label ? `${label} ` : ''}{n == null ? '' : n.toFixed(2)}</span></span>;
}

// ---------- filters, tiles, list ----------
function Filters({ T, f, setF, onRefresh }) {
  const set = (k) => (e, { value }) => setF({ ...f, [k]: value });
  return (
    <div className="jev-bar">
      <label className="f">{T.time}
        <Select value={f.time} onChange={set('time')}>
          {[['-24h', T.h24], ['-7d', T.d7], ['-30d', T.d30], ['-90d', T.d90], ['0', T.allt]].map(([v, l]) => <Select.Option key={v} value={v} label={l} />)}
        </Select></label>
      <label className="f">{T.disp}
        <Select value={f.disp} onChange={set('disp')}>
          <Select.Option value="*" label={T.all} />{DISP.map((d) => <Select.Option key={d} value={d} label={T[d]} />)}
        </Select></label>
      <label className="f">{T.urg}
        <Select value={f.urg} onChange={set('urg')}>
          <Select.Option value="*" label={T.all} />{URG.map((u) => <Select.Option key={u} value={u} label={T[u]} />)}
        </Select></label>
      <label className="f">{T.conf}
        <Select value={f.conf} onChange={set('conf')}>
          {[['0', T.any], ['0.6', '0.6'], ['0.8', '0.8'], ['0.9', '0.9']].map(([v, l]) => <Select.Option key={v} value={v} label={l} />)}
        </Select></label>
      <label className="f">{T.es}
        <Select value={f.es} onChange={set('es')}>
          <Select.Option value="*" label={T.all} /><Select.Option value="0" label={T.undecided} /><Select.Option value="1" label={T.decided} />
        </Select></label>
      <label className="f" style={{ minWidth: 220 }}>{T.find}
        <Text value={f.text} onChange={set('text')} canClear /></label>
      <Button label={T.refresh} onClick={onRefresh} />
    </div>
  );
}

function Tiles({ T, rows, f, setF }) {
  const ok = rows.filter((r) => r.jev_status === 'ok');
  const cnt = (k, v) => ok.filter((r) => r[k] === v).length;
  const ag = rows.filter((r) => r.agree === '0' || r.agree === '1');
  const pct = ag.length ? `${Math.round((100 * ag.filter((r) => r.agree === '1').length) / ag.length)}%` : 'n/a';
  const toggle = (k, v) => setF({ ...f, [k]: f[k] === v ? '*' : v });
  return (
    <div className="jev-tiles">
      {URG.map((u) => (
        <button type="button" key={u} className={`jev-tile ${u}${f.urg === u ? ' active' : ''}`} onClick={() => toggle('urg', u)}>
          <div className="n">{cnt('jev_urgency', u)}</div><div className="l">{T[u]}</div></button>))}
      {DISP.map((d) => (
        <button type="button" key={d} className={`jev-tile ${d}${f.disp === d ? ' active' : ''}`} onClick={() => toggle('disp', d)}>
          <div className="n">{cnt('jev_disposition', d)}</div><div className="l">{T[d]}</div></button>))}
      <div className="jev-tile static err"><div className="n">{rows.filter((r) => r.jev_status === 'error').length}</div><div className="l">{T.errors}</div></div>
      <div className="jev-tile static"><div className="n">{pct}</div><div className="l">{T.agree}</div></div>
    </div>
  );
}

function FindingsTable({ T, rows, sel, onSelect }) {
  if (!rows.length) { return <div className="jev-empty">{T.none}</div>; }
  return (
    <table className="jev-findings">
      <thead><tr>{[T.cUrg, T.cDisp, T.cRule, T.cEntity, T.cTime, T.cEs, T.cAnalyst].map((h) => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.event_id} className={`row u-${r.jev_urgency || 'none'}${sel === r.event_id ? ' selected' : ''}`} onClick={() => onSelect(r.event_id)}>
            <td><Badge u={r.jev_status === 'ok' ? r.jev_urgency : ''} T={T} /></td>
            <td><Chip d={r.jev_disposition} status={r.jev_status} T={T} /> {r.jev_status === 'ok' && <Conf v={r.jev_disposition_confidence} />}</td>
            <td><div className="rule">{r.rule_name}{num(r.jev_rerun_count) ? <span className="jev-tag">{T.rerunTag}</span> : null}</div>
              {r.jev_policy && <div className="sub">{r.jev_policy}</div>}</td>
            <td>{mv(r.entity).slice(0, 2).join(', ')}</td>
            <td className="sub">{fmtTime(r._time)}</td>
            <td className="sub">{r.urgency || ''}</td>
            <td className="sub">{r.analyst_decided === '1' ? (r.disposition_label || r.status_label || '') : '–'}</td>
          </tr>))}
      </tbody>
    </table>
  );
}

// ---------- detail pane ----------
// Text shown in the explanation box when there is no explanation for the current result
function explPlaceholder(T, r, rerun) {
  const st = r.jev_explain_status || '';
  if (/daily limit/.test(st)) { return T.autoLimit; }
  if (/^skipped \((urgency|disposition)/.test(st)) { return fmt(T.autoRule, { why: st.replace(/^skipped \(|\)$/g, '') }); }
  if (rerun && r.jev_prev_had_explanation === '1') { return T.explCleared; }
  return T.noExpl;
}

function Sec({ title, children }) { return <div className="jev-sec"><h3>{title}</h3>{children}</div>; }

function useAction() {
  const [st, setSt] = useState({ busy: false, cls: '', msg: '' });
  const run = async (fn) => {
    setSt({ busy: true, cls: '', msg: '…' });
    try { const r = await fn(); setSt({ busy: false, cls: r.ok ? 'ok' : 'err', msg: r.msg }); } catch (e) { setSt({ busy: false, cls: 'err', msg: e.message }); }
  };
  return [st, run];
}

function Pane({ T, lang, id, listRow, onClose, onChanged }) {
  const [rec, setRec] = useState(undefined);
  const [err, setErr] = useState('');
  const [expl, setExpl] = useState(null);
  const [exSt, runEx] = useAction();
  const [acSt, runAc] = useAction();

  const load = useCallback(() => {
    setRec(undefined); setErr(''); setExpl(null);
    search(`| inputlookup jev_triage_latest where event_id=${q(id)}`).then((rows) => setRec(rows[0] || null), (e) => setErr(e.message));
  }, [id]);
  useEffect(load, [load]);

  const r = rec || {};
  const ok = rec && rec.jev_status === 'ok';
  let st = {};
  try { st = JSON.parse(r.jev_state || '{}'); } catch (e) { st = {}; }
  const facts = mv(st.context_from_siem);
  const others = mv(st.other_alerts_on_same_entity);
  const hasExpl = r.jev_explanation && r.jev_explain_for === r.jev_time;
  const shownExpl = expl != null ? expl : (hasExpl ? r.jev_explanation : null);
  const rerun = num(r.jev_rerun_count);

  const explain = () => runEx(async () => {
    const force = r.jev_explanation ? ' force=true' : '';
    const rows = await search(`| inputlookup jev_triage_latest where event_id=${q(id)} | jevexplain persist=true lang=${lang}${force}`
      + ' | table jev_explanation jev_explain_status jev_explain_model jev_explain_ms jev_persist_error');
    const x = rows[0] || {};
    if (x.jev_explain_status === 'ok' || x.jev_explain_status === 'cached') {
      setExpl(x.jev_explanation || '');
      return { ok: true, msg: `${T.done} · ${x.jev_explain_model || ''}${x.jev_explain_ms ? ` · ${x.jev_explain_ms} ms` : ''}` };
    }
    return { ok: false, msg: `${T.failed}: ${x.jev_explain_status || x.jev_persist_error || ''}` };
  });
  const note = () => runAc(async () => {
    const rows = await search(`| inputlookup jev_triage_latest where event_id=${q(id)} | jevnote persist=true lang=${lang}`
      + ' | table jev_note_status jev_note_id jev_persist_error');
    const x = rows[0] || {};
    if (x.jev_note_status === 'ok') { return { ok: true, msg: `${T.noteDone} (${x.jev_note_id || ''})` }; }
    if (x.jev_note_status === 'already written') { return { ok: true, msg: T.noteAlready }; }
    return { ok: false, msg: `${T.failed}: ${x.jev_note_status || x.jev_persist_error || ''}` };
  });
  const rerunNow = () => runAc(async () => {
    const t = epochFromId(id);
    const rows = await search(`search \`jev_findings\` | search event_id=${q(id)} | head 1 | jevtriage persist=true | table jev_status jev_error jev_persist_error`,
      t ? String(t - 3600) : '-90d', t ? String(t + 3600) : 'now');
    const x = rows[0] || {};
    if (x.jev_status === 'ok' && !x.jev_persist_error) { load(); onChanged(); return { ok: true, msg: T.rerunDone }; }
    return { ok: false, msg: `${T.failed}: ${x.jev_error || x.jev_persist_error || x.jev_status || 'no finding'}` };
  });

  const u = ok ? r.jev_urgency : '';
  const esUrl = createURL('/app/SplunkEnterpriseSecuritySuite/incident_review', { search: `event_id=${q(id)}` });
  return (
    <div className="jev-pane">
      <div className={`jev-pane-head ${u || ''}`}>
        <button type="button" className="jev-close" title={T.close} aria-label={T.close} onClick={onClose}>×</button>
        <h2>{r.rule_name || r.rule_title || listRow.rule_name || id}</h2>
        <div className="sub">{[fmtTime(listRow._time || epochFromId(id)), mv(listRow.entity || r.user || r.src || r.dest || r.risk_object).join(', ')].filter(Boolean).join(' · ')}</div>
      </div>
      <div className="jev-pane-body">
        {err && <Message type="error">{err}</Message>}
        {rec === undefined && !err && <div className="sub">{T.loading}</div>}
        {rec === null && <p className="jev-warn">{T.notFound}</p>}
        {rec && rerun ? (
          <div className="jev-rerun"><div className="t">{T.rerunTitle}</div>
            <div>{fmt(T.rerunInfo, { by: r.jev_rerun_by || '?', at: fmtTime(r.jev_time), n: r.jev_rerun_count,
              pd: r.jev_prev_disposition || '–', pu: r.jev_prev_urgency || '–', pt: fmtTime(r.jev_prev_time) })}</div>
            {r.jev_prev_had_explanation === '1' && !r.jev_explanation && expl == null && <div>{T.rerunCleared}</div>}
          </div>) : null}
        {rec && !ok && <Sec title={T.status}><div className="jev-warn">
          {r.jev_status === 'skipped' ? T.jevSkipped : `${r.jev_status || ''}: ${r.jev_error || ''}`}</div></Sec>}
        {ok && (
          <>
            <Sec title={`${T.sugDisp} / ${T.sugUrg}`}>
              <div className="jev-verdict">
                <div className="jev-vbox"><div className="sub">{T.sugDisp}</div><div className="big"><Chip d={r.jev_disposition} T={T} /></div>
                  <Conf v={r.jev_disposition_confidence} wide label={T.confidence} /></div>
                <div className="jev-vbox"><div className="sub">{T.sugUrg}</div><div className="big"><Badge u={r.jev_urgency} T={T} /></div>
                  <Conf v={r.jev_urgency_confidence} wide label={T.confidence} /></div>
              </div>
              <div className="jev-status">{T.suggestion}</div>
            </Sec>
            {r.jev_policy && <Sec title={T.policy}><div className="jev-policy">{r.jev_policy}</div></Sec>}
            <Sec title={T.signals}>
              <div className="jev-kv">
                {[[T.esc, r.jev_escalate, true], [T.admin, r.jev_admin_activity, false], [T.mismatch, r.jev_logic_mismatch, false]]
                  .filter((x) => x[1] != null && x[1] !== '')
                  .map(([k, v, hot]) => [<div className="k" key={`${k}k`}>{k}</div>, <div key={`${k}v`}><Conf v={v} wide hot={hot} /></div>])}
                {r.jev_tactic && [<div className="k" key="tk">{T.tactic}</div>, <div key="tv">{r.jev_tactic}</div>]}
              </div>
            </Sec>
          </>)}
        {facts.length > 0 && <Sec title={T.context}><ul className="jev-facts">{facts.map((x, i) => <li key={i}>{x}</li>)}</ul></Sec>}
        {others.length > 0 && <Sec title={T.other}><ul className="jev-facts">{others.map((x, i) => <li key={i}>{x}</li>)}</ul></Sec>}
        {r.jev_enrich_errors && <Sec title={T.enrichErr}><div className="sub jev-warn">{r.jev_enrich_errors}</div></Sec>}
        {rec && (
          <Sec title={T.llm}>
            <div className={`jev-explain${shownExpl ? '' : ' placeholder'}`}>
              {shownExpl || explPlaceholder(T, r, rerun)}</div>
            <div className="jev-actions" style={{ marginTop: 8 }}>
              <Button label={shownExpl ? T.reexplain : T.explain} onClick={explain} disabled={exSt.busy || !ok} />
            </div>
            <div className={`jev-status ${exSt.cls}`}>{exSt.busy ? T.working : exSt.msg}</div>
          </Sec>)}
        {rec !== undefined && (
          <Sec title=" ">
            <div className="jev-actions">
              <Button appearance="primary" label={T.note} onClick={note} disabled={acSt.busy || !ok} />
              <Button label={T.rerun} onClick={rerunNow} disabled={acSt.busy} />
              <Button label={T.openEs} to={esUrl} openInNewContext />
            </div>
            <div className="jev-status">{T.rerunHint}</div>
            <div className={`jev-status ${acSt.cls}`}>{acSt.busy ? T.working : acSt.msg}</div>
          </Sec>)}
        {rec && (
          <Sec title={T.meta}>
            <div className="jev-kv">
              {[[T.model, `${r.jev_model || ''} / ${r.jev_questions || ''}`], [T.version, r.jev_version], [T.triaged, fmtTime(r.jev_time)],
                [T.latency, r.jev_latency_ms ? `${r.jev_latency_ms} ms` : ''], ['event_id', id]]
                .filter((x) => x[1]).map(([k, v]) => [<div className="k" key={`${k}k`}>{k}</div>, <div className="sub" key={`${k}v`}>{v}</div>])}
            </div>
          </Sec>)}
      </div>
    </div>
  );
}

// ---------- page ----------
function TriagePage({ theme }) {
  const [lang, setLang] = useLang();
  const T = TEXT[lang];
  const [f, setF] = useState({ time: '-90d', disp: '*', urg: '*', conf: '0', es: '*', text: '' });
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState('');
  const [sel, setSel] = useState(() => urlParam('event_id') || urlParam('form.event_id'));

  const load = useCallback(() => {
    setErr(''); setRows(null);
    search(LIST_SPL, f.time === '0' ? '0' : f.time, 'now').then(setRows, (e) => { setErr(e.message); setRows([]); });
  }, [f.time]);
  useEffect(load, [load]);

  useEffect(() => {
    try { window.history.replaceState(null, '', sel ? `${window.location.pathname}?event_id=${encodeURIComponent(sel)}` : window.location.pathname); } catch (e) { /* ignore */ }
  }, [sel]);

  const shown = useMemo(() => {
    const minc = parseFloat(f.conf); const text = (f.text || '').toLowerCase();
    return (rows || []).filter((r) => {
      if (f.disp !== '*' && r.jev_disposition !== f.disp) { return false; }
      if (f.urg !== '*' && r.jev_urgency !== f.urg) { return false; }
      if (f.es !== '*' && String(r.analyst_decided) !== f.es) { return false; }
      if (r.jev_status === 'ok' && (num(r.jev_disposition_confidence) || 0) < minc) { return false; }
      if (text && ![r.rule_name, mv(r.entity).join(' '), r.jev_tactic, r.event_id].join(' ').toLowerCase().includes(text)) { return false; }
      return true;
    }).sort((a, b) => {
      let ua = URG.indexOf(a.jev_urgency); let ub = URG.indexOf(b.jev_urgency);
      ua = ua < 0 ? 9 : ua; ub = ub < 0 ? 9 : ub;
      return ua !== ub ? ua - ub : (num(b.jev_disposition_confidence) || 0) - (num(a.jev_disposition_confidence) || 0);
    });
  }, [rows, f]);

  const listRow = (rows || []).find((x) => x.event_id === sel) || {};
  return (
    <div className={`jev-root${theme === 'dark' ? ' dark' : ''}`}>
      <div className="jev-top">
        <div><h1>{T.title}</h1><div className="desc">{T.desc}</div></div>
        <LangSwitch lang={lang} onChange={setLang} />
      </div>
      <Filters T={T} f={f} setF={setF} onRefresh={load} />
      {err && <Message type="error">{err}</Message>}
      <Tiles T={T} rows={rows || []} f={f} setF={setF} />
      <div className="jev-split">
        <div className="jev-list">{rows == null ? <div className="jev-empty">{T.loading}</div>
          : <FindingsTable T={T} rows={shown} sel={sel} onSelect={setSel} />}</div>
        {sel && <Pane key={sel} T={T} lang={lang} id={sel} listRow={listRow} onClose={() => setSel(null)} onChanged={load} />}
      </div>
    </div>
  );
}

injectCss();
if (ensureLocale()) getUserTheme().catch(() => 'light').then((theme) => {
  layout(<TriagePage theme={theme} />, { pageTitle: 'Jev Triage', theme, hideFooter: true });
});
