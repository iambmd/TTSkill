import { createJob } from "@/lib/jobs";
import { routeMessages } from "@/lib/messages";
import { choiceProblem, invalid, rangeProblem, videoInputProblem } from "@/lib/validate";

export async function POST(req: Request) {
  const { v, e, offline, t } = routeMessages(req);
  const form = await req.formData();
  // A missing field takes the backend's default; a blank one is checked as sent.
  const field = (k: string, missing = "") => String(form.get(k) ?? missing);
  const problem =
    videoInputProblem(form, v("autocutVideo"), false, v) ??
    choiceProblem(field("mode", "highlights"), "autocut_mode", v("labels.mode"), v) ??
    rangeProblem(field("top_n"), "top_n", v("labels.topN"), true, v) ??
    rangeProblem(field("threshold"), "threshold", v("labels.threshold"), false, v) ??
    rangeProblem(field("gap"), "gap", v("labels.gap"), false, v) ??
    rangeProblem(field("min_hits"), "min_hits", v("labels.minHits"), true, v);
  return problem ? invalid(problem) : createJob("autocut", form, e, offline, t);
}
