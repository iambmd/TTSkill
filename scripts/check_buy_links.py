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
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from time import sleep
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "shared" / "rubber-buy-links.json"
RUBBERS = ROOT / "frontend" / "lib" / "rubbers.json"
BROWSER_USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
AMAZON_TYPES = {"amazon-official", "amazon-other"}
MIN_PRICE_RATIO = Decimal("0.70")
Fetch = Callable[[str], tuple[str, str, str]]


def compact(name: str) -> str:
    name = unicodedata.normalize("NFKD", name.casefold().replace("+", " plus "))
    return re.sub(r"[^a-z0-9]", "", name)


def model(name: str) -> str:
    name = re.sub(r"^\"New\"\s+|\s*\((?:IN|OUT|LONG)\)\s*$", "", name, flags=re.I)
    name = re.sub(r"\bT\.\s*T\.", "TT", name, flags=re.I)
    name = re.sub(r"\s*\((reverse backhand|short pips|anti-spin)\)\s*$", "", name, flags=re.I)
    name = re.sub(r"\b(Hurricane [23])\s+\(H[23]\)", r"\1", name, flags=re.I)
    name = re.sub(r"\bNEO Hurricane ([23])\b", r"Hurricane \1 Neo", name, flags=re.I)
    name = re.sub(r"\b(National|Provincial) Edition\b", r"\1", name, flags=re.I)
    name = re.sub(r"\bDHS H8-80\b", "DHS Hurricane 8-80", name, flags=re.I)
    name = re.sub(r"\bTrinity Charged Hugo Calderano\b", "Trinity Charged", name, flags=re.I)
    name = re.sub(r"\bTackiness Chop II\b", "Tackiness Chop 2", name, flags=re.I)
    name = re.sub(r"\bHurricane Pro (?:III|Ⅲ)\b", "Hurricane Pro 3", name, flags=re.I)
    name = re.sub(r"\b(Nittaku Hurricane Pro 3 Turbo (?:Blue|Orange)) Sponge\b", r"\1", name, flags=re.I)
    name = re.sub(r"\bSkyline TG\s+([23])\b", r"Skyline TG\1", name, flags=re.I)
    name = re.sub(r"\bVega Euro(?:pean)?\b(?! DF)", "Vega Europe", name, flags=re.I)
    name = re.sub(r"\bJekyll (?:and|&) Hyde\b", "Jekyll Hyde", name, flags=re.I)
    name = re.sub(r"\bOmega 8 VIII\b", "Omega 8", name, flags=re.I)
    name = re.sub(r"\bSkyline ([23])\s+TG[23]\b", r"Skyline TG\1", name, flags=re.I)
    name = re.sub(r"\bSkyline TG([23]) Neo\b", r"Neo Skyline TG\1", name, flags=re.I)
    name = re.sub(r"\b(DHS (?:Neo )?Skyline) ([23])\b(?![-\d])", r"\1 TG\2", name, flags=re.I)
    name = re.sub(r"^DHS Provincial Blue Sponge (Skyline TG[23])\b", r"DHS \1 Provincial Blue Sponge", name, flags=re.I)
    name = re.sub(r"\b(DHS Hurricane 9) TT Rubber\s*-\s*(Pink)\b", r"\1 \2", name, flags=re.I)
    name = re.sub(r"\bDHS Skyline 3-60 Mid\b(?! Hard)", "DHS Skyline 3-60 Mid Hard", name, flags=re.I)
    name = re.sub(r"\b(?:Omega (?:IV|V|VII)|Sigma II) Euro(?=\b)", lambda m: m[0] + "pe", name, flags=re.I)
    name = re.sub(r"\b(Xiom Vega) Euro DF\b", r"\1 Europe DF", name, flags=re.I)
    name = re.sub(r"\s+(?:(?:version|offensive|inverted|table tennis|ping[ -]pong|TT)\s+)*rubbers?(?:\s+sheets?)?$", "", name, flags=re.I)
    return compact(name)


def matches(product: str, title: str, store: str) -> bool:
    # Marketing and store suffixes are separate from the model. Compare the whole model,
    # including suffixes such as FX, Hard, Neo, Provincial and National.
    names = rf"{re.escape(store)}|Paddle Palace|Megaspin|JOOLA(?: USA)?|Butterfly(?: Online)?|DHS Sports USA"
    name = re.split(rf"\s*[|⋆»]\s*|\s+[-–]\s+(?:{names})\s*$", title, maxsplit=1, flags=re.I)[0].strip()
    expected, actual = model(product), model(name)
    if expected == actual:
        return True
    prefix = {"Butterfly US": "butterfly", "JOOLA USA": "joola"}.get(store, "")
    return bool(prefix) and expected.removeprefix(prefix) == actual.removeprefix(prefix)


