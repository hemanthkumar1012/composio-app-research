# composio-app-research

A multi-agent pipeline that researches whether an app can become an AI-agent toolkit (auth, credential access, API surface, existing MCP, buildability verdict), with a verbatim-quote evidence trail, verification loops and a human queue. Run across 100 apps for Composio's AI Product Ops take-home, and published as an interactive app.

- **Live page:** https://hemanthkumar1012.github.io/composio-app-research/ (served by the `pipeline` workflow via GitHub Pages)
- **The deliverable:** `docs/index.html`, the *Toolkit Readiness Atlas*: one self-contained interactive page
- **Publish everything in one step:** `bash scripts/publish.sh` (public repo → GitHub Pages → first live sweep of all 100 apps)
- **Dataset for agents:** `docs/data.json` · `docs/llms.txt` · `data/apps_final.json`

## The app (docs/index.html)

| View | What you can do |
|---|---|
| Overview | KPI tiles, six headline patterns, a category → credentials → verdict flow diagram, a clickable category × verdict heat map, blocker clusters. Everything clicks through to the matching apps. |
| Explorer | Faceted filters with live counts, search with highlighting, sortable table or cards, compare up to 3 apps, filtered CSV export. Each app opens a drawer: field-by-field change history from the closed-book draft, evidence, verification status, human-check status, a draft Composio auth config, and an outreach email for gated apps. |
| Planner | Weighted build-queue ranking (credential access, auth simplicity, existing MCP, API breadth, evidence strength) with presets, live re-ranking, sprint grouping and rank movement. |
| Verification | Round-1 sample and holdout, pass 1 → pass 2 → final, with a field-level grid that animates misses turning into matches; per-field accuracy, confidence calibration, the five loops, the human queue. |
| Agent | The pipeline diagram, a replay of the recorded research trace for any app, and live streaming from the local server. |
| Data | JSON/CSV download or copy, field definitions, the full corrections log. |

Keyboard: `1`–`6` switch views, `/` search, `Esc` closes. Light and dark themes.

## Quick start

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...                         # Gemini only; no OpenAI key needed
python -m agent run --ids 25,37,50 --concurrency 6 # research 3 apps -> runs/<date>/{id}.json, traces/, human_queue.csv
python -m agent run                               # all 100
python -m agent run --backend composio --ids 25   # Composio COMPOSIO_SEARCH tools for search + fetch
python -m agent eval --sample holdout             # score the live agent against hand-verified ground truth
python -m agent serve                             # http://localhost:8787 : the app + live research stream (SSE)
python -m agent serve --mock                      # same, replaying the recorded run (no keys, no network)
python -m agent registry "Airtable" airtable.com  # deterministic MCP Registry lookup
python -m agent catalog "Pumble"                  # is it already a Composio toolkit? (slug-page check)
python -m agent sweep                             # live, no keys: registry + catalogue + links + browser for all 100
python -m agent links                             # HTTP-check every evidence URL (concurrent)
python -m agent build                             # offline, no keys: recompute scores/patterns + rebuild docs/
```

Env: `GEMINI_MODEL` (default `gemini-2.5-flash`; set a newer one if retired), `GEMINI_VERIFIER_MODEL` (defaults to the same; use a different model for a more independent check), `COMPOSIO_API_KEY`, `COMPOSIO_USER_ID`.

**Runnable triggers (GitHub Actions):**

| Workflow | Needs | Does |
|---|---|---|
| `pipeline` | nothing | live sweep of all 100 apps (MCP Registry, Composio catalogue, every evidence link, headless browser for JS-only docs) → rebuild → all tests → commit → deploy Pages. Also weekly. |
| `research-agent` | `GEMINI_API_KEY` secret | `mode=eval`: run the LLM agent on the hand-verified holdout and score it; `mode=run`: research any app IDs. Results as a workflow artifact + run summary. |

## How the agent works (per app, apps run concurrently)

```
researcher  draft (closed-book + confidence) -> discover (search) -> read (robots-aware, cached, retried)
            -> MCP Registry + Composio catalogue lookups -> schema-locked extraction, every claim = URL + verbatim quote
verifier    blind re-extraction from the same pages by a second model that never sees the researcher's answer
judge       SUPPORT / CONTRADICT / SILENT per claim on the cited page
router      unsupported quote | verifier disagreement | contradiction | robots block | low confidence -> human_queue.csv
```

| Piece | File |
|---|---|
| Output contract (Pydantic) | `agent/schema.py` |
| Rubric + prompts | `agent/prompts.py` |
| Tools: search, fetch, registry, catalogue, links, quote check | `agent/tools.py` |
| Cache, retries with backoff, JSONL tracer | `agent/infra.py` |
| Multi-agent loop + async runner | `agent/research.py` |
| Eval against ground truth | `agent/evaluate.py` |
| Live server (stdlib, SSE) | `agent/server.py` |
| Live sweep, no keys (registry, catalogue, links, headless browser) | `agent/sweep.py` |
| Recorded-run trace replay | `agent/replay.py` |

## How the published numbers were produced

```
data/pass1_closed_book.tsv   closed-book draft for all 100, written before any search
data/corrections_pass2.tsv   pass-2 research corrections, one row per field, with evidence URL
data/samples.json            seeded samples: round 1 (2 per category) + holdout (1 per category)
data/verification.json       ground truth read from vendor docs ('X' = docs silent, not scored)
data/corrections_verify.tsv  fixes from the verification loops
data/apps_meta.tsv           one-liner, breadth, builder note, evidence URLs, read-this-run flag
data/human_checks.csv        human spot-check queue (fill in, then `python -m agent build`)
scripts/pipeline.py          applies corrections, scores every pass, runs consistency rules, computes patterns
scripts/build_report.py      inlines web/ + data into docs/index.html, data.json, llms.txt
```

**Results:** round-1 sample 90.3% → 96.8% → 100% field accuracy (pass 1 → pass 2 → final); untouched holdout 92.9% → 100% (42/42 checkable fields).

## Tests (all offline)

```bash
python tests/test_offline.py      # namespace matcher, quote check, reproducible numbers
python tests/test_agent_loop.py   # full researcher/verifier/judge/router loop with a fake model + fake web; server SSE stream
python tests/test_ui_smoke.py     # headless click-through of every view, no JS errors, no sideways scroll at 1366/390px (needs Playwright)
```

## Honesty notes

- **How the run was produced.** I ran the 100-app research with an LLM research agent (web search and page fetch) following the protocol and rubric in `agent/prompts.py`, and verified it with the loops described on the page; ground truth was read from vendor pages. The `agent/` package runs the same protocol on Gemini (+ optional Composio tools); its loop is covered by `tests/test_agent_loop.py`, and its live holdout score is pending because a free-tier key allows 20 requests/day.
- **MCP** status changes fastest: official-MCP claims not confirmed by a page read this run are marked `?`.
- **No "already in Composio" column:** a summarised read of the catalogue sitemap contradicted the catalogue homepage, so it wasn't trusted; `python -m agent catalog` checks slug pages directly.
- Rows with `fetched=0` cite the docs root from the brief; `python -m agent links` checks they resolve. Pricing gates drift; verdicts are dated.
