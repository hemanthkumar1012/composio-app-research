/* Toolkit Readiness Atlas: one self-contained app over the embedded dataset (window DATA). No libraries. */
(() => {
const D = JSON.parse(document.getElementById('data').textContent);
const APPS = D.apps, BY = Object.fromEntries(APPS.map(a => [a.id, a]));
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const VL = D.labels.verdict, AL = D.labels.access, FIELDS = ['auth','access','api','mcp','verdict'];
const VORDER = Object.keys(VL), AORDER = Object.keys(AL), CATS = [...new Set(APPS.map(a => a.category))];
const MCPS = ['official','docs-only','community','none'], AUTHS = ['OAuth2','API key','Basic','Other','None','Unknown'];
const authSet = a => a.auth.split(';').map(s => s.trim());
const inCat = a => a.composio == null ? 'not checked' : a.composio.found ? 'in catalogue' : 'not in catalogue';
const catPill = a => a.composio == null ? '<span class="pill p-neutral">not checked</span>' : a.composio.found
  ? `<span class="pill ${a.composio.kind === 'mcp-wrapper' ? 'p-docs-only' : 'p-official'}" title="composio.dev/toolkits/${esc(a.composio.found)}">${a.composio.kind === 'mcp-wrapper' ? 'MCP wrapper' : 'toolkit'}</span>` : '<span class="pill p-neutral">not yet</span>';
const catDot = c => `<i class="cdot" style="background:var(--cat${CATS.indexOf(c)})" aria-hidden="true"></i>`;
const pill = (v, kind) =>`<span class="pill p-${esc(v)}">${esc(kind === 'v' ? VL[v] : kind === 'a' ? AL[v] : v)}</span>`;

/* ---------- toast + tooltip ---------- */
const toastEl = $('#toast'), tipEl = $('#tip'); let toastT;
function toast(msg){ toastEl.textContent = msg; toastEl.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => toastEl.classList.remove('on'), 2200); }
function tip(e, html){ if (!html){ tipEl.classList.remove('on'); return; } tipEl.innerHTML = html; tipEl.classList.add('on');
  tipEl.style.left = Math.min(e.clientX + 14, innerWidth - 290) + 'px'; tipEl.style.top = (e.clientY + 14) + 'px'; }
async function copy(text, what){ try { await navigator.clipboard.writeText(text); toast(`${what} copied`); } catch { toast('Copy was blocked by the browser: select the text instead'); } }
async function download(name, text, type){
  try { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], {type})); a.download = name; document.body.appendChild(a); a.click(); a.remove(); toast(`Downloading ${name}`); }
  catch { copy(text, name); } }

/* ---------- theme ---------- */
const root = document.documentElement;
try { const t = localStorage.getItem('atlas-theme'); if (t) root.dataset.theme = t; } catch {}
$('#theme').addEventListener('click', () => { const dark = getComputedStyle(root).colorScheme.includes('dark') || root.dataset.theme === 'dark';
  root.dataset.theme = dark ? 'light' : 'dark'; try { localStorage.setItem('atlas-theme', root.dataset.theme); } catch {} });

/* ---------- state + router ---------- */
const VIEWS = ['overview','explorer','planner','verification','agent','data'];
const S = { f: {category:new Set(), verdict:new Set(), access:new Set(), mcp:new Set(), auth:new Set(), blocker:new Set(), composio:new Set()}, q:'', readOnly:false,
  sort:{key:'id', dir:1}, layout:'table', compare:new Set(), sample:'round1', stage:'pass1', traceId:37 };
function show(view){
  if (!VIEWS.includes(view)) view = 'overview';
  $$('.view').forEach(v => v.classList.toggle('on', v.id === 'v-' + view));
  $$('.tab').forEach(t => t.setAttribute('aria-selected', t.dataset.view === view));
  if (view === 'explorer') renderExplorer(); if (view === 'planner') renderPlanner(); if (view === 'verification') renderVerification();
}
function route(){ const h = location.hash.slice(1);
  if (h.startsWith('app-')) { const id = +h.slice(4); if (BY[id]) { if (!$('.view.on')) show('explorer'); openDrawer(id); return; } }
  closeDrawer(true); show(h || 'overview'); }
addEventListener('hashchange', route);
$$('.tab').forEach(t => t.addEventListener('click', () => { location.hash = t.dataset.view; }));
function goExplore(filters = {}){ Object.values(S.f).forEach(s => s.clear()); S.q = ''; $('#q').value = '';
  for (const [k, vals] of Object.entries(filters)) (Array.isArray(vals) ? vals : [vals]).forEach(v => S.f[k].add(v));
  location.hash = 'explorer'; renderExplorer(); }

/* ================= OVERVIEW ================= */
function renderOverview(){
  const P = D.patterns, sc = D.scores, ho = sc.holdout.final;
  const k = [
    ['good', `${P.access.free + P.access.trial}<small>/100</small>`, 'self-serve credentials', {access:['free','trial']}],
    ['good', P.verdict.ready, 'build now, no gate', {verdict:'ready'}],
    ['acc', P.mcp.official, `official MCP (${D.mcp_confirmed} confirmed)`, {mcp:'official'}],
    ['bad', P.verdict.outreach, 'need outreach first', {verdict:'outreach'}],
    ['acc', `${ho.acc}%`, `holdout accuracy (${ho.correct}/${ho.checked})`, 'verification'],
    ['', D.changes.length, 'sourced corrections', 'data'],
  ];
  if (P.composio) k.push(['', `${P.composio.in_catalogue}<small>/${P.composio.checked}</small>`, 'already a Composio toolkit (live check)', {composio: 'in catalogue'}]);
  $('#kpis').innerHTML = k.map(([c, b, s], i) => `<button class="kpi ${c}" data-i="${i}"><b>${b}</b><span>${esc(s)}</span></button>`).join('');
  $$('#kpis .kpi').forEach(el => el.addEventListener('click', () => { const t = k[+el.dataset.i][3]; typeof t === 'string' ? (location.hash = t) : goExplore(t); }));
  $('#findings').innerHTML = D.findings.map((f, i) => `<li class="finding"><div class="big">${esc(f.big)}</div><p><strong>${esc(f.claim)}</strong></p>
    <p class="why">${esc(f.why)}</p>${f.filter ? `<button class="link" data-i="${i}">Show these apps →</button>` : ''}</li>`).join('');
  $$('#findings .link').forEach(b => b.addEventListener('click', () => goExplore(D.findings[+b.dataset.i].filter)));
  drawFlow(); drawHeat(); drawBars(); drawBlockers();
}

