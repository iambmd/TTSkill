#!/usr/bin/env python3
"""Check US rubber product URLs and exact model names. Run from any directory."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

CATALOG = Path(__file__).resolve().parents[1] / "shared" / "rubber-buy-links.json"


def compact(name: str) -> str:
    name = unicodedata.normalize("NFKD", name.casefold().replace("+", " plus "))
    return re.sub(r"[^a-z0-9]", "", name)


def model(name: str) -> str:
    name = re.sub(r"\s*\((reverse backhand|short pips|anti-spin)\)\s*$", "", name, flags=re.I)
    name = re.sub(r"\b(Hurricane [23])\s+\(H[23]\)", r"\1", name, flags=re.I)
    name = re.sub(r"\bNEO Hurricane ([23])\b", r"Hurricane \1 Neo", name, flags=re.I)
    name = re.sub(r"\bNational Edition\b", "National", name, flags=re.I)
    name = re.sub(r"\bDHS H8-80\b", "DHS Hurricane 8-80", name, flags=re.I)
    name = re.sub(r"\bTrinity Charged Hugo Calderano\b", "Trinity Charged", name, flags=re.I)
    name = re.sub(r"\s+(?:(?:table tennis|ping pong|TT)\s+)?rubbers?(?:\s+sheets?)?$", "", name, flags=re.I)
    return compact(name)


def matches(product: str, title: str, store: str) -> bool:
    # Marketing and store suffixes are separate from the model. Compare the whole model,
    # including suffixes such as FX, Hard, Neo, Provincial and National.
    name = re.split(r"\s*[|⋆»]\s*|\s+[-–]\s+(?:Paddle Palace|Megaspin|JOOLA(?: USA)?|Butterfly(?: Online)?|DHS Sports USA)\s*$", title, maxsplit=1, flags=re.I)[0].strip()
    expected, actual = model(product), model(name)
    if expected == actual:
        return True
    prefix = {"Butterfly US": "butterfly", "JOOLA USA": "joola"}.get(store, "")
    return bool(prefix) and expected.removeprefix(prefix) == actual.removeprefix(prefix)


class ProductPage(HTMLParser):
    """Only collect model names from primary page metadata or headings."""

    def __init__(self, html: str):
        super().__init__()
        self.names: list[str] = []
        self.orange_sponge = False
        self.tag = ""
        self.parts: list[str] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs)
        if tag in {"title", "h1"}:
            self.tag, self.parts = tag, []
        if tag == "meta" and attrs.get("property") == "og:title" and attrs.get("content"):
            self.names.append(attrs["content"])

    def handle_data(self, data: str) -> None:
        if self.tag:
            self.parts.append(data)
        if re.search(r"\b2\.2\s*mm\s+orange\s+sponge\b", data, re.I):
            self.orange_sponge = True

    def handle_endtag(self, tag: str) -> None:
        if tag == self.tag:
            name = " ".join("".join(self.parts).split())
            if name and name not in self.names:
                self.names.append(name)
            self.tag = ""


def matches_page(product: str, page: ProductPage, store: str) -> bool:
    if store == "Paddle Palace" and model(product) == "dhshurricane3nationalorangesponge":
        # The orange-sponge edition omits the color from its title. The blue sponge has its own product page.
        return page.orange_sponge and any(matches("DHS Hurricane 3 National", title, store) for title in page.names)
    return any(matches(product, title, store) for title in page.names)


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.")


def product_url(url: str, store: str, kind: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.fragment:
        return False
    if kind == "amazon-official":
        return store == "Amazon" and host(url) == "amazon.com" and bool(re.fullmatch(r"/dp/[A-Z0-9]{10}", parts.path)) and not parts.query
    if host(url) == "amazon.com" or store == "Amazon":
        return False
    if store == "Megaspin":
        return host(url) == "megaspin.net" and parts.path == "/store/default.asp" and bool(re.fullmatch(r"pid=[a-zA-Z0-9_-]+", parts.query))
    if store == "Paddle Palace" and host(url) != "paddlepalace.com":
        return False
    return (parts.path.strip("/") != "" and not re.search(r"/(?:search|collections|category)(?:/|$)", parts.path, re.I)
            and set(parse_qs(parts.query)) <= {"variant"})


def fetch(url: str) -> tuple[str, str, str]:
    request = Request(url, headers={"User-Agent": "TTSkill purchase link checker/1.0", "Accept": "text/html"})
    try:
        with urlopen(request, timeout=12) as response:
            if response.status != 200:
                return "BROKEN", f"HTTP {response.status}", ""
            return "OK", response.url, response.read(4_000_000).decode("utf-8", errors="replace")
    except HTTPError as exc:
        status = "UNVERIFIED" if exc.code in {401, 403, 429} or exc.code >= 500 else "BROKEN"
        return status, f"HTTP {exc.code}", ""
    except (URLError, TimeoutError, OSError) as exc:
        return "UNVERIFIED", str(exc), ""


@contextmanager
def product_fetcher(use_browser: bool):
    if not use_browser:
        yield fetch
        return

    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(locale="en-US")
            page.route("**/*", lambda route: route.continue_() if route.request.is_navigation_request() else route.abort())

            def visit(url: str) -> tuple[str, str, str]:
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=12_000)
                    if response is None:
                        return "UNVERIFIED", "No document response", ""
                    if response.status == 200:
                        return "OK", response.url, page.content()
                    status = "UNVERIFIED" if response.status in {401, 403, 429} or response.status >= 500 else "BROKEN"
                    return status, f"HTTP {response.status}", ""
                except Error as exc:
                    return "UNVERIFIED", str(exc).splitlines()[0], ""

            yield visit
        finally:
            browser.close()


def check(entries: dict[str, list[dict[str, str]]], show_ok: bool = False, use_browser: bool = False) -> list[tuple[str, str, str, str, str]]:
    by_host: dict[str, dict[str, list[tuple[str, dict[str, str]]]]] = defaultdict(lambda: defaultdict(list))
    results: list[tuple[str, str, str, str, str]] = []
    for name, links in entries.items():
        for link in links:
            store, url = link["store"], link["url"]
            if not product_url(url, store, link["type"]):
                results.append((name, store, "BROKEN", "Expected a clean HTTPS product URL", url))
                continue
            by_host[host(url)][url].append((name, link))

    def check_store(urls: dict[str, list[tuple[str, dict[str, str]]]]) -> list[tuple[str, str, str, str, str]]:
        found = []
        delay = 0.35
        with product_fetcher(use_browser) as load:
            for i, (url, uses) in enumerate(urls.items()):
                if i:
                    sleep(delay)
                status, detail, html = load(url)
                delay = 3 if detail == "HTTP 429" else 0.35
                page = ProductPage(html) if status == "OK" else None
                for name, link in uses:
                    store, kind = link["store"], link["type"]
                    verdict, note = status, detail
                    if page and (host(url) != host(detail) or not product_url(detail, store, kind)):
                        verdict, note = "BROKEN", f"redirected outside the product store to {detail}"
                    elif page and not matches_page(name, page, store):
                        verdict, note = "MISMATCH", " / ".join(page.names[:3]) or "No product title"
                    elif page and kind == "amazon-official":
                        # Buy Box sellers change by variant and region. Confirm the store and seller manually.
                        verdict, note = "UNVERIFIED", "recheck the official storefront and the current Sold by field"
                    elif page:
                        note = "HTTP 200 and matching product name"
                    found.append((name, store, verdict, note, url))
        return found

    with ThreadPoolExecutor(max_workers=6) as executor:
        for checked in executor.map(check_store, by_host.values()):
            results.extend(checked)
    for name, store, status, detail, url in sorted(results):
        if show_ok or status != "OK":
            print(f"{status:10} {name} | {store} | {detail} | {url}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--show-ok", action="store_true")
    parser.add_argument("--browser", action="store_true", help="use Chromium via the optional Python Playwright package")
    args = parser.parse_args()
    entries = json.loads(args.catalog.read_text(encoding="utf-8"))
    try:
        results = check(entries, args.show_ok, args.browser)
    except ModuleNotFoundError as exc:
        if exc.name not in {"playwright", "playwright.sync_api"}:
            raise
        parser.error("--browser requires Python Playwright and its Chromium browser")
    passed = sum(row[2] == "OK" for row in results)
    print(f"{passed}/{len(results)} links verified across {len(entries)} catalog entries.")
    return int(passed != len(results))


if __name__ == "__main__":
    raise SystemExit(main())
