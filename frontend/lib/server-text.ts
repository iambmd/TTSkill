/** Backend text in the reader's language. The backend sends English plus a reference to the
 * same message in messages/*.json ({key, args}; an argument can be a reference too, like a
 * field label or "10 minutes"): job progress (messageRef), failures (failureRef), warnings
 * (warningRef) and 422 answers (detailRef). See backend/messages.py. */

export type ServerRef = { key: string; args?: Record<string, unknown> };

/** A translator over the whole catalogue: useTranslations() or lib/messages translator(locale, ""). */
export type Catalog = { (key: string, values?: Record<string, string | number>): string; has: (key: string) => boolean };

const isRef = (v: unknown): v is ServerRef =>
  !!v && typeof v === "object" && typeof (v as ServerRef).key === "string";

/** The reference's text, or null when there is none or the catalogue doesn't know the key
 * (an older or newer backend): the caller then shows the English it got. */
export function serverText(ref: unknown, t: Catalog): string | null {
  if (!isRef(ref) || !t.has(ref.key)) return null;
  const values: Record<string, string | number> = {};
  for (const [name, value] of Object.entries(ref.args ?? {})) {
    if (isRef(value)) {
      const text = serverText(value, t);
      if (text === null) return null;
      values[name] = text;
    } else {
      values[name] = typeof value === "number" ? value : String(value ?? "");
    }
  }
  try {
    return t(ref.key, values);
  } catch {
    return null;
  }
}

/** A job's text field (message, failureHint, warning) in the reader's language. */
export function jobText(text: string | null | undefined, ref: unknown, t: Catalog): string | undefined {
  return serverText(ref, t) ?? text ?? undefined;
}

/** A failed request's message: its reference translated, else our route's {error} or FastAPI's {detail}. */
export function errorText(data: { error?: unknown; detail?: unknown; detailRef?: unknown }, t: Catalog | undefined,
  fallback: string): string {
  const translated = t ? serverText(data.detailRef, t) : null;
  return translated ?? (typeof data.detail === "string" ? data.detail : typeof data.error === "string" ? data.error : fallback);
}
