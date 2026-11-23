"""Tools the research agent can call: web search, page fetch, MCP Registry lookup, link check.

Search/fetch backends:
  gemini   - Gemini with Google Search grounding (only needs GEMINI_API_KEY)  [default]
  composio - Composio's COMPOSIO_SEARCH toolkit (Tavily search + Exa page fetch) via the Composio SDK
"""
import os
import re
import json
import urllib.parse
import urllib.robotparser

import requests
from bs4 import BeautifulSoup

from .infra import retry

UA ="composio-app-research/1.0 (+https://github.com/hemanthkumar1012/composio-app-research)"
REGISTRY = "https://registry.modelcontextprotocol.io/v0/servers"
BLOCKED = "BLOCKED_BY_ROBOTS"


# ---------------- search ----------------
def search(query: str, backend: str = "gemini", gemini_client=None, model: str = None) -> list:
    """Return [{title, url}] for a query."""
    if backend == "composio":
        return _composio_search(query)
    from google.genai import types
    resp = gemini_client.models.generate_content(
        model=model,
        contents=query,
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0),
    )
    out = []
    meta = resp.candidates[0].grounding_metadata if resp.candidates else None
    for ch in (getattr(meta, "grounding_chunks", None) or []):
        web = getattr(ch, "web", None)
        if web and web.uri:
            out.append({"title": web.title or "", "url": resolve_redirect(web.uri)})
    return out


def _composio():
    from composio import Composio  # optional dependency
    return Composio(api_key=os.environ["COMPOSIO_API_KEY"])


def _composio_search(query: str) -> list:
    res = _composio().tools.execute("COMPOSIO_SEARCH_TAVILY", user_id=os.getenv("COMPOSIO_USER_ID", "default"),
                                    arguments={"query": query})
    data = res.get("data", res) if isinstance(res, dict) else res
    items = data.get("results") or data.get("response_data", {}).get("results", []) if isinstance(data, dict) else []
    return [{"title": i.get("title", ""), "url": i.get("url", "")} for i in items if i.get("url")]


def resolve_redirect(url: str) -> str:
    """Grounding chunks come back as Google redirect links; follow them to the real page."""
    if "grounding-api-redirect" not in url:
        return url
    try:
        return requests.head(url, allow_redirects=True, timeout=10, headers={"User-Agent": UA}).url
    except requests.RequestException:
        return url


# ---------------- fetch ----------------
@retry()
def _get(url, **kw):
    r = requests.get(url, timeout=20, headers={"User-Agent": UA}, **kw)
    if r.status_code in (429, 500, 502, 503, 504):
        r.raise_for_status()  # HTTPError carries .response -> retried with backoff
    r.raise_for_status()
    return r


def composio_catalog(app: str) -> dict:
    """Deterministic check: does composio.dev/toolkits/<slug>.md exist for any likely slug?
    (A summarised read of the catalogue sitemap proved unreliable, so this checks slug pages directly.)"""
    base = re.sub(r"\(.*?\)", "", app).strip().lower()
    words = re.findall(r"[a-z0-9]+", base)
    # No first-word fallback: "Salesforce Commerce Cloud" must not match the "salesforce" toolkit.
    cands = list(dict.fromkeys(CATALOG_ALIASES.get(app, []) + ["_".join(words), "".join(words), "_".join(words) + "_mcp"]))
    checked = []
    for slug in cands:
        url = f"https://composio.dev/toolkits/{slug}.md"
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": UA})
            ok = r.status_code == 200 and (f'"slug": "{slug}"' in r.text or f'"slug":"{slug}"' in r.text)
        except requests.RequestException:
            ok = False
        checked.append({"slug": slug, "found": ok})
        if ok:
            return {"found": slug, "url": url.replace(".md", ""), "kind": "mcp-wrapper" if slug.endswith("_mcp") else "toolkit",
                    "checked": checked}
    return {"found": None, "checked": checked}


