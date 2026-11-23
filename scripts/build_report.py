"""Build docs/index.html (interactive app), docs/data.json and docs/llms.txt from data/*.json + web/*.

    python scripts/build_report.py      (run scripts/pipeline.py first, or `python -m agent build`)

web/index.html, web/app.css and web/app.js are the editable sources; they are inlined into one
self-contained page so it works on GitHub Pages, as a claude.ai artifact, or opened from disk."""
import csv, html, json, pathlib, sys, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.replay import load_bundle, all_traces  # noqa: E402

D, OUT, WEB = ROOT / "data", ROOT / "docs", ROOT / "web"
REPO = "https://github.com/hemanthkumar1012/composio-app-research"  # change if you push elsewhere
AUTHOR = "V. Hemanth Kumar"
FIELDS = ["auth", "access", "api", "mcp", "verdict"]
e = lambda s: html.escape(str(s), quote=True)

b = load_bundle()
S, V, P1 = b["scores"], b["verification"], b["pass1"]
P = json.load(open(D / "patterns.json"))
apps = [b["apps"][i] for i in sorted(b["apps"])]
human = list(csv.DictReader(open(D / "human_checks.csv", encoding="utf-8")))
LE_PATH = D / "llm_eval" / "holdout.json"
LE = json.load(open(LE_PATH)) if LE_PATH.exists() else None
LE = LE if LE and LE.get("valid") else None
VERDICT = {"ready": "Build now", "caveat": "Build with caveat", "outreach": "Needs outreach", "wrap": "Wrap CLI as skill"}
ACCESS = {"free": "Free / dev account", "trial": "Trial or credits", "review": "Self-serve, then app review",
          "paid": "Paid plan", "gated": "Customer / partner / sales", "na": "No API"}
pct = lambda a, c: round(100 * a / c) if c else 0
today = dt.date.today()

# ---------------- per-app enrichment ----------------
blocker_of = {x["id"]: k for k, v in P["blockers"].items() for x in v}
traces = all_traces(b)
hum = {int(h["id"]): h for h in human}
for a in apps:
    i = a["id"]
    a["pass1"] = P1[i]
    a["blocker"] = blocker_of.get(i)
    a["history"] = [c for c in S["changes"] if c["id"] == i]
    a["sample"] = "round1" if str(i) in V["round1"] else "holdout" if str(i) in V["holdout"] else None
    a["truth"] = (V[a["sample"]][str(i)] if a["sample"] else None)
    a["human"] = hum.get(i)
    a["flags"] = [f["rule"] for f in S["consistency"]["final"] if f["id"] == i]
    a["trace"] = traces[i]

# ---------------- headline findings ----------------
acc, ver, mix, bc = P["access"], P["verdict"], P["auth_mix"], P["by_category"]
selfserve = acc.get("free", 0) + acc.get("trial", 0)
static_any = mix["OAuth2 + static key/Basic"] + mix["Static key / Basic only"]
mcp_off = P["mcp"].get("official", 0)
mcp_conf = sum(a["mcp"] == "official" and a["mcp_confirmed"] for a in apps)
r1, ho = S["round1"], S["holdout"]
p1_misses = r1["pass1"]["misses"] + ho["pass1"]["misses"]
mcp_miss = sum(m["field"] == "mcp" for m in p1_misses)
cvc = S["conf_vs_corrected"]
cal = {k: pct(v["corrected"], v["rows"]) for k, v in cvc.items()}
blk = sorted(P["blockers"].items(), key=lambda kv: -len(kv[1]))
fin, ai = bc["Finance & Fintech"], bc["AI & Media-native"]
devprod = bc["Developer & Infra"]["verdict"].get("ready", 0) + bc["Productivity & PM"]["verdict"].get("ready", 0)
findings = [
    {"big": f"{selfserve}/100", "claim": "are self-serve.", "filter": {"access": ["free", "trial"]},
     "why": f"{acc.get('free',0)} give free credentials (free plan, dev account, sandbox or open source) and {acc.get('trial',0)} a trial or credits. {ver.get('ready',0)} can be built today with no human gate."},
    {"big": f"{static_any} vs {P['auth_support']['OAuth2']}", "claim": "apps take a static key or Basic auth vs OAuth2.", "filter": {"auth": ["API key", "Basic"]},
     "why": f"{mix['OAuth2 + static key/Basic']} offer both, {mix['Static key / Basic only']} are key-only and {mix['OAuth2 only']} OAuth-only. A toolkit factory needs both schemes first-class; key-only apps are the fastest builds."},
    {"big": f"{devprod}/20", "claim": "Developer and Productivity apps are ready; Finance is the hard category.", "filter": {"category": ["Finance & Fintech"]},
     "why": f"Finance has {fin['verdict'].get('ready',0)} ready app and {fin['verdict'].get('outreach',0)} needing outreach (customer-only spend platforms, enterprise data, merchant gateways). Marketing and Ecommerce are mostly buildable with caveats."},
    {"big": f"3 × {len(blk[0][1])}", "claim": "blockers tie for most common.", "filter": {"blocker": [k for k, _ in blk[:3]]},
     "why": f"{blk[0][0]}, {blk[1][0].lower()} and {blk[2][0].lower()} each block {len(blk[0][1])} apps, and cluster by category: review hits big consumer platforms, paid plans hit AI-native and SEO tools, customer-only hits fintech and enterprise data."},
    {"big": f"{mcp_off}/100", "claim": "already run an official MCP server.", "filter": {"mcp": ["official"]},
     "why": f"{mcp_conf} were confirmed by a page read this run; the rest are queued pass-1 claims. {P['mcp'].get('docs-only',0)} vendor MCPs (Twilio, BigCommerce, Vonage) only search docs. AI-native apps are MCP-first ({ai['official_mcp']}/10): Otter's MCP works on any plan while its REST API is Enterprise-only."},
    {"big": f"{r1['pass1']['acc']}% → {ho['final']['acc']}%", "claim": "field accuracy, closed-book draft → verified holdout.", "filter": None,
     "why": f"Half the closed-book misses ({mcp_miss}/{len(p1_misses)}) were the MCP field. The agent's confidence was calibrated: {cal['low']}% of low-confidence rows needed a fix vs {cal['high']}% of high-confidence ones, so research is routed by confidence."},
]

