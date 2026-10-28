// Setup page section "Prompts (support)": support mode for the Jev questions.
// Everything goes through | jevprompt (server-side checks for admin, support mode, structure, tests and audit).
import { useEffect, useState } from 'react';
import Button from '@splunk/react-ui/Button';
import Select from '@splunk/react-ui/Select';
import Text from '@splunk/react-ui/Text';
import TextArea from '@splunk/react-ui/TextArea';
import ControlGroup from '@splunk/react-ui/ControlGroup';
import Message from '@splunk/react-ui/Message';
import { search, job, q, b64 } from '../../common/api';
import { fmt } from '../../common/i18n';

const L = {
  en: {
    title: 'Prompts (support)',
    desc: 'The Jev questions are locked. An admin can open support mode for a limited time to change their wording (names, types, choice keys and the four urgency levels stay as shipped). Every change is a new version that must pass a test before it can be applied, and the shipped questions are always one click away. Each decision model has its own version. All actions are recorded in index=jev_triage sourcetype=jev:prompt:audit.',
    inUse: 'In use', model: 'Decision model', shipped: 'shipped questions ({v})', appliedBy: 'applied by {by} at {at}', revert: 'Back to shipped',
    locked: 'Locked. Start support mode to edit, test, apply or import.', noAdmin: 'Only admins (edit_storage_passwords or admin_all_objects) can use support mode. You can see the versions in use.',
    reason: 'Reason', reasonPh: 'Why (recorded in the audit log), e.g. support case 1234', hours: 'Hours', start: 'Start support mode',
    on: 'Support mode is on until {t} (started by {by}: {r}).', end: 'End support mode', needReason: 'Enter a reason first.',
    versions: 'Versions', cols: ['Version', 'Model', 'Status', 'Author', 'Created', 'Reason', 'Test', ''],
    edit: 'Edit from this', test: 'Test', apply: 'Apply', exp: 'Export', none: 'No versions yet.',
    editor: 'Edit the questions', from: 'Starting from: {v}', forModel: 'For decision model', instructions: 'instructions', examples: 'examples (one per line)',
    changed: '{n} text(s) changed from the shipped questions.', save: 'Save draft', cancel: 'Close editor', saved: 'Saved as draft {id} ({n} changes). Test it next.',
    testing: 'Testing… {s} s (each finding is triaged with the current and the new version; Jev is called 4 times per finding)',
    tested: 'Test of {id}: {s}', blocked: 'This version cannot be applied: more TP findings are missed than with the current version.', warn: 'Check: ',
    chCols: ['Finding', 'Rule', 'Current', 'This version', 'Answer'],
    applied: 'Applied {id} for {m}. New triage results use it.', reverted: 'Shipped questions are in use again for {m}.',
    imp: 'Import a version (JSON exported from another environment)', imported: 'Imported as draft {id}. Test it before applying.',
    evalTitle: 'Test answers (jev_eval_set.csv)',
    evalDesc: 'A test compares the current and the new version on the findings in the lookup file jev_eval_set.csv (columns finding_id, disposition, urgency, note; disposition TP / FP / Benign / Undetermined, urgency low / medium / high / critical). Without it, the last 33 triaged findings are used and only the changes are shown. Upload it in Settings > Lookups > Lookup table files (app TA-jev-triage). To start the table, copy the LLM prompt below (it contains the facts of the last 33 findings), paste it into an LLM, check every row yourself, then upload the CSV.',
    evalBtn: 'Make LLM prompt for test answers', copied: 'Copied to the clipboard ({n} findings). It is also shown below.',
    err: 'Failed: ',
  },
  ja: {
    title: 'プロンプト（サポート用）',
    desc: 'Jev の質問は鍵がかかっています。管理者は期限付きでサポートモードを開き、文言だけを変更できます（質問の名前と種類、選択肢のキー、Urgency の4段階は既定のまま）。変更はすべて新しい版になり、試験を通るまで適用できません。いつでも1クリックで既定の質問に戻せます。版は判定モデルごとに持ちます。操作はすべて index=jev_triage sourcetype=jev:prompt:audit に記録します。',
    inUse: '使用中', model: '判定モデル', shipped: '既定の質問（{v}）', appliedBy: '{at} に {by} が適用', revert: '既定に戻す',
    locked: '鍵がかかっています。編集・試験・適用・読み込みにはサポートモードを開始してください。', noAdmin: 'サポートモードを使えるのは管理者（edit_storage_passwords または admin_all_objects）だけです。使用中の版は確認できます。',
    reason: '理由', reasonPh: '理由（監査ログに記録）。例: 問い合わせ 1234', hours: '時間', start: 'サポートモードを開始',
    on: 'サポートモード中です（{t} まで、開始 {by}: {r}）。', end: 'サポートモードを終了', needReason: '先に理由を入力してください。',
    versions: '版', cols: ['版', 'モデル', '状態', '作成者', '作成', '理由', '試験', ''],
    edit: 'これを元に編集', test: '試験', apply: '適用', exp: '書き出し', none: 'まだ版はありません。',
    editor: '質問の編集', from: '元にした版: {v}', forModel: '対象の判定モデル', instructions: 'instructions', examples: 'examples（1行に1つ）',
    changed: '既定の質問から {n} か所変更しています。', save: '下書きを保存', cancel: '編集を閉じる', saved: '下書き {id} として保存しました（{n} か所）。次に試験してください。',
    testing: '試験中… {s} 秒（各 Finding を今の版と新しい版でトリアージします。Jev は1件あたり4回）',
    tested: '{id} の試験: {s}', blocked: 'この版は適用できません: 今の版より TP の見逃しが増えています。', warn: '確認してください: ',
    chCols: ['Finding', 'ルール', '今の版', 'この版', '正解'],
    applied: '{m} 向けに {id} を適用しました。新しいトリアージ結果から使われます。', reverted: '{m} は既定の質問に戻りました。',
    imp: '版の読み込み（別の環境で書き出した JSON）', imported: '下書き {id} として読み込みました。適用の前に試験してください。',
    evalTitle: '試験の正解表（jev_eval_set.csv）',
    evalDesc: '試験では、ルックアップファイル jev_eval_set.csv（列 finding_id, disposition, urgency, note。disposition は TP / FP / Benign / Undetermined、urgency は low / medium / high / critical）の Finding で今の版と新しい版を比べます。ない場合は直近にトリアージした33件を使い、変わった件だけを表示します。設定 > ルックアップ > ルックアップテーブルファイル（アプリ TA-jev-triage）にアップロードしてください。作り始めるときは、下のボタンで LLM 用のプロンプト（直近33件の事実を含む）をコピーして LLM に貼り、全行を自分で確認してから CSV をアップロードしてください。',
    evalBtn: '正解表を作る LLM 用プロンプトを作成', copied: 'クリップボードにコピーしました（{n} 件）。下にも表示しています。',
    err: '失敗しました: ',
  },
};