def dollar_amount(value: str) -> Decimal | None:
    value = value.strip().replace(",", "")
    if re.fullmatch(r"\$?\d+(?:\.\d{1,2})?", value) and (amount := Decimal(value.lstrip("$"))) > 0:
        return amount
    return None


class AmazonOffer(HTMLParser):
    """Read the active item title and dollar price in the main offer."""

    price_sections = ("corePriceDisplay_desktop_feature_div", "corePrice_feature_div", "apex_desktop", "buybox")

    def __init__(self, html: str):
        super().__init__()
        self.title = ""
        byline = re.search(r'<a\b[^>]*\bid="bylineInfo"[^>]*>\s*(?:Brand:\s*([^<]+)|Visit the ([^<]+?) Store)\s*</a>', html, re.I)
        self.brand = compact(byline[1] or byline[2]) if byline else ""
        color = re.search(r'<th\b[^>]*\bprodDetSectionEntry\b[^>]*>\s*Color\s*</th>\s*<td\b[^>]*>([^<]+)</td>', html, re.I)
        self.color = compact(color[1]) if color else ""
        self.prices: dict[str, Decimal] = {}
        self.stack: list[tuple[str, str, list[str]]] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"div", "span", "h1"}:
            return
        attributes = dict(attrs)
        section = attributes.get("id") or ""
        classes = (attributes.get("class") or "").split()
        if "a-text-price" in classes or "basisPrice" in classes:
            section = "list-price"
        elif "a-price" in classes:
            section = "offer-price"
        elif ("a-offscreen" in classes and any(s == "offer-price" for _, s, _ in self.stack)
              and any(s in self.price_sections for _, s, _ in self.stack)
              and not any(s == "list-price" for _, s, _ in self.stack)):
            section = "amount"
        self.stack.append((tag, section, []))

    def handle_data(self, data: str) -> None:
        for _, section, parts in self.stack:
            if section in {"productTitle", "amount"}:
                parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag not in {"div", "span", "h1"}:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] != tag:
                continue
            _, section, parts = self.stack[i]
            del self.stack[i:]
            value = "".join(parts).strip()
            if section == "productTitle":
                self.title = " ".join(value.split())
            elif section == "amount" and value.startswith("$") and (amount := dollar_amount(value)) is not None:
                parent = next(s for _, s, _ in reversed(self.stack) if s in self.price_sections)
                self.prices.setdefault(parent, amount)
            break

    @property
    def price(self) -> Decimal | None:
        return next((self.prices[section] for section in self.price_sections if section in self.prices), None)


def amazon_matches(product: str, offer: AmazonOffer) -> bool:
    title = re.sub(r"^DHS Sports\s+", "DHS ", offer.title, flags=re.I)
    title = re.sub(r"\b(DHS Hurricane 3 National Blue)\b(?! Sponge)", r"\1 Sponge", title, flags=re.I)
    title = re.sub(r"^XIOM \d{5} (Vega [a-z]+ Table Tennis Rubber) Soft Back$", r"XIOM \1", title, flags=re.I)
    title = re.sub(r"^XIOM Table Tennis Rubber \(?Soft Back\)? (Vega [a-z]+)(?: \d{5})?$", r"XIOM \1", title, flags=re.I)
    title = re.sub(r"^STIGA (?:\(sutexiga\) )?Table Tennis Rubber Tension (?:Series )?Back Soft (Mantra [HMS])$",
                   r"STIGA \1", title, flags=re.I)
    title = re.sub(r"^STIGA \d+ Table Tennis Rubber, Tension Type, Soft Backing, (Mantra Pro [HMS]), \w+, \w+ Thickness$",
                   r"STIGA \1", title, flags=re.I)
    brand = product.split()[0]
    if offer.brand == compact(brand) and not title.casefold().startswith(brand.casefold() + " "):
        title = f"{brand} {title}"
    parts = re.split(r"\s+(?:(?:table tennis(?: and ping pong)?|ping[ -]pong)\s+)?rubbers?(?:\s+sheets?)?\b", title, maxsplit=1, flags=re.I)
    name = re.sub(r"\s+(?:(?:Red|Black)\s+\d\.\d\s*(?:mm)?|\d\.\d\s*(?:mm)?\s+(?:Red|Black))$", "", parts[0], flags=re.I)
    expected, actual = model(product), model(name)
    if expected != actual and (not offer.color or expected != actual + offer.color):
        return False
    # A listing can put the edition after “rubber.” Keep titles with an ambiguous suffix out.
    suffix = re.sub(r"^\s+Table Tennis Rubber\b", "", parts[1], flags=re.I) if len(parts) > 1 else ""
    variant = re.search(r"\b(Neo|FX|Soft|Hard|National|Provincial|Turbo|Blue Sponge|Orange Sponge|[2-9]\s*[- ]?Pack)\b", suffix, re.I)
    return not variant and (not suffix.strip() or bool(re.match(r"\s*[-–:,(/|]", suffix)))