SW = S.get("sweep")
if P.get("composio"):
    C = P["composio"]
    findings.append({"big": f"{C['in_catalogue']}/{C['checked']}", "claim": "already have a Composio toolkit page.",
                     "filter": {"composio": ["not in catalogue"], "verdict": ["ready"]},
                     "why": f"Checked live against composio.dev/toolkits in GitHub Actions. {len(C['net_new_ready'])} apps are buildable today and not yet in the catalogue: that is the real easy-win queue, not the raw {ver.get('ready',0)}."})

# ---------------- static snippets ----------------
flag_kinds = {}
for f in S["consistency"]["final"]:
    flag_kinds[f["rule"]] = flag_kinds.get(f["rule"], 0) + 1
unconf = flag_kinds.get("official MCP not confirmed by a source read this run", 0)
loops = [("Loop A", "Confidence-routed research", f"Every low/med-confidence row re-researched: {S['changed_rows_pass2']} rows changed."),
         ("Loop B", "Seeded doc check", f"20 apps, every field vs primary docs: {r1['pass1']['acc']}% → {r1['pass2']['acc']}%; 3 MCP errors left, then fixed."),
         ("Loop C", "Systemic sweep", "B showed MCP was the weak field, so remaining 'no MCP' rows were swept: Fathom → official, Vonage → docs-only."),
         ("Loop D", "Holdout", f"10 untouched apps, checked only after all fixes: {ho['pass1']['acc']}% → {ho['final']['acc']}%."),
         ("Loop E", "Consistency rules", f"9 offline rules. Logic contradictions: 0. Unconfirmed official-MCP claims: {unconf}, queued."),
         ("Loop F", "Live sweep (GitHub Actions)", (f"{SW['links_ok']}/{SW['links_total']} evidence links readable, {len(SW['browser_read'])} via headless browser; "
                    f"{len(SW['registry_confirmed'])} MCP claims confirmed by vendor registry entries; catalogue checked for all 100.") if SW else
                   "Not run yet: trigger the pipeline workflow to run registry, catalogue, link and browser checks live.")]
LOOPS = "".join(f'<div class="step"><span class="k">{e(k)}</span><h4>{e(t)}</h4><p>{e(d)}</p></div>' for k, t, d in loops)
LIMITS = "".join(f"<li>{x}</li>" for x in [
    f"With {ho['final']['checked']} holdout fields and no misses, the 95% lower bound on accuracy is about 93%: expect a few residual errors, most likely in the MCP column.",
    f"{mcp_off - mcp_conf} official-MCP claims (marked <sup>?</sup>) are pass-1 knowledge, not re-read this run.",
    f"{100 - S['fetched_rows']} rows cite the docs root from the brief and were not re-read this run; <code>python -m agent links</code> checks they resolve.",
    ("The Composio catalogue column comes from direct slug-page checks in the live sweep (a summarised read of the catalogue sitemap contradicted the homepage, so it was not used). A missing page can also mean an unusual slug; each match shows its slug." if SW else
     "No 'already in Composio' data yet: a summarised read of the catalogue sitemap contradicted the homepage, so it was not trusted; the live sweep checks slug pages directly."),
    "Keyword corroboration only tells you an evidence page mentions the auth method; it is a weak signal, used to queue rows, not to score them.",
    f"Plan and pricing gates drift; verdicts are as of {today.strftime('%d %b %Y')}."])