function drawFlow(){
  const cols = [['category', CATS], ['access', AORDER], ['verdict', VORDER]];
  const W = 1000, H = 470, NW = 14, GAP = 7, X = [190, 500, 810], k = (H - GAP * 9) / 100;
  const color = {access: v => `var(--${{free:'good',trial:'teal',review:'warn',paid:'orange',gated:'bad',na:'violet'}[v]})`,
                 verdict: v => `var(--${{ready:'good',caveat:'warn',outreach:'bad',wrap:'violet'}[v]})`, category: v => `var(--cat${CATS.indexOf(v)})`};
  const nodes = {};
  cols.forEach(([key, vals], ci) => {
    const counts = vals.map(v => APPS.filter(a => a[key] === v).length).filter(n => n);
    const used = vals.filter(v => APPS.some(a => a[key] === v));
    const total = counts.reduce((x, y) => x + y, 0) * k + GAP * (used.length - 1); let y = (H - total) / 2;
    used.forEach(v => { const n = APPS.filter(a => a[key] === v).length; nodes[key + ':' + v] = {key, v, ci, x: X[ci], y, h: n * k, n, outY: y, inY: y}; y += n * k + GAP; });
  });
  let links = '';
  [['category','access'], ['access','verdict']].forEach(([s, t]) => {
    const sv = cols.find(c => c[0] === s)[1], tv = cols.find(c => c[0] === t)[1];
    sv.forEach(a => tv.forEach(b => {
      const n = APPS.filter(x => x[s] === a && x[t] === b).length; if (!n) return;
      const S1 = nodes[s + ':' + a], T1 = nodes[t + ':' + b], h = n * k, x0 = S1.x + NW, x1 = T1.x, xm = (x0 + x1) / 2, y0 = S1.outY, y1 = T1.inY;
      S1.outY += h; T1.inY += h;
      links += `<path class="lnk" data-s="${s}:${esc(a)}" data-t="${t}:${esc(b)}" data-n="${n}" fill="${t === 'access' ? color.category(a) : color[t](b)}"
        d="M${x0},${y0}C${xm},${y0} ${xm},${y1} ${x1},${y1}L${x1},${y1 + h}C${xm},${y1 + h} ${xm},${y0 + h} ${x0},${y0 + h}Z"/>`;
    }));
  });
  const label = v => ({...AL, ...VL})[v] || v;
  const nodeSvg = Object.entries(nodes).map(([id, n]) => {
    const tx = n.ci === 0 ? n.x - 8 : n.x + NW + 8, anchor = n.ci === 0 ? 'end' : 'start';
    return `<g class="node" data-id="${esc(id)}"><rect x="${n.x}" y="${n.y}" width="${NW}" height="${Math.max(n.h, 2)}" rx="3" fill="${color[n.key](n.v)}"/>
      <text x="${tx}" y="${n.y + n.h / 2 + 4}" text-anchor="${anchor}">${esc(label(n.v))} <tspan class="n">${n.n}</tspan></text></g>`; }).join('');
  const heads = ['Category', 'How credentials are obtained', 'Verdict'].map((t, i) => `<text class="colhead" x="${X[i] + (i === 0 ? NW : 0)}" y="14" text-anchor="${i === 0 ? 'end' : 'start'}">${t}</text>`).join('');
  const svg = $('#flow'); svg.setAttribute('viewBox', `0 -8 ${W} ${H + 16}`); svg.innerHTML = heads + links + nodeSvg;
  const lab = id => label(id.split(':').slice(1).join(':'));
  $$('.lnk', svg).forEach(p => {
    p.addEventListener('mousemove', e => tip(e, `<b>${esc(lab(p.dataset.s))} → ${esc(lab(p.dataset.t))}</b><br>${p.dataset.n} apps · click to list`));
    p.addEventListener('mouseleave', () => tip());
    p.addEventListener('click', () => { const [a, av] = p.dataset.s.split(/:(.*)/), [b, bv] = p.dataset.t.split(/:(.*)/); tip(); goExplore({[a]: av, [b]: bv}); });
  });
  $$('.node', svg).forEach(g => {
    const id = g.dataset.id;
    g.addEventListener('mouseenter', () => { svg.classList.add('dim'); $$('.lnk', svg).forEach(p => p.classList.toggle('hot', p.dataset.s === id || p.dataset.t === id)); });
    g.addEventListener('mouseleave', () => { svg.classList.remove('dim'); $$('.lnk', svg).forEach(p => p.classList.remove('hot')); });
    g.addEventListener('click', () => { const [key, v] = id.split(/:(.*)/); goExplore({[key]: v}); });
  });
}

function drawHeat(){
  const max = 10;
  $('#heat').innerHTML = `<thead><tr><th>Category</th>${VORDER.map(v => `<th class="num">${esc(VL[v])}</th>`).join('')}<th class="num">Self-serve</th><th class="num">OAuth2</th><th class="num">Official MCP</th></tr></thead><tbody>` +
    CATS.map(c => { const rs = APPS.filter(a => a.category === c);
      return `<tr><th scope="row">${catDot(c)}${esc(c)}</th>${VORDER.map(v => { const n = rs.filter(a => a.verdict === v).length;
        const col = {ready:'good',caveat:'warn',outreach:'bad',wrap:'slate'}[v];
        return n ? `<td class="cell" data-c="${esc(c)}" data-v="${v}" style="background:color-mix(in srgb,var(--${col}) ${15 + 70 * n / max}%,transparent)">${n}</td>` : '<td class="cell zero">0</td>'; }).join('')}
        <td class="num">${rs.filter(a => ['free','trial'].includes(a.access)).length}</td><td class="num">${rs.filter(a => authSet(a).includes('OAuth2')).length}</td><td class="num">${rs.filter(a => a.mcp === 'official').length}</td></tr>`; }).join('') + '</tbody>';
  $$('#heat td.cell:not(.zero)').forEach(td => td.addEventListener('click', () => goExplore({category: td.dataset.c, verdict: td.dataset.v})));
}

