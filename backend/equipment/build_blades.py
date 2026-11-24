"""Builds the blade dataset (see SOURCE.md): RevSpin's saved ratings + specs and US store links from manufacturer and store pages.

    python -m equipment.build_blades            # everything; web pages are cached, so a rerun is quick
    python -m equipment.build_blades --offline  # only what is already cached
    python -m equipment.build_blades --butterfly-shop  # also read Butterfly US product pages (off by default: it answers 429)

RevSpin is never fetched: its numbers come from the saved index in backend/data/revspin_snapshot/."""
from __future__ import annotations

import csv
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import blade_specs as bs
from . import revspin
from .fetching import Fetcher, Refused

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
SNAPSHOT = ROOT / "backend" / "data" / "revspin_snapshot"
INDEX_SNAPSHOT = SNAPSHOT / "blade-index-2026-11-24.html"
SNAPSHOT_DATE = "2026-11-24"
OUT = HERE / "blades.json"
SKIPPED = HERE / "blades_skipped.csv"
FRONTEND = ROOT / "frontend" / "lib" / "blades.json"
BUY_LINKS = ROOT / "shared" / "blade-buy-links.json"
PROS = ROOT / "frontend" / "lib" / "pros.json"
PRO_BLADES = ROOT / "frontend" / "lib" / "pro-blades.json"
MIN_RATINGS = 10  # fewer user ratings than this and the averages mean little

# Shopify stores whose public /products.json robots.txt allows. brand: the only brand the store sells under that name.
SHOPIFY = {
    "TableTennisStore": ("https://tabletennisstore.us", "", "retailer"),
    "Go Table Tennis": ("https://gotabletennis.com", "", "retailer"),
    "eTableTennis": ("https://www.etabletennis.com", "", "retailer"),
    "DHS Sports USA": ("https://dhssportsusa.com", "DHS", "official"),
    "Double Happiness USA": ("https://doublehappinessusa.com", "DHS", "official"),
    "JOOLA USA": ("https://joola.com", "JOOLA", "official"),
}
BUTTERFLY_SPECS = "https://www.butterflyonline.com/butterfly-blade-specifications"
BUTTERFLY_SHOP = "https://shop.butterflyonline.com"
NOT_A_BLADE = re.compile(r"racket|paddle|bundle|combo|\bset\b|pre-assembled|robot|case|sheet|\bkit\b", re.I)


@dataclass
class Product:
    store: str
    kind: str          # official | retailer
    title: str
    url: str
    keys: set[str]
    spec: bs.Spec = field(default_factory=bs.Spec)
    handle_in_title: str | None = None


def text_of(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).split())


def ratings(snapshot: Path = INDEX_SNAPSHOT) -> tuple[list[revspin.IndexRow], list[revspin.IndexRow]]:
    rows = revspin.parse_index(snapshot.read_text(encoding="utf-8", errors="replace"))
    return [r for r in rows if r.ratings >= MIN_RATINGS], [r for r in rows if r.ratings < MIN_RATINGS]


def hardness_pages() -> dict[str, float]:
    """RevSpin hardness, only for the few blade pages that were saved before the crawl was paused."""
    out = {}
    for path in SNAPSHOT.glob("blade-*.html"):
        if path.name.startswith("blade-index"):
            continue
        page = revspin.parse_blade(path.read_text(encoding="utf-8", errors="replace"))
        if page.hardness is not None:
            out[path.stem.removeprefix("blade-")] = page.hardness
    return out


def shopify_products(fetcher: Fetcher, log) -> list[Product]:
    out: list[Product] = []
    for store, (base, brand, kind) in SHOPIFY.items():
        try:
            items = []
            for page in range(1, 40):
                batch = json.loads(fetcher.get(f"{base}/products.json?limit=250&page={page}"))["products"]
                items += batch
                if len(batch) < 250:
                    break
        except Refused as e:
            log(f"  {store}: skipped ({e})")
            continue
        for p in items:
            kind_text = f"{p['title']} {p['product_type']} {' '.join(p['tags'])}"   # a name must still match a RevSpin blade exactly
            if NOT_A_BLADE.search(p["title"]) or not re.search(r"\bbl(?:a|)des?\b|balde|purewood|composite", kind_text, re.I):
                continue
            options = [v for o in p["options"] if re.search(r"handle|grip|style|type", o["name"], re.I) for v in o["values"]]
            handles = bs.split_handles(options)
            ptype = p["product_type"].casefold()
            if "chinese penhold" in ptype and "CS" not in handles:
                handles.append("CS")
            if "japanese penhold" in ptype and "JP" not in handles:
                handles.append("JP")
            if (h := bs.title_handle(p["title"])) and h not in handles:
                handles.append(h)
            spec = bs.parse_text(text_of(p["body_html"]), p["title"])
            spec.handles = [h for h in bs.HANDLES if h in handles or h in spec.handles]
            url = f"{base}/products/{p['handle']}"
            spec.sources = [url]
            out.append(Product(store, kind, p["title"], url, bs.name_keys(p["title"], brand), spec, bs.title_handle(p["title"])))
        log(f"  {store}: {len(items)} products, {sum(1 for x in out if x.store == store)} blades")
    return out


