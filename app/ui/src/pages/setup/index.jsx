// Setup page: Jev / enrichment / LLM / Note settings and API keys.
// Keys go to storage/passwords (realm TA-jev-triage) and are never read back to the browser:
// the page only learns whether a key exists (| rest ... | table username).
import { useEffect, useState } from 'react';
import layout from '@splunk/react-page/18';
import { getUserTheme } from '@splunk/splunk-utils/themes';
import Button from '@splunk/react-ui/Button';
import Select from '@splunk/react-ui/Select';
import Text from '@splunk/react-ui/Text';
import Checkbox from '@splunk/react-ui/Checkbox';
import ControlGroup from '@splunk/react-ui/ControlGroup';
import Message from '@splunk/react-ui/Message';
import { rest, search, APP } from '../../common/api';
import { useLang, ensureLocale } from '../../common/i18n';
import { injectCss } from '../../common/styles';
import { collect, download } from './support';
import LangSwitch from '../../common/LangSwitch';
import PromptPanel from './prompts';

const REALM = APP;
const L = {
  en: {
    title: 'Jev Triage Setup', desc: 'Connection settings for Jev and the LLM. Keys are kept in Splunk\'s encrypted credential store and are never shown again after saving.',
    stored: 'stored', notset: 'not set', remove: 'remove', keyPh: 'Enter a new value to set or replace',
    save: 'Save', test: 'Test connection', testHint: 'Uses the saved settings (save first). Sends one tiny request to Jev and to the LLM.',
    saving: 'Saving…', saved: 'Saved. Changes apply to the next search; no restart needed.', saveFail: 'Save failed: ',
    testing: 'Testing…', bothOk: 'Both connections work.', seeTable: 'See the table for what is missing or failing.', testFail: 'Test failed: ',
    supTitle: 'Support', supDesc: 'Makes a diagnostics file to send with a question or problem report: versions, settings, a connection test, recent errors, response-action results and app logs of the last 24 hours. API keys are never included, and the hosts of the endpoint and proxy are hidden. Anyone who can open this page can make it (beta).',
    supBtn: 'Make diagnostics file', supBusy: 'Collecting… ', supDone: 'Saved as a download. Items collected: ', supMissing: ' Not collected (no permission or no data): ',
    check: 'Check: ', proxyPw: 'Proxy URL must not contain user:password@', unsaved: 'Not saved yet. Click Save, then Test connection.', testUnsaved: 'Save first: Test connection uses the saved settings.', badUrl: ' must start with http:// or https://', urlEx: ' (e.g. http://<host>:11434/v1)', noCap: 'Your role cannot save keys (needs edit_storage_passwords or admin_all_objects). You can view settings.',
    loadFail: 'Could not load settings: ', aclFail: 'Could not share these keys with the jev_triage_user role: ', none: '(none)', cols: ['Target', 'Key', 'Model', 'Status', 'Detail', 'ms'],
    sections: {
      jev: ['TypeSafe Jev', 'Jev suggests the disposition and urgency. The Splunk search head must reach https://api.typesafe.ai (or the endpoint below). Keys can be read by admins and the role jev_triage_user (give that role to your analysts).'],
      enrichment: ['Enrichment', 'Facts collected with SPL before asking Jev. Point the macros at your indexes; the default index=* is slow.'],
      llm: ['LLM explanation', 'Used only when someone clicks Explain. Choose any provider; the credential is stored per app.'],
      note: ['Notes on ES findings', ''],
      limits: ['Limits for automatic runs', 'Daily limits for automatic runs only (detections through the Jev Triage response action, and the scheduled search). Manual actions are not limited. Empty = no limit, 0 = none per day. A day is the Splunk server\'s local calendar day.'],
    },
    usage: 'Used today', usageCols: ['Jev (automatic)', 'Jev (manual)', 'LLM explanations (automatic)', 'LLM explanations (manual)'], usageNone: 'Nothing counted yet today.',
    f: {
      typesafe_api_key: 'Jev API key', model: 'Model|Pinned version. Change only after re-checking accuracy.',
      jev_api_endpoint: 'Endpoint|TypeSafe: https://api.typesafe.ai/v1/systemone (default). Another server with the same System One API, e.g. llama.cpp: http://<host>:8081/v1/systemone (the API key may be empty). Re-check accuracy before switching.',
      confidence_threshold: 'Confidence threshold|Below this, the disposition is Undetermined (0–1)',
      escalation_floor: 'Escalation floor|requires_escalation at or above this raises urgency to at least High (0–1)',
      rollup_urgency_cap: 'Roll-up urgency cap', order_check: 'Option-order check|Second call with reversed options (2 calls per finding)',
      timeout: 'Timeout (seconds)', parallel: 'Parallel findings|Findings processed at the same time (1–8)',
      proxy: 'HTTPS proxy|e.g. http://proxy.example.com:8080 — do not put a password in this URL',
      enabled: 'Enabled', max_facts: 'Max facts per finding', shared_entities: 'Shared entities|Comma-separated patterns never used as join keys',
      jev_cloudtrail: 'CloudTrail data|Macro jev_cloudtrail, e.g. index=aws sourcetype=aws:cloudtrail',
      jev_endpoint: 'Endpoint process data|Macro jev_endpoint, e.g. index=wineventlog OR index=sysmon',
      llm_api_key: 'LLM API key', aws_access_key_id: 'AWS access key ID', aws_secret_access_key: 'AWS secret access key',
      provider: 'Provider|openai = any OpenAI-compatible endpoint; gemini = Google Gemini API (incl. Gemma 4)',
      llm_model: 'Model|e.g. gemma-4-26b-a4b-it, or your provider\'s model id', endpoint: 'Endpoint|Optional base URL with http:// or https://. Ollama: http://<host>:11434/v1, Apple fm serve: http://<mac>:1976/v1',
      region: 'AWS region', thinking_level: 'Thinking level|gemini: Gemma 4 minimal makes answers ~1 s (empty for Gemini models). openai: sent as reasoning_effort; Ollama: gemma4 / qwen3 need none, gpt-oss needs low',
      max_tokens: 'Max tokens', llm_timeout: 'Timeout (seconds)', language: 'Default language', llm_proxy: 'HTTPS proxy|Do not put a password in this URL',
      note_language: 'Note language',
      jev_auto_daily: 'Jev triage per day (automatic)|Findings sent to Jev per day by automatic runs',
      llm_auto_daily: 'LLM explanations per day (automatic)|Only when the response action has “Explain with LLM” on. Default 100',
    },
  },
  ja: {
    title: 'Jev Triage 設定', desc: 'Jev と LLM の接続設定です。キーは Splunk の暗号化された資格情報ストアに保存され、保存後は表示されません。',
    stored: '保存済み', notset: '未設定', remove: '削除', keyPh: '設定・置き換える場合は新しい値を入力',
    save: '保存', test: '接続テスト', testHint: '保存済みの設定を使います（先に保存してください）。Jev と LLM にそれぞれ小さな要求を1回送ります。',
    saving: '保存中…', saved: '保存しました。次の検索から反映されます（再起動は不要）。', saveFail: '保存に失敗しました: ',
    testing: 'テスト中…', bothOk: 'Jev と LLM の両方に接続できました。', seeTable: '未設定・失敗の内容は表を確認してください。', testFail: 'テストに失敗しました: ',
    supTitle: 'サポート', supDesc: '問い合わせや不具合の報告に添える診断ファイルを作ります。内容は版、設定、接続テスト、最近のエラー、レスポンスアクションの結果、直近24時間のアプリのログです。API キーは含みません。エンドポイントとプロキシのホスト名は伏せます。このページを開ける人なら誰でも作れます（β版の間）。',
    supBtn: '診断ファイルを作成', supBusy: '収集中… ', supDone: 'ダウンロードとして保存しました。取得した項目: ', supMissing: ' 取得できなかった項目（権限がない・データがない）: ',
    check: '確認してください: ', proxyPw: 'プロキシの URL に user:password@ を含めないでください', unsaved: '変更はまだ保存されていません。保存してから接続テストを行ってください。', testUnsaved: '先に保存してください（接続テストは保存済みの設定を使います）。', badUrl: ' は http:// または https:// で始めてください', urlEx: '（例: http://<ホスト>:11434/v1）', noCap: 'このロールではキーを保存できません（edit_storage_passwords または admin_all_objects が必要）。設定の表示はできます。',
    loadFail: '設定を読み込めませんでした: ', aclFail: '次のキーを jev_triage_user ロールに共有できませんでした: ', none: '（なし）', cols: ['対象', 'キー', 'モデル', '状態', '詳細', 'ms'],
    sections: {
      jev: ['TypeSafe Jev', 'Jev が Disposition と Urgency を提案します。Splunk の検索ヘッドから https://api.typesafe.ai（または下のエンドポイント）に接続できる必要があります。キーを読めるのは管理者と jev_triage_user ロールです（アナリストのロールにこのロールを追加してください）。'],
      enrichment: ['Enrichment（情報収集）', 'Jev に聞く前に SPL で集める情報です。マクロを実際の index に向けてください（既定の index=* は遅くなります）。'],
      llm: ['LLM による説明', '「LLM で説明」を押したときだけ使います。プロバイダは選べます。資格情報はアプリごとに保存されます。'],
      note: ['ES の Finding への Note', ''],
      limits: ['自動実行の上限', '自動実行（検知から動く Jev Triage レスポンスアクションと定期検索）だけに適用する1日の上限です。手動の操作は制限しません。空欄 = 無制限、0 = 1日0件。1日は Splunk サーバーの現地時間で区切ります。'],
    },
    usage: '本日の使用量', usageCols: ['Jev（自動）', 'Jev（手動）', 'LLM 説明（自動）', 'LLM 説明（手動）'], usageNone: '本日はまだ使用していません。',
    f: {
      typesafe_api_key: 'Jev の API キー', model: 'モデル|固定の版です。精度を再確認してから変更してください。',
      jev_api_endpoint: 'エンドポイント|TypeSafe: https://api.typesafe.ai/v1/systemone（既定）。同じ System One API の別サーバー、例: llama.cpp は http://<ホスト>:8081/v1/systemone（API キーは空でも可）。切り替える前に精度を再確認してください。',
      confidence_threshold: '確信度のしきい値|これ未満の Disposition は判別不可（0〜1）',
      escalation_floor: 'エスカレーションの下限|requires_escalation がこれ以上なら Urgency を High 以上に（0〜1）',
      rollup_urgency_cap: '集約アラートの Urgency 上限', order_check: '選択肢順の確認|選択肢を逆順にして2回目を呼ぶ（1件あたり2回）',
      timeout: 'タイムアウト（秒）', parallel: '同時処理数|同時に処理する Finding の数（1〜8）',
      proxy: 'HTTPS プロキシ|例: http://proxy.example.com:8080（URL にパスワードを入れないでください）',
      enabled: '有効', max_facts: '1件あたりの最大情報数', shared_entities: '共有リソース|結合キーに使わないパターン（カンマ区切り）',
      jev_cloudtrail: 'CloudTrail のデータ|マクロ jev_cloudtrail。例: index=aws sourcetype=aws:cloudtrail',
      jev_endpoint: 'エンドポイントのプロセスデータ|マクロ jev_endpoint。例: index=wineventlog OR index=sysmon',
      llm_api_key: 'LLM の API キー', aws_access_key_id: 'AWS アクセスキー ID', aws_secret_access_key: 'AWS シークレットアクセスキー',
      provider: 'プロバイダ|openai = OpenAI 互換の任意のエンドポイント、gemini = Google Gemini API（Gemma 4 を含む）',
      llm_model: 'モデル|例: gemma-4-26b-a4b-it、またはプロバイダのモデル ID', endpoint: 'エンドポイント|任意。http:// または https:// から書くベース URL。Ollama: http://<ホスト>:11434/v1、Apple fm serve: http://<Mac>:1976/v1',
      region: 'AWS リージョン', thinking_level: 'Thinking level|gemini: Gemma 4 は minimal で約1秒（Gemini モデルは空欄）。openai: reasoning_effort として送信。Ollama の gemma4・qwen3 は none、gpt-oss は low',
      max_tokens: '最大トークン数', llm_timeout: 'タイムアウト（秒）', language: '既定の言語', llm_proxy: 'HTTPS プロキシ|URL にパスワードを入れないでください',
      note_language: 'Note の言語',
      jev_auto_daily: 'Jev トリアージ / 日（自動）|自動実行で Jev に送る Finding の1日の上限',
      llm_auto_daily: 'LLM 説明 / 日（自動）|レスポンスアクションで「Explain with LLM」をオンにした場合だけ。既定 100',
    },
  },
};

