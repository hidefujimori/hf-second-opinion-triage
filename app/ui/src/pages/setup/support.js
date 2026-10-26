// Support bundle: collects what is needed to look into a problem and returns it as one JSON object.
// Never contains keys: storage/passwords is read only as "which names exist".
// Endpoint / proxy hosts are hidden (scheme, port and path stay, e.g. http://***:11434/v1), and every
// URL host in the collected text is hidden the same way.
import { rest, search, APP } from '../../common/api';

const CAPS = ['admin_all_objects', 'edit_storage_passwords', 'list_storage_passwords', 'edit_tcp', 'mc_investigation_write',
  'list_settings', 'search'];

function hideUrl(u) {
  return String(u || '').replace(/^(\w+:\/\/)(?:[^@/\s]*@)?([^:/\s]+)/, '$1***');
}

/** Hide URL hosts and the configured endpoint / proxy hosts everywhere in the bundle. */
function scrub(obj, hosts) {
  let s = JSON.stringify(obj);
  s = s.replace(/(https?:\\?\/\\?\/)(?:[^@/\s"\\]*@)?([^:/\s"\\]+)/gi, '$1***');
  hosts.filter((h) => h && h.length > 2).forEach((h) => { s = s.split(h).join('***'); });
  return JSON.parse(s);
}

function hostOf(u) {
  const m = String(u || '').match(/^\w+:\/\/(?:[^@/\s]*@)?([^:/\s]+)/);
  return m ? m[1] : (String(u || '').split(/[:/]/)[0] || '');
}

const entries = (d) => ((d && d.entry) || []);

/**
 * Run every step; a step that fails (no permission, no index access, ...) records its error and the rest go on.
 * onStep(name, ok) reports progress. Returns { bundle, steps }.
 */
