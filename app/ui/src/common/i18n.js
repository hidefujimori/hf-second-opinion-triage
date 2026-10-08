// Language of the page AND of Splunk's own menus.
// Splunk Web takes its UI language from the locale in the URL (/en-US/app/..., /ja-JP/app/...),
// so the switch moves to the same page under the other locale; the whole screen then matches.
// The choice is remembered in this browser (default English); a page opened under the other locale
// is moved to the remembered one once.
const KEY = 'jev_triage_lang';
const LOCALE = { en: 'en-US', ja: 'ja-JP' };

function urlLang() {
  const m = /^\/([a-z]{2})-[A-Za-z]{2}\//.exec(window.location.pathname);
  return m && m[1] === 'ja' ? 'ja' : 'en';
}
function stored() {
  try { const v = window.localStorage.getItem(KEY); return v === 'ja' || v === 'en' ? v : null; } catch (e) { return null; }
}
function remember(lang) { try { window.localStorage.setItem(KEY, lang); } catch (e) { /* private mode */ } }

function go(lang) {
  const { pathname, search, hash } = window.location;
  const path = /^\/[a-z]{2}-[A-Za-z]{2}\//.test(pathname)
    ? pathname.replace(/^\/[a-z]{2}-[A-Za-z]{2}\//, `/${LOCALE[lang]}/`)
    : `/${LOCALE[lang]}${pathname}`;
  window.location.assign(path + search + hash);
}

/** Call before rendering: returns false if the page is being moved to the remembered locale. */
export function ensureLocale() {
  const want = stored() || 'en';
  if (urlLang() !== want) { go(want); return false; }
  return true;
}

export function useLang() {
  const lang = urlLang();
  document.documentElement.lang = lang;
  const setLang = (l) => { if (l !== lang) { remember(l); go(l); } };
  return [lang, setLang];
}

export function fmt(s, vars) { return String(s).replace(/\{(\w+)\}/g, (m, k) => (vars[k] == null ? '' : vars[k])); }
