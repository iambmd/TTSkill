"use client";

import { useEffect, useId, useRef, useState } from "react";
import { CheckIcon, CloseIcon, UploadIcon } from "./ui";

const VIDEO_EXT = /\.(mov|mp4|m4v|webm|mkv|avi)$/i;

const fmtSize = (b: number) => (b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${(b / 1e6).toFixed(1)} MB`);
const fmtTime = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/**
 * Big upload button that turns into a preview of the chosen clip.
 * The file lives in a real <input type="file" name={name}>, so the parent form's FormData picks it up.
 */
export function VideoPicker({ name = "video", title, hint }: { name?: string; title: string; hint: string }) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [canPreview, setCanPreview] = useState(true);
  const [duration, setDuration] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);

  // Revoke each preview URL once it is replaced or the picker unmounts.
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);

  function pick(f: File | null) {
    setFile(f);
    setCanPreview(true);
    setDuration(null);
    setUrl(f ? URL.createObjectURL(f) : null);
  }

  function clear() {
    if (inputRef.current) inputRef.current.value = "";
    pick(null);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (!f || !(f.type.startsWith("video/") || VIDEO_EXT.test(f.name)) || !inputRef.current) return;
    const dt = new DataTransfer();
    dt.items.add(f);
    inputRef.current.files = dt.files;
    pick(f);
  }

  return (
    <div
      className="rounded-3xl has-[input:focus-visible]:ring-2 has-[input:focus-visible]:ring-white has-[input:focus-visible]:ring-offset-4 has-[input:focus-visible]:ring-offset-ink"
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false); }}
      onDrop={onDrop}
    >
      <input
        ref={inputRef} id={id} name={name} type="file" accept="video/*" className="sr-only"
        onChange={(e) => pick(e.target.files?.[0] ?? null)}
      />
      {!file ? (
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
      ) : (
        <div className={`overflow-hidden rounded-3xl border bg-black ${dragging ? "border-accent" : "border-line"}`}>
          {url && canPreview ? (
            <video
              key={url} src={`${url}#t=0.001`} controls playsInline preload="metadata"
              onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
              onError={() => setCanPreview(false)}
              className="block max-h-[60svh] w-full bg-black object-contain"
            />
          ) : (
            <div className="stripes flex aspect-video items-center justify-center px-6 text-center text-sm text-muted">
              This browser can&apos;t preview the file, but it will still upload.
            </div>
          )}
          <div className="flex items-center gap-3 border-t border-line bg-panel px-4 py-3">
            <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent text-black"><CheckIcon className="size-4" /></span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{file.name}</p>
              <p className="text-xs text-muted">
                {duration && Number.isFinite(duration) ? `${fmtTime(duration)} · ` : ""}{fmtSize(file.size)}
              </p>
            </div>
            <label htmlFor={id} className="cursor-pointer rounded-lg border border-line px-3 py-2 text-xs font-bold uppercase tracking-wide hover:border-white/30">
              Swap
            </label>
            <button type="button" onClick={clear} aria-label="Remove video" className="rounded-lg p-2 text-muted hover:bg-white/5 hover:text-white">
              <CloseIcon />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
