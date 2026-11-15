/** Mirrors backend/app/download.py: YouTube watch, youtu.be, Shorts and /live/ links only. */
const PATTERNS = [
  /^(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/watch\?(?:.*&)?v=([\w-]{11})(?:[&#].*)?$/,
  /^(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/(?:shorts|live)\/([\w-]{11})(?:[/?#].*)?$/,
  /^(?:https?:\/\/)?youtu\.be\/([\w-]{11})(?:[/?#].*)?$/,
];
const YOUTUBE = /^(?:https?:\/\/)?(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)(?:[/?#]|$)/i;
const PLAYLIST = /^(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/playlist\b/i;
const CHANNEL = /^(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/(?:@|channel\/|c\/|user\/)/i;

export function youtubeId(url: string): string | null {
  const u = url.trim();
  for (const p of PATTERNS) {
    const m = u.match(p);
    if (m) return m[1];
  }
  return null;
}

export const LINK_HINT = "Paste a youtube.com/watch, youtu.be or Shorts link.";

/**
 * What's wrong with a pasted link, or null if it's a video link we can fetch. Private,
 * age-restricted, live and too-long videos need the video's details, so the backend checks those.
 */
export function linkProblem(url: string): string | null {
  const u = url.trim();
  if (youtubeId(u)) return null;
  if (PLAYLIST.test(u)) return "That's a playlist. Open one video from it and paste that video's link.";
  if (CHANNEL.test(u)) return "That's a channel link. Open one of its videos and paste that video's link.";
  if (!YOUTUBE.test(u)) return `Only YouTube links work here. ${LINK_HINT} Or upload the file.`;
  return `That isn't a YouTube video link we can use. ${LINK_HINT}`;
}