class ProductPage(HTMLParser):
    """Only collect model names from primary page metadata or headings."""

    def __init__(self, html: str):
        super().__init__()
        self.names: list[str] = []
        self.orange_sponge = False
        self.metadata: dict[str, str] = {}
        self.offer: dict[str, str] = {}
        self.tag = ""
        self.parts: list[str] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs)
        if tag in {"title", "h1"}:
            self.tag, self.parts = tag, []
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.tag, self.parts = tag, []
        if tag == "meta" and attrs.get("property") and attrs.get("content"):
            self.metadata[attrs["property"]] = attrs["content"]
            if attrs["property"] == "og:title":
                self.names.append(attrs["content"])

    def handle_data(self, data: str) -> None:
        if self.tag:
            self.parts.append(data)
        if re.search(r"\b2\.2\s*mm\s+orange\s+sponge\b", data, re.I):
            self.orange_sponge = True

    def handle_endtag(self, tag: str) -> None:
        if tag == self.tag:
            raw = "".join(self.parts)
            self.tag = ""
            if tag == "script":
                self.read_product_schema(raw)
                return
            name = " ".join(raw.split())
            if name and name not in self.names:
                self.names.append(name)

    def read_product_schema(self, raw: str) -> None:
        try:
            schema = json.loads(raw)
        except ValueError:
            return
        if not isinstance(schema, dict) or schema.get("@type") != "Product" or not isinstance(schema.get("name"), str):
            return
        if schema["name"] not in self.names:
            self.names.append(schema["name"])
        if isinstance(schema.get("offers"), dict):
            self.offer = schema["offers"]

    def price(self) -> Decimal | None:
        for prefix in ("product:price:", "og:price:"):
            if self.metadata.get(prefix + "currency") == "USD":
                if (amount := dollar_amount(self.metadata.get(prefix + "amount", ""))) is not None:
                    return amount
        return dollar_amount(str(self.offer.get("price", ""))) if self.offer.get("priceCurrency") == "USD" else None


def matches_page(product: str, page: ProductPage, store: str) -> bool:
    if store == "Paddle Palace" and model(product) == "dhshurricane3nationalorangesponge":
        # The orange-sponge edition omits the color from its title. The blue sponge has its own product page.
        return page.orange_sponge and any(matches("DHS Hurricane 3 National", title, store) for title in page.names)
    if store == "Megaspin" and re.match(r"^DHS (?:Neo )?Skyline \d\b|^DHS (?:Neo )?Skyline TG[23]\b", product, re.I):
        return any(matches(product, re.sub(r"\s+-\s+\d\d Degrees\b", "", title, flags=re.I), store) for title in page.names)
    return any(matches(product, title, store) for title in page.names)


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.")