function drawBars(){
  const mix = D.patterns.auth_mix, keyMap = {'OAuth2 + static key/Basic':['OAuth2','API key'], 'OAuth2 only':['OAuth2'], 'Static key / Basic only':['API key','Basic'], 'Other only (signed keys, JWT)':['Other'], 'None / unknown':['None','Unknown']};
  $('#authbars').innerHTML = Object.entries(mix).map(([lab, n]) => `<div class="hbar" data-k="${esc(lab)}"><span>${esc(lab)}</span><div class="track"><div class="fill c-acc" style="width:${n}%"></div></div><span class="num mono">${n}</span></div>`).join('');
  $$('#authbars .hbar').forEach(el => el.addEventListener('click', () => goExplore({auth: keyMap[el.dataset.k]})));
  $('#accessbars').innerHTML = AORDER.map(k => { const n = D.patterns.access[k] || 0;
    return `<div class="hbar" data-k="${k}"><span>${esc(AL[k])}</span><div class="track"><div class="fill c-${k}" style="width:${n}%"></div></div><span class="num mono">${n}</span></div>`; }).join('');
  $$('#accessbars .hbar').forEach(el => el.addEventListener('click', () => goExplore({access: el.dataset.k})));
}

function drawBlockers(){
  const B = Object.entries(D.patterns.blockers).sort((a, b) => b[1].length - a[1].length);
  $('#blockers').innerHTML = B.map(([k, v]) => `<div class="card blk"><h3>${esc(k)}<span class="count">${v.length}</span> <button class="link small" data-b="${esc(k)}">filter</button></h3>
    <div class="chips">${v.map(x => `<button class="chip" data-id="${x.id}">${esc(x.app)}</button>`).join('')}</div></div>`).join('');
  $$('#blockers .chip').forEach(c => c.addEventListener('click', () => { location.hash = 'app-' + c.dataset.id; }));
  $$('#blockers [data-b]').forEach(b => b.addEventListener('click', () => goExplore({blocker: b.dataset.b})));
}

/* ================= EXPLORER ================= */
const FACETS = [['category','Category', CATS, x => x], ['verdict','Verdict', VORDER, x => VL[x]], ['access','Credentials', AORDER, x => AL[x]],
  ['auth','Auth method', AUTHS, x => x], ['mcp','MCP server', MCPS, x => x], ['blocker','Main blocker', Object.keys(D.patterns.blockers), x => x],
  ['composio','Composio catalogue', ['in catalogue','not in catalogue','not checked'], x => x]];
