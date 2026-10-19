// Page CSS (scoped under .jev-root). Light and dark themes through CSS variables.
const CSS = `
.jev-root { --crit:#c4161c; --high:#e8710a; --med:#d9a400; --low:#3b82c4; --tp:#c4161c; --fp:#2e7d32; --ben:#1e6fa8;
  --und:#6b7280; --err:#8b1d1d; --line:#dfe3e8; --muted:#5c6773; --bg:#f7f8fa; --card:#ffffff; --sel:#eef5ff; --text:#1f2933;
  --hover:#f3f6f9; --critbg:#fff5f5; --critsel:#ffe8e8; --policy:#fff8e6; --policyline:#f3d38a; --rerun:#f5f3ff; --rerunline:#c4b5fd;
  padding:16px 20px; font-size:13px; color:var(--text); }
.jev-root.dark { --line:#3c444d; --muted:#a3acb6; --bg:#1a1c20; --card:#212527; --sel:#1f3550; --text:#e1e6eb; --hover:#2a2f33;
  --critbg:#3a1d1f; --critsel:#4a2326; --policy:#3a3220; --policyline:#7a6230; --rerun:#2a2340; --rerunline:#5b4a9a; }
.jev-root * { box-sizing:border-box; }
.jev-top { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:10px; }
.jev-top h1 { font-size:22px; margin:0 0 2px; font-weight:600; }
.jev-top .desc { color:var(--muted); }
.jev-bar { display:flex; flex-wrap:wrap; gap:10px; align-items:flex-end; margin-bottom:12px; }
.jev-bar .f { display:flex; flex-direction:column; gap:3px; font-size:11px; color:var(--muted); min-width:140px; }
.jev-tiles { display:grid; grid-template-columns:repeat(auto-fit, minmax(110px, 1fr)); gap:8px; margin-bottom:12px; }
.jev-tile { background:var(--card); border:1px solid var(--line); border-radius:6px; padding:8px 10px; cursor:pointer; border-top:4px solid var(--und); text-align:left; color:var(--text); font:inherit; }
.jev-tile.static { cursor:default; }
.jev-tile.active { outline:2px solid var(--text); }
.jev-tile .n { font-size:22px; font-weight:700; line-height:1.1; }
.jev-tile .l { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.03em; }
.jev-tile.critical { border-top-color:var(--crit); } .jev-tile.critical .n { color:var(--crit); }
.jev-tile.high { border-top-color:var(--high); } .jev-tile.high .n { color:var(--high); }
.jev-tile.medium { border-top-color:var(--med); } .jev-tile.low { border-top-color:var(--low); }
.jev-tile.TP { border-top-color:var(--tp); } .jev-tile.FP { border-top-color:var(--fp); }
.jev-tile.Benign { border-top-color:var(--ben); } .jev-tile.err { border-top-color:var(--err); }
.jev-split { display:flex; gap:12px; align-items:flex-start; min-height:420px; }
.jev-list { flex:1 1 auto; min-width:0; background:var(--card); border:1px solid var(--line); border-radius:6px; overflow:auto; max-height:calc(100vh - 290px); }
table.jev-findings { width:100%; border-collapse:collapse; }
table.jev-findings th { position:sticky; top:0; background:var(--bg); text-align:left; font-weight:600; font-size:12px; color:var(--muted); padding:7px 8px; border-bottom:1px solid var(--line); white-space:nowrap; z-index:1; }
table.jev-findings td { padding:7px 8px; border-bottom:1px solid var(--line); vertical-align:middle; }
table.jev-findings tr.row { cursor:pointer; }
table.jev-findings .jev-chk { width:28px; text-align:center; padding-left:4px; padding-right:4px; }
table.jev-findings .jev-chk input { cursor:pointer; }
table.jev-findings tr.row.checked { background:var(--sel); }
.jev-bulk { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin:0 0 10px; padding:8px 10px; background:var(--card); border:1px solid var(--line); border-left:4px solid #7c3aed; border-radius:6px; }
.jev-bulk .cnt { font-weight:600; }
.jev-bulk .warn { color:var(--err); font-weight:600; flex:1 1 320px; }
.jev-bulk .fails { flex-basis:100%; font-size:12px; color:var(--muted); }
table.jev-findings tr.row:hover { background:var(--hover); }
table.jev-findings tr.row.selected { background:var(--sel); }
table.jev-findings tr.row td:first-child { border-left:4px solid transparent; }
table.jev-findings tr.row.u-critical td:first-child { border-left-color:var(--crit); }
table.jev-findings tr.row.u-high td:first-child { border-left-color:var(--high); }
table.jev-findings tr.row.u-critical { background:var(--critbg); }
table.jev-findings tr.row.u-critical.selected { background:var(--critsel); }
.jev-root .rule { font-weight:600; }
.jev-root .sub { color:var(--muted); font-size:12px; }
.jev-badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:700; color:#fff; text-transform:uppercase; letter-spacing:.03em; white-space:nowrap; }
.jev-badge.critical { background:var(--crit); } .jev-badge.high { background:var(--high); }
.jev-badge.medium { background:var(--med); color:#1f2933; } .jev-badge.low { background:var(--low); }
.jev-badge.none { background:#d1d5db; color:#1f2933; }
.jev-chip { display:inline-block; padding:1px 7px; border-radius:4px; font-size:12px; font-weight:600; border:1px solid; white-space:nowrap; }
.jev-chip.TP { color:var(--tp); border-color:var(--tp); background:rgba(196,22,28,.08); }
.jev-chip.FP { color:var(--fp); border-color:var(--fp); background:rgba(46,125,50,.08); }
.jev-chip.Benign { color:var(--ben); border-color:var(--ben); background:rgba(30,111,168,.08); }
.jev-chip.Undetermined, .jev-chip.none { color:var(--und); border-color:var(--und); background:rgba(107,114,128,.08); }
.jev-chip.error { color:#fff; background:var(--err); border-color:var(--err); }
.jev-tag { display:inline-block; margin-left:6px; padding:0 6px; border-radius:8px; font-size:10px; font-weight:600; background:#ede9fe; color:#5b21b6; vertical-align:middle; }
.jev-conf { display:inline-flex; align-items:center; gap:5px; font-size:11px; color:var(--muted); }
.jev-meter { width:54px; height:6px; background:rgba(127,127,127,.25); border-radius:3px; overflow:hidden; display:inline-block; }
.jev-meter > i { display:block; height:100%; background:#6b7280; }
.jev-meter.wide { width:140px; height:8px; }
.jev-meter.hot > i { background:var(--crit); } .jev-meter.warm > i { background:var(--high); }
.jev-empty { padding:30px; text-align:center; color:var(--muted); }
.jev-pane { flex:0 0 46%; max-width:720px; background:var(--card); border:1px solid var(--line); border-radius:6px; max-height:calc(100vh - 290px); overflow:auto; box-shadow:-2px 0 8px rgba(0,0,0,.06); animation:jevslide .15s ease-out; }
@keyframes jevslide { from { transform:translateX(24px); opacity:.4; } to { transform:none; opacity:1; } }
.jev-pane-head { position:sticky; top:0; background:var(--card); border-bottom:1px solid var(--line); padding:12px 14px; z-index:2; }
.jev-pane-head.critical { border-top:5px solid var(--crit); } .jev-pane-head.high { border-top:5px solid var(--high); }
.jev-pane-head.medium { border-top:5px solid var(--med); } .jev-pane-head.low { border-top:5px solid var(--low); }
.jev-pane-head h2 { margin:0 28px 4px 0; font-size:16px; }
.jev-close { position:absolute; right:10px; top:10px; border:none; background:none; font-size:20px; cursor:pointer; color:var(--muted); }
.jev-pane-body { padding:12px 14px; }
.jev-sec { margin-bottom:16px; }
.jev-sec h3 { font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); margin:0 0 6px; font-weight:600; }
.jev-verdict { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.jev-vbox { border:1px solid var(--line); border-radius:6px; padding:10px; }
.jev-vbox .big { font-size:18px; font-weight:700; margin:3px 0; }
.jev-kv { display:grid; grid-template-columns:200px 1fr; gap:4px 10px; align-items:center; }
.jev-kv .k { color:var(--muted); }
ul.jev-facts { margin:0; padding-left:18px; } ul.jev-facts li { margin:3px 0; }
.jev-policy { background:var(--policy); border:1px solid var(--policyline); border-radius:4px; padding:6px 8px; }
.jev-rerun { background:var(--rerun); border:1px solid var(--rerunline); border-left:4px solid #7c3aed; border-radius:4px; padding:8px 10px; margin-bottom:14px; line-height:1.5; }
.jev-rerun .t { font-weight:700; color:#7c3aed; margin-bottom:2px; }
.jev-explain { white-space:pre-wrap; background:var(--bg); border:1px solid var(--line); border-radius:6px; padding:10px; line-height:1.55; }
.jev-explain.placeholder { color:var(--muted); font-style:italic; }
.jev-actions { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.jev-status { font-size:12px; margin-top:6px; color:var(--muted); }
.jev-status.ok { color:var(--fp); } .jev-status.err { color:var(--err); }
.jev-warn { color:var(--err); }
.jev-form { max-width:940px; }
.jev-form h2 { font-size:15px; margin:22px 0 4px; padding-bottom:4px; border-bottom:1px solid var(--line); }
.jev-form .hint { color:var(--muted); margin:2px 0 10px; }
.jev-pill { display:inline-block; padding:1px 8px; border-radius:10px; font-size:12px; font-weight:600; }
.jev-pill.set { background:rgba(46,125,50,.15); color:var(--fp); } .jev-pill.unset { background:rgba(196,22,28,.12); color:var(--crit); }
table.jev-check { border-collapse:collapse; margin-top:8px; } table.jev-check td, table.jev-check th { border:1px solid var(--line); padding:4px 8px; text-align:left; vertical-align:top; }
@media (max-width: 1100px) { .jev-split { flex-direction:column; } .jev-pane { flex-basis:auto; max-width:none; width:100%; } }
`;

export function injectCss() {
  if (document.getElementById('jev-css')) { return; }
  const el = document.createElement('style');
  el.id = 'jev-css';
  el.textContent = CSS;
  document.head.appendChild(el);
}
