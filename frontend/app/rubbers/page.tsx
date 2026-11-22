import { LEVELS, STYLES } from "@/lib/rubbers";
import { RubberFinder } from "./rubber-finder";

export default async function RubbersPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const style = STYLES.find((option) => option === params.style) ?? "spin";
  const level = LEVELS.find((option) => option === params.level) ?? "intermediate";
  const demo = params.demo === "1";
  return <RubberFinder key={`${style}-${level}-${demo}`} initialStyle={style} initialLevel={level} demo={demo} />;
}
