"""Blade spec facts (plies, weight, composition, handles) read from manufacturer and store pages.
Only what a page states outright is kept: a field with no explicit statement, or two sources that disagree, stays empty."""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field

HANDLES = ("FL", "ST", "AN", "CS", "JP", "PH")  # flared, straight, anatomic, Chinese, Japanese and unspecified penhold

# Fibre layers named in the maker's words, most specific first. The id is what the site shows a label for.
FIBERS = (
    (r"super\s*zl(?:c|f)|\bzlc\b|zl[- ]carbon|zylon[- ]carbon", "zlc"),
    (r"super\s*alc|\balc\b|arylate[ /-]*carbon|aryl[- ]carbon|\bac\b(?=\s+structure)", "alc"),
    (r"\bcnf\b|cellulose nano", "cnf"),
    (r"kevlar", "kevlar"),
    (r"glass\s*fib|fibergl|fiberglass", "glass"),
    (r"texalium|\bzyl(?:on)?\b", "other"),
    (r"carbon", "carbon"),
)
_INNER = re.compile(r"inner[- ]?(?:fib(?:er|re)|carbon|force|layer|alc|zlc|structure)|innerforce|\binner\b(?!\s*wood)", re.I)
_OUTER = re.compile(r"outer[- ]?(?:fib(?:er|re)|carbon|force|layer|alc|zlc|structure)|outerforce|\bouter\b(?!\s*(?:ply|wood))", re.I)
_ALL_WOOD = re.compile(r"\ball[- ]?wood\b|\bpure[- ]?wood\b|\b100\s*%\s*wood\b|\bpurewood\b", re.I)
_TT = re.compile(r"\b(?:table tennis|ping[- ]?pong|tt)\b|(?<!\w)t\.\s*t\.(?!\w)|\bbla?de?s?\b|\bbalde\b", re.I)
_HANDLE_WORDS = {
    "fl": "FL", "flared": "FL", "flare": "FL", "fl master": "FL",
    "st": "ST", "straight": "ST",
    "an": "AN", "anatomic": "AN", "anatomical": "AN",
    "cs": "CS", "chinese penhold": "CS", "chinese": "CS", "cp": "CS", "penhold": "PH", "ph": "PH",
    "js": "JP", "jpen": "JP", "jp": "JP", "japanese penhold": "JP", "japanese square": "JP", "japanese": "JP",
}


def compact(name: str) -> str:
    name = unicodedata.normalize("NFKD", name.casefold().replace("&", " and ").replace("+", " plus "))
    return re.sub(r"[^a-z0-9]", "", name)


def strip_title(title: str) -> str:
    """A store title without the words every blade title carries ("Table Tennis Blade") or the retailer's tags."""
    # Only handle codes and the gift line go; any other quoted or bracketed word is part of the model's name.
    title = re.sub(r"[(\"](?:FL|ST|AN|CS|JS|JPen|Flared|Straight|Anatomic)[)\"]|with gift of purchase", " ", html.unescape(title), flags=re.I)
    return " ".join(_TT.sub(" ", title).split())


def handle_of(word: str) -> str | None:
    return _HANDLE_WORDS.get(" ".join(word.casefold().replace("-", " ").split()))


def split_handles(values: list[str]) -> list[str]:
    """Handle codes from option values such as "Flared/Straight", "FL, ST" or "Chinese Penhold"."""
    found: list[str] = []
    for value in values:
        for part in re.split(r"[/,;&]|\band\b", value):
            code = handle_of(part)
            if code and code not in found:
                found.append(code)
    return [h for h in HANDLES if h in found]


def title_handle(title: str) -> str | None:
    """A handle code a title ends with ("... Viscaria FL", '... "CS"'), which says which variant the page sells."""
    m = re.search(r"(?:\(|\"|\s)(FL|ST|AN|CS|JS|JPen|Flared|Straight|Anatomic)[\")]*$", strip_title(title))
    return handle_of(m.group(1)) if m else None


