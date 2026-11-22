import BreakdownForm from "./form";

export default async function BreakdownPage({ searchParams }: { searchParams: Promise<{ source?: string }> }) {
  const { source } = await searchParams;
  return <BreakdownForm sourceJob={typeof source === "string" ? source : undefined} />;
}
