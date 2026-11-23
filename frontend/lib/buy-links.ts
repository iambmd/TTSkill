/** Shared product links and compatibility with older recommendation responses. */
import catalog from "../../shared/rubber-buy-links.json";

export type BuyLink = {
  store: string;
  url: string;
  type: "official" | "amazon-official" | "retailer" | "amazon-other";
  status?: "unverified";
};

export type BuyLinkData = {
  buyLinks?: BuyLink[];
  buyLink?: string;
  buyUrl?: string;
};

const links = catalog as Record<string, BuyLink[]>;

export function rubberBuyLinks(name: string): BuyLink[] {
  return Object.hasOwn(links, name) ? links[name] : [];
}

export function withRubberBuyLinks<T extends BuyLinkData & { name: string }>(rubber: T): T & BuyLinkData {
  if (rubber.buyLinks) return rubber;
  const buyLinks = rubberBuyLinks(rubber.name);
  if (!buyLinks.length && (rubber.buyLink || rubber.buyUrl)) return rubber;
  return { ...rubber, buyLinks };
}
