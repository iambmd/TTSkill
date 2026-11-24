import { useTranslations } from "next-intl";
import { secondaryButtonClass } from "./ui";

export function OfflineNotice({ onRetry, checking = false, message }: {
  onRetry: () => void; checking?: boolean; message?: string;
}) {
  const t = useTranslations();
  return (
    <div className="surface-card flex flex-wrap items-center justify-between gap-3 p-4">
      <p role="alert" className="font-semibold">{message ?? t("offline.analysisSentence")}</p>
      <button type="button" disabled={checking} onClick={onRetry} className={secondaryButtonClass}>
        {checking ? t("common.checking") : t("common.retry")}
      </button>
    </div>
  );
}
