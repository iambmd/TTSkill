import { describe, expect, it } from "vitest";
import { buyMenu } from "@/config/affiliates";
import { withRubberBuyLinks, type BuyLink } from "@/lib/buy-links";

const links: BuyLink[] = [
  { store: "Butterfly US", url: "https://shop.butterflyonline.com/tenergy-05", type: "official" },
  { store: "Amazon", url: "https://www.amazon.com/dp/B000000000", type: "amazon-official" },
  { store: "Megaspin", url: "https://www.megaspin.net/store/default.asp?pid=b-tenergy-05", type: "retailer" },
  { store: "Paddle Palace", url: "https://www.paddlepalace.com/products/butterfly-tenergy-05-rubber", type: "retailer" },
];

describe("rubber purchase menu", () => {
  it("keeps priority order and untouched URLs when tags are unset", () => {
    const menu = buyMenu({ buyLinks: links }, {});
    expect(menu.links).toEqual(links.map((link) => ({ ...link, affiliate: false })));
    expect(menu.disclosure).toBe(false);
  });

  it("pins configured stores in priority order and keeps product parameters", () => {
    const menu = buyMenu({ buyLinks: links }, {
      Amazon: { host: "amazon.com", param: "tag", tag: "example-20" },
      Megaspin: { host: "megaspin.net", param: "aid", tag: "abc 123" },
    });
    expect(menu.links.map((link) => link.store)).toEqual(["Amazon", "Megaspin", "Butterfly US", "Paddle Palace"]);
    expect(menu.links[0].url).toContain("?tag=example-20");
    expect(menu.links[1].url).toContain("?pid=b-tenergy-05&aid=abc+123");
    expect(menu.links[2].type).toBe("official");
    expect(links[1].url).not.toContain("tag=");
    expect(menu.disclosure && menu.amazonDisclosure).toBe(true);
  });

  it("puts other Amazon sellers after specialist retailers even with an affiliate tag", () => {
    const other: BuyLink = { store: "Amazon", url: "https://www.amazon.com/dp/B100000000", type: "amazon-other" };
    const mega: BuyLink = { ...links[2], status: "unverified" };
    const menu = buyMenu({ buyLinks: [other, mega, links[3]] }, {
      Amazon: { host: "amazon.com", param: "tag", tag: "example-20" },
      Megaspin: { host: "megaspin.net", param: "aid", tag: "example" },
    });
    expect(menu.links.map(({ store }) => store)).toEqual(["Paddle Palace", "Megaspin", "Amazon"]);
    expect(menu.links[1].status).toBe("unverified");
    expect(menu.links[2].url).toBe(`${other.url}?tag=example-20`);
  });

  it("preserves a legacy URL until a list is provided, including an explicit empty list", () => {
    const legacy = { name: "Legacy example", buyUrl: "https://example.com/product" };
    expect(buyMenu(withRubberBuyLinks(legacy), {}).links[0].url).toBe(legacy.buyUrl);
    expect(buyMenu({ ...legacy, buyLinks: [] }, {}).links).toEqual([]);
    expect(buyMenu({ buyLink: "https://www.amazon.com/dp/B000000000" }, {}).links).toEqual([]);
  });
});
