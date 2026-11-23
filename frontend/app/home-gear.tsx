import Link from "next/link";
import { rubberByName } from "@/lib/rubbers";
import { GearQuiz } from "./home-quiz";
import { RubberAffiliateDisclosure, RubberBuyMenu } from "./rubber-buy-menu";
import { ChevronIcon } from "./ui";

const featured = [
  { name: "Nittaku Fastarc G-1", tags: ["Spin", "Control"] },
  { name: "Yasaka Rakza 7", tags: ["Spin", "Speed"] },
  { name: "Butterfly Tenergy 05", tags: ["Spin", "Speed"] },
  { name: "DHS NEO Hurricane 3", tags: ["Spin", "Control"] },
];

export function HomeGear() {
  return (
    <section aria-labelledby="home-gear-title" className="home-section">
      <div className="home-section-heading">
        <h2 id="home-gear-title" className="section-title">Gear picks</h2>
        <Link href="/rubbers" prefetch={false} className="home-text-link">Rubber Finder <ChevronIcon className="size-4 -rotate-90" /></Link>
      </div>
      <ul className="home-gear-rail" aria-label="Featured rubbers">
        {featured.map(({ name, tags }, index) => {
          const rubber = rubberByName(name);
          if (!rubber) return null;
          return (
            <li key={name} className="home-gear-card surface-card home-lift">
              <div className="home-gear-detail">
                <span aria-hidden className="home-rubber-sheet" data-charcoal={index % 2 === 1 || undefined} />
                <div className="min-w-0">
                  <h3 className="section-title text-lg">{rubber.name}</h3>
                  <p className="mt-1 text-sm text-muted">{rubber.brand}</p>
                  <ul aria-label="Play style" className="mt-2 flex flex-wrap gap-1">
                    {tags.map((tag) => <li key={tag} className="home-gear-tag">{tag}</li>)}
                  </ul>
                </div>
              </div>
              <RubberBuyMenu product={rubber.name} buyLinks={rubber.buyLinks} featured />
            </li>
          );
        })}
      </ul>
      <RubberAffiliateDisclosure />
      <GearQuiz />
    </section>
  );
}
