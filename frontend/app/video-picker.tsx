"use client";

import { useEffect, useId, useRef, useState } from "react";
import { PlayerPicker } from "./player-picker";
import { LIMITS, type Kind, fileProblem, fmtDuration, mediaProblem, minutes } from "@/lib/validate";
import { linkProblem, youtubeId } from "@/lib/youtube";
import { CheckIcon, CloseIcon, LinkIcon, PlayIcon, UploadIcon, inputClass, labelClass } from "./ui";

const fmtSize = (b: number) => (b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${(b / 1e6).toFixed(1)} MB`);
type Meta = { duration: number; width: number; height: number };

/**
 * Big upload button that turns into a preview of the chosen clip, with a "paste a link" field under it.
 * The file lives in a real <input type="file" name={name}> and the link in <input name={linkName}>,
 * so the parent form's FormData picks up whichever one is set. A chosen file wins over a link.
 * The file (type, size, then length and resolution once the preview loads) and the link are
 * checked as they change; the problem is shown here and passed to `onProblem` so the form can
 * disable its submit button.
 */
export function VideoPicker({ name = "video", linkName = "url", title, hint, kind, onProblem, findPlayer = false, onlyMeOption = false }: {
  name?: string;
  linkName?: string;
  title: string;
  hint: string;
  /** Which page this is, for the link length limit in shared/limits.json. */
  kind: Kind;
  onProblem?: (problem: string | null) => void;
  /** Ask "Which one is you?" when the video shows more than one player (Breakdown, Match, Coach). */
  findPlayer?: boolean;
  /** Offer "Only me in the video": skip finding players and follow whoever plays the most (Coach, Breakdown). */
  onlyMeOption?: boolean;
}) {
  const id = useId();
  const linkInputId = useId();
  const fileErrorId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [canPreview, setCanPreview] = useState(true);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [dragging, setDragging] = useState(false);
  const [link, setLink] = useState("");
  const ytId = youtubeId(link);
  const linkError = !file && link.trim() ? linkProblem(link) : null;
  const fileError = file ? fileProblem(file) ?? (meta ? mediaProblem(meta) : null) : null;
  const [playerProblem, setPlayerProblem] = useState<string | null>(null);
  const [onlyMe, setOnlyMe] = useState(false);
  const onlyMeId = useId();
  const problem = fileError ?? linkError ?? (findPlayer && !onlyMe ? playerProblem : null);

  // Revoke each preview URL once it is replaced or the picker unmounts.
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  useEffect(() => { onProblem?.(problem); }, [problem, onProblem]);

  function pick(f: File | null) {
    setFile(f);
    setCanPreview(true);
    setMeta(null);
    setUrl(f ? URL.createObjectURL(f) : null);
  }

  function clear() {
    if (inputRef.current) inputRef.current.value = "";
    pick(null);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    // Any file is taken, so a wrong one gets a clear message instead of being silently ignored.
    const f = e.dataTransfer.files[0];
    if (!f || !inputRef.current) return;
    const dt = new DataTransfer();
    dt.items.add(f);
    inputRef.current.files = dt.files;
    pick(f);
  }

  return (
    <div className="space-y-4">
      <div
        className="rounded-3xl has-[input:focus-visible]:ring-2 has-[input:focus-visible]:ring-white has-[input:focus-visible]:ring-offset-4 has-[input:focus-visible]:ring-offset-ink"
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false); }}
        onDrop={onDrop}
      >
        <input
          ref={inputRef} id={id} name={name} type="file" accept="video/*" className="sr-only"
          aria-invalid={!!fileError} aria-describedby={fileError ? fileErrorId : undefined}
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <div className={`overflow-hidden rounded-3xl border bg-black ${dragging ? "border-accent" : fileError ? "border-red-500/50" : "border-line"}`}>
            {url && canPreview ? (
              <video
                key={url} src={`${url}#t=0.001`} controls playsInline preload="metadata"
                onLoadedMetadata={(e) => {
                  // videoWidth is 0 when the browser can't decode the picture (e.g. HEVC on some desktops):
                  // that's "unknown", not "no video", so the server makes that call.
                  const v = e.currentTarget;
                  setMeta({ duration: v.duration, width: v.videoWidth, height: v.videoHeight });
                }}
                onError={() => setCanPreview(false)}
                className="block max-h-[60svh] w-full bg-black object-contain"
              />
            ) : (
              <div className="stripes flex aspect-video items-center justify-center px-6 text-center text-sm text-muted">
                This browser can&apos;t preview the file, but it will still upload.
              </div>
            )}
            <div className="flex items-center gap-3 border-t border-line bg-panel px-4 py-3">
              {fileError ? (
                <span className="grid size-8 shrink-0 place-items-center rounded-full bg-red-500/80 text-neutral-50"><CloseIcon className="size-4" /></span>
              ) : (
                <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent text-black"><CheckIcon className="size-4" /></span>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{file.name}</p>
                <p className="text-xs text-muted">
                  {meta && Number.isFinite(meta.duration) ? `${fmtDuration(meta.duration)} · ` : ""}{fmtSize(file.size)}
                </p>
              </div>
              <label htmlFor={id} className="cursor-pointer rounded-lg border border-line px-3 py-2 text-xs font-bold uppercase tracking-wide hover:border-white/30">
                Swap
              </label>
              <button type="button" onClick={clear} aria-label="Remove video" className="rounded-lg p-2 text-muted hover:bg-white/5 hover:text-white">
                <CloseIcon />
              </button>
            </div>
            {fileError && (
              <p id={fileErrorId} role="alert" className="border-t border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                {fileError}
              </p>
            )}
          </div>
        ) : ytId ? (
          <div className={`overflow-hidden rounded-3xl border bg-black ${dragging ? "border-accent" : "border-line"}`}>
            <div className="relative aspect-video">
              {/* YouTube's own thumbnail; nothing is downloaded until the form is sent. */}
              <img src={`https://i.ytimg.com/vi/${ytId}/hqdefault.jpg`} alt="" className="size-full object-cover opacity-80" />
              <span aria-hidden className="absolute inset-0 grid place-items-center">
                <span className="grid size-16 place-items-center rounded-full bg-accent text-black shadow-[0_0_30px_rgb(255_107_44/0.6)]">
                  <PlayIcon className="size-7" />
                </span>
              </span>
            </div>
            <div className="flex items-center gap-3 border-t border-line bg-panel px-4 py-3">
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent text-black"><CheckIcon className="size-4" /></span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">YouTube video</p>
                <p className="text-xs text-muted">We fetch it at up to 720p when you submit.</p>
              </div>
              <label htmlFor={id} className="cursor-pointer rounded-lg border border-line px-3 py-2 text-xs font-bold uppercase tracking-wide hover:border-white/30">
                Upload instead
              </label>
            </div>
          </div>
        ) : (
          <label
            htmlFor={id}
            className={`hatch relative flex min-h-64 w-full cursor-pointer flex-col items-center justify-center gap-4 overflow-hidden rounded-3xl bg-accent px-6 py-10 text-center text-black shadow-[0_24px_60px_-24px_rgb(255_107_44/0.7)] transition hover:bg-accent-hot active:scale-[.99] ${dragging ? "scale-[1.01] ring-4 ring-white" : ""}`}
          >
            <span className="grid size-20 place-items-center rounded-full bg-black text-accent">
              <UploadIcon className="size-9" />
            </span>
            <span className="headline text-4xl sm:text-5xl">{title}</span>
            <span className="max-w-xs text-sm font-medium text-black/70">
              {hint}<span className="hidden sm:inline"> Or drop a file here.</span>
            </span>
          </label>
        )}
      </div>
      {onlyMeOption && (
        <label htmlFor={onlyMeId} className="flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border border-line bg-panel px-4 py-2">
          <input
            id={onlyMeId} type="checkbox" name="only_me" value="1" checked={onlyMe}
            onChange={(e) => setOnlyMe(e.target.checked)} className="size-5 shrink-0 accent-accent"
          />
          <span className="text-sm">
            <span className="font-semibold">Only me in the video</span>
            <span className="block text-xs text-muted">Skip choosing a player: we follow whoever plays the most, at the table.</span>
          </span>
        </label>
      )}
      {findPlayer && !onlyMe && kind !== "autocut" && !fileError && !linkError && (
        <PlayerPicker
          previewUrl={file && meta ? url : null} duration={file && meta ? meta.duration : null}
          file={file} unreadable={!!file && !canPreview}
          link={!file && ytId ? link.trim() : null} kind={kind} onProblem={setPlayerProblem}
        />
      )}
      {!file && (
        <div>
          <label className={labelClass} htmlFor={linkInputId}>Or paste a video link</label>
          <div className="relative">
            <LinkIcon className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted" />
            <input
              id={linkInputId} name={linkName} type="url" inputMode="url" autoComplete="off" spellCheck={false}
              placeholder="youtube.com/shorts/…" value={link} onChange={(e) => setLink(e.target.value)}
              aria-invalid={!!linkError} aria-describedby={`${linkInputId}-hint`}
              className={`${inputClass} pr-12 pl-12 ${linkError ? "border-red-500/50" : ""}`}
            />
            {link && (
              <button
                type="button" onClick={() => setLink("")} aria-label="Clear link"
                className="absolute top-1/2 right-2 -translate-y-1/2 rounded-lg p-2 text-muted hover:bg-white/5 hover:text-white"
              >
                <CloseIcon />
              </button>
            )}
          </div>
          <p
            id={`${linkInputId}-hint`} role={linkError ? "alert" : undefined}
            className={`mt-2 ${linkError ? "text-sm text-red-200" : "text-xs text-muted"}`}
          >
            {linkError ?? `YouTube videos and Shorts, up to ${minutes(LIMITS.link_max_seconds[kind])}.`}
          </p>
        </div>
      )}
    </div>
  );
}
