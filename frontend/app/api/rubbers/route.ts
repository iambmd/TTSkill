import { BACKEND_URL } from "@/lib/jobs";
import { withRubberBuyLinks } from "@/lib/buy-links";
import { routeMessages } from "@/lib/messages";
import { DEFAULT_BUDGET, LEVELS, STYLES, TYPES, recommend, type Level, type Recommendation, type RubberType, type Style } from "@/lib/rubbers";

const usd = (locale: string, n: number) =>
  new Intl.NumberFormat(locale, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

/** GET /api/rubbers?style=&rubber_type=&level=&budget= : the backend's recommender, or the local port without one. */
export async function GET(req: Request): Promise<Response> {
  const { e, locale } = routeMessages(req);
  const q = new URL(req.url).searchParams;
  const style = q.get("style") ?? "spin";
  const type = q.get("rubber_type") ?? "inverted";
  const level = q.get("level") ?? "intermediate";
  if (!STYLES.includes(style as Style)) return Response.json({ error: e("pickStyle") }, { status: 400 });
  if (!TYPES.includes(type as RubberType)) return Response.json({ error: e("pickType") }, { status: 400 });
  if (!LEVELS.includes(level as Level)) return Response.json({ error: e("pickLevel") }, { status: 400 });
  const budget = Number(q.get("budget") ?? DEFAULT_BUDGET);
  if (!(budget > 0 && budget <= 500)) return Response.json({ error: e("budget", { min: usd(locale, 1), max: usd(locale, 500) }) }, { status: 400 });
  if (BACKEND_URL && q.get("demo") !== "1") {
    try {
      const res = await fetch(`${BACKEND_URL}/equipment/rubbers?${new URLSearchParams({ style, rubber_type: type, level, budget: String(budget) })}`, {
        signal: AbortSignal.timeout(2500),
      });
      if (res.ok) {
        const body = await res.json() as Recommendation;
        return Response.json({ ...body, results: body.results.map(withRubberBuyLinks) });
      }
    } catch {
      // fall through to the local copy, the data is the same
    }
  }
  return Response.json(recommend(style as Style, type as RubberType, level as Level, budget));
}