HUMAN_LIST = "".join(f"<li>{x}</li>" for x in [
    "<strong>Agent-blocked sources:</strong> systeme.io developer docs disallow bots (robots.txt); fanbasis and PitchBook refused fetches; Ramp's docs need JavaScript.",
    "<strong>No findable docs:</strong> fanbasis, Paygent Connect, iPayX. Recorded as 'no public API docs', not guessed.",
    "<strong>Rubric calls:</strong> what counts as self-serve (one-off credits = trial) and as an official MCP (docs-only does not count). Decided by a human, then encoded in the prompt.",
    f"<strong>Sign-off:</strong> {len(human)} items in the human queue; {sum(h['status'] not in ('', 'pending') for h in human)} closed."])
RUNTIME_LLM = (f" The Gemini runner was then executed live on the holdout ({LE['accuracy']}% of {LE['checked']} fields, model {LE.get('model')})." if LE else "")
RUNTIME_SWEEP = (f" The agent's network tools (MCP Registry, Composio catalogue, link checks, headless-browser reads) were executed live across all 100 apps in GitHub Actions on {SW['meta']['generated'][:10]}"
                 + (f" (<a href=\"{SW['meta']['run_url']}\">run log</a>)." if SW['meta'].get('run_url') else ".")) if SW else ""
RUNTIME = ("<strong>Runtime used for this run.</strong> The published 100-app run was executed by an LLM agent (Claude, Anthropic) with web search and page fetch, "
           "following the protocol and rubric in <code>agent/prompts.py</code>. The repo's runner executes the same protocol on Gemini (optional Composio search tools) "
           "with a blind verifier and judge; it was not executed in the build sandbox, which had no outbound network. Its loop is covered by offline tests with a fake model. "
           "All ground truth was read from vendor pages." + RUNTIME_SWEEP + RUNTIME_LLM)
OVERVIEW_LEDE = (f"An agent researched auth, credential access, API surface and existing MCP servers for all 100 apps; a seeded sample and an untouched holdout were then "
                 f"checked against vendors' own docs ({ho['final']['correct']}/{ho['final']['checked']} holdout fields correct). Click anything to drill in.")
VER_LEDE = (f"Samples were drawn by a seeded script before any checking: two apps per category for round 1, then one fresh app per category as a holdout checked only after "
            f"all fixes. Fields the vendor's docs did not state were excluded rather than guessed ({S['excluded_fields']['round1']} in round 1, {S['excluded_fields']['holdout']} in the holdout). "
            "Press Play to watch misses turn into matches loop by loop.")
def _list(items, fmt, limit=12):
    if not items:
        return "<p class='small muted'>None.</p>"
    more = f"<li class='muted'>+{len(items)-limit} more in data.json</li>" if len(items) > limit else ""
    return "<ul class='small'>" + "".join(f"<li>{fmt(x)}</li>" for x in items[:limit]) + more + "</ul>"
if LE:
    pf = LE["per_field"]
    LLMEVAL = ("<h2>Loop G: the Gemini agent, run live on the holdout</h2><p class='lede'>The repo's own multi-agent runner (researcher, blind verifier, judge) "
               f"executed in GitHub Actions with <code>{e(LE.get('model'))}</code> on the 10 holdout apps, scored by the same scorer against the hand-verified ground truth.</p>"
               "<div class='grid g3'>"
               f"<div class='card'><div class='bigacc' style='font-size:44px'>{LE['accuracy']}%</div><p class='small muted'>{LE['correct']} of {LE['checked']} checkable fields correct, "
               f"without any human input</p><p class='small'>Verifier agreement {LE['mean_verifier_agreement']} · routed to human: {LE['routed_to_human']} of {len(LE.get('apps', []))}</p>"
               + (f"<p class='small'><a href='{e(LE['run_url'])}'>run log</a></p>" if LE.get('run_url') else "") + "</div>"
               "<div class='card'><h3>By field</h3>" + "".join(f"<div class='hbar' style='cursor:default'><span>{e(k)} <span class='muted small'>{v['correct']}/{v['checked']}</span></span>"
               f"<div class='track'><div class='fill c-acc' style='width:{pct(v['correct'], v['checked'])}%'></div></div><span class='num mono'>{pct(v['correct'], v['checked'])}%</span></div>" for k, v in pf.items()) + "</div>"
               "<div class='card'><h3>Its misses</h3>" + (_list(LE["misses"], lambda m: f"<a href='#app-{m['id']}'>{e(m['app'])}</a> · {e(m['field'])}: said <del>{e(str(m['said']))}</del>, docs say <ins>{e(str(m['truth']))}</ins>", 15) if LE["misses"] else "<p class='small'>None.</p>") + "</div></div>")
