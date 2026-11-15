import { createJob } from "@/lib/jobs";
import { LINK_HINT, youtubeId } from "@/lib/youtube";

export async function POST(req: Request) {
  const form = await req.formData();
  const video = form.get("video");
  const mode = String(form.get("mode") ?? "");
  const url = String(form.get("url") ?? "").trim();
  const hasVideo = video instanceof File && video.size > 0;
  if (!hasVideo && !url) {
    return Response.json({ error: "Upload a match video or paste a YouTube link." }, { status: 400 });
  }
  if (!hasVideo && !youtubeId(url)) {
    return Response.json({ error: LINK_HINT }, { status: 400 });
  }
  if (mode !== "highlights" && mode !== "full") {
    return Response.json({ error: "mode must be 'highlights' or 'full'." }, { status: 400 });
  }
  return createJob("autocut", form);
}
