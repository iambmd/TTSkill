"use client";

import { use, useEffect, useState } from "react";
import type { Job } from "@/lib/submit";

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
          <video src={job.resultUrl} controls className="w-full rounded-xl" />
          <a href={job.resultUrl} download className="text-accent underline">Download</a>
        </div>
      )}
      <pre className="overflow-x-auto rounded-lg bg-white/5 p-4 text-xs text-white/70">{JSON.stringify(job.params, null, 2)}</pre>
    </div>
  );
}
