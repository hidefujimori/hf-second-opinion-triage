// Small REST helpers for Splunk Web (session cookie + CSRF header from @splunk/splunk-utils).
import { createRESTURL } from '@splunk/splunk-utils/url';
import { defaultFetchInit } from '@splunk/splunk-utils/fetch';
import { username } from '@splunk/splunk-utils/config';

export const APP = 'TA-jev-triage';

function init(method, body, contentType) {
  const headers = { ...(defaultFetchInit.headers || {}) };
  if (contentType) { headers['Content-Type'] = contentType; }
  return { ...defaultFetchInit, method, headers, body };
}

async function parse(res) {
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
  if (!res.ok) {
    const msg = (data && data.messages && data.messages[0] && data.messages[0].text) || text || res.statusText;
    const err = new Error(`HTTP ${res.status}: ${msg}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

/** REST call. path: 'configs/conf-jev_triage' (namespaced in this app) or '/apps/local/x' (under /services). */
export async function rest(path, { method = 'GET', params = null, owner = 'nobody' } = {}) {
  let url = path.startsWith('/') ? createRESTURL(path.slice(1)) : createRESTURL(path, { app: APP, owner });  // '/x' -> /services/x
  if (method === 'GET' || method === 'DELETE') {
    const q = new URLSearchParams({ output_mode: 'json', ...(params || {}) });
    url += (url.includes('?') ? '&' : '?') + q.toString();
    return parse(await fetch(url, init(method)));
  }
  // POST/DELETE handlers of configs and storage/passwords reject output_mode in the body
  const body = new URLSearchParams(params || {});
  return parse(await fetch(url, init(method, body.toString(), 'application/x-www-form-urlencoded')));
}

/** Run a search and return its result rows (oneshot). Runs as the current user in this app. */
export async function search(spl, earliest = '', latest = '') {
  const params = { search: spl, exec_mode: 'oneshot', output_mode: 'json', count: '0' };
  if (earliest) { params.earliest_time = earliest; }
  if (latest) { params.latest_time = latest; }
  const url = createRESTURL('search/jobs', { app: APP, owner: username || 'nobody' });
  const data = await parse(await fetch(url, init('POST', new URLSearchParams(params).toString(),
    'application/x-www-form-urlencoded')));
  return (data && data.results) || [];
}

/** Quote a value for SPL. */
export function q(v) { return `"${String(v).replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`; }
