import { createJob } from "@/lib/jobs";

const STROKES = new Set(["forehand", "backhand", "serve", "flick", "block", "footwork"]);

export async function POST(req: Request) {
  const form = await req.formData();
  const video = form.get("video");
  const text = String(form.get("text") ?? "").trim();
  const stroke = String(form.get("stroke") ?? "");
  const hasVideo = video instanceof File && video.size > 0;
  if (!hasVideo && !text) {
    return Response.json({ error: "Provide a video or a text description." }, { status: 400 });
  }
  if (!STROKES.has(stroke)) {
    return Response.json({ error: `Unknown stroke: ${stroke}` }, { status: 400 });
  }
  return createJob("breakdown", form);
}
