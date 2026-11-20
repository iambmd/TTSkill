"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

const LINKS = [
  ["/", "Home"], ["/coach", "Coach"], ["/breakdown", "Breakdown"], ["/match", "Pro match"], ["/autocut", "Auto-Cut"],
  ["/rubbers", "Gear"],
] as const;
// The Gear link covers both equipment pages.
const GEAR = ["/rubbers", "/pros"];

export function Nav() {
  const path = usePathname();
  const bar = useRef<HTMLDivElement>(null);
  // On a narrow phone the active link can sit off-screen; scroll the bar so it shows.
  useEffect(() => {
    const el = bar.current?.querySelector<HTMLElement>('[aria-current="page"]');
    if (el && bar.current) bar.current.scrollLeft = el.offsetLeft - bar.current.clientWidth / 2 + el.clientWidth / 2;
  }, [path]);
  return (
    // Scrolls sideways on narrow phones instead of wrapping.
    <div ref={bar} className="site-nav-links relative -mr-4 flex min-w-0 gap-0.5 overflow-x-auto pr-4 [scrollbar-width:none] sm:mr-0 sm:gap-1 sm:pr-0">
      {LINKS.map(([href, label]) => {
        const active = href === "/" ? path === "/" : href === "/rubbers" ? GEAR.some((g) => path.startsWith(g)) : path.startsWith(href);
        return (
          <Link
            key={href} href={href} aria-current={active ? "page" : undefined}
            className={`shrink-0 rounded-full px-2 py-2 text-[0.7rem] sm:px-3.5 sm:text-sm font-bold uppercase tracking-wide transition ${active ? "bg-accent text-black" : "text-white/70 hover:bg-white/5 hover:text-white"}`}
          >
            {label}
          </Link>
        );
      })}
    </div>
  );
}
