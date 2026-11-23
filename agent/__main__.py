"""CLI.

  python -m agent run --ids 25,37,50 [--backend composio] [--concurrency 6] [--no-cache]
  python -m agent eval --sample holdout       score the live agent against hand-verified ground truth
  python -m agent serve [--mock]              local app + live research stream (SSE) at :8787
  python -m agent registry "Airtable" airtable.com
  python -m agent catalog "Pumble"            is it already a Composio toolkit?
  python -m agent sweep                       live: registry + Composio catalogue + links + browser, all 100 (no keys)
  python -m agent links                       HTTP-check every evidence URL
  python -m agent build                       offline: rebuild data + docs/ (no keys needed)
"""
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(prog="agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--ids", default=""); r.add_argument("--out")
    r.add_argument("--backend", default="gemini", choices=["gemini", "composio"])
    r.add_argument("--concurrency", type=int, default=4); r.add_argument("--no-cache", action="store_true")
    ev = sub.add_parser("eval"); ev.add_argument("--sample", default="holdout", choices=["holdout", "round1"])
    ev.add_argument("--backend", default="gemini", choices=["gemini", "composio"])
    s = sub.add_parser("serve"); s.add_argument("--port", type=int, default=8787); s.add_argument("--mock", action="store_true")
    g = sub.add_parser("registry"); g.add_argument("app"); g.add_argument("domain")
    c = sub.add_parser("catalog"); c.add_argument("app")
    sw = sub.add_parser("sweep"); sw.add_argument("--ids", default=""); sw.add_argument("--out"); sw.add_argument("--workers", type=int, default=8)
    sub.add_parser("links"); sub.add_parser("build")
    a = ap.parse_args()

    if a.cmd == "run":
        from .research import run
        ids = {int(x) for x in a.ids.split(",") if x.strip()} or None
        run(ids, a.backend, a.out, a.concurrency, cache=not a.no_cache)
    elif a.cmd == "eval":
        from .evaluate import evaluate
        evaluate(a.sample, a.backend)
    elif a.cmd == "serve":
        from .server import serve
        serve(a.port, a.mock)
    elif a.cmd == "registry":
        from .tools import mcp_registry
        print(json.dumps(mcp_registry(a.app, a.domain), indent=1))
    elif a.cmd == "catalog":
        from .tools import composio_catalog
        print(json.dumps(composio_catalog(a.app), indent=1))
    elif a.cmd == "sweep":
        from .sweep import run as sweep
        sweep(a.out, a.workers, {int(x) for x in a.ids.split(",") if x.strip()} or None)
    elif a.cmd == "links":
        from concurrent.futures import ThreadPoolExecutor
        from .tools import link_status
        rows = [(row["app"], u) for row in json.load(open(ROOT / "data" / "apps_final.json")) for u in row["evidence"]]
        with ThreadPoolExecutor(8) as pool:
            codes = list(pool.map(lambda x: link_status(x[1]), rows))
        bad = 0
        for (app, u), s in zip(rows, codes):
            ok = 200 <= s < 400; bad += not ok
            print(f"{'ok ' if ok else 'BAD'} {s:>3} {app:<26} {u}")
        print(f"\n{bad} broken or unreachable evidence link(s) of {len(rows)}")
    elif a.cmd == "build":
        for script in ("scripts/pipeline.py", "scripts/build_report.py"):
            subprocess.run([sys.executable, str(ROOT / script)], check=True)


if __name__ == "__main__":
    main()
