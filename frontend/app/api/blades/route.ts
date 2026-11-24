import { routeMessages } from "@/lib/messages";
import { DEFAULT_BUDGET, FEELS, HANDLE_FILTERS, LEVELS, STYLES, recommend, type BladeLevel, type BladeStyle, type Feel, type HandleFilter } from "@/lib/blades";

const usd = (locale: string, n: number) =>
  new Intl.NumberFormat(locale, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

/** GET /api/blades?style=&level=&budget=&handle=&feel= : the bundled blade data ranked like the rubbers (no backend needed). */
export async function GET(req: Request): Promise<Response> {
  const { e, locale } = routeMessages(req);
  const q = new URL(req.url).searchParams;
  const style = q.get("style") ?? "spin";
  const level = q.get("level") ?? "intermediate";
  const handle = q.get("handle") ?? "any";
  const feel = q.get("feel") ?? "any";
  if (!STYLES.includes(style as BladeStyle)) return Response.json({ error: e("pickStyle") }, { status: 400 });
  if (!LEVELS.includes(level as BladeLevel)) return Response.json({ error: e("pickLevel") }, { status: 400 });
  if (!HANDLE_FILTERS.includes(handle as HandleFilter)) return Response.json({ error: e("pickHandle") }, { status: 400 });
  if (!FEELS.includes(feel as Feel)) return Response.json({ error: e("pickFeel") }, { status: 400 });
  const budget = Number(q.get("budget") ?? DEFAULT_BUDGET);
  if (!(budget > 0 && budget <= 500)) return Response.json({ error: e("budget", { min: usd(locale, 1), max: usd(locale, 500) }) }, { status: 400 });
  return Response.json(recommend(style as BladeStyle, level as BladeLevel, budget, handle as HandleFilter, feel as Feel));
}
