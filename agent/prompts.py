"""The research protocol. The same rubric drove the run published on the case-study page."""

RUBRIC = """Rubric (apply literally):
- auth: list every method a third-party integration can use. OAuth2; API key (includes personal access tokens,
  bot tokens, service-account tokens); Basic (HTTP Basic, including key-as-username); Other (signed keys such as
  HMAC/RSA/Ed25519, JWT key-pair, OAuth 1.0a, HTTP Digest); None (no auth, e.g. a local CLI); Unknown (not published).
- access: free | trial | paid | review | gated | na.
  free = a developer can get working credentials at no cost with no time limit (free plan, dev account, sandbox, OSS).
  trial = only a time-limited trial or one-off credits. paid = credentials need a paid plan.
  review = self-serve dev credentials, but production use needs a platform app review (Meta, Google, Intuit...).
  gated = customer-only, enterprise add-on, vetted partner application, or contact-sales.
- api: REST | GraphQL | REST+GraphQL | CLI | None.  breadth: broad | moderate | narrow | none.
- mcp: official only if the vendor runs an MCP server that acts on account data. A vendor MCP that only searches
  documentation is docs-only. Third-party servers only = community.
- verdict: ready | caveat | outreach | wrap (see access; wrap = no API, wrap a CLI as a sandboxed skill).
- Never guess. If the pages do not state a field, set confidence low and say so in note."""

PASS1 = """You are researching whether {app} ({hint}, category: {category}) can become an AI-agent toolkit.
Answer from your own knowledge only (no browsing). Be honest about uncertainty in `confidence`.
{rubric}
Return JSON with keys: auth (list), access, api, mcp, verdict, confidence (high/med/low)."""

DISCOVER = """Find the official developer documentation for {app} ({hint}). I need the pages that state:
(1) API authentication methods, (2) how a developer gets credentials and which plan is required,
(3) whether {app} runs an official MCP server. List the most authoritative URLs (vendor domains first)."""

EXTRACT = """Fill the research record for {app} (id {id}, category {category}, hint {hint}).
Use ONLY the page texts below. Every non-obvious field needs a Claim whose quote is copied verbatim from a page.
If the pages are silent on a field, choose the most conservative value and set confidence to low.
{rubric}

MCP Registry lookup (deterministic, from registry.modelcontextprotocol.io): {registry}

PAGES:
{pages}"""

BLIND = """You are an independent verifier. You have NOT seen anyone else's answer.
From the page texts below only, determine for {app}: auth (list), access, mcp, verdict.
{rubric}
Return JSON: {{"auth": [...], "access": "...", "mcp": "...", "verdict": "...", "confidence": "high|med|low"}}

PAGES:
{pages}"""

JUDGE ="""Claim about {app}: "{field} = {value}".
Does the page text below SUPPORT, CONTRADICT, or say nothing (SILENT) about this claim?
Answer with one word (SUPPORT, CONTRADICT or SILENT), then one sentence quoting the deciding line.

PAGE ({url}):
{text}"""
