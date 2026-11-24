import { useTranslations } from "next-intl";
import { buyMenu } from "@/config/affiliates";
import type { BuyLink, BuyLinkData } from "@/lib/buy-links";
import { secondaryButtonClass } from "./ui";

const external = { target: "_blank", rel: "sponsored nofollow noopener" } as const;

type T = (key: string) => string;

function storeLabel(link: BuyLink, t: T) {
  return link.type === "amazon-other" ? t("amazonOther") : link.store;
}

function Store({ link }: { link: BuyLink }) {
  const t = useTranslations("buy");
  return <>
    {storeLabel(link, t)}
    {(link.type === "official" || link.type === "amazon-official") && <span className="ml-1 rounded border border-line px-1.5 py-0.5 text-xs font-medium text-muted">{t("official")}</span>}
    {link.status === "unverified" && <span className="ml-1 text-muted">{t("unverified")}</span>}
  </>;
}

export function RubberAffiliateDisclosure() {
  const t = useTranslations("buy");
  const { disclosure, amazonDisclosure } = buyMenu({});
  if (!disclosure) return null;
  return <p className="text-xs text-muted">
    {t("disclosure")}
    {amazonDisclosure && t("amazonDisclosure")}
  </p>;
}

export function RubberBuyMenu({ product, featured = false, ...data }: BuyLinkData & { product: string; featured?: boolean }) {
  const t = useTranslations("buy");
  const { links: [first, ...others] } = buyMenu(data);
  if (!first) return <p className="text-xs text-muted">{t("notSold")}</p>;
  const action = first.status === "unverified" ? t("check") : t("buy");

  return (
    <div className="space-y-1.5" aria-label={t("stores", { product })} role="group">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <a {...external} href={first.url} aria-label={t("linkLabel", { action, product, store: storeLabel(first, t), unverified: first.status === "unverified" ? t("unverifiedSuffix") : "" })} className={`${secondaryButtonClass} ${featured ? "home-buy-button" : "h-11 normal-case tracking-normal"}`}>
          {action}
        </a>
        <span className="text-xs text-muted"><Store link={first} /></span>
      </div>
      {others.length > 0 && (
        <div className="flex flex-wrap items-baseline gap-x-2 text-xs">
          <span className="text-muted">{t("alsoAt")}</span>
          {others.map((link) => (
            <a {...external} key={link.url} href={link.url} className="py-1 font-semibold text-accent underline underline-offset-2"><Store link={link} /></a>
          ))}
        </div>
      )}
      {!featured && <RubberAffiliateDisclosure />}
    </div>
  );
}