const ts = (v) => (v ? new Date(Number(v) * 1000).toLocaleString() : '');

function changedCount(a, b) {
  let n = 0;
  const walk = (x, y) => {
    if (x && typeof x === 'object' && y && typeof y === 'object') {
      const keys = Array.isArray(x) ? [...Array(Math.max(x.length, y.length)).keys()] : Object.keys(x);
      keys.forEach((k) => walk(x[k], y[k]));
    } else if (x !== y) { n += 1; }
  };
  walk(a, b);
  return n;
}

function QuestionsForm({ T, qs, setQs }) {
  const upd = (fn) => { const c = JSON.parse(JSON.stringify(qs)); fn(c); setQs(c); };
  const area = (value, onChange, rows = 2) => <TextArea value={value} rowsMin={rows} rowsMax={8} style={{ width: '100%', maxWidth: 'none' }} onChange={(e, { value: v }) => onChange(v)} />;
  return (
    <div>{Object.entries(qs).map(([name, item]) => (
      <div key={name} className="jev-card" style={{ margin: '10px 0', padding: 10 }}>
        <div><b>{name}</b> <span className="hint" style={{ margin: 0 }}>({item.type})</span></div>
        <ControlGroup label={T.instructions} labelWidth={160}>{area(item.instructions, (v) => upd((c) => { c[name].instructions = v; }))}</ControlGroup>
        {item.criteria && !Array.isArray(item.criteria) && Object.keys(item.criteria).map((k) => (
          <ControlGroup key={k} label={k} labelWidth={160}>{area(item.criteria[k], (v) => upd((c) => { c[name].criteria[k] = v; }))}</ControlGroup>))}
        {Array.isArray(item.criteria) && item.criteria.map((lv, i) => (
          <div key={i}>{/* eslint-disable-line react/no-array-index-key */}
            <ControlGroup label={`level ${i} what`} labelWidth={160}>{area(lv.what, (v) => upd((c) => { c[name].criteria[i].what = v; }))}</ControlGroup>
            <ControlGroup label={T.examples} labelWidth={160}>{area((lv.examples || []).join('\n'),
              (v) => upd((c) => { c[name].criteria[i].examples = v.split('\n').map((x) => x.trim()).filter(Boolean); }), 3)}</ControlGroup>
          </div>))}
      </div>))}
    </div>);
}

