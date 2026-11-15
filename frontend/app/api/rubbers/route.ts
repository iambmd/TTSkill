import { LEVELS, STYLES, TYPES, recommend, type Level, type RubberType, type Style } from "@/lib/rubbers";

const BACKEND_URL = process.env.BACKEND_URL;

/** GET /api/rubbers?style=&rubber_type=&level= : the backend's recommender, or the local port without one. */
export async function GET(req: Request): Promise<Response> {
  const q = new URL(req.url).searchParams;
  const style = q.get("style") ?? "spin";
  const type = q.get("rubber_type") ?? "inverted";
  const level = q.get("level") ?? "intermediate";
  if (!STYLES.includes(style as Style)) return Response.json({ error: "Pick spin or speed." }, { status: 400 });
  if (!TYPES.includes(type as RubberType)) return Response.json({ error: "Pick a rubber type." }, { status: 400 });
  if (!LEVELS.includes(level as Level)) return Response.json({ error: "Pick your level." }, { status: 400 });
  if (BACKEND_URL) {
    try {
      const res = await fetch(`${BACKEND_URL}/equipment/rubbers?${new URLSearchParams({ style, rubber_type: type, level })}`);
      if (res.ok) return Response.json(await res.json());
    } catch {
      // fall through to the local copy, the data is the same
    }
  }
  return Response.json(recommend(style as Style, type as RubberType, level as Level));
}
