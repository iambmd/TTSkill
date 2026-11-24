import { rerunJob } from "@/lib/jobs";
import { routeMessages } from "@/lib/messages";
import { invalid, playerSelectionProblem } from "@/lib/validate";

/** "Change player": re-run a Breakdown, Pro match or Coach job following another player. */
export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { v, e, t } = routeMessages(req);
  const { id } = await params;
  const form = await req.formData();
  const picked = form.get("player_time") && form.get("player_box");
  const problem = playerSelectionProblem(form, v) ?? (picked ? null : v("pickAgain"));
  return problem ? invalid(problem) : rerunJob(id, form, e, t);
}
