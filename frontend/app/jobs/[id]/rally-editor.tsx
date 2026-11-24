import Image from "next/image";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { AnalysisOfflineError, unavailableStatus } from "@/lib/analysis-status";
import { PUBLIC_API_URL, type RallyClip } from "@/lib/submit";
import { fmtDuration } from "@/lib/validate";
import { buttonBaseClass, DownloadIcon, FieldError, secondaryButtonClass } from "../../ui";

export function RallyEditor({ id, clips }: { id: string; clips: RallyClip[] }) {
  const t = useTranslations("rallies");
  const tAll = useTranslations();
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
    setAnnouncement(t("moved", { id: next[to].id, position: to + 1 }));
    restoreFocus(controlId(next[to], step < 0 ? "up" : "down"));
  }

  function remove(index: number) {
    const clip = selection[index];
    const next = selection.filter((_, i) => i !== index);
    setSelection(next);
    setDownload(null);
    setAnnouncement(t("removed", { id: clip.id }));
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
        throw new Error(t("exportFailed"));
      }
      const url = `${root}${data.url}`;
      setDownload(url);
      setAnnouncement(t("ready"));
      const link = document.createElement("a");
      link.href = url;
      link.download = "ttskill-highlights.mp4";
      link.click();
    } catch (err) {
      setError(err instanceof TypeError || err instanceof AnalysisOfflineError ? tAll("offline.analysis") : (err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="rallies-title" className="space-y-4">
      <h2 id="rallies-title" className="section-title text-2xl">{t("title")}</h2>
      <p className="text-sm text-muted">{t("hint")}</p>
      <p role="status" className="sr-only">{announcement}</p>
      {selection.length ? (
        <ol className="space-y-3">
          {selection.map((clip, index) => (
            <li key={clip.id} className="surface-card grid grid-cols-[minmax(0,6rem)_minmax(0,1fr)] gap-3 p-3 sm:grid-cols-[minmax(0,9rem)_minmax(0,1fr)]">
              <Image src={clip.thumbnailUrl} alt="" width={320} height={180} unoptimized
                className="video-frame aspect-video w-full object-contain" />
              <div className="min-w-0 space-y-1">
                <h3 className="font-bold">{t("rally", { id: clip.id })}</h3>
                <p className="text-sm text-muted">{t("rank", { id: clip.id, length: fmtDuration(Math.ceil(clip.end - clip.start)) })}</p>
                <p className="text-xs text-muted">{t("inMatch", { start: fmtDuration(clip.start), end: fmtDuration(clip.end) })}</p>
              </div>
              <div className="col-span-2 flex flex-wrap gap-2">
                <button id={controlId(clip, "up")} type="button" aria-disabled={busy || index === 0} onClick={() => move(index, -1)}
                  aria-label={t("moveUp", { id: clip.id })} className={`${secondaryButtonClass} aria-disabled:opacity-45`}>{t("up")}</button>
                <button id={controlId(clip, "down")} type="button" aria-disabled={busy || index === selection.length - 1} onClick={() => move(index, 1)}
                  aria-label={t("moveDown", { id: clip.id })} className={`${secondaryButtonClass} aria-disabled:opacity-45`}>{t("down")}</button>
                <button id={controlId(clip, "remove")} type="button" disabled={busy} onClick={() => remove(index)}
                  aria-label={t("removeLabel", { id: clip.id })} className={`${secondaryButtonClass} disabled:opacity-45`}>{t("remove")}</button>
                <a href={clip.clipUrl} download aria-label={t("downloadLabel", { id: clip.id })} className={secondaryButtonClass}>
                  <DownloadIcon /> {tAll("common.download")}
                </a>
                <Link href={`/coach?source=${id}&rally=${clip.id}`} aria-label={t("coachLabel", { id: clip.id })} className={secondaryButtonClass}>
                  {t("coach")}
                </Link>
              </div>
            </li>
          ))}
        </ol>
      ) : <p className="surface-card p-4">{t("none")}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" aria-disabled={busy || !selection.length} onClick={() => void exportSelection()}
          className={`${buttonBaseClass} min-h-12 text-xl`}>
          <DownloadIcon /> {busy ? t("preparing") : error ? t("retry") : t("downloadAll")}
        </button>
        <button id={resetId} type="button" disabled={busy} className={`${secondaryButtonClass} disabled:opacity-45`} onClick={() => {
          setSelection(clips);
          setDownload(null);
          setError(null);
          setAnnouncement(t("restored"));
        }}>{t("reset")}</button>
        {download && <a href={download} download className={secondaryButtonClass}>{t("again")}</a>}
      </div>
      <FieldError id="export-error">{error}</FieldError>
    </section>
  );
}
