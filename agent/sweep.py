"""Live sweep: run the agent's deterministic network tools across all 100 apps. No LLM, no API keys.

  python -m agent sweep                      -> data/sweep.json  (runs in GitHub Actions: .github/workflows/pipeline.yml)

Per app:
  registry   official MCP Registry lookup; vendor-owned namespaces are positive evidence of an official MCP
  catalog    does a Composio toolkit page exist (composio.dev/toolkits/<slug>.md)?
  links      every evidence URL: HTTP status, robots.txt verdict, readable text length
  browser    pages that come back as a JavaScript shell (or 403 to plain HTTP) are rendered in headless Chromium
  corroborate  do the evidence pages mention the auth methods the row claims? (keyword check, a weak signal)
"""
import concurrent.futures as cf
import csv
import datetime as dt
import json
import os
import pathlib
import re

import requests

from . import tools

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUTH_WORDS = {
    "OAuth2": [r"oauth"],
    "API key": [r"api[ _-]?key", r"api[ _-]?token", r"access token", r"bearer", r"personal access token", r"private app"],
    "Basic": [r"basic auth", r"http basic", r"basic authentication", r"username"],
    "Other": [r"hmac", r"jwt", r"signature", r"key[ -]pair", r"digest", r"oauth 1"],
}


def _text(url):
    """Plain HTTP read: (status, text). Never raises."""
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": tools.UA})
        if "json" in r.headers.get("content-type", ""):
            return r.status_code, r.text
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "svg"]):
            t.decompose()
        return r.status_code, re.sub(r"\s+", " ", soup.get_text(" "))
    except requests.RequestException:
        return 0, ""   # never let an error message (which contains the URL) count as page text


class Browser:
    """Headless Chromium for JS-rendered docs (the 'browser-use' loop). Optional: skipped if Playwright is absent."""

    def __init__(self):
        try:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._b = self._pw.chromium.launch()
        except Exception as e:  # noqa: BLE001
            self._b, self.error = None, str(e)

    def render(self, url):
        if not self._b:
            return None
        pg = self._b.new_page(user_agent=tools.UA)
        try:
            pg.goto(url, wait_until="networkidle", timeout=30000)
            return re.sub(r"\s+", " ", pg.inner_text("body"))
        except Exception as e:  # noqa: BLE001
            return f"ERROR {e}"
        finally:
            pg.close()

    def close(self):
        if self._b:
            self._b.close(); self._pw.stop()


def sweep_app(app, row):
    hint = app["hint"].split(" ")[0]
    out = {"id": int(app["id"]), "app": app["app"], "links": []}
    try:
        out["registry"] = tools.mcp_registry(app["app"], hint)
    except Exception as e:  # noqa: BLE001
        out["registry"] = {"error": str(e)}
    try:
        out["catalog"] = tools.composio_catalog(app["app"])
    except Exception as e:  # noqa: BLE001
        out["catalog"] = {"error": str(e)}
    for u in row["evidence"]:
        ok = tools.robots_allows(u)
        status, text = _text(u) if ok else (None, "")   # robots-disallowed pages are not fetched at all
        out["links"].append({"url": u, "status": status, "robots_ok": ok, "chars": len(text), "_text": text})
    return out


def run(out_path=None, workers=8, ids=None):
    apps = {int(a["id"]): a for a in csv.DictReader(open(ROOT / "apps.csv", encoding="utf-8"))}
    rows = {r["id"]: r for r in json.load(open(ROOT / "data" / "apps_final.json"))}
    todo = [i for i in sorted(apps) if not ids or i in ids]
    with cf.ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(lambda i: sweep_app(apps[i], rows[i]), todo))

    # browser loop: render pages that plain HTTP could not read (JS shells, 403 to bots)
    br = Browser()
    rendered = 0
    for res in results:
        for l in res["links"]:
            if "registry.modelcontextprotocol.io" in l["url"]:
                continue
            if l["robots_ok"] and (l["chars"] < 600 or l["status"] in (401, 403)):
                txt = br.render(l["url"])
                if txt and not txt.startswith("ERROR"):
                    l["browser_chars"] = len(txt); l["_text"] = txt; rendered += 1
                else:
                    l["browser_error"] = (txt or getattr(br, "error", "no browser"))[:200]
    br.close()

    for res in results:
        row = rows[res["id"]]
        blob = " ".join(l.pop("_text", "") for l in res["links"]).lower()
        claimed = [m for m in row["auth"].split(";") if m in AUTH_WORDS]
        res["corroboration"] = {m: any(re.search(p, blob) for p in AUTH_WORDS[m]) for m in claimed}
        res["evidence_chars"] = len(blob)

    meta = {"generated": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "runner": "github-actions" if os.getenv("GITHUB_ACTIONS") else "local",
            "run_url": (f"{os.getenv('GITHUB_SERVER_URL')}/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"
                        if os.getenv("GITHUB_RUN_ID") else None),
            "browser_rendered": rendered}
    out = {"meta": meta, "apps": {r["id"]: r for r in results}}
    path = pathlib.Path(out_path or ROOT / "data" / "sweep.json")
    path.write_text(json.dumps(out, indent=1))
    checked = [l for r in results for l in r["links"] if l["robots_ok"]]
    ok = sum(bool(200 <= (l["status"] or 0) < 400 or l.get("browser_chars")) for l in checked)
    tot = len(checked)
    cat = sum(bool((r.get("catalog") or {}).get("found")) for r in results)
    print(f"sweep: {len(results)} apps · links readable {ok}/{tot} · browser-rendered {rendered} · in Composio catalogue {cat}")
    return out
