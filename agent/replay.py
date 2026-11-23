"""Turn the recorded run (data/*.json) into a step-by-step trace per app.

The same events feed the page's trace replay and the local server's mock stream, so what you watch is the
recorded run, not an animation made up for the demo."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIELDS = ["auth", "access", "api", "mcp", "verdict"]


def load_bundle():
    d = ROOT / "data"
    pass1 = {}
    for line in open(d / "pass1_closed_book.tsv", encoding="utf-8"):
        if line.startswith("#") or line.startswith("id\t") or not line.strip():
            continue
        i, app, auth, access, api, mcp, verdict, conf = line.rstrip("\n").split("\t")
        pass1[int(i)] = {"auth": auth, "access": access, "api": api, "mcp": mcp, "verdict": verdict, "conf": conf}
    return {
        "apps": {a["id"]: a for a in json.load(open(d / "apps_final.json"))},
        "scores": json.load(open(d / "scores.json")),
        "verification": json.load(open(d / "verification.json")),
        "pass1": pass1,
    }


def trace(app_id, b):
    a, p1, S, V = b["apps"][app_id], b["pass1"][app_id], b["scores"], b["verification"]
    changes = [c for c in S["changes"] if c["id"] == app_id]
    ev = []
    add = lambda step, title, status="ok", **data: ev.append({"step": step, "title": title, "status": status, "data": data})

    add("draft", f"Closed-book draft (confidence: {p1['conf']})", "ok" if p1["conf"] == "high" else "warn",
        values={f: p1[f] for f in FIELDS})
    routed = p1["conf"] != "high" or any(c["stage"] == "pass2-research" for c in changes)
    add("route", "Routed to web research" if routed else "High confidence: accepted, spot-checked by samples",
        "ok", reason=f"pass-1 confidence {p1['conf']}")
    reg = [u for u in a["evidence"] if "registry.modelcontextprotocol.io" in u]
    docs = [u for u in a["evidence"] if u not in reg]
    add("read", f"{'Read' if a['fetched'] else 'Cited (not re-read)'} {len(docs)} vendor page(s)",
        "ok" if a["fetched"] else "warn", urls=docs)
    if reg:
        add("registry", "MCP Registry lookup", "ok", urls=reg, mcp=a["mcp"])
    for c in changes:
        add("correct", f"{c['field']}: {c['old']} → {c['new']} ({c['stage']})", "fix", note=c["note"], url=c["evidence"])
    for sample in ("round1", "holdout"):
        t = V[sample].get(str(app_id))
        if t:
            ok = {f: ("excluded" if t[f] == "X" else "match") for f in FIELDS}
            misses = [m for m in S[sample]["final"]["misses"] if m["id"] == app_id]
            add("verify", f"Checked field-by-field against primary docs ({'round 1 sample' if sample == 'round1' else 'holdout'})",
                "fix" if misses else "ok", fields=ok, sources=t["src"])
    flags = [f["rule"] for f in S["consistency"]["final"] if f["id"] == app_id]
    if flags:
        add("check", "Consistency rules flagged this row", "human", flags=flags)
    add("final", f"Final: {a['verdict']} · access {a['access']} · MCP {a['mcp']}",
        {"ready": "ok", "caveat": "warn", "outreach": "human", "wrap": "warn"}[a["verdict"]],
        values={f: a[f] for f in FIELDS}, note=a["note"])
    return ev


def all_traces(b=None):
    b = b or load_bundle()
    return {i: trace(i, b) for i in b["apps"]}
