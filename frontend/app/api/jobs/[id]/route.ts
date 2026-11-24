import { getJob } from "@/lib/jobs";
import { routeMessages } from "@/lib/messages";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return getJob(id, routeMessages(req).e);
}
