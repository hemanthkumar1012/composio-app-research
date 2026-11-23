"""Local live server (stdlib only): serves the case-study app and streams research as Server-Sent Events.

    python -m agent serve                 # http://localhost:8787 ; live mode if GEMINI_API_KEY is set
    python -m agent serve --mock          # replays the recorded run (no keys, no network)

Endpoints: /api/health · /api/trace/<id> (recorded) · /api/research?id=<id> (SSE stream of agent steps)
"""
import json
import os
import pathlib
import queue
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from .replay import load_bundle, trace

ROOT = pathlib.Path(__file__).resolve().parents[1]


def make_handler(mock):
    bundle = load_bundle()
    live = (not mock) and bool(os.getenv("GEMINI_API_KEY"))

    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ROOT / "docs"), **kw)

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def _sse(self, ev):
            self.wfile.write(f"data: {json.dumps(ev, default=str)}\n\n".encode()); self.wfile.flush()

        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            if u.path == "/api/health":
                return self._json({"ok": True, "mode": "live" if live else "mock"})
            if u.path.startswith("/api/trace/"):
                i = int(u.path.rsplit("/", 1)[1])
                return self._json(trace(i, bundle)) if i in bundle["apps"] else self._json({"error": "unknown id"}, 404)
            if u.path == "/api/research":
                i = int(parse_qs(u.query).get("id", ["0"])[0])
                if i not in bundle["apps"]:
                    return self._json({"error": "unknown id"}, 404)
                self.send_response(200); self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache"); self.end_headers()
                try:
                    self._stream(i)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            return super().do_GET()

        def _stream(self, i):
            if not live:
                for ev in trace(i, bundle):
                    self._sse({"id": i, "mode": "mock", **ev}); time.sleep(0.6)
                return self._sse({"id": i, "done": True})
            from .infra import Tracer
            from .research import Agent, load_apps
            q = queue.Queue()
            app = load_apps({i})[0]
            def work():
                try:
                    q.put({"result": Agent().research(app, Tracer(emit=q.put))})
                except Exception as e:  # noqa: BLE001
                    q.put({"error": str(e)})
                q.put(None)
            threading.Thread(target=work, daemon=True).start()
            while (ev := q.get()) is not None:
                self._sse({"id": i, "mode": "live", **ev})
            self._sse({"id": i, "done": True})

        def log_message(self, *a):
            pass

    return H, live


def serve(port=8787, mock=False):
    handler, live = make_handler(mock)
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Serving http://localhost:{port}  ({'LIVE research with ' + os.getenv('GEMINI_MODEL', 'gemini-2.5-flash') if live else 'mock replay of the recorded run'})")
    srv.serve_forever()
