"""A polite, cached fetcher: robots.txt respected, a pause between live requests, pages cached on disk."""
from __future__ import annotations

import re
import time
from hashlib import sha1
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

CACHE = Path(__file__).resolve().parents[1] / "data" / "web_cache"  # git-ignored, local only
USER_AGENT = "TTSkillBot/0.1 (table tennis coaching app; cached read-only requests, one every 2 s)"
DELAY = 2.0
# revspin.net refused our crawler (HTTP 403) on 2026-11-24 and we've asked for permission: don't fetch it at all.
NEVER = {"revspin.net"}


class Refused(Exception):
    """The site said no: robots.txt, an HTTP 403, or our own block list. Don't try another way in."""


class Fetcher:
    """GET with an on-disk cache and robots.txt respected. A 403 or 401 is final: it raises `Refused`."""

    def __init__(self, cache: Path = CACHE, delay: float = DELAY, user_agent: str = USER_AGENT):
        self.cache, self.delay, self.user_agent = cache, delay, user_agent
        self.cache.mkdir(parents=True, exist_ok=True)
        self._last = 0.0
        self._robots: dict[str, RobotFileParser] = {}
        self._delay: dict[str, float] = {}   # per host, doubled after a 429
        self._stopped: set[str] = set()
        self.live_requests = 0

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = RobotFileParser()
            parser.parse(self._get(origin + "/robots.txt", missing_ok=True).splitlines())
            self._robots[origin] = parser
        return self._robots[origin].can_fetch(self.user_agent, url)

    def get(self, url: str) -> str:
        host = (urlsplit(url).hostname or "").removeprefix("www.")
        if host in NEVER:
            raise Refused(f"{host} is on the block list")
        if not self.allowed(url):
            raise Refused(f"robots.txt disallows {url}")
        return self._get(url)

    def _path(self, url: str) -> Path:
        return self.cache / (sha1(url.encode()).hexdigest()[:16] + "-" + re.sub(r"[^a-z0-9]+", "-", url.lower().split("//", 1)[-1]).strip("-")[:70])

    def _get(self, url: str, missing_ok: bool = False) -> str:
        path = self._path(url)
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
        host = urlsplit(url).netloc
        if host in self._stopped:
            raise Refused(f"{host} kept answering 429; stopped for this run")
        for attempt in range(5):
            delay = self._delay.get(host, self.delay)
            wait = self._last + delay - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.live_requests += 1
            try:
                with urlopen(Request(url, headers={"User-Agent": self.user_agent, "Accept": "text/html,application/json,text/plain"}), timeout=30) as r:
                    text = r.read().decode("utf-8", errors="replace")
                path.write_text(text, encoding="utf-8")
                return text
            except HTTPError as e:
                if e.code in (401, 403):
                    raise Refused(f"HTTP {e.code} from {url}") from e
                if missing_ok and e.code == 404:
                    path.write_text("", encoding="utf-8")
                    return ""
                if e.code == 429:
                    # Slow down for good on this host, and wait as long as it asks before the next try.
                    self._delay[host] = min(30.0, max(delay * 2, 5.0))
                    asked = e.headers.get("Retry-After", "")
                    pause = min(300.0, float(asked)) if asked.isdigit() else 60.0 * (attempt + 1)
                    print(f"  429 from {host} (Retry-After {asked or 'not given'}): waiting {pause:.0f} s, then {self._delay[host]:.0f} s between requests", flush=True)
                    time.sleep(pause)
                    if attempt == 4:
                        self._stopped.add(host)
                        raise Refused(f"{host} kept answering 429") from e
                    continue
                if e.code in (500, 502, 503, 504) and attempt < 3:
                    time.sleep(10 * (attempt + 1))
                    continue
                raise
            except URLError:
                if attempt < 3:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise
        raise RuntimeError(url)
