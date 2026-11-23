"""Per-app research loop (multi-agent), run concurrently across apps.

  researcher  pass 1 closed-book draft + confidence  ->  discover docs  ->  robots-aware fetch
              ->  MCP Registry + Composio catalogue lookups  ->  schema-locked extraction with verbatim quotes
  verifier    blind re-extraction from the SAME pages by a second model that never sees the researcher's answer
  judge       claim-level SUPPORT / CONTRADICT / SILENT on each cited page
  router      disagreement, unsupported quote, blocked page, contradiction or low confidence -> human queue

Every step is written to runs/<date>/traces/<id>.jsonl and can be streamed live (python -m agent serve).
"""
import asyncio
import csv
import re
import datetime as dt
import json
import os
import pathlib

from . import tools
from .infra import DiskCache, RateLimiter, Tracer, daily_quota, retry
from .prompts import RUBRIC, PASS1, DISCOVER, EXTRACT, JUDGE, BLIND
from .schema import AppResearch

ROOT = pathlib.Path(__file__).resolve().parents[1]
FALLBACK_MODEL = "gemini-2.5-flash"
MODEL = os.getenv("GEMINI_MODEL", FALLBACK_MODEL)   # resolved per run by resolve_model()
VERIFIER_MODEL = os.getenv("GEMINI_VERIFIER_MODEL", MODEL)
_SKIP = ("lite", "image", "tts", "live", "audio", "embedding", "exp", "preview", "thinking", "robotics")


def resolve_models(gc):
    """Ordered fallback chain. GEMINI_MODEL (+ GEMINI_FALLBACK_MODELS) if set; otherwise newest stable Flash, then newest
    stable Flash-Lite, then other Flash models. Live runs showed why: gemini-2.5-flash was retired for new keys, and a
    free-tier key ran out of its 20-requests/day Flash quota mid-eval."""
    if os.getenv("GEMINI_MODEL"):
        extra = [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "").split(",") if m.strip()]
        return [os.environ["GEMINI_MODEL"]] + extra
    try:
        names = []
        for m in gc.models.list():
            acts = getattr(m, "supported_actions", None) or ["generateContent"]
            if "generateContent" in acts:
                names.append(m.name.split("/")[-1])
    except Exception:  # noqa: BLE001
        return [FALLBACK_MODEL]
    ver = lambda n: tuple(float(x) for x in re.findall(r"\d+(?:\.\d+)?", n)[:1]) or (0.0,)
    flash = sorted((n for n in names if re.fullmatch(r"gemini-\d+(?:\.\d+)?-flash", n)), key=ver, reverse=True)
    lite = sorted((n for n in names if re.fullmatch(r"gemini-\d+(?:\.\d+)?-flash-lite", n)), key=ver, reverse=True)
    other = sorted((n for n in names if "flash" in n and n not in flash + lite and not any(t in n for t in _SKIP)), key=ver, reverse=True)
    chain = flash[:2] + lite[:2] + other[:2]
    return chain or [FALLBACK_MODEL]


def resolve_model(gc):
    return resolve_models(gc)[0]
KEY_FIELDS = ("access", "mcp", "verdict")
LIMITER = RateLimiter(int(os.getenv("GEMINI_RPM", "8")))   # shared by every model call in the process
GHA = bool(os.getenv("GITHUB_ACTIONS"))


def annotate(level, title, msg):
    """GitHub workflow annotation (readable through the API even when logs are not)."""
    if GHA:
        print(f"::{level} title={title}::" + str(msg).replace("\n", " ")[:900], flush=True)


def client():
    from google import genai
    return genai.Client()  # reads GEMINI_API_KEY


def load_apps(ids=None):
    rows = list(csv.DictReader(open(ROOT / "apps.csv", encoding="utf-8")))
    return [r for r in rows if not ids or int(r["id"]) in ids]


