export const inputClass =
  "field-input w-full border px-4 py-3 text-base focus:ring-2 focus:ring-accent/30";
export const labelTextClass = "text-xs font-bold uppercase tracking-[0.14em] text-muted";
export const labelClass = `mb-2 block ${labelTextClass}`;
/** Primary button without a size, for callers that need a smaller one. */
export const buttonBaseClass =
  "primary-button headline relative inline-flex items-center justify-center gap-2 overflow-hidden px-6 transition motion-safe:active:scale-[.98] disabled:cursor-wait";
export const buttonClass = `${buttonBaseClass} h-14 text-2xl`;
export const secondaryButtonClass =
  "inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-line bg-panel px-4 text-sm font-bold uppercase tracking-wide transition hover:border-white/30 motion-safe:active:scale-[.98]";

export function PageIntro({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="page-intro space-y-3">
      <p className="eyebrow">{eyebrow}</p>
      <h1 className="headline text-5xl sm:text-6xl">{title}</h1>
      <p className="text-muted">{body}</p>
    </div>
  );
}

type Option<T extends string> = { value: T; label: string; sub?: string };

/** Radio buttons drawn as big tap targets. Pass `value` + `onChange` to control it, or `defaultValue` to leave it to the form. */
export function RadioTiles<T extends string>({ name, options, value, defaultValue, onChange, className = "" }: {
  name: string;
  options: readonly Option<T>[];
  value?: T;
  defaultValue?: T;
  onChange?: (v: T) => void;
  className?: string;
}) {
  return (
    <div className={`grid gap-2 ${className}`}>
      {options.map((o) => (
        <label key={o.value} className="cursor-pointer">
          <input
            type="radio" name={name} value={o.value} className="peer sr-only"
            {...(value !== undefined
              ? { checked: value === o.value, onChange: () => onChange?.(o.value) }
              : { defaultChecked: o.value === defaultValue })}
          />
          <span className="flex h-full min-h-12 flex-col justify-center rounded-xl border border-line bg-panel px-4 py-2.5 transition peer-checked:border-accent peer-checked:bg-accent/10 peer-focus-visible:ring-2 peer-focus-visible:ring-accent">
            <span className="font-semibold capitalize">{o.label}</span>
            {o.sub && <span className="text-xs text-muted">{o.sub}</span>}
          </span>
        </label>
      ))}
    </div>
  );
}

/** Submit button that sticks to the bottom of the screen on long forms and fills up as the upload goes. */
export function SubmitBar({ label, progress, error, startingLabel = "Starting...", blocked = false, blockedHint }: {
  label: string;
  progress: number | null;
  error: string | null;
  /** Shown once the upload is done and the server is still answering, e.g. while it checks a link. */
  startingLabel?: string;
  /** A field has an error (shown next to it), so there is nothing to send yet. */
  blocked?: boolean;
  blockedHint?: string;
}) {
  const busy = progress !== null;
  const waitingForInput = blocked && !busy;
  const pct = Math.round((progress ?? 0) * 100);
  const text = !busy ? label : pct === 0 ? "Uploading..." : pct < 100 ? `Uploading ${pct}%` : startingLabel;
  return (
    <div className="sticky bottom-0 z-10 -mx-4 bg-linear-to-t from-ink from-60% to-transparent px-4 pt-8 pb-[max(1rem,env(safe-area-inset-bottom))]">
      {error && (
        <p role="alert" className="mb-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p>
      )}
      <button
        type="submit" disabled={busy || blocked}
        className={`${buttonClass} w-full ${waitingForInput ? "cursor-not-allowed" : ""}`}
      >
        {busy && <span aria-hidden className="absolute inset-y-0 left-0 bg-accent/15 transition-[width] duration-300" style={{ width: `${pct}%` }} />}
        <span className="relative" aria-live="polite">{text}</span>
      </button>
      {waitingForInput && blockedHint && <p className="mt-2 text-center text-sm text-muted">{blockedHint}</p>}
    </div>
  );
}

/** Inline error under a field. Give the field aria-invalid and aria-describedby={id}. */
export function FieldError({ id, children }: { id: string; children: React.ReactNode }) {
  if (!children) return null;
  return <p id={id} role="alert" className="mt-2 text-sm text-red-200">{children}</p>;
}

/** A heads-up that doesn't stop anything, e.g. a pro whose backhand you shouldn't copy. */
export function Warning({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <p role="note" className={`flex gap-2.5 notice rounded-xl border px-3 py-2.5 text-sm ${className}`}>
      <WarningIcon className="mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

type IconProps = { className?: string };
const stroke = {
  viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2.2,
  strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true,
} as const;

export const UploadIcon = ({ className = "size-6" }: IconProps) => (
  <svg {...stroke} className={className}><path d="M12 16V4M6 10l6-6 6 6M4 20h16" /></svg>
);
export const DownloadIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...stroke} className={className}><path d="M12 4v12M6 10l6 6 6-6M4 20h16" /></svg>
);
export const ArrowIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...stroke} className={className}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
);
export const CheckIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...stroke} className={className}><path d="M5 12.5l4.5 4.5L19 7" /></svg>
);
export const CloseIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...stroke} className={className}><path d="M6 6l12 12M18 6L6 18" /></svg>
);
export const PlayIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...stroke} className={className}><path d="M8 5v14l11-7z" fill="currentColor" /></svg>
);
export const PauseIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...stroke} className={className}><path d="M8 5v14M16 5v14" /></svg>
);
export const LinkIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...stroke} className={className}><path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1" /></svg>
);
export const ChevronIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...stroke} className={className}><path d="M6 9l6 6 6-6" /></svg>
);
export const WarningIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...stroke} className={className}><path d="M12 4 2.5 20h19L12 4zM12 10v4.5M12 17.5v.01" /></svg>
);

/** The stroke family used to style the existing result labels. */
export function strokeFamily(stroke?: string | null) {
  return stroke?.match(/^(forehand|backhand)(?:\b|_)/i)?.[1].toLowerCase();
}
