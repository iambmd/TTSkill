import { expect, it } from "vitest";
import RubbersPage from "@/app/rubbers/page";
import { renderIntl } from "./intl";

it.each([
  { budget: "1", expected: 1 },
  { budget: "40", expected: 40 },
  { budget: "500", expected: 500 },
  { budget: undefined, expected: 60 },
  { budget: "0.5", expected: 60 },
  { budget: "501", expected: 60 },
  { budget: "bad", expected: 60 },
  { budget: ["40", "80"], expected: 60 },
])("sets the Finder budget to $expected for query value $budget", async ({ budget, expected }) => {
  const page = await RubbersPage({ searchParams: Promise.resolve({ budget }) });
  const html = renderIntl(page);
  expect(html).toMatch(new RegExp(`<input[^>]+id="budget"[^>]+value="${expected}"`));
});
