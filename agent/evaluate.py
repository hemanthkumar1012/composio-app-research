"""Regression eval: run the live agent on the seeded samples and score it against the hand-verified ground truth
(data/verification.json) with the SAME scorer used for the published numbers. Use it after every prompt change.

    python -m agent eval --sample holdout       # 10 apps
    python -m agent eval --sample round1        # 20 apps
"""
import importlib.util
import json
import pathlib
import sys

from .research import run

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _pipeline():
    spec = importlib.util.spec_from_file_location("pipeline", ROOT / "scripts" / "pipeline.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def evaluate(sample="holdout", backend="gemini", out_dir=None):
    pl = _pipeline()
    truth = json.load(open(ROOT / "data" / "verification.json"))[sample]
    ids = {int(i) for i in truth}
    out_dir = out_dir or ROOT / "runs" / f"eval-{sample}"
    recs = run(ids, backend, out_dir)
    rows = {}
    for r in recs:
        res = r.get("result") or {}
        rows[r["id"]] = {"app": r["app"], "auth": ";".join(res.get("auth", ["Unknown"])), "access": res.get("access", "?"),
                         "api": res.get("api", "?"), "mcp": res.get("mcp", "?"), "verdict": res.get("verdict", "?")}
    score = pl.score({"agent": rows}, truth)["agent"]
    agree = [r["verifier"]["agreement"] for r in recs if "verifier" in r]
    report = {"sample": sample, "accuracy": score["acc"], "correct": score["correct"], "checked": score["checked"],
              "per_field": score["per_field"], "misses": score["misses"],
              "mean_verifier_agreement": round(sum(agree) / len(agree), 3) if agree else None,
              "routed_to_human": sum(r["needs_human"] for r in recs),
              "errors": sum("error" in r for r in recs), "model": next((r.get("model") for r in recs if r.get("model")), None)}
    report["valid"] = report["errors"] == 0
    (pathlib.Path(out_dir) / "eval_report.json").write_text(json.dumps(report, indent=1))
    if not report["valid"]:
        print(f"\nEVAL INVALID: {report['errors']} of {len(recs)} apps errored (first: {next(r['error'] for r in recs if 'error' in r)[:200]})")
        sys.exit(1)   # never publish a score made of errors
    print(f"\n{sample}: {score['acc']}% ({score['correct']}/{score['checked']} fields) with {report['model']}")
    for m in score["misses"]:
        print(f"  miss  {m['app']:<24} {m['field']:<8} said {m['said']!r:<22} truth {m['truth']!r}")
    return report
