import { createJob } from "@/lib/jobs";
import { LINK_HINT, youtubeId } from "@/lib/youtube";

import { STROKE_TYPE_VALUES } from "@/lib/strokes";

// "" means auto-detect; the named strokes are kept for API callers that still send them.
const STROKES = new Set(["", "auto", "forehand", "backhand", "serve", "flick", "block", "footwork"]);

export async function POST(req: Request) {
  const form = await req.formData();
  const video = form.get("video");
  const text = String(form.get("text") ?? "").trim();
  const stroke = String(form.get("stroke") ?? "");
  const url = String(form.get("url") ?? "").trim();
  const hasVideo = video instanceof File && video.size > 0;
  if (!hasVideo && !url && !text) {
    return Response.json({ error: "Upload a clip, paste a YouTube link, or describe the training." }, { status: 400 });
  }
  if (!hasVideo && url && !youtubeId(url)) {
    return Response.json({ error: LINK_HINT }, { status: 400 });
  }
  const strokeType = String(form.get("stroke_type") ?? "");
  if (!STROKES.has(stroke)) {
    return Response.json({ error: `Unknown stroke: ${stroke}` }, { status: 400 });
  }
  if (strokeType && !STROKE_TYPE_VALUES.has(strokeType)) {
    return Response.json({ error: `Unknown stroke type: ${strokeType}` }, { status: 400 });
  }
  return createJob("breakdown", form);
}