class Agent:
    def __init__(self, backend="gemini", cache=None, gc=None, model=None):
        self.backend, self.cache = backend, cache or DiskCache()
        self.gc = gc or client()
        self.chain = [model] if model else resolve_models(self.gc)
        self.model = self.chain[0]
        self.verifier_model = os.getenv("GEMINI_VERIFIER_MODEL", self.model)
        self.exhausted, self.used, self._mlock = set(), set(), __import__("threading").Lock()

    def _live(self, wanted):
        """The wanted model unless its daily quota is gone; then the next model in the chain."""
        with self._mlock:
            if wanted not in self.exhausted:
                return wanted
            for m in self.chain:
                if m not in self.exhausted:
                    return m
        raise RuntimeError(f"daily quota exhausted for every model in {self.chain}")

    # ---- model calls (cached, rate-limited, retried, model fallback on daily quota) ----
    def _gen(self, model, contents, json_mode=False, schema=None):
        while True:
            m = self._live(model)
            try:
                out = self._gen_once(m, contents, json_mode, schema)
                self.used.add(m)
                return out
            except Exception as e:  # noqa: BLE001
                if not daily_quota(e):
                    raise
                with self._mlock:
                    self.exhausted.add(m)
                annotate("warning", "Daily quota", f"{m} exhausted; falling back along {self.chain}")

    @retry()
    def _gen_once(self, model, contents, json_mode=False, schema=None):
        from google.genai import types
        LIMITER.wait()
        cfg = types.GenerateContentConfig(temperature=0, response_mime_type="application/json" if json_mode or schema else None,
                                          response_schema=schema)
        resp = self.gc.models.generate_content(model=model, contents=contents, config=cfg)
        return resp.text

    def llm(self, contents, model=None, json_mode=False, schema=None):
        model = model or self.model
        return self.cache.memo("llm", lambda: self._gen(model, contents, json_mode, schema), model, contents, bool(schema))

    def search(self, q):
        def go():
            if self.backend == "gemini":
                LIMITER.wait()
            m = self._live(self.model)
            try:
                return retry()(tools.search)(q, self.backend, self.gc, m)
            except Exception as e:  # noqa: BLE001
                if not daily_quota(e):
                    raise
                with self._mlock:
                    self.exhausted.add(m)
                return retry()(tools.search)(q, self.backend, self.gc, self._live(m))
        return self.cache.memo("search", go, self.backend, q)

    def fetch(self, url):
        return self.cache.memo("fetch", lambda: tools.fetch(url, self.backend), self.backend, url)

    # ---- one app ----
    def research(self, app, tracer):
        rec = {"id": int(app["id"]), "app": app["app"], "run_at": dt.datetime.utcnow().isoformat() + "Z",
               "model": self.model, "verifier_model": self.verifier_model, "backend": self.backend, "human_reasons": []}
        rec["model_chain"] = self.chain
        fmt = dict(app=app["app"], hint=app["hint"], category=app["category"], id=app["id"], rubric=RUBRIC)

        with tracer.span("draft", "Closed-book draft"):
            rec["pass1"] = json.loads(self.llm(PASS1.format(**fmt), json_mode=True))
        tracer.event("draft", f"Draft confidence: {rec['pass1'].get('confidence')}", values=rec["pass1"])

        hint = app["hint"].split(" ")[0]
        urls = [f"https://{hint}"] if "." in hint else []
        for q in (DISCOVER.format(**fmt), f"{app['app']} official MCP server and API pricing plan"):
            hits = self.search(q)
            urls += [h["url"] for h in hits]
            tracer.event("discover", f"Search: {q[:70]}", hits=len(hits))
        brand = hint.split("/")[0].split(".")[-2] if hint.count(".") else app["app"].lower()
        urls = sorted(dict.fromkeys(urls), key=lambda u: brand not in u)[:6]

        pages, blocked = {}, []
        for u in urls:
            try:
                text = self.fetch(u)
            except Exception as e:  # noqa: BLE001
                tracer.event("read", f"Fetch failed: {u}", "warn", error=str(e)); continue
            if text == tools.BLOCKED:
                blocked.append(u); tracer.event("read", f"robots.txt blocks agents: {u}", "human")
            elif len(text) > 400:
                pages[u] = text; tracer.event("read", f"Read {u}", chars=len(text))
        if blocked:
            rec["human_reasons"].append(f"robots.txt blocks agents on {blocked}")

        for name, fn in (("registry", lambda: tools.mcp_registry(app["app"], hint)),
                         ("catalog", lambda: tools.composio_catalog(app["app"]))):
            try:
                rec[name] = self.cache.memo(name, fn, app["app"])
            except Exception as e:  # noqa: BLE001
                rec[name] = {"error": str(e)}
            tracer.event("registry" if name == "registry" else "catalog",
                         "MCP Registry lookup" if name == "registry" else "Composio catalogue lookup", result=rec[name])

        joined = "\n\n".join(f"### {u}\n{t}" for u, t in pages.items())[:120000] or "(no pages could be fetched)"
        with tracer.span("extract", "Schema-locked extraction"):
            raw = self.llm(EXTRACT.format(**fmt, registry=json.dumps(rec.get("registry")), pages=joined), schema=AppResearch)
            res = AppResearch.model_validate_json(raw).model_dump(mode="json")

        # loop A: deterministic quote check
        for c in res["claims"]:
            c["supported"] = tools.quote_supported(c["quote"], pages.get(c["url"], ""))
        bad = sorted({c["field"] for c in res["claims"] if not c["supported"]})
        tracer.event("check", "Quote check", "human" if bad else "ok", unsupported=bad)
        if bad:
            rec["human_reasons"].append(f"quote not found on cited page for: {bad}")

        # loop B: independent blind verifier on the same pages
        with tracer.span("verify", "Blind re-extraction by verifier model"):
            blind = json.loads(self.llm(BLIND.format(**fmt, pages=joined), model=self.verifier_model, json_mode=True))
        disagree = [f for f in KEY_FIELDS if str(blind.get(f)) != str(res.get(f))]
        if set(map(str, blind.get("auth", []))) != set(res["auth"]):
            disagree.append("auth")
        rec["verifier"] = {"answer": blind, "disagreements": disagree, "agreement": round(1 - len(disagree) / 4, 2)}
        tracer.event("verify", f"Researcher vs verifier agreement {rec['verifier']['agreement']:.0%}",
                     "human" if disagree else "ok", disagreements=disagree)
        if disagree:
            rec["human_reasons"].append(f"researcher and verifier disagree on {disagree}")

        # loop C: claim-level judge
        rec["judge"] = []
        key_claims = sorted(res["claims"], key=lambda c: (c["field"] not in KEY_FIELDS, not c.get("supported")))[:3]
        for c in key_claims:
            text = pages.get(c["url"]) or ""
            if not text:
                continue
            ans = self.llm(JUDGE.format(app=app["app"], field=c["field"], value=c["value"], url=c["url"], text=text[:30000])).strip()
            rec["judge"].append({"field": c["field"], "value": c["value"], "verdict": ans.split()[0].upper().strip(".,:"), "why": ans})
        contra = [j["field"] for j in rec["judge"] if j["verdict"] == "CONTRADICT"]
        tracer.event("judge", f"Judge: {len(rec['judge'])} claims graded", "human" if contra else "ok", contradicted=contra)
        if contra:
            rec["human_reasons"].append(f"judge contradicted: {contra}")
        if res["confidence"] == "low":
            rec["human_reasons"].append("agent confidence low")
        if not pages:
            rec["human_reasons"].append("no vendor page could be fetched")

        rec["result"] = res
        rec["models_used"] = sorted(self.used)
        rec["needs_human"] = bool(rec["human_reasons"])
        tracer.event("final", f"Final: {res['verdict']} · access {res['access']} · MCP {res['mcp']}",
                     "human" if rec["needs_human"] else "ok", values={k: res[k] for k in ("auth", "access", "api", "mcp", "verdict")},
                     human_reasons=rec["human_reasons"])
        return rec


