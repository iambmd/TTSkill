import { createJob } from "@/lib/jobs";
import { routeMessages } from "@/lib/messages";
import { STROKE_TYPE_VALUES } from "@/lib/strokes";
import { choiceProblem, invalid, langProblem, onlyMeProblem, playerSelectionProblem, textProblem, videoInputProblem } from "@/lib/validate";

// "" means auto-detect; the named strokes are kept for API callers that still send them.
const STROKES = new Set(["", "auto", "forehand", "backhand", "serve", "flick", "block", "footwork"]);

export async function POST(req: Request) {
  const { v, e, offline } = routeMessages(req);
  const form = await req.formData();
  // A missing field takes the backend's default; a blank one is checked as sent.
  const field = (k: string, missing = "") => String(form.get(k) ?? missing);
  const video = form.get("video");
  const hasInput = (video instanceof File && video.size > 0) || !!field("url").trim() || !!field("staged").trim() || !!field("source_job");
  const text = field("text").trim();
  const stroke = field("stroke");
  const strokeType = field("stroke_type");
  // A description alone is enough; a clip or link, when given, must be usable.
  const problem =
    playerSelectionProblem(form, v) ??
    onlyMeProblem(form, v) ??
    langProblem(form, v) ??
    (!hasInput && !text ? v("breakdownInput") : null) ??
    (hasInput ? videoInputProblem(form, "", true, v) : null) ??
    (STROKES.has(stroke) ? null : v("unknownStroke", { stroke })) ??
    (!strokeType || STROKE_TYPE_VALUES.has(strokeType) ? null : v("unknownStrokeType", { stroke: strokeType })) ??
    choiceProblem(field("hand", "auto"), "hand", v("labels.hand"), v) ??
    textProblem(field("player"), "player", v("labels.playerName"), v) ??
    textProblem(text, "training_text", v("labels.trainingDescription"), v);
  return problem ? invalid(problem) : createJob("breakdown", form, e, offline);
}