# Known slug spellings for multi-word names (checked first). Every match is shown with its slug so a human can judge it.
CATALOG_ALIASES = {
    "Zoho CRM": ["zoho", "zoho_crm"], "Monday.com": ["monday"], "Help Scout": ["help_scout", "helpscout"],
    "Lark (Larksuite)": ["lark", "larksuite"], "Google Ads": ["googleads", "google_ads"], "Meta Ads": ["metaads", "meta_ads", "facebook_ads"],
    "LinkedIn Ads": ["linkedin_ads"], "GoHighLevel": ["highlevel", "gohighlevel"], "WhatsApp Business": ["whatsapp"],
    "Threads (Meta)": ["threads"], "Magento (Adobe Commerce)": ["magento", "adobe_commerce"],
    "Amazon Selling Partner": ["amazon_selling_partner", "amazon_sp_api", "amazon_seller"], "Salesforce Commerce Cloud": ["salesforce_commerce_cloud"],
    "MongoDB Atlas": ["mongodb_atlas", "mongodb"], "Bright Data": ["brightdata", "bright_data"], "Otter AI": ["otter_ai", "otter", "otter_ai_mcp"],
    "Mermaid CLI": ["mermaid_cli", "mermaid", "mermaid_chart_mcp"], "YouTube Transcript": ["youtube_transcript", "transcriptapi"],
    "Paygent Connect": ["paygent"], "Waterfall.io": ["waterfall"], "systeme.io": ["systeme", "systeme_io"], "Zoho Cliq": ["zoho_cliq"],
    "SE Ranking": ["seranking", "se_ranking"], "Devin": ["devin", "devin_mcp"], "NotebookLM": ["notebooklm", "notebook_lm"],
    "Pylon": ["pylon", "pylon_mcp"], "Front": ["front", "frontapp"], "DataForSEO": ["dataforseo"], "QuickBooks": ["quickbooks"],
    "Twilio": ["twilio"], "Jira": ["jira"],
}
def robots_allows(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser(f"{parts.scheme}://{parts.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        return True
    return rp.can_fetch(UA, url)


def fetch(url: str, backend: str = "gemini", max_chars: int = 30000) -> str:
    """Readable page text. Respects robots.txt: a disallowed page returns BLOCKED and goes to the human queue."""
    if not robots_allows(url):
        return BLOCKED
    if backend == "composio":
        res = _composio().tools.execute("COMPOSIO_SEARCH_FETCH_URL_CONTENT",
                                        user_id=os.getenv("COMPOSIO_USER_ID", "default"), arguments={"url": url})
        return json.dumps(res)[:max_chars]
    r = _get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "svg"]):
        tag.decompose()
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n"))
    return text[:max_chars]


# ---------------- MCP Registry ----------------
def vendor_namespace(server_name: str, domain: str, app: str) -> bool:
    """True if a registry namespace is owned by the vendor: reverse-DNS of its domain (com.airtable/...)
    or the vendor's GitHub org (io.github.mongodb-js/...). Registry namespaces are domain/org-verified."""
    ns = server_name.split("/")[0].lower()
    host = domain.lower().split("/")[0]
    labels = host.split(".")
    root = ".".join(labels[-2:]) if len(labels) >= 2 else host
    rev = ".".join(reversed(root.split(".")))
    if ns == rev or ns.startswith(rev + "."):
        return True
    brand = labels[-2] if len(labels) >= 2 else host                     # mongodb.com -> "mongodb"
    first = re.sub(r"[^a-z0-9]", "", app.lower().split()[0])            # "MongoDB Atlas" -> "mongodb"
    if ns.startswith("io.github."):
        org = re.sub(r"[^a-z0-9]", "", ns[len("io.github."):])
        return any(k and org.startswith(k) for k in (brand, first))
    ns_labels = ns.split(".")
    # same brand on another TLD, e.g. ai.fathom.api while the brief lists fathom.video
    return len(ns_labels) >= 2 and ns_labels[1] in (brand, first)


def mcp_registry(app: str, domain: str) -> dict:
    """Positive evidence only: vendors often run MCP servers that are not in the registry."""
    q = app.split(" (")[0]
    r = _get(REGISTRY, params={"search": q, "limit": 50})
    names = []
    for item in r.json().get("servers", []):
        srv = item.get("server", item)
        if srv.get("name"):
            names.append(srv["name"])
    names = sorted(set(names))
    vendor = [n for n in names if vendor_namespace(n, domain, q)]
    return {"query": q, "vendor_entries": vendor, "other_entries": [n for n in names if n not in vendor]}


# ---------------- links ----------------
def link_status(url: str) -> int:
    try:
        r = requests.head(url, allow_redirects=True, timeout=15, headers={"User-Agent": UA})
        if r.status_code in (403, 405):
            r = requests.get(url, allow_redirects=True, timeout=15, headers={"User-Agent": UA})
        return r.status_code
    except requests.RequestException:
        return 0


def quote_supported(quote: str, page_text: str) -> bool:
    """Cheap, deterministic check that a claimed quote really appears on the page (whitespace/case-insensitive)."""
    norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[“”\"'`’]", "", s)).strip().lower()
    q, t = norm(quote), norm(page_text)
    if not q:
        return False
    if q in t:
        return True
    words = q.split()
    window = " ".join(words[: max(6, len(words) // 2)])  # tolerate truncated/edited tails
    return len(words) >= 6 and window in t
