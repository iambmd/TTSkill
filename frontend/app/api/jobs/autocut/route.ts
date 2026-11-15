import { createJob } from "@/lib/jobs";
import { choiceProblem, invalid, rangeProblem, videoInputProblem } from "@/lib/validate";

export async function POST(req: Request) {
  const form = await req.formData();
  // A missing field takes the backend's default; a blank one is checked as sent.
  const field = (k: string, missing = "") => String(form.get(k) ?? missing);
  const problem =
    videoInputProblem(form, "Upload a match video or paste a YouTube link.") ??
    choiceProblem(field("mode", "highlights"), "autocut_mode", "Mode") ??
    rangeProblem(field("top_n"), "top_n", "Rallies in the reel", true) ??
    rangeProblem(field("threshold"), "threshold", "Hit threshold") ??
    rangeProblem(field("gap"), "gap", "Max gap") ??
    rangeProblem(field("min_hits"), "min_hits", "Min hits", true);
  return problem ? invalid(problem) : createJob("autocut", form);
}