def butterfly_products(fetcher: Fetcher, brand_blades: list[revspin.IndexRow], log, shop_pages: bool = False) -> tuple[dict[str, bs.Spec], list[Product]]:
    """Butterfly's own spec table (one request), then the US shop page of each Butterfly blade whose address matches its name."""
    table = bs.parse_butterfly_table(fetcher.get(BUTTERFLY_SPECS), BUTTERFLY_SPECS)
    log(f"  Butterfly spec table: {len(table)} blades")
    sitemap = fetcher.get(f"{BUTTERFLY_SHOP}/sitemap_shop.butterflyonline.com_Index.xml")
    urls: list[str] = []
    for child in re.findall(r"<loc>([^<]+)</loc>", sitemap):
        urls += re.findall(r"<loc>([^<]+)</loc>", fetcher.get(child))
    by_key: dict[str, str] = {}
    for url in urls:
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        slug = re.sub(r"-\d{3,5}[a-z]{0,2}$", "", slug, flags=re.I)
        for variant in {slug, re.sub(r"-?blade$", "", slug, flags=re.I)}:
            by_key.setdefault(bs.compact("butterfly " + variant.replace("-", " ")), url)
    products = []
    for row in brand_blades if shop_pages else []:
        url = by_key.get(bs.compact(row.name)) or by_key.get(bs.compact(row.name + " blade"))
        if not url:
            continue
        try:
            page = fetcher.get(url)
        except Refused as e:
            log(f"  Butterfly US shop: stopped early ({e}); the pages cached so far are kept")
            break
        title = text_of(re.search(r"<title>(.*?)</title>", page, re.S).group(1)) if "<title>" in page else ""
        title = re.split(r"\s*\|\s*", title)[0]
        if bs.compact("Butterfly " + bs.strip_title(title)) != bs.compact(row.name) and bs.compact(bs.strip_title(title)) != bs.compact(row.name):
            continue  # the address looked right but the page is a different product
        body = text_of(re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S))
        spec = bs.parse_text(body, title)
        m = re.search(r"Handle Style\s*:?\s*((?:(?:FL|ST|AN|CS|JS)\s*)+)", body)
        spec.handles = bs.split_handles(m.group(1).split()) if m else []
        # The page's own words are about this blade, but plies and fibre come from the spec table: keep this to links and handles.
        spec.plies = spec.weight = spec.composition = spec.fiber = None
        spec.sources = [url]
        products.append(Product("Butterfly US", "official", title, url, {bs.compact(row.name)}, spec))
    log(f"  Butterfly US shop: {len(products)} blade pages")
    return table, products


def paddle_palace_products(fetcher: Fetcher, blades: list[revspin.IndexRow], log) -> list[Product]:
    """Paddle Palace's blade pages, found through its sitemap (its agent guide's way in) by the `{name}-shakehand-blade`
    and `-penhold-blade` addresses, each checked against the exact product name on the page."""
    base = "https://www.paddlepalace.com"
    try:
        sitemap = fetcher.get(f"{base}/sitemap.xml")
        urls: list[str] = []
        for child in re.findall(r"<loc>([^<]+)</loc>", sitemap):
            if "sitemap_products" in child:
                urls += re.findall(r"<loc>([^<]+/products/[^<]+)</loc>", fetcher.get(html.unescape(child)))
    except Refused as e:
        log(f"  Paddle Palace: skipped ({e})")
        return []
    by_name = {bs.compact(r.name): r for r in blades}
    found: list[tuple[revspin.IndexRow, str, str]] = []
    for url in urls:
        m = re.fullmatch(r"(.+?)-(shakehand|penhold)-blade", url.rsplit("/", 1)[1])
        if m and (row := by_name.get(bs.compact(m.group(1).replace("-", " ")))):
            found.append((row, m.group(2), url))
    products = []
    for row, kind, url in found:
        try:
            page = fetcher.get(url)
        except Refused as e:
            log(f"  Paddle Palace: stopped early ({e})")
            break
        product = None
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break
        if not product or bs.compact(bs.strip_title(product.get("name", ""))) not in {bs.compact(row.name), bs.compact(row.name + "penhold")}:
            continue
        ids = {m.group(1) for o in product.get("offers", []) for m in [re.search(r"variant=(\d+)", o.get("url", ""))] if m}
        titles = [v for vid, v in re.findall(r'"id":"(\d+)"[^{}]*?"title":"([^"]+)"', page) if vid in ids]
        handles = bs.split_handles(titles)
        if kind == "penhold" and not any(h in handles for h in ("CS", "JP")):
            handles = ["PH"]
        spec = bs.parse_text(text_of(product.get("description", "")), product["name"])
        spec.handles, spec.sources = handles, [url]
        products.append(Product("Paddle Palace", "retailer", product["name"], url, {bs.compact(row.name)}, spec, "PH" if kind == "penhold" else None))
    log(f"  Paddle Palace: {len(products)} blade pages")
    return products


