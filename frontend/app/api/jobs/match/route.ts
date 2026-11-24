import { createJob } from "@/lib/jobs";
import { routeMessages } from "@/lib/messages";
import { choiceProblem, heightProblem, invalid, langProblem, playerSelectionProblem, videoInputProblem } from "@/lib/validate";

export async function POST(req: Request) {
  const { v, e, offline, t } = routeMessages(req);
  const form = await req.formData();
  // A missing field takes the backend's default; a blank one is checked as sent.
  const field = (k: string, missing = "") => String(form.get(k) ?? missing);
  const problem =
    playerSelectionProblem(form, v) ??
    langProblem(form, v) ??
    videoInputProblem(form, v("matchVideo"), false, v) ??
    choiceProblem(field("stroke", "forehand"), "match_stroke", v("labels.stroke"), v) ??
    choiceProblem(field("hand", "auto"), "hand", v("labels.hand"), v) ??
    choiceProblem(field("grip", "shakehand"), "grip", v("labels.grip"), v) ??
    heightProblem(field("height_cm"), v);
  return problem ? invalid(problem) : createJob("match", form, e, offline, t);
}
