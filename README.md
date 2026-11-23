# composio-app-research

A multi-agent pipeline that researches whether an app can become an AI-agent toolkit (auth, credential access, API surface, existing MCP, buildability verdict), with a verbatim-quote evidence trail, verification loops and a human queue. Run across 100 apps for Composio's AI Product Ops take-home, and published as an interactive app.

- **Live page:** https://hemanthkumar1012.github.io/composio-app-research/ (served by the `pipeline` workflow via GitHub Pages)
- **The deliverable:** `docs/index.html`, the *Toolkit Readiness Atlas*: one self-contained interactive page
- **Publish everything in one step:** `bash scripts/publish.sh` (public repo → GitHub Pages → first live sweep of all 100 apps)
- **Dataset for agents:** `docs/data.json` · `docs/llms.txt` · `data/apps_final.json`

## Results at a glance

| | |
|---|---|
| Apps researched | **100** across 10 categories, every field with evidence URLs |
| Already Composio toolkits | **81** (checked live against composio.dev); **19** are not |
| Buildable today, no human gate | **58** · self-serve: **70** (48 free, 22 trial or credits) |
| Official vendor MCP server | **56** (3 of them only search docs) |
| Accuracy, round 1 (20 apps, 93 fields) | 90.3% closed-book → 96.8% after web research → 100% after fixes |
| Accuracy, untouched holdout (10 apps, 42 fields) | 92.9% → **100% (42/42)** |
| Live sweep in GitHub Actions | 131/132 evidence links readable (5 via headless browser) |
| Human queue | 10 items the agent could not settle on its own |

## What I would do next for Composio

1. **Build now (5):** LiveAgent, Vonage, systeme.io, SE Ranking, Reducto: not yet in the catalogue, but self-serve and documented.
2. **Build with a workaround (5):** WooCommerce and Magento (per-store base URL), Squarespace and Ecwid (paid plan for credentials), Binance (financial-risk review).
3. **Partnership outreach (8):** DealCloud, Gladly, Salesforce Commerce Cloud, Amazon Selling Partner, Waterfall.io (customer or partner-only), fanbasis, Paygent Connect, iPayX (no public docs). Each app's drawer has an outreach draft.
4. **Ship as a skill (1):** Sherlock is a local CLI, not a hosted API.

Product calls: make API-key auth first-class (74/100 accept a static key, 30 only that); run app review for Meta, Google, Slack and Intuit as one programme (11 apps); position toolkits against docs-only vendor MCPs (Twilio, BigCommerce, Vonage); keep the scheduled sweep running to catch doc drift.

## Brief checklist

| The brief asked for | Where it is |
|---|---|
| 100 apps: category, one-liner, auth, self-serve vs gated, API surface, existing MCP, verdict, blocker, evidence | Explorer view, app drawers, `data/apps_final.json`, CSV/JSON in the Data view |
| Patterns, insight over a raw table | Overview: 7 findings, flow diagram, heat map, blocker clusters, "What I would do next" |
| An agent or pipeline, ideally with Composio | `agent/` (Gemini researcher, blind verifier, claim judge, human router); Composio catalogue check; optional Composio search tools |
| Where a human was needed | Verification view: human spot-check queue; Honesty notes below |
| Verification loops on a sample, accuracy moving up | Verification view: seeded round 1 and untouched holdout, 7 loops, field-level grid |
| The agent's mistakes shown | Corrections log (Data view) and "What the first live run caught" |
| One HTML page, live link, repo with README | `docs/index.html` on GitHub Pages, this repo |

## The app (docs/index.html)

| View | What you can do |
|---|---|
| Overview | KPI tiles, seven headline patterns, a category → credentials → verdict flow diagram, a clickable category × verdict heat map, blocker clusters, an action plan for the 19 catalogue gaps and a brief checklist. Everything clicks through to the matching apps. |
| Explorer | Faceted filters with live counts, search with highlighting, sortable table or cards, compare up to 3 apps, filtered CSV export. Each app opens a drawer: field-by-field change history from the closed-book draft, evidence, verification status, human-check status, a draft Composio auth config, and an outreach email for gated apps. |
| Planner | Weighted build-queue ranking (credential access, auth simplicity, existing MCP, API breadth, evidence strength) with presets, live re-ranking, sprint grouping and rank movement. |
| Verification | Round-1 sample and holdout, pass 1 → pass 2 → final, with a field-level grid that animates misses turning into matches; per-field accuracy, confidence calibration, the seven loops, the live sweep, the human queue. |
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