def without_handle(title: str) -> str:
    return re.sub(r"[\s(\"-]+(?:FL|ST|AN|CS|JS|JPen|Flared|Straight|Anatomic|Chinese Penhold)[\")]*\s*$", "", title.strip(), flags=re.I)


def name_keys(title: str, brand: str = "") -> set[str]:
    """The comparable forms of a store title: with and without a trailing handle, with the brand supplied if missing."""
    out = set()
    stripped = strip_title(title)
    for base in {stripped, without_handle(stripped)}:
        for text in {base, f"{brand} {base}" if brand and not base.casefold().startswith(brand.casefold()) else base}:
            if text:
                out.add(compact(text))
    return out


@dataclass
class Spec:
    maker: bool = False                # the manufacturer's own page; it outranks a store's description
    plies: int | None = None
    weight: float | None = None
    composition: str | None = None     # wood | inner | outer | composite
    fiber: str | None = None
    handles: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


def fiber_of(text: str) -> str | None:
    low = text.casefold()
    for pattern, ident in FIBERS:
        if re.search(pattern, low):
            return ident
    return None


_NEGATED = re.compile(r"\b(?:without|no|non|free of)[- ]+(?:\w+[- ]+)?(?:carbon|fib(?:er|re)s?)\b|\bcarbon[- ]free\b", re.I)
_LAYER_CUE = re.compile(r"\bpl(?:y|ies)\b|\blayers?\b|all[- ]?wood|pure[- ]?wood|\d\s*\+\s*\d|construction|structure|fib(?:er|re)|inlay|composite", re.I)


def own_layers(text: str) -> str:
    """Only the sentences that talk about the blade's own layers, with negations ("without carbon") removed:
    a description also mentions rubbers, other blades and marketing."""
    sentences = re.split(r"(?<=[.!?])\s+|\s\|\s", _NEGATED.sub(" ", text))
    return " ".join(x for x in sentences if _LAYER_CUE.search(x))


def composition_of(text: str, name: str = "", strict: bool = False) -> tuple[str | None, str | None]:
    """(composition, fiber) from text that talks about the blade's own layers; (None, None) if it says nothing.
    `strict` is for free-text descriptions (see `own_layers`); a spec table cell is already about the blade."""
    if strict:
        text = own_layers(text)
    fiber = fiber_of(text)
    if fiber:
        inner, outer = bool(_INNER.search(text) or _INNER.search(name)), bool(_OUTER.search(text) or _OUTER.search(name))
        if inner == outer:  # neither, or both (a blade line that mixes them): the position isn't stated
            return "composite", fiber
        return ("inner" if inner else "outer"), fiber
    if _ALL_WOOD.search(text):
        return "wood", None
    return None, None


def plies_of(text: str) -> int | None:
    """Total plies when the text states them: "5+2 ALC", "5W+2ALC", "5-ply + 2 Super ALC", "Plies: 7", or "7-ply" on a
    blade with no fibre layers. A lone "5-ply wood" next to carbon layers is only the wood count, and "5 layers" isn't
    plies, so those give None."""
    m = re.search(r"\b(\d)\s*(?:-?\s*ply|w)?\s*\+\s*(\d)\s*(?:-?\s*ply\s*)?(?:w\b|h\b)?\s*(?:[A-Za-z]|carbon)", text, re.I)
    if m:
        return int(m.group(1)) + int(m.group(2))
    m = re.search(r"\bplies\W{1,4}(\d{1,2})(?=w?\b)", text, re.I)
    if m:
        return int(m.group(1))
    counts = {int(n) for n in re.findall(r"\b(\d{1,2})[- ]?(?:ply|plies)\b", text, re.I)}
    return counts.pop() if len(counts) == 1 and not fiber_of(own_layers(text)) else None


def weight_of(text: str) -> float | None:
    m = re.search(r"\bweight\b[^0-9]{0,40}?(?:~|approx\.?\s*|avg\.?\s*)?(\d{2,3}(?:\.\d)?)\s*(?:g\b|gr?\b|grams?)", text, re.I)
    if m and 40 <= float(m.group(1)) <= 130:
        return float(m.group(1))
    return None


