import { createJob } from "@/lib/jobs";
import { choiceProblem, heightProblem, invalid, playerSelectionProblem, videoInputProblem } from "@/lib/validate";

export async function POST(req: Request) {
  const form = await req.formData();
  // A missing field takes the backend's default; a blank one is checked as sent.
  const field = (k: string, missing = "") => String(form.get(k) ?? missing);
  const problem =
    playerSelectionProblem(form) ??
    videoInputProblem(form, "Upload a clip of yourself or paste a YouTube link.") ??
    choiceProblem(field("stroke", "forehand"), "match_stroke", "Stroke") ??
    choiceProblem(field("hand", "auto"), "hand", "Bat hand") ??
    choiceProblem(field("grip", "shakehand"), "grip", "Grip") ??
    heightProblem(field("height_cm"));
  return problem ? invalid(problem) : createJob("match", form);
}