async def run_async(ids=None, backend="gemini", out_dir=None, concurrency=4, emit=None, cache=True):
    out = pathlib.Path(out_dir or ROOT / "runs" / dt.date.today().isoformat())
    (out / "traces").mkdir(parents=True, exist_ok=True)
    agent = Agent(backend, DiskCache(enabled=cache))
    print(f"model: {agent.model} · verifier: {agent.verifier_model} · backend: {backend}")
    annotate("notice", "Model", f"chain {agent.chain} (verifier {agent.verifier_model}), backend {backend}, {os.getenv('GEMINI_RPM', '8')} RPM")
    sem = asyncio.Semaphore(concurrency)
    results = []

    async def one(app):
        async with sem:
            tr = Tracer(out / "traces" / f"{int(app['id']):03d}.jsonl",
                        emit=(lambda ev, i=int(app["id"]): emit({"id": i, **ev})) if emit else None)
            try:
                rec = await asyncio.to_thread(agent.research, app, tr)
            except Exception as e:  # noqa: BLE001
                tr.event("final", f"Agent error: {e}", "human")
                annotate("error", f"App {app['id']} {app['app']}", f"{type(e).__name__}: {e}")
                rec = {"id": int(app["id"]), "app": app["app"], "error": str(e), "needs_human": True, "human_reasons": [f"agent error: {e}"]}
            (out / f"{int(app['id']):03d}.json").write_text(json.dumps(rec, indent=1))
            print(f"[{rec['id']:>3}] {rec['app']:<28} {'HUMAN: ' + '; '.join(rec['human_reasons']) if rec['needs_human'] else 'ok'}")
            results.append(rec)

    await asyncio.gather(*(one(a) for a in load_apps(ids)))
    queue = [{"id": r["id"], "app": r["app"], "reasons": " | ".join(r["human_reasons"])} for r in results if r["needs_human"]]
    with open(out / "human_queue.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "app", "reasons"]); w.writeheader(); w.writerows(sorted(queue, key=lambda q: q["id"]))
    print(f"\n{len(results)} researched, {len(queue)} need a human. Cache hits {agent.cache.hits}, misses {agent.cache.misses}.")
    return results


def run(ids=None, backend="gemini", out_dir=None, concurrency=4, cache=True):
    return asyncio.run(run_async(ids, backend, out_dir, concurrency, cache=cache))
