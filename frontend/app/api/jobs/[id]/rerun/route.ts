import { rerunJob } from "@/lib/jobs";
import { invalid, playerSelectionProblem } from "@/lib/validate";

/** "Change player": re-run a Breakdown, Pro match or Coach job following another player. */
export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const form = await req.formData();
  const picked = form.get("player_time") && form.get("player_box");
  const problem = playerSelectionProblem(form) ?? (picked ? null : "The player you picked didn't come through. Pick the player again.");
  return problem ? invalid(problem) : rerunJob(id, form);
}
