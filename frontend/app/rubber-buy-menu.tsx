import { buyMenu } from "@/config/affiliates";
import type { BuyLink, BuyLinkData } from "@/lib/buy-links";
import { secondaryButtonClass } from "./ui";

const external = { target: "_blank", rel: "sponsored nofollow noopener" } as const;

function storeLabel(link: BuyLink) {
  return link.type === "amazon-other" ? "Amazon (other seller)" : link.store;
}

function Store({ link }: { link: BuyLink }) {
  return <>
    {storeLabel(link)}
    {(link.type === "official" || link.type === "amazon-official") && <span className="ml-1 rounded border border-line px-1.5 py-0.5 text-xs font-medium text-muted">Official store</span>}
    {link.status === "unverified" && <span className="ml-1 text-muted">(unverified)</span>}
  </>;
}

export function RubberAffiliateDisclosure() {
  const { disclosure, amazonDisclosure } = buyMenu({});
  if (!disclosure) return null;
  return <p className="text-xs text-muted">
    As an affiliate, TTSkill may earn a commission from qualifying purchases.
    {amazonDisclosure && " As an Amazon Associate I earn from qualifying purchases."}
  </p>;
}

export function RubberBuyMenu({ product, featured = false, ...data }: BuyLinkData & { product: string; featured?: boolean }) {
  const { links: [first, ...others] } = buyMenu(data);
  if (!first) return <p className="text-xs text-muted">Not sold in the US yet</p>;
  const action = first.status === "unverified" ? "Check US listing" : "Buy in the US";

  return (
    <div className="space-y-1.5" aria-label={`US stores for ${product}`} role="group">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <a {...external} href={first.url} aria-label={`${action}: ${product} at ${storeLabel(first)}${first.status === "unverified" ? " (unverified)" : ""}`} className={`${secondaryButtonClass} ${featured ? "home-buy-button" : "h-11 normal-case tracking-normal"}`}>
          {action}
        </a>
        <span className="text-xs text-muted"><Store link={first} /></span>
      </div>
      {others.length > 0 && (
        <div className="flex flex-wrap items-baseline gap-x-2 text-xs">
          <span className="text-muted">Also at</span>
          {others.map((link) => (
            <a {...external} key={link.url} href={link.url} className="py-1 font-semibold text-accent underline underline-offset-2"><Store link={link} /></a>
          ))}
        </div>
      )}
      {!featured && <RubberAffiliateDisclosure />}
    </div>
  );
}
