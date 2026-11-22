export const ANALYSIS_OFFLINE = "Our analysis server is offline right now, try again in a few minutes";

export class AnalysisOfflineError extends Error {
  constructor() { super(ANALYSIS_OFFLINE); }
}

export function unavailableStatus(status: number) {
  return status === 502 || status === 503 || status === 504 || (status >= 520 && status <= 530);
}

export async function checkAnalysisHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const res = await fetch("/api/health", { cache: "no-store", signal });
    return res.ok && (await res.json()).ok === true;
  } catch {
    return false;
  }
}
