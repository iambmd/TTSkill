import Link from "next/link";
import { MatchUpload } from "./match-upload";

export default function Home() {
  return (
    <section aria-labelledby="match-title" className="mx-auto max-w-3xl space-y-6">
      <div className="page-intro space-y-3">
        <p className="eyebrow">TTSkill</p>
        <h1 id="match-title" className="headline">Upload your match</h1>
        <p className="text-muted">Get a highlight reel, then take any match into Coach or Technique Breakdown.</p>
      </div>
      <MatchUpload />
      <Link href="/jobs/demo-autocut" className="inline-flex min-h-11 items-center font-semibold text-accent underline">
        See an example reel
      </Link>
    </section>
  );
}