export async function collect({ hours = 24, onStep = () => {} } = {}) {
  const span = `-${hours}h`;
  const out = { generated: new Date().toISOString(), period_hours: hours, app: APP };
  const steps = [];
  const step = async (name, fn) => {
    try { out[name] = await fn(); steps.push({ name, ok: true }); onStep(name, true); }
    catch (e) { out[name] = { error: String(e.message || e).slice(0, 500) }; steps.push({ name, ok: false, error: out[name].error }); onStep(name, false); }
  };

  await step('environment', async () => {
    const info = (entries(await rest('/server/info'))[0] || {}).content || {};
    const app = async (n) => { try { const c = (entries(await rest(`/apps/local/${n}`))[0] || {}).content || {}; return { version: c.version, build: c.build, disabled: c.disabled }; } catch (e) { return null; } };
    return {
      splunk_version: info.version, build: info.build, product_type: info.product_type, instance_type: info.instance_type,
      server_roles: info.server_roles, os: info.os_name, server_name_hidden: true,
      apps: { 'TA-jev-triage': await app(APP), SplunkEnterpriseSecuritySuite: await app('SplunkEnterpriseSecuritySuite'),
        missioncontrol: await app('missioncontrol') },
    };
  });

  await step('user', async () => {
    const c = (entries(await rest('/authentication/current-context'))[0] || {}).content || {};
    const caps = c.capabilities || [];
    return { roles: c.roles, capabilities: Object.fromEntries(CAPS.map((k) => [k, caps.includes(k)])) };
  });

  await step('settings', async () => {
    const conf = {};
    entries(await rest('configs/conf-jev_triage', { params: { count: 0 } })).forEach((e) => {
      const c = {}; Object.entries(e.content || {}).forEach(([k, v]) => { if (!k.startsWith('eai:') && k !== 'disabled' && k !== 'output_mode') { c[k] = v; } });
      if (c.endpoint) { c.endpoint = hideUrl(c.endpoint); }
      if (c.proxy) { c.proxy = hideUrl(c.proxy); }
      conf[e.name] = c;
    });
    const macros = {};
    for (const m of ['jev_cloudtrail', 'jev_endpoint', 'jev_findings']) {   // eslint-disable-line no-restricted-syntax
      try { macros[m] = ((entries(await rest(`configs/conf-macros/${m}`))[0] || {}).content || {}).definition; }   // eslint-disable-line no-await-in-loop
      catch (e) { macros[m] = `error: ${e.message}`; }
    }
    const keys = await search(`| rest splunk_server=local count=0 /servicesNS/nobody/${APP}/storage/passwords | search realm="${APP}" | table username`);
    return { jev_triage_conf: conf, macros, keys_stored: keys.map((r) => r.username) };
  });

  await step('connection_test', async () => search('| jevcheck target=all'));

  await step('saved_searches', async () => {
    const list = entries(await rest('saved/searches', { params: { count: 0, search: `eai:acl.app=${APP}` } }))
      .map((e) => ({ name: e.name, disabled: e.content.disabled, cron: e.content.cron_schedule, next: e.content.next_scheduled_time,
        actions: e.content.actions }));
    let runs = [];
    try {
      runs = await search(`search index=_internal sourcetype=scheduler app="${APP}" earliest=${span}`
        + ' | stats count latest(_time) as last latest(status) as last_status values(status) as statuses by savedsearch_name'
        + ' | eval last=strftime(last, "%F %T %z")');
    } catch (e) { runs = { error: e.message }; }
    return { list, runs_in_period: runs };
  });

  // Support mode (prompts): versions in use per model, in the export format, with their diff and the audit log
  await step('prompts', async () => {
    const rows = await search('| jevprompt action=status');
    const active = rows.filter((r) => r.row === 'active');
    const inUse = [];
    for (const a of active) {   // eslint-disable-line no-restricted-syntax
      try {
        const v = await rest(`storage/collections/data/jev_prompt_versions/${encodeURIComponent(a.id)}`);   // eslint-disable-line no-await-in-loop
        inUse.push({ model: a.model, applied_by: a.applied_by, applied_at: a.applied_at, diff: JSON.parse(v.diff || '[]'),
          export: { format: 'jev-triage-questions/1', id: v._key, kind: v.kind, model: v.model, base: v.base, hash: v.hash, author: v.author,
            created: v.created, reason: v.reason, status: v.status, test: v.test, questions: JSON.parse(v.content) } });
      } catch (e) { inUse.push({ model: a.model, id: a.id, error: e.message }); }
    }
    let audit = [];
    try {
      audit = await search(`search index=jev_triage sourcetype=jev:prompt:audit earliest=-30d | head 50 | eval time=strftime(_time, "%F %T %z")`
        + ' | table time action user id model reason summary blocked previous');
    } catch (e) { audit = { error: e.message }; }
    return { state: rows.find((r) => r.row === 'state'), in_use: inUse, versions: rows.filter((r) => r.row === 'version'), audit_30d: audit };
  });

  await step('results_summary', async () => search('| inputlookup jev_triage_latest'
    + ' | eval explain=replace(coalesce(jev_explain_status,"-"), ":.*", ""), note=replace(coalesce(jev_note_status,"-"), ":.*", "")'
    + ' | stats count by jev_status explain note'));

  await step('recent_errors', async () => search('| inputlookup jev_triage_latest'
    + ' | where (jev_status!="ok" AND jev_status!="skipped") OR like(jev_explain_status, "error%") OR like(jev_note_status, "error%")'
    + ' | eval time=strftime(jev_time, "%F %T %z") | sort - jev_time | head 50'
    + ' | table event_id rule_name time jev_status jev_error jev_enrich_errors jev_explain_status jev_note_status jev_persist_error'));

  // KV collections without a lookup definition: read through the REST API
  const fmt = (t) => (t ? new Date(Number(t) * 1000).toISOString() : '');
  await step('queue', async () => {
    const docs = await rest('storage/collections/data/jev_triage_queue', { params: { sort: 'queued_time:-1', limit: 20 } });
    return (Array.isArray(docs) ? docs : []).map((d) => ({ queued: fmt(d.queued_time), done: fmt(d.done_time), status: d.status,
      search_name: d.search_name, rids: d.rids, write_note: d.write_note, auto_explain: d.auto_explain, result: d.result }));
  });

  await step('usage', async () => {
    const docs = await rest('storage/collections/data/jev_usage', { params: { sort: 'date:-1', limit: 40 } });
    return (Array.isArray(docs) ? docs : []).map((d) => ({ date: d.date, kind: d.kind, count: d.count }));
  });

  await step('response_actions', async () => search(`search index=cim_modactions action_name=jev_triage earliest=${span}`
    + ' | stats count by action_status signature | sort - count | head 50'));

  await step('app_logs', async () => search(`search index=_internal earliest=${span} (source=*jev_triage* OR source=*jevtriage* OR source=*jevexplain* OR source=*jevnote* OR source=*jevqueue*)`
    + ' (ERROR OR WARN* OR Traceback OR failed)'
    + ' | head 200 | eval time=strftime(_time, "%F %T %z") | table time source _raw'));

  await step('search_errors', async () => search(`search index=_internal earliest=${span} sourcetype=splunkd component=ChunkedExternProcessor`
    + ' (jevtriage OR jevexplain OR jevnote OR jevqueue OR jevcheck OR jevpersist)'
    + ' | head 100 | eval time=strftime(_time, "%F %T %z") | table time log_level _raw'));

  const hosts = [];
  try {
    entries(await rest('configs/conf-jev_triage', { params: { count: 0 } })).forEach((e) => {
      const c = e.content || {}; [c.endpoint, c.proxy].forEach((u) => { if (u) { hosts.push(hostOf(u)); } });
    });
  } catch (e) { /* hosts stay empty; URL hosts are still hidden */ }
  return { bundle: scrub(out, hosts), steps };
}

/** Offer the bundle as a file download. */
export function download(bundle) {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `jev-triage-support-${stamp}.json`;
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}
