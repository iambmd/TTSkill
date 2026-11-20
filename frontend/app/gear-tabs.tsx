import Link from "next/link";

/** Switches between the two equipment pages. */
export function GearTabs({ active }: { active: "rubbers" | "pros" }) {
  const tab = (href: string, label: string, on: boolean) => (
    <Link
      href={href} aria-current={on ? "page" : undefined}
      className={`flex h-12 flex-1 items-center justify-center rounded-xl text-sm font-bold uppercase tracking-wide transition ${on ? "action-fill" : "text-white/70 hover:text-white"}`}
    >
      {label}
    </Link>
  );
  return (
    <nav className="surface-card flex gap-1 p-1">
      {tab("/rubbers", "Rubber finder", active === "rubbers")}
      {tab("/pros", "Pro setups", active === "pros")}
    </nav>
  );
}
