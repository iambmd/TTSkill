import { getSourceRally } from "@/lib/match-source";
import BreakdownForm from "./form";

export default async function BreakdownPage({ searchParams }: { searchParams: Promise<{ source?: string; rally?: string }> }) {
  const query = await searchParams;
  const source = typeof query.source === "string" ? query.source : undefined;
  const rally = typeof query.rally === "string" ? query.rally : undefined;
  const clip = await getSourceRally(source, rally);
  return <BreakdownForm sourceJob={source} rallyId={rally} clip={clip} />;
}
