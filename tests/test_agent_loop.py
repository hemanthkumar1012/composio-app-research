"""Drive the whole researcher -> verifier -> judge -> router loop with a fake model and a fake web.
No network, no keys:  python tests/test_agent_loop.py"""
import json, pathlib, sys, threading, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import tools, research, server  # noqa: E402
from agent.infra import DiskCache, Tracer  # noqa: E402

PAGE = ("Pumble API Overview. This feature is available on all plans. By using the Pumble API addon you can "
        "interact with Pumble's API documentation without using any complex authentication processes. "
        "Once your API addon is installed, you can generate API keys directly in Pumble. "
        "Click on API in the left sidebar, select Add API key, enter a name and click Generate. The full list of "
        "available actions is in the Swagger documentation; enter your API key in the Authorize part.")


class FakeAgent(research.Agent):
    def __init__(self, verifier_access="free", judge="SUPPORT"):
        super().__init__("gemini", DiskCache(enabled=False), gc=object())
        self.verifier_access, self.judge_word = verifier_access, judge

    def _gen(self, model, contents, json_mode=False, schema=None):
        if contents.startswith("You are researching"):
            return json.dumps({"auth": ["API key"], "access": "free", "api": "REST", "mcp": "none", "verdict": "caveat", "confidence": "low"})
        if contents.startswith("You are an independent verifier"):
            return json.dumps({"auth": ["API key"], "access": self.verifier_access, "mcp": "none", "verdict": "ready", "confidence": "high"})
        if contents.startswith("Claim about"):
            return f"{self.judge_word} The page says it is available on all plans."
        return json.dumps({"id": 25, "app": "Pumble", "category": "Communications", "one_liner": "Team chat",
                           "auth": ["API key"], "access": "free", "api": "REST", "breadth": "narrow", "mcp": "none",
                           "verdict": "ready", "note": "API add-on keys on all plans", "confidence": "high",
                           "claims": [{"field": "access", "value": "free", "url": "https://pumble.com/help/api",
                                       "quote": "This feature is available on all plans."}]})


def fake_web(monkey_blocked=False):
    tools.search = lambda q, backend, gc, model: [{"title": "Pumble API", "url": "https://pumble.com/help/api"}]
    tools.fetch = lambda url, backend="gemini": tools.BLOCKED if (monkey_blocked and "help" in url) else PAGE
    tools.mcp_registry = lambda app, domain: {"vendor_entries": [], "other_entries": []}
    tools.composio_catalog = lambda app: {"found": "pumble", "url": "https://composio.dev/toolkits/pumble"}


APP = {"id": "25", "app": "Pumble", "category": "Communications", "hint": "pumble.com"}


def test_clean_run_needs_no_human():
    fake_web()
    events = []
    rec = FakeAgent().research(APP, Tracer(emit=events.append))
    assert rec["result"]["verdict"] == "ready" and rec["result"]["claims"][0]["supported"]
    assert rec["verifier"]["agreement"] == 1.0 and not rec["needs_human"], rec["human_reasons"]
    assert rec["catalog"]["found"] == "pumble"
    assert [e["step"] for e in events][0] == "draft" and events[-1]["step"] == "final"


def test_verifier_disagreement_routes_to_human():
    fake_web()
    rec = FakeAgent(verifier_access="paid").research(APP, Tracer())
    assert rec["needs_human"] and "access" in rec["verifier"]["disagreements"]


def test_judge_contradiction_and_robots_route_to_human():
    fake_web(monkey_blocked=True)
    rec = FakeAgent(judge="CONTRADICT").research(APP, Tracer())
    reasons = " ".join(rec["human_reasons"])
    assert "robots.txt" in reasons and rec["needs_human"]


def test_server_mock_stream():
    server.time.sleep = lambda s: None
    handler, live = server.make_handler(mock=True)
    srv = server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    assert json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health"))["mode"] == "mock"
    body = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/research?id=37").read().decode()
    evs = [json.loads(l[6:]) for l in body.splitlines() if l.startswith("data: ")]
    assert evs[0]["step"] == "draft" and evs[-1].get("done") and any(e.get("step") == "correct" for e in evs)
    assert b"<!DOCTYPE html>" in urllib.request.urlopen(f"http://127.0.0.1:{port}/").read()[:200]
    srv.shutdown()


def test_sweep_logic_with_fake_web(tmp=pathlib.Path("/tmp/sweep_test.json")):
    from agent import sweep
    tools.mcp_registry = lambda app, domain: {"vendor_entries": ["com.example/mcp"] if app == "GitHub" else [], "other_entries": []}
    tools.composio_catalog = lambda app: {"found": app.lower(), "url": "u", "kind": "toolkit"} if app == "Pumble" else {"found": None}
    tools.robots_allows = lambda url: True
    sweep._text = lambda url: (200, "Use your API key as a Bearer token. OAuth apps use OAuth 2.0." * 20) if "github" in url else (404, "")
    class NoBrowser:  # browser loop path without a real browser
        def render(self, url): return None
        def close(self): pass
    sweep.Browser = NoBrowser
    out = sweep.run(tmp, workers=2, ids={25, 61})
    gh, pu = out["apps"][61], out["apps"][25]
    assert gh["registry"]["vendor_entries"] and gh["corroboration"]["OAuth2"] and gh["corroboration"]["API key"]
    assert pu["catalog"]["found"] == "pumble" and pu["links"][0]["status"] == 404 and pu["corroboration"]["API key"] is False


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
