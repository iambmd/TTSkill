import { detectPlayers } from "@/lib/jobs";
import { routeMessages } from "@/lib/messages";
import { invalid, playerFramesProblem } from "@/lib/validate";

/** The players in a few frames of the chosen video, for "Which one is you?". */
export async function POST(req: Request) {
  const { v, e } = routeMessages(req);
  const form = await req.formData();
  const problem = playerFramesProblem(form, v);
  return problem ? invalid(problem) : detectPlayers(form, req.signal, e);
}
