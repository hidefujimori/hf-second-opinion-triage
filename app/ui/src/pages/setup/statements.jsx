// Setup page section "Analyst statements": the statements an analyst can give to a re-triage (1.1).
// Built-in ones ship with the app (bin/jev_triage/conditions.py); admins add their own here (KV jev_conditions).
// The same checks run in the search commands, which ignore a statement that does not pass them.
import { useCallback, useEffect, useState } from 'react';
import Button from '@splunk/react-ui/Button';
import Text from '@splunk/react-ui/Text';
import ControlGroup from '@splunk/react-ui/ControlGroup';
import Message from '@splunk/react-ui/Message';
import { search, kv } from '../../common/api';
import { fmt } from '../../common/i18n';

const COLL = 'jev_conditions';
const MAX_TEXT = 240;
const L = {
  en: {
    title: 'Analyst statements (re-triage)',
    desc: 'On the triage page an analyst can re-triage a finding with up to 3 of these statements, for what they know and the SIEM does not. The decision model reads the English text and takes it as true; the result without the statements is kept beside it and every attempt is written to the Note. Built-in statements cannot be changed; add your own below.',
    builtin: 'Built-in', custom: 'Added by admins', cols: ['ID', 'Label (English)', 'Label (Japanese)', 'Text sent to the decision model', ''],
    none: 'No statements added yet.', add: 'Add a statement', id: 'ID', labelEn: 'Label (English)', labelJa: 'Label (Japanese)', text: 'Text (English, sent to the decision model)',
    idHint: 'lower-case letters, digits and _ (2-40), e.g. vendor_maintenance', textHint: 'One sentence that starts with "The analyst confirmed ..." or "The analyst knows ...". English only, at most {n} characters.',
    save: 'Add', del: 'Delete', disable: 'Turn off', enable: 'Turn on', off: '(off)', saved: 'Saved.', deleted: 'Deleted.', noAdmin: 'Only admins can add or change statements.',
    eId: 'ID: lower-case letters, digits and _ (2-40 characters, starting with a letter).', eDup: 'This ID is already used.', eText: 'Text is required.',
    eLong: 'Text: at most {n} characters.', eAscii: 'Text: English (ASCII) only - the decision model reads English.', eLabel: 'Enter a label.',
  },
  ja: {
    title: 'アナリストの申告（再トリアージ）',
    desc: 'トリアージ画面で、アナリストはここにある申告を3つまで選んで Finding を再トリアージできます。SIEM にはない、アナリストが知っていることを伝えるためのものです。判定モデルは英文を読み、申告を正しいものとして扱います。申告なしの判定も並べて残り、試した内容はすべて Note に書かれます。組み込みの申告は変更できません。下で独自の申告を追加できます。',
    builtin: '組み込み', custom: '管理者が追加', cols: ['ID', '名前（英語）', '名前（日本語）', '判定モデルに渡す英文', ''],
    none: 'まだ追加された申告はありません。', add: '申告を追加', id: 'ID', labelEn: '名前（英語）', labelJa: '名前（日本語）', text: '英文（判定モデルに渡します）',
    idHint: '英小文字・数字・_（2〜40文字）。例: vendor_maintenance', textHint: '"The analyst confirmed ..." や "The analyst knows ..." で始まる1文。英語のみ、{n}文字まで。',
    save: '追加', del: '削除', disable: '無効にする', enable: '有効にする', off: '（無効）', saved: '保存しました。', deleted: '削除しました。', noAdmin: '申告の追加・変更は管理者だけができます。',
    eId: 'ID: 英小文字・数字・_ で、英字から始まる2〜40文字にしてください。', eDup: 'この ID はすでに使われています。', eText: '英文を入力してください。',
    eLong: '英文は {n} 文字までです。', eAscii: '英文は英語（ASCII）だけにしてください。判定モデルは英語を読みます。', eLabel: '名前を入力してください。',
  },
};

export function check(c, used, T) {
  if (!/^[a-z][a-z0-9_]{1,39}$/.test(c.id || '')) { return T.eId; }
  if (used.includes(c.id)) { return T.eDup; }
  const text = (c.text || '').trim();
  if (!text) { return T.eText; }
  if (text.length > MAX_TEXT) { return fmt(T.eLong, { n: MAX_TEXT }); }
  if (/[^\x20-\x7e]/.test(text)) { return T.eAscii; }
  if (!(c.label_en || c.label_ja || '').trim()) { return T.eLabel; }
  return '';
}