else:
    LLMEVAL = ""
CAUGHT = ("<div class='card' style='margin-top:14px'><h3>What the first live run caught (all fixed, with regression tests)</h3><ul class='small'>"
          "<li><strong>False 'vendor-owned' MCP matches.</strong> Prefix matching on GitHub org names accepted <code>io.github.Xerolo44</code> as Xero, <code>io.github.Ramp-Jet</code> as Ramp and "
          "<code>io.github.copperline-labs</code> as Copper; a stranger's <code>app.netlify.&lt;user&gt;</code> site passed as Netlify; Binance's <code>github.io</code> docs host made every "
          "<code>io.github.*</code> entry look like Binance's. Fixed: exact org match, shared-hosting denylist; vendor matches are now recomputed from raw registry names on every build.</li>"
          "<li><strong>robots.txt over-blocking.</strong> Python's built-in reader treats a 403 on robots.txt as 'disallow everything', which flagged 30 docs sites (mostly bot protection). "
          "Replaced with RFC 9309 behaviour (4xx = no rules, 5xx = disallow); disallowed pages are now not fetched at all.</li>"
          "<li><strong>A broken link in the brief.</strong> The Neo4j hint <code>neo4j.com/docs/api</code> returns 404; the evidence now points at the docs root.</li></ul></div>")
if SW:
    a_ = lambda x: f"<a href='#app-{x['id']}'>{e(x['app'])}</a>"
    canon = lambda app: __import__("re").findall(r"[a-z0-9]+", __import__("re").sub(r"\(.*?\)", "", app).lower())
    alias = [x for x in SW["catalog"] if x["slug"] not in ("_".join(canon(x["app"])), "".join(canon(x["app"])))]
    SWEEP = (f"<div class='grid g3'>"
      f"<div class='card'><h3>Evidence links</h3><div class='bigacc' style='font-size:40px'>{pct(SW['links_ok'], SW['links_total'])}%</div>"
      f"<p class='small muted'>{SW['links_ok']} of {SW['links_total']} fetched evidence URLs readable · {len(SW['browser_read'])} needed the headless browser · {len(SW['robots_blocked'])} not fetched (robots.txt)</p>"
      f"<h3>Not readable</h3>{_list(SW['broken'], lambda x: a_(x) + f' <span class="pill p-bad">{x["status"] or "no response"}</span>')}</div>"
      f"<div class='card'><h3>MCP Registry</h3><p class='small'>{len(SW['registry_confirmed'])} official-MCP claims confirmed by a vendor-owned namespace.</p>{_list(SW['registry_confirmed'], lambda x: a_(x) + ' · <code>' + e(x['entries'][0]) + '</code>')}"
      f"<h3>Vendor entry, row says otherwise</h3>{_list(SW['registry_vendor_mismatch'], lambda x: a_(x) + f' ({e(x["mcp"])}) · <code>' + e(x['entries'][0]) + '</code>')}</div>"
      f"<div class='card'><h3>Composio catalogue</h3><p class='small'>{len(SW['catalog'])} of 100 have a toolkit page.</p>{_list(SW['catalog'], lambda x: a_(x) + ' · <code>' + e(x['slug']) + '</code>' + (' <span class="pill p-docs-only">MCP wrapper</span>' if x['kind']=='mcp-wrapper' else ''), 40)}"
      f"<h3>Matched via an alias slug (check)</h3>{_list(alias, lambda x: a_(x) + ' → <code>' + e(x['slug']) + '</code>')}"
      f"<h3>robots.txt disallows agents (not fetched)</h3>{_list(SW['robots_blocked'], a_)}"
      f"<h3>Auth claims corroborated by evidence text</h3><p class='small'>{SW['corr_hits']} of {SW['corr_claims']} ({pct(SW['corr_hits'], SW['corr_claims'])}%)</p></div></div>"
      f"<p class='small muted'>Run {e(SW['meta']['generated'])} on {e(SW['meta']['runner'])}" + (f" · <a href='{e(SW['meta']['run_url'])}'>run log</a>" if SW['meta'].get('run_url') else "") + ".</p>" + CAUGHT)
