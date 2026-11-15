/** The link check shared by the forms and the API routes (mirrors backend/app/download.py). */
import { describe, expect, it } from "vitest";
import { youtubeId } from "@/lib/youtube";

describe("youtubeId", () => {
  it.each([
    "https://www.youtube.com/watch?v=g3n9jVP0fMU",
    "https://youtube.com/watch?feature=share&v=g3n9jVP0fMU&t=3",
    "https://m.youtube.com/watch?v=g3n9jVP0fMU",
    "https://youtu.be/g3n9jVP0fMU?si=abc",
    "https://youtube.com/shorts/g3n9jVP0fMU",
    "youtube.com/shorts/g3n9jVP0fMU?feature=share",
    "  https://youtu.be/g3n9jVP0fMU  ",
  ])("accepts %s", (url) => {
    expect(youtubeId(url)).toBe("g3n9jVP0fMU");
  });

  it.each(["", "hello", "https://vimeo.com/123", "https://www.youtube.com/@swift_TT",
    "https://www.youtube.com/watch?v=short", "https://evil.com/youtu.be/g3n9jVP0fMU"])("rejects %s", (url) => {
    expect(youtubeId(url)).toBeNull();
  });
});
