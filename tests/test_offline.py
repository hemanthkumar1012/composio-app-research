"""Offline tests (no network, no keys):  python tests/test_offline.py"""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.tools import vendor_namespace, quote_supported  # noqa: E402


def test_vendor_namespace():
    assert vendor_namespace("com.airtable/mcp", "airtable.com/developers", "Airtable")
    assert vendor_namespace("io.github.mongodb-js/mongodb-mcp-server", "mongodb.com/docs/atlas/api", "MongoDB Atlas")
    assert vendor_namespace("ai.fathom.api/mcp", "fathom.ai", "Fathom")
    assert vendor_namespace("ai.fathom.api/mcp", "fathom.video", "Fathom")       # brief lists the old domain
    assert not vendor_namespace("dev.cotlet/zendesk", "zendesk.com", "Zendesk")
    assert vendor_namespace("io.github.vonage/vonage-documentation-mcp", "developer.vonage.com", "Vonage")  # vendor-owned (docs-only is judged later)
    assert not vendor_namespace("io.github.mrfentmen/klaviyo-mcp", "developers.klaviyo.com", "Klaviyo")
    assert not vendor_namespace("io.github.kesslerio/attio-mcp-server", "attio.com", "Attio")
    assert not vendor_namespace("com.insightfulpipe/klaviyo", "developers.klaviyo.com", "Klaviyo")


def test_quote_supported():
    page = "Basic authentication is the only way to access DataForSEO API. Credentials are Base64-encoded."
    assert quote_supported("Basic authentication is the only way to access DataForSEO API", page)
    assert not quote_supported("OAuth 2.0 is supported for all endpoints of the API", page)


def test_pipeline_numbers_are_reproducible():
    subprocess.run([sys.executable, str(ROOT / "scripts/pipeline.py")], check=True, capture_output=True)
    s = json.load(open(ROOT / "data/scores.json"))
    assert s["holdout"]["final"]["checked"] > 0
    assert s["round1"]["pass1"]["acc"] < s["round1"]["pass2"]["acc"] <= s["round1"]["final"]["acc"]
    rows = json.load(open(ROOT / "data/apps_final.json"))
    assert len(rows) == 100 and all(r["evidence"] for r in rows)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
