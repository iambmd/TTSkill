import CoachForm from "./form";

export default async function CoachPage({ searchParams }: { searchParams: Promise<{ source?: string }> }) {
  const { source } = await searchParams;
  return <CoachForm sourceJob={typeof source === "string" ? source : undefined} />;
}
