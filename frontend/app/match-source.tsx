import Link from "next/link";

export function MatchSource({ job, form }: { job: string; form: "coach" | "breakdown" }) {
  return (
    <div className="surface-card space-y-2 p-4">
      <input type="hidden" name="source_job" value={job} />
      <p className="font-semibold">Using your uploaded match</p>
      <Link href={`/${form}`} className="inline-flex min-h-11 items-center text-sm font-semibold text-accent underline">
        Choose a different video
      </Link>
    </div>
  );
}
