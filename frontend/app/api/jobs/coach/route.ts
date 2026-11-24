import { createJob } from "@/lib/jobs";
import { routeMessages } from "@/lib/messages";
import { invalid, langProblem, onlyMeProblem, playerSelectionProblem, textProblem, videoInputProblem } from "@/lib/validate";

export async function POST(req: Request) {
  const { v, e, offline } = routeMessages(req);
  const form = await req.formData();
  const request = String(form.get("request") ?? "").trim();
  if (!request) return invalid(v("coachRequest"));
  const problem =
    playerSelectionProblem(form, v) ??
    onlyMeProblem(form, v) ??
    langProblem(form, v) ??
    textProblem(request, "coach_request", v("labels.request"), v) ??
    videoInputProblem(form, v("coachVideo"), true, v);
  if (problem) return invalid(problem);
  form.set("request", request);
  return createJob("coach", form, e, offline);
}