// id: unique field id; label key in L.f; stanza+key for jev_triage.conf, or macro
const SECTIONS = [
  { id: 'jev', secrets: [{ name: 'typesafe_api_key' }], fields: [
    { id: 'jev_api_endpoint', stanza: 'jev', key: 'endpoint', url: true }, { id: 'model', stanza: 'jev', key: 'model' }, { id: 'confidence_threshold', stanza: 'jev', key: 'confidence_threshold', num: [0, 1] },
    { id: 'escalation_floor', stanza: 'jev', key: 'escalation_floor', num: [0, 1] },
    { id: 'rollup_urgency_cap', stanza: 'jev', key: 'rollup_urgency_cap', options: ['', 'low', 'medium', 'high', 'critical'] },
    { id: 'order_check', stanza: 'jev', key: 'order_check', options: ['true', 'false'], bool: true },
    { id: 'timeout', stanza: 'jev', key: 'timeout', num: [5, 300] }, { id: 'parallel', stanza: 'jev', key: 'parallel', num: [1, 8] },
    { id: 'proxy', stanza: 'jev', key: 'proxy', proxy: true }] },
  { id: 'enrichment', fields: [
    { id: 'enabled', stanza: 'enrichment', key: 'enabled', options: ['true', 'false'], bool: true },
    { id: 'max_facts', stanza: 'enrichment', key: 'max_facts', num: [1, 50] }, { id: 'shared_entities', stanza: 'enrichment', key: 'shared_entities' },
    { id: 'jev_cloudtrail', macro: 'jev_cloudtrail' }, { id: 'jev_endpoint', macro: 'jev_endpoint' }] },
  { id: 'llm', secrets: [{ name: 'llm_api_key', providers: ['anthropic', 'openai', 'gemini'] },
    { name: 'aws_access_key_id', providers: ['bedrock'] }, { name: 'aws_secret_access_key', providers: ['bedrock'] }], fields: [
    { id: 'provider', stanza: 'llm', key: 'provider', options: ['anthropic', 'openai', 'bedrock', 'gemini'] },
    { id: 'llm_model', stanza: 'llm', key: 'model' }, { id: 'endpoint', stanza: 'llm', key: 'endpoint', url: true, providers: ['anthropic', 'openai', 'gemini'] },
    { id: 'region', stanza: 'llm', key: 'region', providers: ['bedrock'] },
    { id: 'thinking_level', stanza: 'llm', key: 'thinking_level', options: ['', 'none', 'minimal', 'low'], providers: ['gemini', 'openai'] },
    { id: 'max_tokens', stanza: 'llm', key: 'max_tokens', num: [100, 4000] }, { id: 'llm_timeout', stanza: 'llm', key: 'timeout', num: [5, 300] },
    { id: 'language', stanza: 'llm', key: 'language', options: ['en', 'ja'] }, { id: 'llm_proxy', stanza: 'llm', key: 'proxy', proxy: true }] },
  { id: 'note', fields: [{ id: 'note_language', stanza: 'es_note', key: 'language', options: ['en', 'ja'] }] },
  { id: 'limits', usage: true, fields: [{ id: 'jev_auto_daily', stanza: 'limits', key: 'jev_auto_daily', num: [0, 1000000] },
    { id: 'llm_auto_daily', stanza: 'limits', key: 'llm_auto_daily', num: [0, 1000000] }] },
];
const ALL_FIELDS = SECTIONS.flatMap((s) => s.fields);
// Field ids must be unique: values are kept by id (0.9.15-0.10.3 had jev_endpoint twice, so the Jev endpoint and the
// macro jev_endpoint shared one value and the page could not be saved).
const DUP_IDS = ALL_FIELDS.map((f) => f.id).filter((id, i, a) => a.indexOf(id) !== i);
if (DUP_IDS.length) { throw new Error(`Setup page: duplicate field ids ${DUP_IDS.join(', ')}`); }
const ALL_SECRETS = SECTIONS.flatMap((s) => s.secrets || []);

