import { createJob } from "@/lib/jobs";

export async function POST(req: Request) {
  const form = await req.formData();
  const video = form.get("video");
  const mode = String(form.get("mode") ?? "");
  if (!(video instanceof File) || video.size === 0) {
    return Response.json({ error: "Upload a match video." }, { status: 400 });
  }
  if (mode !== "highlights" && mode !== "full") {
    return Response.json({ error: "mode must be 'highlights' or 'full'." }, { status: 400 });
  }
  return createJob("autocut", form);
}
