/** A small Markdown renderer for the coach's notes: paragraphs, headings, numbered and bullet
 * lists, **bold**, *italic* and `code`. Everything renders as React text (no HTML is parsed), and
 * links show their text only: the notes never link anywhere. Underscores stay literal, so stroke
 * keys like forehand_topspin never turn into italics. */
import type { ReactNode } from "react";

type Block =
  | { type: "h"; text: string }
  | { type: "p"; lines: string[] }
  | { type: "ol"; start: number; items: string[] }
  | { type: "ul"; items: string[] };

export function parseBlocks(md: string): Block[] {
  const out: Block[] = [];
  let cur: Block | null = null;
  for (const raw of md.replace(/\r\n?/g, "\n").split("\n")) {
    const line = raw.trim();
    let m: RegExpExecArray | null;
    if (!line) {
      cur = null;
    } else if ((m = /^#{1,6}\s+(.*)$/.exec(line))) {
      out.push({ type: "h", text: m[1] });
      cur = null;
    } else if ((m = /^(\d{1,3})[.)]\s+(.*)$/.exec(line))) {
      if (cur?.type !== "ol") out.push((cur = { type: "ol", start: Number(m[1]), items: [] }));
      cur.items.push(m[2]);
    } else if ((m = /^[-*+•]\s+(.*)$/.exec(line))) {
      if (cur?.type !== "ul") out.push((cur = { type: "ul", items: [] }));
      cur.items.push(m[1]);
    } else if ((cur?.type === "ol" || cur?.type === "ul") && /^\s/.test(raw)) {
      cur.items[cur.items.length - 1] += ` ${line}`;   // an indented line continues the item
    } else {
      if (cur?.type !== "p") out.push((cur = { type: "p", lines: [] }));
      cur.lines.push(line);
    }
  }
  return out;
}

const INLINE = /\*\*(.+?)\*\*|`([^`]+)`|\*(\S(?:.*?\S)?)\*|\[([^\]]+)\]\([^)]*\)/g;

export function Inline({ text }: { text: string }) {
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    const i = m.index ?? 0;
    if (i > last) out.push(text.slice(last, i));
    const key = out.length;
    const [, bold, code, em, link] = m;
    if (bold) out.push(<strong key={key} className="font-bold text-fg"><Inline text={bold} /></strong>);
    else if (code) out.push(<code key={key} className="rounded bg-white/10 px-1 font-mono text-[0.9em]">{code}</code>);
    else if (em) out.push(<em key={key}><Inline text={em} /></em>);
    else out.push(link);
    last = i + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return <>{out}</>;
}

export function Markdown({ text, className = "" }: { text: string; className?: string }) {
  return (
    // overflow-wrap:anywhere: a long unbroken token wraps instead of widening the page
    <div className={`space-y-3 leading-relaxed [overflow-wrap:anywhere] ${className}`}>
      {parseBlocks(text).map((b, i) => {
        if (b.type === "h") return <h3 key={i} className="pt-1 font-bold text-fg"><Inline text={b.text} /></h3>;
        if (b.type === "p") {
          return (
            <p key={i}>
              {b.lines.map((l, j) => <span key={j}>{j > 0 && <br />}<Inline text={l} /></span>)}
            </p>
          );
        }
        const items = b.items.map((it, j) => <li key={j} className="pl-1"><Inline text={it} /></li>);
        return b.type === "ol" ? (
          <ol key={i} start={b.start} className="list-decimal space-y-2 pl-6 marker:font-bold marker:text-accent">{items}</ol>
        ) : (
          <ul key={i} className="list-disc space-y-2 pl-6 marker:text-accent">{items}</ul>
        );
      })}
    </div>
  );
}
