import { getResult } from "@/lib/jobs";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return getResult(id, req.headers.get("range"));
}
