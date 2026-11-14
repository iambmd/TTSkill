import Link from "next/link";

const features = [
  {
    href: "/breakdown",
    title: "Technique Breakdown",
    body: "Upload a clip of your favorite player, or describe their training, pick a stroke, and get a step-by-step coaching video.",
  },
  {
    href: "/autocut",
    title: "Match Auto-Cut",
    body: "Upload your match. We hear every ball contact, find the rallies, and cut the full match or your longest-rally highlights.",
  },
];

export default function Home() {
  return (
    <div className="space-y-10">
      <section className="space-y-3">
        <h1 className="text-4xl font-bold tracking-tight">
          Learn the stroke. <span className="text-accent">Keep the rally.</span>
        </h1>
        <p className="text-white/70">AI tools for amateur table tennis players and coaches.</p>
      </section>
      <section className="grid gap-4 sm:grid-cols-2">
        {features.map((f) => (
          <Link key={f.href} href={f.href} className="rounded-xl border border-white/10 bg-white/5 p-5 hover:border-accent">
            <h2 className="mb-2 font-semibold">{f.title}</h2>
            <p className="text-sm text-white/70">{f.body}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
