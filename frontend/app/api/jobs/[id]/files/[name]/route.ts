import { getResult } from "@/lib/jobs";

export async function GET(req: Request, { params }: { params: Promise<{ id: string; name: string }> }) {
  const { id, name } = await params;
  if (!/^[\w-]{1,64}\.mp4$/.test(name)) return Response.json({ error: "Not found" }, { status: 404 });
  return getResult(id, req.headers.get("range"), name);
}
