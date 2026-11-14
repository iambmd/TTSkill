"use client";

import { use, useEffect, useState } from "react";
import type { Breakdown, Job } from "@/lib/submit";

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

function BreakdownCard({ b }: { b: Breakdown }) {
  const facts: [string, string][] = [
    ["Grip", b.grip], ["Stance", b.stance], ["Swing path", b.swing_path],
    ["Contact point", b.contact_point], ["Follow-through", b.follow_through],
  ];
  return (
    <div className="space-y-4 rounded-xl border border-white/10 bg-white/5 p-5">
      <h2 className="text-xl font-bold">{b.headline}</h2>
      <ol className="space-y-3">
        {b.steps.map((s, i) => (
          <li key={i}>
            <p className="font-semibold"><span className="text-accent">{i + 1}.</span> {s.title}</p>
            {s.lines.map((l) => <p key={l} className="text-sm text-white/70">{l}</p>)}
          </li>
        ))}
      </ol>
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        {facts.map(([k, v]) => (
          <div key={k}><dt className="text-white/50">{k}</dt><dd>{v}</dd></div>
        ))}
      </dl>
    </div>
  );
}

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      const res = await fetch(`/api/jobs/${id}`);
      const data = await res.json();
      if (!res.ok) return setError(data.error ?? "Job not found");
      setJob(data);
      if (data.status === "queued" || data.status === "running") timer = setTimeout(poll, 1500);
    }
    poll();
    return () => clearTimeout(timer);
  }, [id]);

  if (error) return <p className="text-red-400">{error}</p>;
  if (!job) return <p className="text-white/70">Loading...</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold capitalize">{job.kind} job</h1>
      <div className="space-y-2">
        <div className="flex justify-between text-sm"><span className="capitalize">{job.status}</span><span>{Math.round(job.progress * 100)}%</span></div>
        <div className="h-2 rounded-full bg-white/10"><div className="h-2 rounded-full bg-accent" style={{ width: `${job.progress * 100}%` }} /></div>
        {job.message && <p className="text-sm text-white/70">{job.message}</p>}
      </div>
      {job.resultUrl && (
        <div className="space-y-3">
          <video src={job.resultUrl} controls playsInline
            className={`rounded-xl ${job.kind === "breakdown" ? "mx-auto max-h-[80vh]" : "w-full"}`} />
          <a href={job.resultUrl} download className="text-accent underline">Download</a>
        </div>
      )}
      {job.breakdown && <BreakdownCard b={job.breakdown} />}
      {job.rallies && job.rallies.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead className="text-white/50"><tr><th>#</th><th>Start</th><th>End</th><th>Shots</th></tr></thead>
          <tbody>
            {job.rallies.map((r, i) => (
              <tr key={i} className="border-t border-white/10">
                <td className="py-1">{i + 1}</td><td>{fmt(r.start)}</td><td>{fmt(r.end)}</td><td>{r.shots}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <pre className="overflow-x-auto rounded-lg bg-white/5 p-4 text-xs text-white/70">{JSON.stringify(job.params, null, 2)}</pre>
    </div>
  );
}
