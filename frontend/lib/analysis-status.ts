import { english } from "./english";

export const ANALYSIS_OFFLINE = english("offline")("analysis");

/** The analysis server is down. Pages show their own translated notice; the message is the English default. */
export class AnalysisOfflineError extends Error {
  constructor(message = ANALYSIS_OFFLINE) { super(message); }
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
