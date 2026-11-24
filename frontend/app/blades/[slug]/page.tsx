import Link from "next/link";
import { notFound } from "next/navigation";
import { useTranslations } from "next-intl";
import { bladeBySlug, layers } from "@/lib/blades";
import { GearTabs } from "../../gear-tabs";
import { PageIntro, secondaryButtonClass } from "../../ui";
import { BladeCard } from "../blade-card";

function Detail({ slug }: { slug: string }) {
  const t = useTranslations("blades");
  const blade = bladeBySlug(slug);
  if (!blade) notFound();
  return (
    <div className="space-y-7">
      <GearTabs active="blades" />
      <PageIntro eyebrow={blade.brand} title={blade.name} body={t("note")} />
      <ol className="max-w-xl"><BladeCard blade={{ ...blade, ...layers(blade) }} linkName={false} /></ol>
      <Link href="/blades" className={`${secondaryButtonClass} h-11 normal-case tracking-normal`}>{t("openFinder")}</Link>
    </div>
  );
}

export default async function BladePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <Detail slug={slug} />;
}
