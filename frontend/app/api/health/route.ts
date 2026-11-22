import { backendHealth } from "@/lib/jobs";

export async function GET() {
  return backendHealth();
}