export default function PromptPanel({ lang }) {
  const T = L[lang] || L.en;
  const [st, setSt] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState('');
  const [hours, setHours] = useState('4');
  const [ed, setEd] = useState(null);   // { from, base: questions, qs, model }
  const [shipped, setShipped] = useState(null);
  const [res, setRes] = useState(null);   // last test
  const [evalText, setEvalText] = useState('');

  const load = () => search('| jevprompt action=status').then((rows) => {
    const state = rows.find((r) => r.row === 'state') || {};
    setSt({ state, active: rows.filter((r) => r.row === 'active'), versions: rows.filter((r) => r.row === 'version') });
  }, (e) => setMsg({ type: 'error', text: T.err + e.message }));
  useEffect(() => { load(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!st) { return <div><h2 style={{ marginTop: 32 }}>{T.title}</h2>{msg ? <Message type={msg.type}>{msg.text}</Message> : '…'}</div>; }
  const s = st.state;
  const admin = s.can_edit === '1';
  const on = s.support_on === '1';
  const R = () => `reason=${q(reason)}`;
  const run = async (fn) => {
    setBusy(true); setMsg(null);
    try { await fn(); } catch (e) { setMsg({ type: 'error', text: T.err + e.message }); } finally { setBusy(false); load(); }
  };
  const needR = () => { if (!reason.trim()) { setMsg({ type: 'warning', text: T.needReason }); return false; } return true; };

  const startEdit = (id) => run(async () => {
    const [d] = await search('| jevprompt action=get id=default');
    const base = JSON.parse(d.content); setShipped(base);
    const src = id === 'default' ? d : (await search(`| jevprompt action=get id=${q(id)}`))[0];
    const v = st.versions.find((x) => x.id === id);
    setEd({ from: id === 'default' ? T.shipped.replace('{v}', d.base) : id, qs: JSON.parse(src.content), model: (v && v.model) || s.model_in_use });
  });
  const save = () => { if (!needR()) { return; } run(async () => {
    const [r] = await search(`| jevprompt action=save model=${q(ed.model)} ${R()} content=${q(b64(JSON.stringify(ed.qs)))}`);
    setMsg({ type: 'success', text: fmt(T.saved, { id: r.id, n: r.changes }) }); setEd(null);
  }); };
  const test = (id) => run(async () => {
    setMsg({ type: 'info', text: fmt(T.testing, { s: 0 }) }); setRes(null);
    const [r] = await job(`| jevprompt action=test id=${q(id)}`, { onProgress: (sec) => setMsg({ type: 'info', text: fmt(T.testing, { s: sec }) }) });
    const t = JSON.parse(r.test || '{}');
    setRes({ id, t });
    setMsg({ type: t.blocked ? 'error' : (t.warnings || []).length ? 'warning' : 'success',
      text: `${fmt(T.tested, { id, s: t.summary })}${t.blocked ? ` ${T.blocked}` : ''}${(t.warnings || []).length ? ` ${T.warn}${t.warnings.join(', ')}` : ''}` });
  });
  const apply = (id) => { if (!needR()) { return; } run(async () => {
    const [r] = await search(`| jevprompt action=apply id=${q(id)} ${R()}`);
    setMsg({ type: 'success', text: fmt(T.applied, { id: r.id, m: r.model }) });
  }); };
  const revert = (m) => { if (!needR()) { return; } run(async () => {
    const [r] = await search(`| jevprompt action=revert model=${q(m)} ${R()}`);
    setMsg({ type: 'success', text: fmt(T.reverted, { m: r.model }) });
  }); };
  const exp = (id) => run(async () => {
    const [r] = await search(`| jevprompt action=export id=${q(id)}`);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([r.export], { type: 'application/json' })); a.download = r.filename; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  });
  const imp = (file) => { if (!file) { return; } if (!needR()) { return; } run(async () => {
    const text = await file.text();
    const [r] = await search(`| jevprompt action=import ${R()} content=${q(b64(text))}`);
    setMsg({ type: r.warning ? 'warning' : 'success', text: fmt(T.imported, { id: r.id }) + (r.warning ? ` ${r.warning}` : '') });
  }); };
  const evalPrompt = () => run(async () => {
    const [r] = await search(`| jevprompt action=evalset_prompt lang=${lang === 'ja' ? 'ja' : 'en'}`);
    setEvalText(r.prompt || '');
    try { await navigator.clipboard.writeText(r.prompt || ''); } catch (e) { /* shown below */ }
    setMsg({ type: 'success', text: fmt(T.copied, { n: r.count }) });
  });

  const models = [...new Set([s.model_in_use, ...st.active.map((a) => a.model), ...st.versions.map((v) => v.model)].filter(Boolean))];
  return (
    <div>
      <h2 style={{ marginTop: 32 }}>{T.title}</h2>
      <div className="hint">{T.desc}</div>
      <table className="jev-check" style={{ width: '100%' }}><thead><tr><th>{T.model}</th><th>{T.inUse}</th><th /></tr></thead>
        <tbody>{models.map((m) => {
          const a = st.active.find((x) => x.model === m);
          return (
            <tr key={m}><td>{m}{m === s.model_in_use ? ' *' : ''}</td>
              <td>{a ? `${a.id} (${fmt(T.appliedBy, { by: a.applied_by, at: ts(a.applied_at) })})` : fmt(T.shipped, { v: s.default_version })}</td>
              <td>{a && admin && <Button appearance="secondary" label={T.revert} onClick={() => revert(m)} disabled={busy} />}</td></tr>);
        })}</tbody></table>
      {!admin && <Message type="info">{T.noAdmin}</Message>}
      {admin && (
        <ControlGroup label={T.reason} labelWidth={160}>
          <Text value={reason} placeholder={T.reasonPh} onChange={(e, { value }) => setReason(value)} style={{ maxWidth: 420 }} />
          {!on && <Select value={hours} onChange={(e, { value }) => setHours(value)} style={{ width: 90, marginLeft: 8 }}>
            {['1', '2', '4', '8', '12', '24'].map((h) => <Select.Option key={h} value={h} label={`${h} ${T.hours}`} />)}</Select>}
          {!on && <Button appearance="primary" label={T.start} style={{ marginLeft: 8 }} disabled={busy}
            onClick={() => { if (needR()) { run(() => search(`| jevprompt action=support_on ${R()} hours=${hours}`)); } }} />}
          {on && <Button label={T.end} style={{ marginLeft: 8 }} disabled={busy} onClick={() => run(() => search('| jevprompt action=support_off'))} />}
        </ControlGroup>)}
      {admin && !on && <Message type="info">{T.locked}</Message>}
      {on && <Message type="warning">{fmt(T.on, { t: ts(s.support_expires), by: s.support_by, r: s.support_reason })}</Message>}
      {msg && <Message type={msg.type}>{msg.text}</Message>}

      <h3>{T.versions}</h3>
      {admin && on && <div className="jev-actions" style={{ margin: '6px 0' }}>
        <Button label={`${T.edit}: ${fmt(T.shipped, { v: s.default_version })}`} onClick={() => startEdit('default')} disabled={busy} />
        <span className="hint" style={{ margin: '0 0 0 12px' }}>{T.imp}</span>
        <input type="file" accept=".json,application/json" disabled={busy} onChange={(e) => { imp(e.target.files[0]); e.target.value = ''; }} />
      </div>}
      {st.versions.length ? (
        <table className="jev-check" style={{ width: '100%' }}><thead><tr>{T.cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{st.versions.map((v) => (
            <tr key={v.id}><td>{v.id}{v.imported_from ? ' (import)' : ''}</td><td>{v.model}</td><td>{v.status}</td><td>{v.author}</td><td>{ts(v.created)}</td>
              <td>{v.reason}</td><td>{v.tested === '1' ? `${v.test_blocked === '1' ? 'NG: ' : ''}${v.test_summary}` : ''}</td>
              <td style={{ whiteSpace: 'nowrap' }}>{admin && <>
                {on && <Button appearance="secondary" label={T.edit} onClick={() => startEdit(v.id)} disabled={busy} />}
                {on && <Button appearance="secondary" label={T.test} onClick={() => test(v.id)} disabled={busy} />}
                {on && v.status !== 'active' && <Button appearance="primary" label={T.apply} onClick={() => apply(v.id)}
                  disabled={busy || v.tested !== '1' || v.test_blocked === '1'} />}
                <Button appearance="secondary" label={T.exp} onClick={() => exp(v.id)} disabled={busy} /></>}</td></tr>))}
          </tbody></table>) : <div className="hint">{T.none}</div>}

      {res && res.t.changes && res.t.changes.length > 0 && (
        <table className="jev-check" style={{ width: '100%' }}><thead><tr>{T.chCols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{res.t.changes.map((c) => <tr key={c.event_id}><td>{c.event_id.slice(0, 8)}</td><td>{c.rule_name}</td><td>{c.cur}</td><td>{c.new}</td><td>{c.truth}</td></tr>)}</tbody></table>)}

      {ed && (
        <div style={{ marginTop: 16 }}>
          <h3>{T.editor}</h3>
          <div className="hint">{fmt(T.from, { v: ed.from })}</div>
          <ControlGroup label={T.forModel} labelWidth={160}>
            <Text value={ed.model} onChange={(e, { value }) => setEd({ ...ed, model: value })} style={{ maxWidth: 300 }} />
          </ControlGroup>
          <QuestionsForm T={T} qs={ed.qs} setQs={(qs) => setEd({ ...ed, qs })} />
          {shipped && <div className="hint">{fmt(T.changed, { n: changedCount(shipped, ed.qs) })}</div>}
          <div className="jev-actions" style={{ margin: '8px 0' }}>
            <Button appearance="primary" label={T.save} onClick={save} disabled={busy} />
            <Button label={T.cancel} onClick={() => setEd(null)} disabled={busy} />
          </div>
        </div>)}

      {admin && <>
        <h3>{T.evalTitle}</h3>
        <div className="hint">{T.evalDesc}</div>
        <div className="jev-actions" style={{ margin: '6px 0' }}><Button label={T.evalBtn} onClick={evalPrompt} disabled={busy} /></div>
        {evalText && <TextArea value={evalText} rowsMin={6} rowsMax={16} readOnly />}
      </>}
    </div>);
}
