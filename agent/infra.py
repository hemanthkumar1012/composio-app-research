"""Run infrastructure: disk cache (resumable, cheap re-runs), retries with backoff, and a JSONL tracer."""
import contextlib
import functools
import hashlib
import json
import pathlib
import random
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


class DiskCache:
    """Content-addressed JSON cache. Page fetches and model calls are keyed by their inputs, so a crashed or
    repeated run costs nothing for work already done."""

    def __init__(self, root=ROOT / ".cache", ttl_hours=72, enabled=True):
        self.root, self.ttl, self.enabled = pathlib.Path(root), ttl_hours * 3600, enabled
        self.hits = self.misses = 0

    def _path(self, ns, parts):
        h = hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:24]
        return self.root / ns / f"{h}.json"

    def get(self, ns, *parts):
        p = self._path(ns, parts)
        if self.enabled and p.exists() and time.time() - p.stat().st_mtime < self.ttl:
            self.hits += 1
            return json.loads(p.read_text())["v"]
        self.misses += 1
        return None

    def set(self, ns, value, *parts):
        if self.enabled:
            p = self._path(ns, parts)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"v": value}))
        return value

    def memo(self, ns, fn, *parts):
        v = self.get(ns, *parts)
        return v if v is not None else self.set(ns, fn(), *parts)


def _retryable(exc):
    code = getattr(exc, "code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if code in (408, 409, 425, 429, 500, 502, 503, 504):
        return True
    name = type(exc).__name__
    return name in ("ConnectionError", "Timeout", "ReadTimeout", "ConnectTimeout", "ServerError", "ResourceExhausted")


def retry(attempts=4, base=1.5, cap=30):
    """Exponential backoff with full jitter on rate limits and transient errors only."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            for i in range(attempts):
                try:
                    return fn(*a, **kw)
                except Exception as exc:  # noqa: BLE001
                    if i == attempts - 1 or not _retryable(exc):
                        raise
                    time.sleep(random.uniform(0, min(cap, base * 2 ** i)))
        return wrapper
    return deco


class Tracer:
    """Append-only JSONL trace of every step (one file per app) + optional live callback (used by the SSE server)."""

    def __init__(self, path=None, emit=None):
        self.path, self.emit, self.t0 = path, emit, time.time()
        self._lock = threading.Lock()
        if path:
            pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)

    def event(self, step, title, status="ok", **data):
        ev = {"t": round(time.time() - self.t0, 3), "step": step, "title": title, "status": status, "data": data}
        with self._lock:
            if self.path:
                with open(self.path, "a") as f:
                    f.write(json.dumps(ev, default=str) + "\n")
        if self.emit:
            self.emit(ev)
        return ev

    @contextlib.contextmanager
    def span(self, step, title, **data):
        t = time.time()
        try:
            yield
        finally:
            self.event(step, title, ms=round(1000 * (time.time() - t)), **data)
