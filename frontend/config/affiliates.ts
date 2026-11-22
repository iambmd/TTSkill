/** Public merchant tracking parameters, applied only when configured. */
import type { BuyLink, BuyLinkData } from "@/lib/buy-links";

const affiliates = {
  Amazon: { host: "amazon.com", param: "tag", tag: process.env.NEXT_PUBLIC_AMAZON_TAG?.trim() },
  Megaspin: { host: "megaspin.net", param: "aid", tag: process.env.NEXT_PUBLIC_MEGASPIN_TAG?.trim() },
  "Paddle Palace": {
    host: "paddlepalace.com",
    param: process.env.NEXT_PUBLIC_PADDLE_PALACE_TAG_PARAM?.trim(),
    tag: process.env.NEXT_PUBLIC_PADDLE_PALACE_TAG?.trim(),
  },
};

type AffiliateConfig = Partial<Record<string, { host: string; param?: string; tag?: string }>>;

function priority(link: BuyLink) {
  if (link.type === "official") return 0;
  if (link.type === "amazon-official") return 1;
  if (link.store === "Megaspin") return 2;
  if (link.store === "Paddle Palace") return 3;
  return 4;
}

/** Build the menu from clean URLs, pinning active affiliate stores in their normal order. */
export function buyMenu(data: BuyLinkData, config: AffiliateConfig = affiliates) {
  const old = data.buyLink || data.buyUrl;
  const links: BuyLink[] = data.buyLinks ?? (old ? [{ store: "Retailer", url: old, type: "retailer" }] : []);
  const menu = links.flatMap((link) => {
    let url: URL;
    try { url = new URL(link.url); } catch { return []; }
    if (!["https:", "http:"].includes(url.protocol)) return [];
    const host = url.hostname.replace(/^www\./, "");
    if (host === "amazon.com" && link.type !== "amazon-official") return [];
    const rule = Object.hasOwn(config, link.store) ? config[link.store] : undefined;
    if (rule?.host !== host || !rule.tag || !rule.param) return [{ ...link, affiliate: false }];
    url.searchParams.set(rule.param, rule.tag);
    return [{ ...link, url: url.href, affiliate: true }];
  });
  menu.sort((a, b) => Number(b.affiliate) - Number(a.affiliate) || priority(a) - priority(b));
  return {
    links: menu,
    disclosure: Object.values(config).some((rule) => rule?.tag && rule.param),
    amazonDisclosure: !!config.Amazon?.tag,
  };
}