def parse_text(text: str, name: str = "") -> Spec:
    """Spec facts a description states in words. Marketing copy about other things is ignored."""
    spec = Spec()
    spec.plies, spec.weight = plies_of(text), weight_of(text)
    spec.composition, spec.fiber = composition_of(text, name, strict=True)
    m = re.search(r"\bhandle(?:s| types?| styles?| options?)?\s*[:\-]\s*([A-Za-z ,/()&-]{2,80})", text, re.I)
    if m:
        spec.handles = split_handles([re.sub(r"\(.*?\)", "", m.group(1))])
    return spec


def merge(specs: list[Spec]) -> Spec:
    """One spec from several sources. Per field the maker's page wins when it states the field; otherwise the stores
    that state it must agree (weights within 3 g count as the same). If they disagree the field stays empty.
    Handles are the union (each store lists what it sells)."""
    out = Spec()
    for name in ("plies", "weight", ("composition", "fiber")):  # layers and fibre are one fact: they stand or fall together
        fields = name if isinstance(name, tuple) else (name,)
        for makers in (True, False):
            values = {tuple(getattr(s, f) for f in fields) for s in specs
                      if s.maker == makers and any(getattr(s, f) is not None for f in fields)}
            if not values:
                continue
            if name == "weight" and max(values)[0] - min(values)[0] <= 3:
                out.weight = round(sum(v[0] for v in values) / len(values))
            elif len(values) == 1:
                for f, v in zip(fields, next(iter(values))):
                    setattr(out, f, v)
            break  # a maker's value, even a missing agreement among stores, ends the search for this field
    handles = {h for s in specs for h in s.handles}
    out.handles = [h for h in HANDLES if h in handles]
    out.sources = list(dict.fromkeys(u for s in specs for u in s.sources))
    return out


def parse_butterfly_table(page: str, url: str) -> dict[str, Spec]:
    """Butterfly's blade specification page: one row per blade, the maker's own plies, weight, material and
    handle sizes (a blank size means no such handle). Keys are compact names, with the brand."""
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", page, flags=re.S)
    out: dict[str, Spec] = {}
    for table in re.findall(r"<table.*?</table>", page, re.S):
        rows = [[" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)]
                for r in re.findall(r"<tr.*?</tr>", table, re.S)]
        if not rows or rows[0][:3] != ["Blade", "Playing Style", "Plies"]:
            continue
        head = rows[0]
        for row in rows[1:]:
            if len(row) != len(head):
                continue
            cell = dict(zip(head, row))
            spec = Spec(maker=True, sources=[url])
            spec.plies = plies_of(cell["Plies"]) or (int(m.group(1)) if (m := re.fullmatch(r"(\d+)-ply", cell["Plies"])) else None)
            weight = next((v for k, v in cell.items() if k.startswith("Weight")), "")
            spec.weight = float(weight) if re.fullmatch(r"\d{2,3}(?:\.\d)?", weight) else None
            material = cell.get("Material", "")
            spec.composition, spec.fiber = composition_of(material + " " + cell.get("Special Structure", ""), cell["Blade"])
            if spec.composition is None and _ALL_WOOD.search(material):
                spec.composition = "wood"
            sizes = {k.split(" ")[0]: v for k, v in cell.items() if "Handle Dims" in k}
            if "Handle Dims (mm)" in cell:  # the penhold table has a single column: Chinese or Japanese by blade name
                code = "JP" if re.search(r"\bJS\b|japan|\bJP", cell["Blade"], re.I) else "CS"
                spec.handles = [code] if cell["Handle Dims (mm)"] else []
            else:
                spec.handles = [h for h, code in (("FL", "FL"), ("ST", "ST"), ("AN", "AN")) if sizes.get(h)]
            out[compact("Butterfly " + strip_title(cell["Blade"]))] = spec
    return out