else:
    SWEEP = "<div class='card'><p class='small'>The live sweep has not run yet. In the repo: Actions → <code>pipeline</code> → Run workflow (no keys needed), or <code>python -m agent sweep</code> anywhere with internet.</p></div>"
schema = [("auth", "OAuth2, API key (incl. PATs, bot tokens), Basic, Other (signed keys, JWT, OAuth1, Digest), None, Unknown"),
          ("access", " · ".join(f"{k} = {v}" for k, v in ACCESS.items())), ("api / breadth", "REST, GraphQL, REST+GraphQL, CLI, None · broad / moderate / narrow / none"),
          ("mcp", "official (vendor MCP acting on account data) · docs-only · community · none"), ("verdict", " · ".join(f"{k} = {v}" for k, v in VERDICT.items())),
          ("mcp_confirmed", "official MCP confirmed by a page read this run"), ("fetched", "at least one evidence URL read this run"),
          ("history / trace", "every field change with its source / the recorded research steps")]
SCHEMA = "<tbody>" + "".join(f"<tr><th><code>{e(k)}</code></th><td class='small'>{e(v)}</td></tr>" for k, v in schema) + "</tbody>"
NOSCRIPT = ("<h2>Findings</h2><ol>" + "".join(f"<li><strong>{e(f['big'])}</strong> {e(f['claim'])} {e(f['why'])}</li>" for f in findings) +
            "</ol><p>Interactive views need JavaScript. The dataset is in <code>data.json</code> and <code>llms.txt</code>.</p>")

data = {"meta": {"generated": today.isoformat(), "author": AUTHOR, "repo": REPO},
        "labels": {"verdict": VERDICT, "access": ACCESS}, "apps": apps, "patterns": P, "findings": findings,
        "scores": {k: S[k] for k in ("round1", "holdout", "excluded_fields", "conf_vs_corrected", "fetched_rows", "sweep")},
        "verification": {k: V[k] for k in ("round1", "holdout")}, "human": human, "changes": S["changes"], "mcp_confirmed": mcp_conf}

template = (WEB / "index.html").read_text(encoding="utf-8")
vals = {"CSS":(WEB / "app.css").read_text(), "JS": (WEB / "app.js").read_text(),
             "DATA": json.dumps(data, separators=(",", ":")).replace("</", "<\\/"),
             "AUTHOR": e(AUTHOR), "DATE": today.strftime("%d %b %Y").upper(), "REPO": REPO, "REPO_SHORT": REPO.replace("https://", ""),
             "OVERVIEW_LEDE": e(OVERVIEW_LEDE), "VER_LEDE": e(VER_LEDE), "NOT_READY": str(100 - ver.get("ready", 0)),
             "LOOPS": LOOPS, "LIMITS": LIMITS, "HUMAN_LIST": HUMAN_LIST, "RUNTIME_NOTE": RUNTIME, "SCHEMA": SCHEMA, "NOSCRIPT": NOSCRIPT, "SWEEP": SWEEP, "LLMEVAL": LLMEVAL}
import re  # noqa: E402
missing = set(re.findall(r"\{\{([A-Z_]+)\}\}", template)) - set(vals)
assert not missing, f"unfilled placeholders: {missing}"
page = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: vals[m.group(1)], template)  # one pass: inserted JS/JSON is never re-scanned

OUT.mkdir(exist_ok=True)
(OUT / "index.html").write_text(page, encoding="utf-8")
slim = {**data, "apps": [{k: v for k, v in a.items() if k != "trace"} for a in apps]}
(OUT / "data.json").write_text(json.dumps(slim, indent=1), encoding="utf-8")
llms = [f"# Toolkit Readiness Atlas: 100 apps ({today.isoformat()})", "", "## Findings"] + \
       [f"- {f['big']} {f['claim']} {f['why']}" for f in findings] + ["", "## Apps (id | app | auth | access | api | mcp | verdict | note)"] + \
       [f"{a['id']} | {a['app']} | {a['auth']} | {a['access']} | {a['api']} | {a['mcp']} | {a['verdict']} | {a['note']}" for a in apps]
(OUT / "llms.txt").write_text("\n".join(llms) + "\n", encoding="utf-8")
print("wrote", OUT / "index.html", f"{len(page)//1024} KB")
