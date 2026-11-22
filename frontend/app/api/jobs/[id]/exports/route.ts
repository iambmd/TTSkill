import { exportHighlights } from "@/lib/jobs";
import { invalid } from "@/lib/validate";

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await req.json().catch(() => null);
  const rallies = body?.rallies;
  if (!/^[0-9a-f]{32}$/.test(id) || !Array.isArray(rallies) || !rallies.length ||
      !rallies.every((rally) => Number.isSafeInteger(rally) && rally > 0) || new Set(rallies).size !== rallies.length) {
    return invalid("Choose at least one available rally, once each.");
  }
  return exportHighlights(id, rallies);
}