def build(offline: bool = False, shop_pages: bool = False, log=print) -> list[dict]:
    kept, skipped = ratings()
    log(f"RevSpin snapshot {SNAPSHOT_DATE}: {len(kept) + len(skipped)} blades, {len(kept)} with {MIN_RATINGS}+ ratings, {len(skipped)} skipped")
    hardness = hardness_pages()
    fetcher = Fetcher()
    fetcher._delay["shop.butterflyonline.com"] = 4.0  # it answered 429 at one request per 2 s
    if offline:
        fetcher.delay = 0
    log("Store catalogs:")
    products = shopify_products(fetcher, log)
    table, butterfly = butterfly_products(fetcher, [r for r in kept if r.brand == "Butterfly"], log, shop_pages)
    products += butterfly
    products += paddle_palace_products(fetcher, kept, log)
    blades, links = [], {}
    for r in kept:
        key = bs.compact(r.name)
        found = [p for p in products if key in p.keys]
        # The maker's page first. A penhold listing is a different blade (weight, plies): it only adds its handle.
        penhold_only = [p for p in found if p.handle_in_title in ("CS", "JP", "PH") and not re.search(r"\b(?:CS|JS|JPen)\b", r.name)]
        specs = ([table[key]] if key in table else []) + [
            bs.Spec(handles=p.spec.handles, sources=p.spec.sources) if p in penhold_only else p.spec for p in found]
        spec = bs.merge(specs)
        blade = {
            "slug": r.slug, "name": r.name, "brand": r.brand, "price": r.price,
            "speed": r.speed, "control": r.control, "stiffness": r.stiffness, "hardness": hardness.get(r.slug),
            "overall": r.overall, "ratings": r.ratings, "url": r.url,
            "plies": spec.plies, "weight": spec.weight, "composition": spec.composition, "fiber": spec.fiber,
            "handles": spec.handles, "specSources": spec.sources,
        }
        blades.append(blade)
        per_store: dict[str, Product] = {}
        for p in sorted(found, key=lambda p: (p.handle_in_title is not None, len(p.title))):
            per_store.setdefault(p.store, p)
        if per_store:
            links[r.name] = [{"store": p.store, "url": p.url, "type": p.kind} for p in per_store.values()]
    blades.sort(key=lambda b: (b["brand"], b["name"]))
    OUT.write_text(json.dumps(blades, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    FRONTEND.write_text(json.dumps(blades, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    BUY_LINKS.write_text(json.dumps(dict(sorted(links.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    by_name = {bs.compact(b["name"]): b["slug"] for b in blades}
    pro_map = {}
    for p in json.loads(PROS.read_text(encoding="utf-8"))["players"]:
        label = p["blade"]  # exact names only: "Butterfly Viscaria Golden (FL)" is not "Butterfly Viscaria"
        for candidate in (label, re.sub(r"\s*\((?:FL|ST|AN|CS|JS)\)\s*$", "", label)):
            if bs.compact(candidate) in by_name:
                pro_map[label] = by_name[bs.compact(candidate)]
                break
    PRO_BLADES.write_text(json.dumps(pro_map, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"Pro setups: {len(pro_map)} of {len({p['blade'] for p in json.loads(PROS.read_text(encoding='utf-8'))['players']})} blades have an entry")
    with SKIPPED.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Name", "Ratings"])
        w.writerows((s.name, s.ratings) for s in sorted(skipped, key=lambda s: (-s.ratings, s.name)))
    n = len(blades)
    log(f"Wrote {n} blades. With: plies {sum(b['plies'] is not None for b in blades)}, weight {sum(b['weight'] is not None for b in blades)}, "
        f"composition {sum(b['composition'] is not None for b in blades)}, handles {sum(bool(b['handles']) for b in blades)}, "
        f"buy links {len(links)}")
    log(f"Fetched live: {fetcher.live_requests} requests")
    return blades


if __name__ == "__main__":
    build(offline="--offline" in sys.argv, shop_pages="--butterfly-shop" in sys.argv)
