"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [["/breakdown", "Breakdown"], ["/match", "Pro match"], ["/autocut", "Auto-Cut"]] as const;

export function Nav() {
  const path = usePathname();
  return (
    <div className="flex gap-0.5 sm:gap-1">
      {LINKS.map(([href, label]) => {
        const active = path.startsWith(href);
        return (
          <Link
            key={href} href={href} aria-current={active ? "page" : undefined}
            className={`rounded-full px-2.5 py-2 text-xs sm:px-3.5 sm:text-sm font-bold uppercase tracking-wide transition ${active ? "bg-accent text-black" : "text-white/70 hover:bg-white/5 hover:text-white"}`}
          >
            {label}
          </Link>
        );
      })}
    </div>
  );
}