const val = (a, key) => key === 'auth' ? authSet(a) : key === 'blocker' ? [a.blocker || '(none: build now)'] : key === 'composio' ? [inCat(a)] : [a[key]];
function matches(a, skip){
  for (const [key] of FACETS) { if (key === skip) continue; const sel = S.f[key]; if (sel.size && !val(a, key).some(v => sel.has(v))) return false; }
  if (S.readOnly && !a.fetched) return false;
  if (S.q) { const hay = [a.app, a.one_liner, a.category, a.auth, a.note, a.access, a.mcp, a.verdict, AL[a.access], VL[a.verdict]].join(' ').toLowerCase();
    if (!S.q.toLowerCase().split(/\s+/).every(w => hay.includes(w))) return false; }
  return true;
}
function hl(s){ if (!S.q) return esc(s); let out = esc(s); S.q.split(/\s+/).filter(w => w.length > 1).forEach(w => { out = out.replace(new RegExp(`(${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'), '<mark>$1</mark>'); }); return out; }
function renderFacets(){
  $('#facets').innerHTML = FACETS.map(([key, title, vals, lab]) => `<div class="facet"><h4>${title}</h4>${vals.map(v => {
    const n = APPS.filter(a => matches(a, key) && val(a, key).includes(v)).length;
    return `<label class="${n ? '' : 'zero'}"><input type="checkbox" data-k="${key}" value="${esc(v)}" ${S.f[key].has(v) ? 'checked' : ''}> ${key === 'category' ? catDot(v) : ''}${esc(lab(v))}<span class="n">${n}</span></label>`; }).join('')}</div>`).join('') +
    `<div class="facet"><h4>Evidence</h4><label><input type="checkbox" id="readonly" ${S.readOnly ? 'checked' : ''}> Read in this run only<span class="n">${APPS.filter(a => a.fetched).length}</span></label></div>
     <button class="btn" id="reset">Reset filters</button>`;
  $$('#facets input[data-k]').forEach(i => i.addEventListener('change', () => { i.checked ? S.f[i.dataset.k].add(i.value) : S.f[i.dataset.k].delete(i.value); renderExplorer(); }));
  $('#readonly').addEventListener('change', e => { S.readOnly = e.target.checked; renderExplorer(); });
  $('#reset').addEventListener('click', () => goExplore({}));
}
const SORTS = {id: a => a.id, app: a => a.app.toLowerCase(), category: a => a.category, access: a => AORDER.indexOf(a.access), mcp: a => MCPS.indexOf(a.mcp),
  verdict: a => VORDER.indexOf(a.verdict), auth: a => a.auth, api: a => a.api, composio: a => inCat(a)};
function renderExplorer(){
  renderFacets();
  const rows = APPS.filter(a => matches(a)).sort((x, y) => { const f = SORTS[S.sort.key]; const a = f(x), b = f(y); return (a > b ? 1 : a < b ? -1 : 0) * S.sort.dir || x.id - y.id; });
  $('#count').textContent = `${rows.length} of ${APPS.length} apps`;
  const act = Object.entries(S.f).flatMap(([k, s]) => [...s].map(v => `<button class="chip" data-k="${k}" data-v="${esc(v)}">${esc(k)}: ${esc(k === 'verdict' ? VL[v] : k === 'access' ? AL[v] : v)}</button>`));
  $('#active').innerHTML = act.join('');
  $$('#active .chip').forEach(c => c.addEventListener('click', () => { S.f[c.dataset.k].delete(c.dataset.v); renderExplorer(); }));
  if (S.layout === 'table') {
    $('#results').innerHTML = `<div class="tablewrap"><table class="apps"><thead><tr><th>Compare</th>${[['id','#'],['app','App'],['category','Category'],['auth','Auth'],['access','Credentials'],['api','API'],['mcp','MCP'],['composio','Composio'],['verdict','Verdict']].map(([k, l]) =>
      `<th data-sort="${k}" class="${S.sort.key === k ? 'sorted' + (S.sort.dir < 0 ? ' desc' : '') : ''}">${l}</th>`).join('')}<th>What a builder must know</th></tr></thead><tbody>${rows.map(a => `
      <tr data-id="${a.id}"><td><input type="checkbox" class="cmp" data-id="${a.id}" aria-label="Compare ${esc(a.app)}" ${S.compare.has(a.id) ? 'checked' : ''}></td>
      <td class="num">${a.id}</td><td class="app"><strong>${hl(a.app)}</strong><span>${hl(a.one_liner)}</span></td><td class="cat">${catDot(a.category)}${hl(a.category)}</td>
      <td>${hl(a.auth.replaceAll(';', ' · '))}</td><td>${pill(a.access, 'a')}</td><td>${esc(a.api)} <span class="muted small">${esc(a.breadth)}</span></td>
      <td>${pill(a.mcp)}${a.mcp === 'official' && !a.mcp_confirmed ? '<sup title="pass-1 claim, not confirmed this run">?</sup>' : ''}</td><td>${catPill(a)}</td><td>${pill(a.verdict, 'v')}</td><td class="small">${hl(a.note)}</td></tr>`).join('')}</tbody></table></div>`;
    $$('#results th[data-sort]').forEach(th => th.addEventListener('click', () => { const k = th.dataset.sort; S.sort = {key: k, dir: S.sort.key === k ? -S.sort.dir : 1}; renderExplorer(); }));
  } else {
    $('#results').innerHTML = `<div class="cards">${rows.map(a => `<div class="acard v-${a.verdict}" data-id="${a.id}" tabindex="0"><div style="display:flex;justify-content:space-between;gap:8px">
      <h4>${hl(a.app)}</h4><input type="checkbox" class="cmp" data-id="${a.id}" aria-label="Compare ${esc(a.app)}" ${S.compare.has(a.id) ? 'checked' : ''}></div><p>${hl(a.one_liner)}</p>
      <div class="chips">${pill(a.verdict, 'v')} ${pill(a.access, 'a')} <span class="pill p-neutral">${esc(a.auth.replaceAll(';', ' · '))}</span>${a.mcp === 'official' ? '<span class="pill p-official">official MCP</span>' : ''}</div>
      <p class="small">${catDot(a.category)}${hl(a.category)}</p>
      <p class="small">${hl(a.note)}</p></div>`).join('')}</div>`;
  }
  $$('#results [data-id]').forEach(el => el.addEventListener('click', e => { if (e.target.classList.contains('cmp')) return; location.hash = 'app-' + el.dataset.id; }));
  $$('#results .cmp').forEach(c => c.addEventListener('change', () => toggleCompare(+c.dataset.id, c)));
  renderTray();
}
$('#q').addEventListener('input', e => { S.q = e.target.value.trim(); renderExplorer(); });
$$('#layout button').forEach(b => b.addEventListener('click', () => { S.layout = b.dataset.l; $$('#layout button').forEach(x => x.setAttribute('aria-pressed', x === b)); renderExplorer(); }));
$('#csv').addEventListener('click', () => download('toolkit-readiness.csv', toCSV(APPS.filter(a => matches(a))), 'text/csv'));

/* ---------- compare ---------- */
function toggleCompare(id, box){ if (S.compare.has(id)) S.compare.delete(id); else if (S.compare.size >= 3) { box && (box.checked = false); toast('Compare up to 3 apps'); return; } else S.compare.add(id); renderTray(); }
function renderTray(){ const t = $('#tray'); t.classList.toggle('on', S.compare.size > 0); document.body.classList.toggle('traying', S.compare.size > 0);
  $('#traylist').innerHTML = [...S.compare].map(id => `<span class="pill p-neutral">${esc(BY[id].app)}</span>`).join(' ');
  $('#cmpgo').disabled = S.compare.size < 2; }
$('#cmpclear').addEventListener('click', () => { S.compare.clear(); renderTray(); $$('.cmp').forEach(c => c.checked = false); });
$('#cmpgo').addEventListener('click', () => {
  const ids = [...S.compare], rows = [['Category', a => esc(a.category)], ['What it does', a => esc(a.one_liner)], ['Auth', a => esc(a.auth.replaceAll(';', ' · '))],
    ['Credentials', a => pill(a.access, 'a')], ['API', a => `${esc(a.api)} (${esc(a.breadth)})`], ['MCP', a => esc(a.mcp)], ['Verdict', a => pill(a.verdict, 'v')],
    ['Main blocker', a => esc(a.blocker || 'none')], ['Builder note', a => esc(a.note)], ['Planner score', a => scoreOf(a, DEFAULT_W).toFixed(0)]];
  $('#modalbody').innerHTML = `<h2 style="margin-top:0">Compare</h2><div style="overflow-x:auto"><table><thead><tr><th></th>${ids.map(i => `<th>${esc(BY[i].app)}</th>`).join('')}</tr></thead><tbody>${rows.map(([l, f]) => `<tr><th>${l}</th>${ids.map(i => `<td>${f(BY[i])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  openModal();
});

/* ---------- drawer ---------- */
function authConfig(a){
  const s = authSet(a), schemes = [];
  if (s.includes('OAuth2')) schemes.push({auth_scheme: 'OAUTH2', you_provide: ['client_id', 'client_secret', 'scopes'], step: 'register an OAuth app with the vendor'});
  if (s.includes('API key')) schemes.push({auth_scheme: 'API_KEY', user_provides: ['api_key']});
  if (s.includes('Basic')) schemes.push({auth_scheme: 'BASIC', user_provides: ['username', 'password_or_token']});
  if (s.includes('Other')) schemes.push({auth_scheme: 'CUSTOM', step: 'signed keys / JWT / OAuth1 / Digest need a custom auth handler'});
  if (s.includes('None')) schemes.push({auth_scheme: 'NO_AUTH', step: 'local CLI: run inside a sandbox'});
  return JSON.stringify({toolkit: a.app.toLowerCase().replace(/\(.*?\)/g, '').trim().replace(/[^a-z0-9]+/g, '_'), auth_schemes: schemes,
    default_for_multi_tenant: schemes.find(x => x.auth_scheme === 'OAUTH2') ? 'OAUTH2' : (schemes[0] || {}).auth_scheme || 'UNKNOWN',
    vendor_mcp: a.mcp === 'official' ? 'available: consider proxying it' : a.mcp, blocker: a.blocker || null, note: a.note}, null, 1);
}
function outreach(a){ return `Subject: Partner API access for an AI-agent integration with ${a.app}

Hi ${a.app} team,

I work on Composio, which turns apps into tools that AI agents can call. Customers have asked for a ${a.app} toolkit (${a.one_liner.toLowerCase()}).

From your public docs, the blocker today is: ${a.note}.

Could you help with:
1. How a technology partner gets sandbox or test credentials.
2. Whether OAuth (or another delegated auth) is available for multi-tenant apps.
3. Rate limits and any partner-programme or review requirements.

Happy to share our security documentation and a short demo.

Thanks,
[Name], Composio`; }
function openDrawer(id){
  const a = BY[id], p1 = a.pass1, d = $('#drawer');
  const diff = f => p1[f] !== a[f] ? `<del>${esc(p1[f].replaceAll(';', ' · '))}</del> → <ins>${esc(a[f].replaceAll(';', ' · '))}</ins>` : esc(a[f].replaceAll(';', ' · '));
  const ver = a.truth ? `<p class="small">Checked against primary docs in the <strong>${a.sample === 'round1' ? 'round-1 sample' : 'holdout'}</strong>:</p><div class="chips">${FIELDS.map(f =>
     `<span class="pill p-${a.truth[f] === 'X' ? 'neutral' : 'ok'}">${f}: ${a.truth[f] === 'X' ? 'not stated in docs' : 'verified'}</span>`).join('')}</div>` : '<p class="small muted">Not in a verification sample; covered by the consistency rules and the sample error rate.</p>';
  d.innerHTML = `<button class="iconbtn close" id="dclose" aria-label="Close">✕ Esc</button>
    <p class="muted small mono">#${a.id} · ${catDot(a.category)}${esc(a.category)}</p><h2>${esc(a.app)}</h2><p>${esc(a.one_liner)}</p>
    <div class="chips">${pill(a.verdict, 'v')} ${pill(a.access, 'a')} ${a.blocker ? `<span class="pill p-bad">${esc(a.blocker)}</span>` : ''}</div>
    <dl class="kv"><dt>Auth</dt><dd>${diff('auth')}</dd><dt>Credentials</dt><dd>${diff('access')}</dd><dt>API</dt><dd>${diff('api')} · ${esc(a.breadth)}</dd>
      <dt>MCP</dt><dd>${diff('mcp')} ${a.mcp === 'official' ? (a.mcp_confirmed ? '<span class="pill p-ok">confirmed this run</span>' : '<span class="pill p-pending">pass-1 claim</span>') : ''}</dd>
      <dt>Verdict</dt><dd>${diff('verdict')}</dd><dt>Builder note</dt><dd>${esc(a.note)}</dd>
      <dt>Draft conf.</dt><dd>${esc(p1.conf)}</dd><dt>Planner</dt><dd>score ${scoreOf(a, DEFAULT_W).toFixed(0)} / 100, rank #${defaultRank()[a.id]}</dd></dl>
    <dl class="kv"><dt>Composio</dt><dd>${catPill(a)} ${a.composio && a.composio.found ? `<a href="${esc(a.composio.url)}" rel="noopener">composio.dev/toolkits/${esc(a.composio.found)}</a>` : ''}</dd>
      ${a.registry_vendor && a.registry_vendor.length ? `<dt>MCP Registry</dt><dd><code>${esc(a.registry_vendor.join(', '))}</code></dd>` : ''}
      ${a.corroboration && Object.keys(a.corroboration).length ? `<dt>Auth in docs</dt><dd>${Object.entries(a.corroboration).map(([m, h]) => `<span class="pill ${h ? 'p-ok' : 'p-pending'}">${esc(m)} ${h ? 'mentioned' : 'not found'}</span>`).join(' ')}</dd>` : ''}</dl>
    <h3>Evidence</h3><ul class="small">${a.evidence.map(u => { const l = (a.links || []).find(x => x.url === u);
      const st = !l ? '' : (200 <= l.status && l.status < 400) ? `<span class="pill p-ok">${l.status}</span>` : l.browser_chars ? '<span class="pill p-official">read by browser</span>' : `<span class="pill p-bad">${l.status || 'no response'}</span>`;
      return `<li><a href="${esc(u)}" rel="noopener">${esc(u)}</a> ${st}${l && l.robots_ok === false ? ' <span class="pill p-pending">robots.txt blocks agents</span>' : ''}</li>`; }).join('')}</ul>
    <p class="small muted">${a.fetched ? '● At least one of these was read in this run.' : '○ Vendor docs root from the brief, not re-read in this run.'}</p>
    <h3>Verification</h3>${ver}
    ${a.human ? `<h3>Human check</h3><p class="small"><span class="pill p-${esc(a.human.status || 'pending')}">${esc(a.human.status || 'pending')}</span> ${esc(a.human.question)} <span class="muted">(${esc(a.human.why_agent_could_not_close_it)})</span></p>` : ''}
    <h3>How this row changed</h3>${a.history.length ? `<ol class="timeline">${a.history.map(c => `<li class="fix"><div class="t">${esc(c.field)}: ${esc(c.old)} → ${esc(c.new)}</div><div class="d">${esc(c.stage)} · ${esc(c.note)} · <a href="${esc(c.evidence)}" rel="noopener">source</a></div></li>`).join('')}</ol>` : '<p class="small muted">No change from the closed-book draft.</p>'}
    <h3>Draft Composio auth config <button class="link small" id="cpcfg">copy</button></h3><pre>${esc(authConfig(a))}</pre>
    ${a.verdict === 'outreach' || a.access === 'gated' ? `<h3>Outreach email draft <button class="link small" id="cpmail">copy</button></h3><pre style="white-space:pre-wrap">${esc(outreach(a))}</pre>` : ''}
    <div class="toolbar" style="margin-top:14px"><button class="btn primary" id="dtrace">Replay research trace</button><button class="btn" id="dcmp">${S.compare.has(a.id) ? 'Remove from compare' : 'Add to compare'}</button></div>`;
  d.classList.add('on'); $('#scrim').classList.add('on'); d.focus();
  $('#dclose').addEventListener('click', () => history.back());
  $('#cpcfg').addEventListener('click', () => copy(authConfig(a), 'Auth config'));
  $('#cpmail') && $('#cpmail').addEventListener('click', () => copy(outreach(a), 'Email draft'));
  $('#dtrace').addEventListener('click', () => { S.traceId = a.id; location.hash = 'agent'; setTimeout(() => { $('#tracepick').value = traceLabel(a); startTrace(); }, 50); });
  $('#dcmp').addEventListener('click', () => { toggleCompare(a.id); openDrawer(a.id); });
}
function closeDrawer(silent){ $('#drawer').classList.remove('on'); if (!$('#modal').classList.contains('on')) $('#scrim').classList.remove('on'); }
function openModal(){ $('#modal').classList.add('on'); $('#scrim').classList.add('on'); }
function closeModal(){ $('#modal').classList.remove('on'); if (!$('#drawer').classList.contains('on')) $('#scrim').classList.remove('on'); }
$('#mclose').addEventListener('click', closeModal);
$('#scrim').addEventListener('click', () => { if ($('#modal').classList.contains('on')) closeModal(); else if (location.hash.startsWith('#app-')) history.back(); });

/* ================= PLANNER ================= */
const AS = {free: 1, trial: .85, review: .45, paid: .35, gated: .05, na: .3}, BS = {broad: 1, moderate: .7, narrow: .45, none: 0};
const MS = {official: 1, 'docs-only': .3, community: .4, none: 0};
function authScore(a){ const s = authSet(a); if (s.includes('Unknown')) return 0; if (s.includes('API key') || s.includes('Basic')) return 1; if (s.includes('OAuth2')) return .75; if (s.includes('None')) return .6; return .5; }
const DIMS = [['access', 'Credential access', 'free 1 · trial .85 · review .45 · paid .35 · gated .05', a => AS[a.access]],
  ['auth', 'Auth simplicity', 'static key/Basic 1 · OAuth-only .75 · signed keys .5', authScore],
  ['mcp', 'Existing official MCP', 'fast path: proxy or mirror the vendor server', a => MS[a.mcp]],
  ['breadth', 'API breadth', 'broad 1 · moderate .7 · narrow .45', a => BS[a.breadth]],
  ['evidence', 'Evidence strength', 'read this run 1 · docs root only .6', a => a.fetched ? 1 : .6]];
const DEFAULT_W = {access: 8, auth: 5, mcp: 3, breadth: 4, evidence: 2};
const PRESETS = {'Fastest wins': {access: 10, auth: 8, mcp: 2, breadth: 2, evidence: 3}, 'Biggest surface': {access: 5, auth: 2, mcp: 1, breadth: 10, evidence: 2},
  'MCP-first wrap': {access: 6, auth: 3, mcp: 10, breadth: 2, evidence: 2}, 'Balanced': DEFAULT_W};
const W = {...DEFAULT_W}; let incOutreach = false, hideCat = false;
function scoreOf(a, w){ const tot = Object.values(w).reduce((x, y) => x + y, 0) || 1; return 100 * DIMS.reduce((s, [k, , , f]) => s + w[k] * f(a), 0) / tot; }
let _dr; function defaultRank(){ if (_dr) return _dr; _dr = {}; [...APPS].sort((x, y) => scoreOf(y, DEFAULT_W) - scoreOf(x, DEFAULT_W) || x.id - y.id).forEach((a, i) => _dr[a.id] = i + 1); return _dr; }
function renderPlanner(){
  if (!$('#sliders').children.length) {
    $('#sliders').innerHTML = DIMS.map(([k, l, h]) => `<div class="slider"><label for="w-${k}">${l} <span class="mono" id="wv-${k}">${W[k]}</span></label>
      <input type="range" id="w-${k}" min="0" max="10" value="${W[k]}"><p>${h}</p></div>`).join('') +
      `<label class="small"><input type="checkbox" id="incout"> Include apps that need outreach</label>` +
      (D.patterns.composio ? `<br><label class="small"><input type="checkbox" id="hidecat"> Hide apps already in Composio's catalogue</label>` : '');
    $('#presets').innerHTML = Object.keys(PRESETS).map(p => `<button class="btn" data-p="${p}">${p}</button>`).join('');
    DIMS.forEach(([k]) => $('#w-' + k).addEventListener('input', e => { W[k] = +e.target.value; renderPlanner(); }));
    $('#incout').addEventListener('change', e => { incOutreach = e.target.checked; renderPlanner(); });
    $('#hidecat') && $('#hidecat').addEventListener('change', e => { hideCat = e.target.checked; renderPlanner(); });
    $$('#presets button').forEach(b => b.addEventListener('click', () => { Object.assign(W, PRESETS[b.dataset.p]); DIMS.forEach(([k]) => $('#w-' + k).value = W[k]); renderPlanner(); }));
  }
  DIMS.forEach(([k]) => $('#wv-' + k).textContent = W[k]);
  const pool = APPS.filter(a => a.verdict !== 'wrap' && (incOutreach || a.verdict !== 'outreach') && !(hideCat && inCat(a) === 'in catalogue'));
  const ranked = pool.map(a => ({a, s: scoreOf(a, W)})).sort((x, y) => y.s - x.s || x.a.id - y.a.id), dr = defaultRank();
  const def = pool.slice().sort((x, y) => dr[x.id] - dr[y.id]).map(a => a.id);
  let html = '';
  ranked.forEach(({a, s}, i) => {
    if (i % 10 === 0) html += `<div class="sprint">Sprint ${i / 10 + 1}${i === 0 ? ' · build first' : ''}</div>`;
    const d = def.indexOf(a.id) - i;
    html += `<div class="rank" data-id="${a.id}"><span class="r">${i + 1}</span><span><strong>${esc(a.app)}</strong> <span class="muted small">${esc(a.category)}</span> ${pill(a.verdict, 'v')}</span>
      <div class="track"><div class="fill c-acc" style="width:${s}%"></div></div><span class="s">${s.toFixed(0)}</span><span class="delta ${d > 0 ? 'up' : d < 0 ? 'down' : ''}">${d > 0 ? '▲' + d : d < 0 ? '▼' + -d : '·'}</span></div>`;
  });
  $('#ranked').innerHTML = html;
  $$('#ranked .rank').forEach(r => r.addEventListener('click', () => { location.hash = 'app-' + r.dataset.id; }));
  const s1 = ranked.slice(0, 10).map(x => x.a);
  $('#plansum').innerHTML = `Sprint 1 covers <strong>${new Set(s1.map(a => a.category)).size}</strong> categories; <strong>${s1.filter(a => authSet(a).includes('OAuth2')).length}</strong> of 10 need an OAuth app registered, <strong>${s1.filter(a => a.mcp === 'official').length}</strong> already have a vendor MCP to mirror. ${pool.length} apps in the queue.`;
}

/* ================= VERIFICATION ================= */
function renderVerification(){
  const sc = D.scores[S.sample][S.stage], truth = D.verification[S.sample], ids = Object.keys(truth).map(Number);
  $$('#sampleseg button').forEach(b => b.setAttribute('aria-pressed', b.dataset.s === S.sample));
  $$('#stageseg button').forEach(b => b.setAttribute('aria-pressed', b.dataset.st === S.stage));
  $('#bigacc').textContent = sc.acc + '%';
  $('#accsub').textContent = `${sc.correct} of ${sc.checked} checkable fields correct · ${D.scores.excluded_fields[S.sample]} fields excluded (docs silent)`;
  const miss = new Map(sc.misses.map(m => [m.id + ':' + m.field, m]));
  $('#vgrid').innerHTML = `<thead><tr><th></th>${FIELDS.map(f => `<th>${f}</th>`).join('')}</tr></thead><tbody>${ids.map(i => `<tr><td class="name" data-id="${i}">${esc(BY[i].app)}</td>${FIELDS.map(f => {
    if (truth[i][f] === 'X') return '<td class="c e" data-tip="not stated in the vendor\'s docs: excluded">–</td>';
    const m = miss.get(i + ':' + f); return m ? `<td class="c x" data-tip="${esc(`said “${m.said}”, docs say “${m.truth}”`)}">✕</td>` : '<td class="c m" data-tip="matches primary docs">✓</td>'; }).join('')}</tr>`).join('')}</tbody>`;
  $$('#vgrid td.c').forEach(td => { td.addEventListener('mousemove', e => tip(e, esc(td.dataset.tip))); td.addEventListener('mouseleave', () => tip()); });
  $$('#vgrid td.name').forEach(td => td.addEventListener('click', () => { location.hash = 'app-' + td.dataset.id; }));
  $('#perfield').innerHTML = FIELDS.map(f => { const p = sc.per_field[f], v = p.checked ? Math.round(100 * p.correct / p.checked) : 0;
    return `<div class="hbar" style="cursor:default"><span>${f} <span class="muted small">${p.correct}/${p.checked}</span></span><div class="track"><div class="fill c-acc" style="width:${v}%"></div></div><span class="num mono">${v}%</span></div>`; }).join('');
  $('#stagepath').innerHTML = ['pass1', 'pass2', 'final'].map(st => { const x = D.scores[S.sample][st];
    return `<div class="hbar" style="cursor:pointer" data-st="${st}"><span>${{pass1: 'Pass 1 · closed-book', pass2: 'Pass 2 · web research', final: 'Final · after loops'}[st]}</span><div class="track"><div class="fill c-acc" style="width:${x.acc}%"></div></div><span class="num mono">${x.acc}%</span></div>`; }).join('');
  $$('#stagepath .hbar').forEach(h => h.addEventListener('click', () => { S.stage = h.dataset.st; renderVerification(); }));
}
$$('#sampleseg button').forEach(b => b.addEventListener('click', () => { S.sample = b.dataset.s; renderVerification(); }));
$$('#stageseg button').forEach(b => b.addEventListener('click', () => { S.stage = b.dataset.st; renderVerification(); }));
let playT; $('#vplay').addEventListener('click', () => { clearTimeout(playT); const seq = ['pass1', 'pass2', 'final']; let i = 0;
  const step = () => { S.stage = seq[i]; renderVerification(); if (++i < seq.length) playT = setTimeout(step, 1300); }; step(); });
function renderCalib(){
  const c = D.scores.conf_vs_corrected;
  $('#calib').innerHTML = ['low', 'med', 'high'].map(k => { const v = c[k], p = Math.round(100 * v.corrected / v.rows);
    return `<div class="hbar" style="cursor:default"><span>${k} confidence <span class="muted small">${v.corrected}/${v.rows} rows</span></span><div class="track"><div class="fill ${k === 'low' ? 'c-outreach' : k === 'med' ? 'c-caveat' : 'c-ready'}" style="width:${p}%"></div></div><span class="num mono">${p}%</span></div>`; }).join('');
  $('#humanq').innerHTML = `<thead><tr><th>App</th><th>Field</th><th>Question</th><th>Why the agent could not close it</th><th>Status</th><th>Result</th></tr></thead><tbody>${D.human.map(h =>
    `<tr><td><a href="#app-${h.id}">${esc(h.app)}</a></td><td>${esc(h.field)}</td><td>${esc(h.question)}</td><td class="small">${esc(h.why_agent_could_not_close_it)}</td><td><span class="pill p-${esc(h.status || 'pending')}">${esc(h.status || 'pending')}</span></td><td>${esc(h.result)}</td></tr>`).join('')}</tbody>`;
}

/* ================= AGENT: trace replay + live ================= */
const STEPMAP = {draft: 'draft', route: 'draft', discover: 'discover', read: 'read', registry: 'registry', catalog: 'registry', correct: 'extract', extract: 'extract',
  check: 'check', verify: 'check', judge: 'check', final: 'human'};
const traceLabel = a => `#${a.id} ${a.app}`;
$('#tracelist').innerHTML = APPS.map(a => `<option value="${esc(traceLabel(a))}">`).join('');
let traceT = null, traceI = 0, traceEv = [];
function evHTML(e){ const d = e.data || {}; const bits = [];
  if (d.values) bits.push(Object.entries(d.values).map(([k, v]) => `${k}: ${esc(String(v).replaceAll(';', ' · '))}`).join(' · '));
  if (d.urls) bits.push(d.urls.map(u => `<a href="${esc(u)}" rel="noopener">${esc(u.replace(/^https?:\/\//, '').slice(0, 70))}</a>`).join('<br>'));
  if (d.note) bits.push(esc(d.note)); if (d.url) bits.push(`<a href="${esc(d.url)}" rel="noopener">source</a>`);
  if (d.fields) bits.push(Object.entries(d.fields).map(([k, v]) => `${k} ${v === 'match' ? '✓' : '–'}`).join(' · '));
  if (d.flags) bits.push(esc(d.flags.join('; '))); if (d.reason) bits.push(esc(d.reason));
  if (d.disagreements && d.disagreements.length) bits.push('disagree: ' + esc(d.disagreements.join(', ')));
  return `<li class="${esc(e.status)}"><div class="t">${esc(e.title)}</div><div class="d">${bits.join('<br>')}</div></li>`; }
function lightStep(step){ $$('#agentflow .step').forEach(s => s.classList.toggle('live', s.dataset.step === STEPMAP[step])); }
function startTrace(){
  const v = $('#tracepick').value, m = v.match(/^#(\d+)/), a = m && BY[+m[1]]; if (!a) { toast('Pick an app from the list'); return; }
  clearTimeout(traceT); S.traceId = a.id; traceEv = a.trace; traceI = 0; $('#tracelog').innerHTML = ''; $('#tracehead').textContent = `${a.app}: recorded run, ${traceEv.length} steps`; tick();
}
function tick(){ if (traceI >= traceEv.length) { lightStep(null); return; } const e = traceEv[traceI++]; $('#tracelog').insertAdjacentHTML('beforeend', evHTML(e)); lightStep(e.step);
  traceT = setTimeout(tick, +$('#speed').value); }
$('#tplay').addEventListener('click', startTrace);
$('#tstep').addEventListener('click', () => { clearTimeout(traceT); if (!traceEv.length || traceI >= traceEv.length) { startTrace(); clearTimeout(traceT); return; }
  const e = traceEv[traceI++]; $('#tracelog').insertAdjacentHTML('beforeend', evHTML(e)); lightStep(e.step); });
$('#tall').addEventListener('click', () => { clearTimeout(traceT); const a = BY[S.traceId]; $('#tracelog').innerHTML = a.trace.map(evHTML).join(''); traceI = a.trace.length; lightStep(null); });
// live mode: only when served by `python -m agent serve`
const localServer = /^https?:$/.test(location.protocol) && /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname);
(localServer ? fetch('api/health') : Promise.reject()).then(r => r.ok ? r.json() : null).then(h => {
  if (!h || !h.ok) return;
  $('#livestatus').innerHTML = `<span class="pill p-ok">Connected to local agent server (${esc(h.mode)})</span>`; $('#livego').disabled = false;
}).catch(() => {});
$('#livego').addEventListener('click', () => {
  const m = $('#tracepick').value.match(/^#(\d+)/); if (!m) { toast('Pick an app first'); return; }
  clearTimeout(traceT); $('#tracelog').innerHTML = ''; $('#tracehead').textContent = `${BY[+m[1]].app}: streaming from server`;
  const es = new EventSource('api/research?id=' + m[1]);
  es.onmessage = ev => { const e = JSON.parse(ev.data); if (e.done) { es.close(); lightStep(null); toast('Stream finished'); return; }
    if (e.step) { $('#tracelog').insertAdjacentHTML('beforeend', evHTML(e)); lightStep(e.step); } };
  es.onerror = () => { es.close(); toast('Stream closed'); };
});

/* ================= DATA ================= */
function toCSV(rows){ const cols = ['id', 'app', 'category', 'auth', 'access', 'api', 'breadth', 'mcp', 'mcp_confirmed', 'composio_slug', 'verdict', 'blocker', 'note', 'fetched', 'evidence'];
  const q = v => `"${String(Array.isArray(v) ? v.join(' | ') : v ?? '').replaceAll('"', '""')}"`; return [cols.join(','), ...rows.map(a => cols.map(c => q(c === 'composio_slug' ? (a.composio ? a.composio.found || '' : 'not checked') : a[c])).join(','))].join('\n'); }
const slim = () => JSON.stringify({generated: D.meta.generated, fields: D.labels, apps: APPS.map(({trace, ...a}) => a)}, null, 1);
$('#djson').addEventListener('click', () => download('toolkit-readiness.json', slim(), 'application/json'));
$('#dcsv').addEventListener('click', () => download('toolkit-readiness.csv', toCSV(APPS), 'text/csv'));
$('#cjson').addEventListener('click', () => copy(slim(), 'JSON'));
$('#ccsv').addEventListener('click', () => copy(toCSV(APPS), 'CSV'));
$('#changes').innerHTML = `<thead><tr><th>Stage</th><th>App</th><th>Field</th><th>From</th><th>To</th><th>Why</th><th>Source</th></tr></thead><tbody>${D.changes.map(c =>
  `<tr><td>${esc(c.stage)}</td><td><a href="#app-${c.id}">${esc(c.app)}</a></td><td>${esc(c.field)}</td><td><del>${esc(c.old.replaceAll(';', ' · '))}</del></td><td><ins>${esc(c.new.replaceAll(';', ' · '))}</ins></td><td class="small">${esc(c.note)}</td><td><a href="${esc(c.evidence)}" rel="noopener">source</a></td></tr>`).join('')}</tbody>`;

/* ---------- keyboard ---------- */
addEventListener('keydown', e => {
  const ae = document.activeElement;
  const typing = ae.isContentEditable || /SELECT|TEXTAREA/.test(ae.tagName) || (ae.tagName === 'INPUT' && /^(text|search|number|email|url)$/.test(ae.type || 'text'));
  if (e.key === 'Escape') { if ($('#modal').classList.contains('on')) closeModal(); else if (location.hash.startsWith('#app-')) history.back(); return; }
  if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === '/') { e.preventDefault(); location.hash = 'explorer'; setTimeout(() => $('#q').focus(), 30); }
  const n = +e.key; if (n >= 1 && n <= VIEWS.length) location.hash = VIEWS[n - 1];
});

$('#tracepick').value = traceLabel(BY[S.traceId]);
renderOverview(); renderCalib(); route();
})();