function label(T, id) { const [l, h] = (T.f[id] || id).split('|'); return { l, h }; }
const entries = (d) => ((d && d.entry) || []);

function SetupPage({ theme }) {
  const [lang, setLang] = useLang();
  const T = L[lang];
  const [vals, setVals] = useState(null);
  const [stored, setStored] = useState({});
  const [secrets, setSecrets] = useState({});      // name -> new value
  const [removes, setRemoves] = useState({});
  const [msg, setMsg] = useState(null);
  const [check, setCheck] = useState(null);
  const [busy, setBusy] = useState(false);
  const [canSave, setCanSave] = useState(true);
  const [savedVals, setSavedVals] = useState(null);   // JSON of vals as last loaded / saved
  const [usage, setUsage] = useState(null);
  const [sup, setSup] = useState(null);   // { busy, text, type }   // { date, jev_auto, jev_manual, llm_auto, llm_manual }

  const loadUsage = () => rest('storage/collections/data/jev_usage', { params: { sort: 'date:-1', limit: 20 } })
    .then((docs) => {
      const list = Array.isArray(docs) ? docs : [];
      if (!list.length) { setUsage({}); return; }
      const day = list[0].date;
      const u = { date: day };
      list.filter((d) => d.date === day).forEach((d) => { u[d.kind] = d.count; });
      setUsage(u);
    }).catch(() => setUsage({}));

  const loadSecrets = () => search(`| rest splunk_server=local count=0 /servicesNS/nobody/${APP}/storage/passwords | search realm="${REALM}" | table username`)
    .then((rows) => { const s = {}; rows.forEach((r) => { s[r.username] = true; }); setStored(s); });

  useEffect(() => {
    Promise.all([rest('configs/conf-jev_triage', { params: { count: 0 } }), rest('configs/conf-macros/jev_cloudtrail'), rest('configs/conf-macros/jev_endpoint')])
      .then(([conf, m1, m2]) => {
        const c = {}; entries(conf).forEach((e) => { c[e.name] = e.content || {}; });
        const v = {};
        ALL_FIELDS.forEach((f) => {
          let x = f.macro ? '' : ((c[f.stanza] || {})[f.key] ?? '');
          if (f.bool) { x = /^(1|true|yes|t)$/i.test(String(x)) ? 'true' : (x === '' ? '' : 'false'); }
          v[f.id] = String(x);
        });
        [m1, m2].forEach((m) => { const e = entries(m)[0]; if (e) { v[e.name] = (e.content || {}).definition || ''; } });
        setVals(v); setSavedVals(JSON.stringify(v));
      }, (e) => setMsg({ type: 'error', text: T.loadFail + e.message }));
    loadSecrets().catch(() => {});
    loadUsage();
    rest('/authentication/current-context').then((d) => {
      const caps = ((entries(d)[0] || {}).content || {}).capabilities || [];
      setCanSave(caps.includes('admin_all_objects') || caps.includes('edit_storage_passwords'));
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = !!vals && (JSON.stringify(vals) !== savedVals
    || Object.values(secrets).some((x) => x) || Object.values(removes).some((x) => x));
  useEffect(() => {   // warn before leaving the page with unsaved changes
    if (!dirty) { return undefined; }
    const h = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', h);
    return () => window.removeEventListener('beforeunload', h);
  }, [dirty]);

  if (!vals) {
    return <div className={`jev-root${theme === 'dark' ? ' dark' : ''}`}>{msg ? <Message type={msg.type}>{msg.text}</Message> : '…'}</div>;
  }
  const provider = vals.provider;
  const visible = (x) => !x.providers || x.providers.includes(provider);
  const set = (id) => (e, { value }) => setVals({ ...vals, [id]: value });

  const validate = () => {
    const bad = [];
    ALL_FIELDS.forEach((f) => {
      const v = (vals[f.id] || '').trim();
      if (f.num && v !== '') { const n = Number(v); if (Number.isNaN(n) || n < f.num[0] || n > f.num[1]) { bad.push(`${label(T, f.id).l} (${f.num[0]}–${f.num[1]})`); } }
      if (f.proxy && /\/\/[^/]*@/.test(v)) { bad.push(T.proxyPw); }
      if ((f.url || f.proxy) && v !== '' && visible(f) && !/^https?:\/\/[^/\s]+/i.test(v)) {
        bad.push(label(T, f.id).l + T.badUrl + (f.url ? T.urlEx : ''));
      }
    });
    return bad;
  };

  const saveSecret = async (name) => {
    const entity = `storage/passwords/${REALM}:${name}:`;
    if (removes[name]) { await rest(entity, { method: 'DELETE' }); return; }
    const value = secrets[name];
    if (!value) { return; }
    if (stored[name]) { await rest(entity, { method: 'POST', params: { password: value } }); }
    else { await rest('storage/passwords', { method: 'POST', params: { name, realm: REALM, password: value } }); }
  };

  const save = async () => {
    const bad = validate();
    if (bad.length) { setMsg({ type: 'error', text: T.check + bad.join(', ') }); return; }
    setBusy(true); setMsg({ type: 'info', text: T.saving });
    try {
      const byStanza = {};
      const jobs = [];
      ALL_FIELDS.forEach((f) => {
        const v = (vals[f.id] || '').trim();
        if (f.macro) { jobs.push(rest(`configs/conf-macros/${f.macro}`, { method: 'POST', params: { definition: v || 'index=*' } })); }
        else { (byStanza[f.stanza] = byStanza[f.stanza] || {})[f.key] = v; }
      });
      Object.keys(byStanza).forEach((s) => jobs.push(rest(`configs/conf-jev_triage/${s}`, { method: 'POST', params: byStanza[s] })));
      await Promise.all(jobs);
      for (const s of ALL_SECRETS) { await saveSecret(s.name); }   // eslint-disable-line no-await-in-loop
      // Who may read the keys: admins and the role jev_triage_user (give it to analysts).
      // Users also need list_storage_passwords, which that role has. Applied to every stored key on each save.
      const aclFailed = [];
      const present = await search(`| rest splunk_server=local count=0 /servicesNS/nobody/${APP}/storage/passwords | search realm="${REALM}" | table username`);
      for (const row of present) {   // eslint-disable-line no-restricted-syntax
        try {
          await rest(`storage/passwords/${REALM}:${row.username}:/acl`, { method: 'POST',   // eslint-disable-line no-await-in-loop
            params: { sharing: 'app', owner: 'nobody', 'perms.read': 'admin,sc_admin,jev_triage_user', 'perms.write': 'admin,sc_admin' } });
        } catch (e) { aclFailed.push(row.username); }
      }
      await rest(`/apps/local/${APP}`, { method: 'POST', params: { configured: '1' } });
      setSecrets({}); setRemoves({}); setSavedVals(JSON.stringify(vals));
      await loadSecrets();
      setMsg(aclFailed.length ? { type: 'warning', text: `${T.saved} ${T.aclFail}${aclFailed.join(', ')}` } : { type: 'success', text: T.saved });
    } catch (e) {
      setMsg({ type: 'error', text: T.saveFail + e.message }); loadSecrets().catch(() => {});
    } finally { setBusy(false); }
  };

  const makeSupport = async () => {
    setSup({ busy: true, text: T.supBusy, type: 'info' });
    try {
      const { bundle, steps } = await collect({ hours: 24, onStep: (n) => setSup({ busy: true, text: T.supBusy + n, type: 'info' }) });
      download(bundle);
      const okN = steps.filter((s) => s.ok).length; const miss = steps.filter((s) => !s.ok).map((s) => s.name);
      setSup({ busy: false, type: miss.length ? 'warning' : 'success', text: `${T.supDone}${okN}/${steps.length}.${miss.length ? T.supMissing + miss.join(', ') : ''}` });
    } catch (e) { setSup({ busy: false, type: 'error', text: String(e.message || e) }); }
  };

  const test = async () => {
    if (dirty) { setMsg({ type: 'warning', text: T.testUnsaved }); return; }
    setBusy(true); setCheck(null); setMsg({ type: 'info', text: T.testing });
    try {
      const rows = await search('| jevcheck target=all');
      setCheck(rows);
      const ok = rows.length && rows.every((r) => r.status === 'ok');
      setMsg({ type: ok ? 'success' : 'warning', text: ok ? T.bothOk : T.seeTable });
    } catch (e) { setMsg({ type: 'error', text: T.testFail + e.message }); } finally { setBusy(false); }
  };

  return (
    <div className={`jev-root jev-form${theme === 'dark' ? ' dark' : ''}`}>
      <div className="jev-top">
        <div><h1>{T.title}</h1><div className="desc">{T.desc}</div></div>
        <LangSwitch lang={lang} onChange={setLang} />
      </div>
      {!canSave && <Message type="warning">{T.noCap}</Message>}
      {SECTIONS.map((sec) => (
        <div key={sec.id}>
          <h2>{T.sections[sec.id][0]}</h2>
          {T.sections[sec.id][1] && <div className="hint">{T.sections[sec.id][1]}</div>}
          {sec.usage && usage && (
            <ControlGroup label={T.usage + (usage.date ? ` (${usage.date})` : '')} labelWidth={240}>
              {usage.date ? (
                <table className="jev-check" style={{ marginTop: 0 }}><thead><tr>{T.usageCols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody><tr>{['jev_auto', 'jev_manual', 'llm_auto', 'llm_manual'].map((k) => <td key={k}>{usage[k] || 0}</td>)}</tr></tbody></table>
              ) : <span className="hint" style={{ margin: 0 }}>{T.usageNone}</span>}
            </ControlGroup>)}
          {(sec.secrets || []).filter(visible).map((s) => (
            <ControlGroup key={s.name} label={label(T, s.name).l} labelWidth={240}>
              <Text type="password" autoComplete="new-password" placeholder={T.keyPh} value={secrets[s.name] || ''}
                onChange={(e, { value }) => setSecrets({ ...secrets, [s.name]: value })} style={{ maxWidth: 360 }} />
              <span className={`jev-pill ${stored[s.name] ? 'set' : 'unset'}`} style={{ alignSelf: 'center', marginLeft: 8 }}>{stored[s.name] ? T.stored : T.notset}</span>
              {stored[s.name] && <Checkbox checked={!!removes[s.name]} onChange={(e, { checked }) => setRemoves({ ...removes, [s.name]: !checked })}
                style={{ marginLeft: 8, alignSelf: 'center' }}>{T.remove}</Checkbox>}
            </ControlGroup>))}
          {sec.fields.filter(visible).map((f) => {
            const { l, h } = label(T, f.id);
            return (
              <ControlGroup key={f.id} label={l} help={h} labelWidth={240}>
                {f.options ? (
                  <Select value={vals[f.id]} onChange={set(f.id)} style={{ maxWidth: 360 }}>
                    {[...new Set([...f.options, vals[f.id]])].map((o) => <Select.Option key={o} value={o} label={o === '' ? T.none : o} />)}
                  </Select>
                ) : <Text value={vals[f.id]} onChange={set(f.id)} style={{ maxWidth: 520 }} />}
              </ControlGroup>);
          })}
        </div>))}
      <div style={dirty ? { position: 'sticky', bottom: 0, zIndex: 5, background: 'var(--bg)', borderTop: '1px solid var(--line)', padding: '10px 0 4px' } : undefined}>
      {dirty && <Message type="warning">{T.unsaved}</Message>}
      <div className="jev-actions" style={{ margin: dirty ? '8px 0 6px' : '22px 0 10px' }}>
        <Button appearance="primary" label={T.save} onClick={save} disabled={busy} />
        <Button label={T.test} onClick={test} disabled={busy} />
        <span className="hint" style={{ margin: 0 }}>{T.testHint}</span>
      </div>
      </div>
      {msg && <Message type={msg.type}>{msg.text}</Message>}
      {check && (
        <table className="jev-check"><thead><tr>{T.cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{check.map((r) => (
            <tr key={r.target}>{[r.target === 'jev' ? 'Jev' : 'LLM', r.key_set, r.model, r.status, r.detail, r.latency_ms || ''].map((v, i) => <td key={i}>{v}</td>)}</tr>))}
          </tbody></table>)}
      <PromptPanel lang={lang} />
      <h2 style={{ marginTop: 32 }}>{T.supTitle}</h2>
      <div className="hint">{T.supDesc}</div>
      <div className="jev-actions" style={{ margin: '10px 0' }}>
        <Button label={T.supBtn} onClick={makeSupport} disabled={!!(sup && sup.busy)} />
      </div>
      {sup && <Message type={sup.type}>{sup.text}</Message>}
    </div>
  );
}

injectCss();
if (ensureLocale()) getUserTheme().catch(() => 'light').then((theme) => {
  layout(<SetupPage theme={theme} />, { pageTitle: 'Jev Triage Setup', theme, hideFooter: true });
});
