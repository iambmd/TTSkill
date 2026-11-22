import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { ANALYSIS_OFFLINE, AnalysisOfflineError, unavailableStatus } from "@/lib/analysis-status";
import { PUBLIC_API_URL, type RallyClip } from "@/lib/submit";
import { fmtDuration } from "@/lib/validate";
import { buttonBaseClass, DownloadIcon, FieldError, secondaryButtonClass } from "../../ui";

export function RallyEditor({ id, clips }: { id: string; clips: RallyClip[] }) {
  const [selection, setSelection] = useState(clips);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [download, setDownload] = useState<string | null>(null);
  const root = PUBLIC_API_URL || "/api";
  const resetId = `reset-rallies-${id}`;
  const controlId = (clip: RallyClip, action: string) => `rally-${id}-${clip.id}-${action}`;

  function restoreFocus(target: string) {
    // React may move or unmount the focused button when it updates the list.
    requestAnimationFrame(() => document.getElementById(target)?.focus());
  }

  function move(index: number, step: -1 | 1) {
    const next = [...selection];
    const to = index + step;
    if (busy || to < 0 || to >= next.length) return;
    [next[index], next[to]] = [next[to], next[index]];
    setSelection(next);
    setDownload(null);
    setAnnouncement(`Rally ${next[to].id} moved to position ${to + 1}.`);
    restoreFocus(controlId(next[to], step < 0 ? "up" : "down"));
  }

  function remove(index: number) {
    const clip = selection[index];
    const next = selection.filter((_, i) => i !== index);
    setSelection(next);
    setDownload(null);
    setAnnouncement(`Rally ${clip.id} removed.`);
    const neighbor = next[index] ?? next[index - 1];
    restoreFocus(neighbor ? controlId(neighbor, "remove") : resetId);
  }

  async function exportSelection() {
    if (busy || !selection.length) return;
    setBusy(true);
    setError(null);
    setDownload(null);
    try {
      const response = await fetch(`${root}/jobs/${id}/exports`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ rallies: selection.map((clip) => clip.id) }),
      });
      if (unavailableStatus(response.status)) throw new AnalysisOfflineError();
      const data = await response.json().catch(() => ({}));
      if (!response.ok || typeof data.url !== "string") {
        throw new Error("Couldn't make this download. Check the selection and try again.");
      }
      const url = `${root}${data.url}`;
      setDownload(url);
      setAnnouncement("Your highlights are ready to download.");
      const link = document.createElement("a");
      link.href = url;
      link.download = "ttskill-highlights.mp4";
      link.click();
    } catch (err) {
      setError(err instanceof TypeError ? ANALYSIS_OFFLINE : (err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="rallies-title" className="space-y-4">
      <h2 id="rallies-title" className="section-title text-2xl">Your rallies</h2>
      <p className="text-sm text-muted">Move or remove rallies to choose what goes in your download.</p>
      <p role="status" className="sr-only">{announcement}</p>
      {selection.length ? (
        <ol className="space-y-3">
          {selection.map((clip, index) => (
            <li key={clip.id} className="surface-card grid grid-cols-[minmax(0,6rem)_minmax(0,1fr)] gap-3 p-3 sm:grid-cols-[minmax(0,9rem)_minmax(0,1fr)]">
              <Image src={clip.thumbnailUrl} alt="" width={320} height={180} unoptimized
                className="video-frame aspect-video w-full object-contain" />
              <div className="min-w-0 space-y-1">
                <h3 className="font-bold">Rally {clip.id}</h3>
                <p className="text-sm text-muted">Rank {clip.id} · {fmtDuration(Math.ceil(clip.end - clip.start))}</p>
                <p className="text-xs text-muted">{fmtDuration(clip.start)} – {fmtDuration(clip.end)} in match</p>
              </div>
              <div className="col-span-2 flex flex-wrap gap-2">
                <button id={controlId(clip, "up")} type="button" aria-disabled={busy || index === 0} onClick={() => move(index, -1)}
                  aria-label={`Move rally ${clip.id} up`} className={`${secondaryButtonClass} aria-disabled:opacity-45`}>Up</button>
                <button id={controlId(clip, "down")} type="button" aria-disabled={busy || index === selection.length - 1} onClick={() => move(index, 1)}
                  aria-label={`Move rally ${clip.id} down`} className={`${secondaryButtonClass} aria-disabled:opacity-45`}>Down</button>
                <button id={controlId(clip, "remove")} type="button" disabled={busy} onClick={() => remove(index)}
                  aria-label={`Remove rally ${clip.id}`} className={`${secondaryButtonClass} disabled:opacity-45`}>Remove</button>
                <a href={clip.clipUrl} download aria-label={`Download rally ${clip.id}`} className={secondaryButtonClass}>
                  <DownloadIcon /> Download
                </a>
                <Link href={`/coach?source=${id}&rally=${clip.id}`} aria-label={`Coach this stroke from rally ${clip.id}`} className={secondaryButtonClass}>
                  Coach this stroke
                </Link>
              </div>
            </li>
          ))}
        </ol>
      ) : <p className="surface-card p-4">No rallies selected. Reset the selection to bring them back.</p>}
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" aria-disabled={busy || !selection.length} onClick={() => void exportSelection()}
          className={`${buttonBaseClass} min-h-12 text-xl`}>
          <DownloadIcon /> {busy ? "Preparing your download…" : error ? "Retry download" : "Download highlights"}
        </button>
        <button id={resetId} type="button" disabled={busy} className={`${secondaryButtonClass} disabled:opacity-45`} onClick={() => {
          setSelection(clips);
          setDownload(null);
          setError(null);
          setAnnouncement("Original rally selection restored.");
        }}>Reset selection</button>
        {download && <a href={download} download className={secondaryButtonClass}>Download again</a>}
      </div>
      <FieldError id="export-error">{error}</FieldError>
    </section>
  );
}
