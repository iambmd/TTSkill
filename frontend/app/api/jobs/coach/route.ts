import { createJob } from "@/lib/jobs";
import { invalid, textProblem, videoInputProblem } from "@/lib/validate";

export async function POST(req: Request) {
  const form = await req.formData();
  const request = String(form.get("request") ?? "").trim();
  if (!request) return invalid("Tell the coach what you want, e.g. 'show my best rallies and fix my forehand'.");
  const problem =
    textProblem(request, "coach_request", "Your request") ??
    videoInputProblem(form, "Add a video: upload a clip or paste a YouTube link.");
  if (problem) return invalid(problem);
  form.set("request", request);
  return createJob("coach", form);
}
