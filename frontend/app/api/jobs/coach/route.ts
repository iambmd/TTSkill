import { createJob } from "@/lib/jobs";
import { LINK_HINT, youtubeId } from "@/lib/youtube";

export async function POST(req: Request) {
  const form = await req.formData();
  const video = form.get("video");
  const url = String(form.get("url") ?? "").trim();
  const request = String(form.get("request") ?? "").trim();
  const hasVideo = video instanceof File && video.size > 0;
  if (!request) return Response.json({ error: "Tell the coach what you want." }, { status: 400 });
  if (!hasVideo && !url) return Response.json({ error: "Add a video: upload a clip or paste a YouTube link." }, { status: 400 });
  if (!hasVideo && !youtubeId(url)) return Response.json({ error: LINK_HINT }, { status: 400 });
  return createJob("coach", form);
}
