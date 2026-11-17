import { detectPlayers } from "@/lib/jobs";
import { invalid, playerFramesProblem } from "@/lib/validate";

/** The players in a few frames of the chosen video, for "Which one is you?". */
export async function POST(req: Request) {
  const form = await req.formData();
  const problem = playerFramesProblem(form);
  return problem ? invalid(problem) : detectPlayers(form);
}
