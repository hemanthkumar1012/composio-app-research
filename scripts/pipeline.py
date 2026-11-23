"""Offline build step: pass1 + corrections -> pass2 -> final, then score, check, and compute the patterns.

    python scripts/pipeline.py      # writes data/apps_final.json, data/scores.json, data/patterns.json

Needs no network or API keys. Every number on the case-study page comes out of this file."""
import csv, json, collections, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.tools import vendor_namespace  # noqa: E402  (pure function, no network)
D = ROOT / "data"
FIELDS = ["auth", "access", "api", "mcp", "verdict"]


def read_tsv(path):
    lines = [l for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#")]
    return list(csv.DictReader(lines, delimiter="\t"))


def load_apps():
    apps = {int(r["id"]): r for r in csv.DictReader(open(ROOT / "apps.csv", encoding="utf-8"))}
    return apps


def apply(rows, corrections, stage):
    out = {k: dict(v) for k, v in rows.items()}
    log = []
    for c in corrections:
        i = int(c["id"])
        old = out[i][c["field"]]
        out[i][c["field"]] = c["new"]
        log.append({"id": i, "app": out[i]["app"], "field": c["field"], "old": old, "new": c["new"],
                    "evidence": c["evidence"], "note": c["note"], "stage": stage})
    return out, log


# ---------- scoring ----------
def norm_auth(v):
    return frozenset(x.strip() for x in v.split(";") if x.strip())


def mcp_yes(v):
    return v == "official"


def same(field, pred, truth):
    if field == "auth":
        return norm_auth(pred) == norm_auth(truth)
    if field == "mcp":
        return mcp_yes(pred) == mcp_yes(truth)
    return pred == truth


def score(passes, truth):
    res = {}
    for name, rows in passes.items():
        hit = tot = 0
        per_field = {f: [0, 0] for f in FIELDS}
        misses = []
        for sid, t in truth.items():
            i = int(sid)
            for f in FIELDS:
                if t[f] == "X":
                    continue
                ok = same(f, rows[i][f], t[f])
                tot += 1; hit += ok
                per_field[f][0] += ok; per_field[f][1] += 1
                if not ok:
                    misses.append({"id": i, "app": rows[i]["app"], "field": f, "said": rows[i][f], "truth": t[f]})
        res[name] = {"correct": hit, "checked": tot, "acc": round(100 * hit / tot, 1),
                     "per_field": {f: {"correct": a, "checked": b} for f, (a, b) in per_field.items()},
                     "misses": misses}
    return res


# ---------- consistency rules (offline verification loop 2) ----------
RULES = [
    ("ready but gated", lambda r: r["verdict"] == "ready" and r["access"] == "gated"),
    ("outreach but self-serve", lambda r: r["verdict"] == "outreach" and r["access"] in ("free", "trial")),
    ("unknown auth marked buildable", lambda r: r["auth"] == "Unknown" and r["verdict"] in ("ready", "caveat")),
    ("no API but not wrap/outreach", lambda r: r["api"] in ("None", "CLI") and r["verdict"] in ("ready", "caveat")),
    ("CLI without wrap verdict", lambda r: r["api"] == "CLI" and r["verdict"] != "wrap"),
    ("review access marked ready", lambda r: r["access"] == "review" and r["verdict"] == "ready"),
    ("official MCP not confirmed by a source read this run", lambda r: r["mcp"] == "official" and not r.get("mcp_confirmed")),
    ("evidence link broken in live sweep", lambda r: any(l.get("robots_ok", True) and not (200 <= (l.get("status") or 0) < 400 or l.get("browser_chars")) for l in r.get("links") or [])),
    ("registry lists a vendor MCP the row does not call official", lambda r: bool(r.get("registry_vendor")) and r["mcp"] != "official"),
]
# Official-MCP claims that a vendor page / vendor-namespaced registry entry read in this run actually confirmed.
MCP_CONFIRMED = {8, 10, 17, 37, 51, 52, 53, 54, 60, 62, 67, 68, 72, 75, 81, 92, 93, 94, 95, 96, 97, 98, 99, 100}


def check(rows):
    flags = []
    for i, r in rows.items():
        for name, fn in RULES:
            if fn(r):
                flags.append({"id": i, "app": r["app"], "rule": name})
    return flags


# ---------- pattern analysis ----------
BLOCKER = {
    "App review / platform policy": [21, 24, 28, 29, 31, 32, 38, 39, 82, 86, 87],
    "Paid plan needed for credentials": [9, 34, 46, 47, 53, 60, 92, 94, 96, 97, 100],
    "Customer, enterprise or vetted-partner only": [10, 15, 20, 33, 44, 49, 59, 88, 89, 90, 91],
    "No public API docs found": [50, 84, 85],
    "Self-hosted / per-instance base URL": [5, 42, 45],
    "Not an API (local CLI)": [58, 98],
    "Regulatory / financial risk": [83],
}


def patterns(rows):
    n = len(rows)
    cats = list(dict.fromkeys(r["category"] for r in rows.values()))
    auth_sets = {i: norm_auth(r["auth"]) for i, r in rows.items()}
    has = lambda m: sum(1 for s in auth_sets.values() if m in s)
    keyish = {"API key", "Basic"}
    p = {
        "n": n,
        "auth_support": {m: has(m) for m in ["OAuth2", "API key", "Basic", "Other"]},
        "auth_mix": {
            "OAuth2 + static key/Basic": sum(1 for s in auth_sets.values() if "OAuth2" in s and s & keyish),
            "OAuth2 only": sum(1 for s in auth_sets.values() if "OAuth2" in s and not s & keyish),
            "Static key / Basic only": sum(1 for s in auth_sets.values() if "OAuth2" not in s and s & keyish),
            "Other only (signed keys, JWT)": sum(1 for s in auth_sets.values() if s == {"Other"}),
            "None / unknown": sum(1 for s in auth_sets.values() if s & {"None", "Unknown"}),
        },
        "access": collections.Counter(r["access"] for r in rows.values()),
        "verdict": collections.Counter(r["verdict"] for r in rows.values()),
        "mcp": collections.Counter(r["mcp"] for r in rows.values()),
        "by_category": {},
        "blockers": {k: [{"id": i, "app": rows[i]["app"]} for i in v] for k, v in BLOCKER.items()},
    }
    for c in cats:
        rs = [r for r in rows.values() if r["category"] == c]
        p["by_category"][c] = {
            "verdict": collections.Counter(r["verdict"] for r in rs),
            "access": collections.Counter(r["access"] for r in rs),
            "self_serve": sum(r["access"] in ("free", "trial") for r in rs),
            "official_mcp": sum(r["mcp"] == "official" for r in rs),
            "oauth": sum("OAuth2" in norm_auth(r["auth"]) for r in rs),
        }
    p["easy_wins"] = [{"id": i, "app": r["app"]} for i, r in rows.items()
                      if r["verdict"] == "ready" and r["access"] in ("free", "trial")]
    p["outreach"] = [{"id": i, "app": r["app"]} for i, r in rows.items() if r["verdict"] == "outreach"]
    if any(r.get("composio") is not None for r in rows.values()):
        inc = lambda r: bool((r.get("composio") or {}).get("found"))
        p["composio"] = {"in_catalogue": sum(inc(r) for r in rows.values()),
                         "checked": sum(r.get("composio") is not None for r in rows.values()),
                         "net_new_ready": [{"id": i, "app": r["app"]} for i, r in rows.items() if r["verdict"] == "ready" and not inc(r)],
                         "by_category": {c: sum(inc(r) for r in rows.values() if r["category"] == c) for c in cats}}
    # blocker classification must cover every non-ready app exactly once
    covered = sorted(i for v in BLOCKER.values() for i in v)
    nonready = sorted(i for i, r in rows.items() if r["verdict"] != "ready")
    assert covered == nonready, ("blocker map out of sync", set(covered) ^ set(nonready))
    return p


def merge_sweep(final):
    """Fold data/sweep.json (live run of the agent's network tools in GitHub Actions) into the final rows."""
    path = D / "sweep.json"
    if not path.exists():
        for r in final.values():
            r["composio"] = r["links"] = r["corroboration"] = None; r["registry_vendor"] = []
        return None
    SW = json.load(open(path))
    stats = {"meta": SW["meta"], "links_total": 0, "links_ok": 0, "broken": [], "robots_blocked": [], "browser_read": [],
             "catalog": [], "catalog_errors": 0, "registry_confirmed": [], "registry_vendor_mismatch": [], "corr_claims": 0, "corr_hits": 0,
             "uncorroborated": []}
    for i, r in final.items():
        s = SW["apps"].get(str(i), {})
        cat = s.get("catalog") or {}
        r["composio"] = None if cat.get("error") or not cat else {"found": cat.get("found"), "url": cat.get("url"), "kind": cat.get("kind")}
        stats["catalog_errors"] += bool(cat.get("error"))
        if r["composio"] and r["composio"]["found"]:
            stats["catalog"].append({"id": i, "app": r["app"], "slug": r["composio"]["found"], "kind": r["composio"]["kind"]})
        reg = s.get("registry") or {}
        # recompute vendor ownership from ALL names with the current matcher, so matcher fixes apply without a re-run
        names = sorted(set(reg.get("vendor_entries", []) + reg.get("other_entries", [])))
        r["registry_vendor"] = [n for n in names if vendor_namespace(n, r["hint"].split(" ")[0], r["app"])]
        if r["registry_vendor"] and r["mcp"] == "official" and not r["mcp_confirmed"]:
            r["mcp_confirmed"] = True; stats["registry_confirmed"].append({"id": i, "app": r["app"], "entries": r["registry_vendor"]})
        if r["registry_vendor"] and r["mcp"] != "official":
            stats["registry_vendor_mismatch"].append({"id": i, "app": r["app"], "mcp": r["mcp"], "entries": r["registry_vendor"]})
        r["links"] = s.get("links", [])
        for l in r["links"]:
            if not l.get("robots_ok", True):   # not fetched: robots.txt disallows agents
                stats["robots_blocked"].append({"id": i, "app": r["app"], "url": l["url"]}); continue
            stats["links_total"] += 1
            ok = 200 <= (l.get("status") or 0) < 400 or bool(l.get("browser_chars"))
            stats["links_ok"] += ok
            if not ok:
                stats["broken"].append({"id": i, "app": r["app"], "url": l["url"], "status": l.get("status")})
            if l.get("browser_chars"):
                stats["browser_read"].append({"id": i, "app": r["app"], "url": l["url"], "chars": l["browser_chars"]})
        r["corroboration"] = s.get("corroboration", {})
        for m, hit in (r["corroboration"] or {}).items():
            stats["corr_claims"] += 1; stats["corr_hits"] += bool(hit)
            if not hit:
                stats["uncorroborated"].append({"id": i, "app": r["app"], "auth": m})
    return stats


def main():
    apps = load_apps()
    p1 = {int(r["id"]): {"app": r["app"], **{f: r[f] for f in FIELDS}, "conf": r["conf"]}
          for r in read_tsv(D / "pass1_closed_book.tsv")}
    for i, r in p1.items():
        r["category"] = apps[i]["category"]
    p2, log2 = apply(p1, read_tsv(D / "corrections_pass2.tsv"), "pass2-research")
    final, log3 = apply(p2, read_tsv(D / "corrections_verify.tsv"), "verify-loops")

    meta = {int(r["id"]): r for r in read_tsv(D / "apps_meta.tsv")}
    for i, r in final.items():
        m = meta[i]
        r.update({"id": i, "hint": apps[i]["hint"], "one_liner": m["one_liner"], "breadth": m["breadth"],
                  "note": m["note"], "evidence": m["evidence"].split(), "fetched": m["fetched"] == "1"})
    for i in p1:
        p1[i]["fetched"] = p2[i]["fetched"] = final[i]["fetched"]
        p1[i]["id"] = p2[i]["id"] = i
        p1[i]["mcp_confirmed"] = p2[i]["mcp_confirmed"] = i in MCP_CONFIRMED
    for i, r in final.items():
        r["mcp_confirmed"] = i in MCP_CONFIRMED
    sweep = merge_sweep(final)

    ver = json.load(open(D / "verification.json"))
    samples = json.load(open(D / "samples.json"))
    passes = {"pass1": p1, "pass2": p2, "final": final}
    scores = {
        "round1": score(passes, ver["round1"]),
        "holdout": score(passes, ver["holdout"]),
        "excluded_fields": {k: sum(1 for t in ver[k].values() for f in FIELDS if t[f] == "X") for k in ("round1", "holdout")},
        "samples": samples,
        "consistency": {k: check(v) for k, v in passes.items()},
        "changes": log2 + log3,
        "changed_rows_pass2": len({c["id"] for c in log2}),
        "changed_rows_verify": len({c["id"] for c in log3}),
        "fetched_rows": sum(r["fetched"] for r in final.values()),
        "pass1_conf": collections.Counter(r["conf"] for r in p1.values()),
        "sweep": sweep,
    }
    # how good was pass-1's self-reported confidence? (share of pass-1 rows later corrected, by confidence)
    changed = {c["id"] for c in log2 + log3}
    scores["conf_vs_corrected"] = {c: {"rows": sum(r["conf"] == c for r in p1.values()),
                                       "corrected": sum(r["conf"] == c and i in changed for i, r in p1.items())}
                                   for c in ("high", "med", "low")}

    json.dump(list(final.values()), open(D / "apps_final.json", "w"), indent=1)
    json.dump(scores, open(D / "scores.json", "w"), indent=1)
    json.dump(patterns(final), open(D / "patterns.json", "w"), indent=1, default=dict)

    for k in ("round1", "holdout"):
        print(k, {n: f'{s["acc"]}% ({s["correct"]}/{s["checked"]})' for n, s in scores[k].items()})
    print("consistency flags:", {k: len(v) for k, v in scores["consistency"].items()})
    print("conf vs corrected:", scores["conf_vs_corrected"])


if __name__ == "__main__":
    main()
