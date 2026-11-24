/** Shared product links (one catalog for rubbers, one for blades) and compatibility with older recommendation responses. */
import bladeCatalog from "../../shared/blade-buy-links.json";
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

const rubberLinks = catalog as Record<string, BuyLink[]>;
const bladeLinks = bladeCatalog as Record<string, BuyLink[]>;
const lookup = (links: Record<string, BuyLink[]>, name: string): BuyLink[] => (Object.hasOwn(links, name) ? links[name] : []);

export const rubberBuyLinks = (name: string) => lookup(rubberLinks, name);
export const bladeBuyLinks = (name: string) => lookup(bladeLinks, name);

function withLinks<T extends BuyLinkData & { name: string }>(product: T, find: (name: string) => BuyLink[]): T & BuyLinkData {
  if (product.buyLinks) return product;
  const buyLinks = find(product.name);
  if (!buyLinks.length && (product.buyLink || product.buyUrl)) return product;
  return { ...product, buyLinks };
}

export const withRubberBuyLinks = <T extends BuyLinkData & { name: string }>(rubber: T) => withLinks(rubber, rubberBuyLinks);
export const withBladeBuyLinks = <T extends BuyLinkData & { name: string }>(blade: T) => withLinks(blade, bladeBuyLinks);
