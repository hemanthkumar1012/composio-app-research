"""Output contract for one researched app. Gemini is forced to return exactly this shape (response_schema)."""
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class Access(str, Enum):
    free = "free"        # free plan / free developer account / sandbox / open source
    trial = "trial"      # time-limited trial or one-off free credits
    paid = "paid"        # credentials need a paid plan
    review = "review"    # self-serve dev access, production needs platform app review
    gated = "gated"      # customer-only, enterprise, partner application or contact-sales
    na = "na"            # no API (local CLI / OSS library)


class Verdict(str, Enum):
    ready = "ready"        # build the toolkit today
    caveat = "caveat"      # buildable, with a named caveat (trial, review, per-instance URL, paid plan)
    outreach = "outreach"  # needs a partnership, customer tenant or vendor contact first
    wrap = "wrap"          # no API: wrap a CLI as a sandboxed skill


class Mcp(str, Enum):
    official = "official"      # vendor-run MCP that acts on account data
    docs_only = "docs-only"    # vendor MCP that only searches docs
    community = "community"    # only third-party servers
    none = "none"


class Claim(BaseModel):
    field: str = Field(description="one of auth, access, api, mcp, verdict")
    value: str
    url: str = Field(description="page the value was read from")
    quote: str = Field(description="verbatim sentence copied from that page, max 200 characters")


class AppResearch(BaseModel):
    id: int
    app: str
    category: str
    one_liner: str
    auth: List[str] = Field(description="subset of: OAuth2, API key, Basic, Other, None, Unknown. PATs and bot tokens count as API key")
    access: Access
    api: str = Field(description="REST, GraphQL, REST+GraphQL, CLI or None")
    breadth: str = Field(description="broad, moderate, narrow or none")
    mcp: Mcp
    verdict: Verdict
    note: str = Field(description="one line: the main blocker or caveat a toolkit builder must know")
    confidence: str = Field(description="high, med or low")
    claims: List[Claim]
