import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { rating, usd } from "@/lib/format";
import { controlTier, flexTier, paceTier, type Blade, type Combo, type Layers } from "@/lib/blade-types";
import { BuyMenu } from "../buy-menu";

type T = ReturnType<typeof useTranslations>;

function Chip({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full border border-line px-2.5 py-1 text-xs text-muted">{children}</span>;
}

/** What the layers are, in words: only what the data states, or the name's hint marked as such. */
export function layersText(b: Pick<Blade, "composition" | "fiber"> & Layers, t: T): string | null {
  if (b.composition === "wood") return t("layers.wood");
  if (b.composition) return t(`layers.${b.composition}`, { fiber: t(`fibers.${b.fiber ?? "other"}`) });
  return b.inferred ? t("layers.inferred") : null;
}

/** One blade: RevSpin's ratings (with the source and its link), our own one-line summary, the specs we could confirm,
 * the US store links and, in the finder, a rubber to pair with it. A spec nobody states is simply not shown. */
export function BladeCard({ blade, rank, combo, linkName = true }: {
  blade: Blade & Layers; rank?: number; combo?: Combo; linkName?: boolean;
}) {
  const t = useTranslations("blades");
  const tr = useTranslations("rubbers");
  const format = useFormatter();
  const r = (v: number) => rating(format, v);
  const layers = layersText(blade, t);
  const site = blade.specSources[0] ? new URL(blade.specSources[0]).hostname.replace(/^www\./, "") : null;
  const hasSpecs = blade.plies !== null || blade.weight !== null || blade.handles.length > 0 || layers !== null;
  return (
    <li className="surface-card space-y-3 p-4">
      <div className="flex items-center gap-4">
        {rank !== undefined && <span className="stat w-6 shrink-0 text-xl text-accent">{rank}</span>}
        <div className="min-w-0 flex-1">
          <p className="break-words font-bold">
            {linkName ? <Link href={`/blades/${blade.slug}`} className="underline-offset-2 hover:underline">{blade.name}</Link> : blade.name}
          </p>
          <p className="text-xs text-muted">{t("ratings", { speed: r(blade.speed), control: r(blade.control), stiffness: r(blade.stiffness) })}</p>
        </div>
        <div className="text-right">
          <p className="stat text-xl">{usd(format, blade.price, true)}</p>
          <p className="text-xs text-muted">{t("score", { score: r(blade.overall) })}</p>
        </div>
      </div>
      <p className="text-xs text-muted">
        {t("source")}{" "}
        <a href={blade.url} target="_blank" rel="noopener noreferrer" className="font-semibold underline underline-offset-2 hover:text-fg">{t("sourceName")}</a>
        {" · "}{t("ratingCount", { n: blade.ratings })}
      </p>
      <p className="text-sm">
        {t("summary", { pace: t(`paces.${paceTier(blade.speed)}`), control: t(`controls.${controlTier(blade.control)}`), flex: t(`flexes.${flexTier(blade.stiffness)}`) })}
      </p>
      {hasSpecs ? (
        <div className="space-y-1.5">
          <div className="flex flex-wrap gap-1.5">
            {layers && <Chip>{layers}</Chip>}
            {blade.plies !== null && <Chip>{t("plies", { n: blade.plies })}</Chip>}
            {blade.weight !== null && <Chip>{t("weight", { n: format.number(blade.weight) })}</Chip>}
            {blade.handles.length > 0 && <Chip>{t("handlesList", { list: blade.handles.map((h) => t(`handles.${h}`)).join(", ") })}</Chip>}
          </div>
          {site && <p className="text-xs text-muted">{t("specsFrom", { site })}</p>}
        </div>
      ) : <p className="text-xs text-muted">{t("noSpecs")}</p>}
      <BuyMenu product={blade.name} buyLinks={blade.buyLinks} empty="noLink" />
      {combo && (
        <div className="space-y-2 rounded-2xl border border-line p-3">
          <p className="text-xs font-bold uppercase tracking-wide text-muted">{t("comboTitle")}</p>
          {combo.rubber ? (
            <>
              <div className="flex items-baseline justify-between gap-3">
                <p className="min-w-0 break-words font-semibold">{combo.rubber.name}</p>
                <p className="stat text-lg">{combo.rubber.price !== null && usd(format, combo.rubber.price, true)}</p>
              </div>
              <p className="text-xs text-muted">
                {tr("ratings", {
                  speed: combo.rubber.speed === null ? tr("tbd") : r(combo.rubber.speed),
                  spin: combo.rubber.spin === null ? tr("tbd") : r(combo.rubber.spin),
                  control: combo.rubber.control === null ? tr("tbd") : r(combo.rubber.control),
                })}
              </p>
              <BuyMenu product={combo.rubber.name} buyLinks={combo.rubber.buyLinks} buyLink={combo.rubber.buyLink} buyUrl={combo.rubber.buyUrl} disclosure={false} />
            </>
          ) : <p className="text-sm text-muted">{t("comboNone", { amount: usd(format, combo.budget, true) })}</p>}
          <p className="text-xs text-muted">{t("comboLeft", { amount: usd(format, combo.budget, true) })} · {t("comboHint")}</p>
        </div>
      )}
    </li>
  );
}
