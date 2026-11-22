import { ANALYSIS_OFFLINE } from "@/lib/analysis-status";
import { secondaryButtonClass } from "./ui";

export function OfflineNotice({ onRetry, checking = false }: { onRetry: () => void; checking?: boolean }) {
  return (
    <div className="surface-card flex flex-wrap items-center justify-between gap-3 p-4">
      <p role="alert" className="font-semibold">{ANALYSIS_OFFLINE}.</p>
      <button type="button" disabled={checking} onClick={onRetry} className={secondaryButtonClass}>
        {checking ? "Checking…" : "Retry"}
      </button>
    </div>
  );
}
