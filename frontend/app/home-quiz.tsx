"use client";

import Link from "next/link";
import { useState } from "react";
import type { Level, Style } from "@/lib/rubbers";

export function GearQuiz({ results }: { results: Record<Style, Record<Level, string | undefined>> }) {
  const [style, setStyle] = useState<Style>();
  const [level, setLevel] = useState<Level>();
  const pick = style && level ? results[style][level] : undefined;

  return (
    <section aria-labelledby="home-quiz-title" className="home-quiz surface-card">
      <div className="home-quiz-controls">
        <h3 id="home-quiz-title" className="section-title text-xl">Find your rubber</h3>
        <fieldset className="home-quiz-options">
          <legend>Play style</legend>
          {(["spin", "speed"] as const).map((value) => (
            <button key={value} type="button" aria-pressed={style === value} onClick={() => setStyle(value)}>{value}</button>
          ))}
        </fieldset>
        <fieldset className="home-quiz-options">
          <legend>Level</legend>
          {(["beginner", "intermediate", "advanced"] as const).map((value) => (
            <button key={value} type="button" aria-pressed={level === value} onClick={() => setLevel(value)}>{value}</button>
          ))}
        </fieldset>
      </div>
      {style && level && (
        <div className="home-quiz-result">
          <p role="status">{pick ? <>Your pick <strong className="text-accent">{pick}</strong></> : "See the closest picks in Rubber Finder."}</p>
          <Link href={`/rubbers?style=${style}&level=${level}`} prefetch={false} className="home-text-link">Open Rubber Finder</Link>
        </div>
      )}
    </section>
  );
}