def product_url(url: str, store: str, kind: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.fragment:
        return False
    if kind in AMAZON_TYPES:
        return store == "Amazon" and host(url) == "amazon.com" and bool(re.fullmatch(r"/dp/[A-Z0-9]{10}", parts.path)) and not parts.query
    if host(url) == "amazon.com" or store == "Amazon":
        return False
    if store == "Megaspin":
        return host(url) == "megaspin.net" and parts.path == "/store/default.asp" and bool(re.fullmatch(r"pid=[a-zA-Z0-9_-]+", parts.query))
    if store == "Paddle Palace" and host(url) != "paddlepalace.com":
        return False
    return (parts.path.strip("/") != "" and not re.search(r"/(?:search|collections|category)(?:/|$)", parts.path, re.I)
            and set(parse_qs(parts.query)) <= {"variant"})


def fetch(url: str, user_agent: str = BROWSER_USER_AGENT) -> tuple[str, str, str]:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"})
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
def product_fetcher(use_browser: bool, user_agent: str):
    if not use_browser:
        yield lambda url: fetch(url, user_agent)
        return

    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(locale="en-US", user_agent=user_agent)
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


def check_amazon(name: str, link: dict[str, str], html: str, final_url: str,
                 reference: Decimal | None) -> tuple[str, str]:
    asin = urlsplit(link["url"]).path.rsplit("/", 1)[-1]
    if host(final_url) != "amazon.com" or not re.search(rf"/dp/{asin}(?:/|$)", urlsplit(final_url).path):
        return "BROKEN", "Redirected away from the requested Amazon ASIN"
    offer = AmazonOffer(html)
    if not offer.title:
        return "UNVERIFIED", "Amazon product title unavailable"
    if not amazon_matches(name, offer):
        return "MISMATCH", offer.title
    if link["type"] == "amazon-official":
        return "OK", "Matching product on the trusted storefront"
    if offer.price is None:
        return "UNVERIFIED", "Current Amazon offer price unavailable"
    if reference is None:
        return "UNVERIFIED", "Reference price unavailable"
    if offer.price < reference * MIN_PRICE_RATIO:
        return "SUSPECT", "Current Amazon offer is more than 30% below the reference price"
    return "OK", "Matching product and offer within the price threshold"


def reference_price(name: str, links: list[dict[str, str]], prices: dict[str, Decimal], load: Fetch) -> Decimal | None:
    if name in prices:
        return prices[name]
    for link in sorted(links, key=lambda entry: entry["type"] != "official"):
        store, kind, url = link["store"], link["type"], link["url"]
        if (kind != "official" and store != "Paddle Palace") or link.get("status") == "unverified":
            continue
        if not product_url(url, store, kind):
            continue
        status, final_url, html = load(url)
        if status == "OK" and host(final_url) == host(url) and product_url(final_url, store, kind):
            page = ProductPage(html)
            if matches_page(name, page, store) and (amount := page.price()) is not None:
                return amount
    return None


def check(entries: dict[str, list[dict[str, str]]], show_ok: bool = False, use_browser: bool = False,
          user_agent: str = BROWSER_USER_AGENT, megaspin_delay: float = 2.5) -> list[tuple[str, str, str, str, str]]:
    by_host: dict[str, dict[str, list[tuple[str, dict[str, str]]]]] = defaultdict(lambda: defaultdict(list))
    results: list[tuple[str, str, str, str, str]] = []
    prices = {entry["name"]: Decimal(str(entry["price"])) for entry in json.loads(RUBBERS.read_text(encoding="utf-8"))
              if entry["price"] and entry["price"] > 0}
    for name, links in entries.items():
        for link in links:
            store, url = link["store"], link["url"]
            if not product_url(url, store, link["type"]):
                results.append((name, store, "BROKEN", "Expected a clean HTTPS product URL", url))
                continue
            by_host[host(url)][url].append((name, link))

    def check_store(item: tuple[str, dict[str, list[tuple[str, dict[str, str]]]]]) -> list[tuple[str, str, str, str, str]]:
        domain, urls = item
        found = []
        base_delay = megaspin_delay if domain == "megaspin.net" else 0.35
        delay = base_delay
        references: dict[str, Decimal | None] = {}
        with product_fetcher(use_browser, user_agent) as load:
            for i, (url, uses) in enumerate(urls.items()):
                if i:
                    sleep(delay)
                status, detail, html = load(url)
                delay = 3 if detail == "HTTP 429" else base_delay
                page = ProductPage(html) if status == "OK" and domain != "amazon.com" else None
                for name, link in uses:
                    store, kind = link["store"], link["type"]
                    verdict, note = status, detail
                    if status == "OK" and kind in AMAZON_TYPES:
                        if kind == "amazon-other" and name not in references:
                            references[name] = reference_price(name, entries[name], prices, load)
                        verdict, note = check_amazon(name, link, html, detail, references.get(name))
                    elif page and (host(url) != host(detail) or not product_url(detail, store, kind)):
                        verdict, note = "BROKEN", f"redirected outside the product store to {detail}"
                    elif page and not matches_page(name, page, store):
                        verdict, note = "MISMATCH", " / ".join(page.names[:3]) or "No product title"
                    elif page:
                        note = "HTTP 200 and matching product name"
                    found.append((name, store, verdict, note, url))
        return found

    with ThreadPoolExecutor(max_workers=6) as executor:
        for checked in executor.map(check_store, by_host.items()):
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
    parser.add_argument("--user-agent", default=BROWSER_USER_AGENT, help="User-Agent used for product requests")
    parser.add_argument("--megaspin-delay", type=float, default=2.5, help="seconds between Megaspin requests (2–3)")
    args = parser.parse_args()
    if not 2 <= args.megaspin_delay <= 3:
        parser.error("--megaspin-delay must be between 2 and 3 seconds")
    entries = json.loads(args.catalog.read_text(encoding="utf-8"))
    try:
        results = check(entries, args.show_ok, args.browser, args.user_agent, args.megaspin_delay)
    except ModuleNotFoundError as exc:
        if exc.name not in {"playwright", "playwright.sync_api"}:
            raise
        parser.error("--browser requires Python Playwright and its Chromium browser")
    passed = sum(row[2] == "OK" for row in results)
    print(f"{passed}/{len(results)} links verified across {len(entries)} catalog entries.")
    return int(passed != len(results))


if __name__ == "__main__":
    raise SystemExit(main())
