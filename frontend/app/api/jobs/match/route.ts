import { createJob } from "@/lib/jobs";
import { LINK_HINT, youtubeId } from "@/lib/youtube";

export async function POST(req: Request) {
  const form = await req.formData();
  const video = form.get("video");
  const url = String(form.get("url") ?? "").trim();
  const stroke = String(form.get("stroke") ?? "");
  const height = String(form.get("height_cm") ?? "").trim();
  const hasVideo = video instanceof File && video.size > 0;
  if (!hasVideo && !url) {
    return Response.json({ error: "Upload a clip of yourself or paste a YouTube link." }, { status: 400 });
  }
  if (!hasVideo && !youtubeId(url)) {
    return Response.json({ error: LINK_HINT }, { status: 400 });
  }
  if (stroke !== "forehand" && stroke !== "backhand") {
    return Response.json({ error: "Pick forehand or backhand." }, { status: 400 });
  }
  if (height && !(Number(height) >= 100 && Number(height) <= 230)) {
    return Response.json({ error: "Height should be between 100 and 230 cm." }, { status: 400 });
  }
  return createJob("match", form);
}
