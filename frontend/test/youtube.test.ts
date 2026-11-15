/** The link check shared by the forms and the API routes (mirrors backend/app/download.py). */
import { describe, expect, it } from "vitest";
import { linkProblem, youtubeId } from "@/lib/youtube";

describe("youtubeId", () => {
  it.each([
    "https://www.youtube.com/watch?v=g3n9jVP0fMU",
    "https://youtube.com/watch?feature=share&v=g3n9jVP0fMU&t=3",
    "https://m.youtube.com/watch?v=g3n9jVP0fMU",
    "https://youtu.be/g3n9jVP0fMU?si=abc",
    "https://youtube.com/shorts/g3n9jVP0fMU",
    "youtube.com/shorts/g3n9jVP0fMU?feature=share",
    "  https://youtu.be/g3n9jVP0fMU  ",
    "https://www.youtube.com/live/g3n9jVP0fMU?si=x",
    "https://www.youtube.com/watch?v=g3n9jVP0fMU&list=PL1&index=2",
  ])("accepts %s", (url) => {
    expect(youtubeId(url)).toBe("g3n9jVP0fMU");
  });

  it.each(["", "hello", "https://vimeo.com/123", "https://www.youtube.com/@swift_TT",
    "https://www.youtube.com/watch?v=short", "https://evil.com/youtu.be/g3n9jVP0fMU"])("rejects %s", (url) => {
    expect(youtubeId(url)).toBeNull();
  });
});

describe("linkProblem", () => {
  it.each([
    ["https://www.youtube.com/playlist?list=PL1", "That's a playlist"],
    ["https://www.youtube.com/@swift_TT", "That's a channel link"],
    ["https://www.youtube.com/channel/UC123", "That's a channel link"],
    ["https://youtube.com/c/PingSkills", "That's a channel link"],
    ["https://m.youtube.com/user/pingskills", "That's a channel link"],
    ["https://vimeo.com/123", "Only YouTube links work here"],
    ["https://evil.com/youtu.be/g3n9jVP0fMU", "Only YouTube links work here"],
    ["https://www.youtube.com/feed/trending", "isn't a YouTube video link"],
  ])("explains %s", (url, text) => {
    expect(linkProblem(url)).toContain(text);
  });
  it("is null for a usable link", () => {
    expect(linkProblem("youtu.be/g3n9jVP0fMU")).toBeNull();
  });
});
