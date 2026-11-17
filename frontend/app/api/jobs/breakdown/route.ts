import { createJob } from "@/lib/jobs";
import { STROKE_TYPE_VALUES } from "@/lib/strokes";
import { choiceProblem, invalid, playerSelectionProblem, textProblem, videoInputProblem } from "@/lib/validate";

// "" means auto-detect; the named strokes are kept for API callers that still send them.
const STROKES = new Set(["", "auto", "forehand", "backhand", "serve", "flick", "block", "footwork"]);

export async function POST(req: Request) {
  const form = await req.formData();
  // A missing field takes the backend's default; a blank one is checked as sent.
  const field = (k: string, missing = "") => String(form.get(k) ?? missing);
  const video = form.get("video");
  const hasInput = (video instanceof File && video.size > 0) || !!field("url").trim();
  const text = field("text").trim();
  const stroke = field("stroke");
  const strokeType = field("stroke_type");
  // A description alone is enough; a clip or link, when given, must be usable.
  const problem =
    playerSelectionProblem(form) ??
    (!hasInput && !text ? "Upload a clip, paste a YouTube link, or describe the training." : null) ??
    (hasInput ? videoInputProblem(form, "") : null) ??
    (STROKES.has(stroke) ? null : `Unknown stroke: ${stroke}. Leave it blank to auto-detect.`) ??
    (!strokeType || STROKE_TYPE_VALUES.has(strokeType)
      ? null : `Unknown stroke type: ${strokeType}. Pick one from the list, or leave it blank to auto-detect.`) ??
    choiceProblem(field("hand", "auto"), "hand", "Bat hand") ??
    textProblem(field("player"), "player", "The player's name") ??
    textProblem(text, "training_text", "The training description");
  return problem ? invalid(problem) : createJob("breakdown", form);
}
