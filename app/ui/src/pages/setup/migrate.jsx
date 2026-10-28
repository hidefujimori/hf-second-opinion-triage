// Setup page section shown only while the old app TA-jev-triage (before 0.11.0) is installed:
// copy its settings, keys and KV data into this app with | jevmigrate.
import { useEffect, useState } from 'react';
import Button from '@splunk/react-ui/Button';
import Message from '@splunk/react-ui/Message';
import { rest, search } from '../../common/api';

const L = {
  en: {
    title: 'Move from TA-jev-triage', desc: 'This app was renamed in 0.11.0 (TA-jev-triage → second_opinion_triage), so Splunk sees it as a new app. Copy the settings, API keys and stored results of the old app here, then disable or remove the old app and restart Splunk. The lookup jev_eval_set.csv is not copied: upload it again if you use it.',
    plan: 'Check what will be copied', run: 'Copy now', busy: 'Working…', cols: ['Item', 'Status', 'Detail', 'Count'], done: 'Copied. Next: disable or remove TA-jev-triage, restart Splunk, reload this page and run Test connection.', admin: 'Only admins can copy.',
  },
  ja: {
    title: 'TA-jev-triage からの移行', desc: '0.11.0 でアプリ名を変更しました（TA-jev-triage → second_opinion_triage）。Splunk からは新しいアプリに見えるため、旧アプリの設定・API キー・保存済みの結果をここにコピーしてください。その後、旧アプリを無効化または削除し、Splunk を再起動します。ルックアップ jev_eval_set.csv はコピーしないので、使っている場合はアップロードし直してください。',
    plan: 'コピーする内容を確認', run: 'コピーする', busy: '実行中…', cols: ['項目', '状態', '内容', '件数'], done: 'コピーしました。次に TA-jev-triage を無効化または削除し、Splunk を再起動してから、このページを開き直して接続テストを行ってください。', admin: 'コピーできるのは管理者だけです。',
  },
};

export default function MigratePanel({ lang, canSave }) {
  const T = L[lang] || L.en;
  const [old, setOld] = useState(null);
  const [rows, setRows] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    rest('/apps/local/TA-jev-triage').then((d) => setOld(((d.entry || [])[0] || {}).content || {}), () => setOld(false));
  }, []);
  if (!old) { return null; }
  const go = async (action) => {
    setBusy(true); setMsg(null);
    try {
      const r = await search(`| jevmigrate action=${action}`);
      setRows(r);
      if (action === 'run') { setMsg({ type: r.some((x) => x.status === 'error') ? 'warning' : 'success', text: T.done }); }
    } catch (e) { setMsg({ type: 'error', text: e.message }); } finally { setBusy(false); }
  };
  return (
    <div>
      <h2 style={{ marginTop: 24 }}>{T.title}</h2>
      <Message type="warning">{T.desc}</Message>
      {canSave ? (
        <div className="jev-actions" style={{ margin: '8px 0' }}>
          <Button label={T.plan} onClick={() => go('plan')} disabled={busy} />
          <Button appearance="primary" label={T.run} onClick={() => go('run')} disabled={busy} />
          {busy && <span className="hint" style={{ margin: 0 }}>{T.busy}</span>}
        </div>) : <div className="hint">{T.admin}</div>}
      {msg && <Message type={msg.type}>{msg.text}</Message>}
      {rows && (
        <table className="jev-check" style={{ width: '100%' }}><thead><tr>{T.cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i}><td>{r.item}</td><td>{r.status}</td><td>{r.detail}</td><td>{r.count}</td></tr>)}</tbody></table>)}{/* eslint-disable-line react/no-array-index-key */}
    </div>);
}