export default function StatementsPanel({ lang, canSave }) {
  const T = L[lang] || L.en;
  const [builtin, setBuiltin] = useState([]);
  const [rows, setRows] = useState(null);
  const [form, setForm] = useState({ id: '', label_en: '', label_ja: '', text: '' });
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    search('| jevstatements').then((r) => setBuiltin(r.filter((x) => String(x.custom) !== '1')), () => setBuiltin([]));
    kv(COLL).then((r) => setRows(Array.isArray(r) ? r : []), () => setRows([]));
  }, []);
  useEffect(load, [load]);
  const used = [...builtin.map((b) => b.id), ...(rows || []).map((r) => r.id || r._key)];
  const act = async (fn, okText) => {
    setBusy(true); setMsg(null);
    try { await fn(); setMsg({ type: 'success', text: okText }); load(); } catch (e) { setMsg({ type: 'error', text: e.message }); } finally { setBusy(false); }
  };
  const add = () => {
    const c = { ...form, id: form.id.trim(), text: form.text.trim(), label_en: form.label_en.trim(), label_ja: form.label_ja.trim() };
    const e = check(c, used, T);
    if (e) { setMsg({ type: 'error', text: e }); return; }
    act(async () => { await kv(COLL, { method: 'POST', doc: { _key: c.id, ...c, enabled: '1', created: Math.floor(Date.now() / 1000) } }); setForm({ id: '', label_en: '', label_ja: '', text: '' }); }, T.saved);
  };
  const toggle = (r) => act(() => kv(COLL, { method: 'POST', key: r._key, doc: { ...r, enabled: String(r.enabled) === '0' ? '1' : '0' } }), T.saved);
  const del = (r) => act(() => kv(COLL, { method: 'DELETE', key: r._key }), T.deleted);
  const cell = { padding: '3px 6px', verticalAlign: 'top', borderTop: '1px solid var(--line)' };
  return (
    <div>
      <h2>{T.title}</h2>
      <p className="hint">{T.desc}</p>
      <table className="jev-check" style={{ width: '100%' }}>
        <thead><tr>{T.cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {builtin.map((b) => (
            <tr key={b.id}><td style={cell}>{b.id}</td><td style={cell}>{b.label_en}</td><td style={cell}>{b.label_ja}</td>
              <td style={cell}>{b.text}</td><td style={cell} className="hint">{T.builtin}</td></tr>))}
          {(rows || []).map((r) => (
            <tr key={r._key}><td style={cell}>{r.id || r._key}{String(r.enabled) === '0' ? ` ${T.off}` : ''}</td><td style={cell}>{r.label_en}</td>
              <td style={cell}>{r.label_ja}</td><td style={cell}>{r.text}</td>
              <td style={cell}>{canSave && (
                <>
                  <Button appearance="pill" label={String(r.enabled) === '0' ? T.enable : T.disable} onClick={() => toggle(r)} disabled={busy} />
                  <Button appearance="pill" label={T.del} onClick={() => del(r)} disabled={busy} />
                </>)}</td></tr>))}
        </tbody>
      </table>
      {rows && rows.length === 0 && <p className="hint">{T.none}</p>}
      {canSave ? (
        <div style={{ marginTop: 10 }}>
          <h3>{T.add}</h3>
          <ControlGroup label={T.id} labelWidth={240} help={T.idHint}>
            <Text value={form.id} onChange={(e, { value }) => setForm({ ...form, id: value })} /></ControlGroup>
          <ControlGroup label={T.labelEn} labelWidth={240}>
            <Text value={form.label_en} onChange={(e, { value }) => setForm({ ...form, label_en: value })} /></ControlGroup>
          <ControlGroup label={T.labelJa} labelWidth={240}>
            <Text value={form.label_ja} onChange={(e, { value }) => setForm({ ...form, label_ja: value })} /></ControlGroup>
          <ControlGroup label={T.text} labelWidth={240} help={fmt(T.textHint, { n: MAX_TEXT })}>
            <Text value={form.text} onChange={(e, { value }) => setForm({ ...form, text: value })} /></ControlGroup>
          <Button appearance="primary" label={T.save} onClick={add} disabled={busy} />
        </div>) : <p className="hint">{T.noAdmin}</p>}
      {msg && <Message type={msg.type}>{msg.text}</Message>}
    </div>
  );
}
