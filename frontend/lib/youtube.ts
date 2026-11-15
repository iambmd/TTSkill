/** Mirrors backend/app/download.py: YouTube watch, youtu.be and Shorts links only. */
const PATTERNS = [
  /^(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/watch\?(?:.*&)?v=([\w-]{11})(?:[&#].*)?$/,
  /^(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/shorts\/([\w-]{11})(?:[/?#].*)?$/,
  /^(?:https?:\/\/)?youtu\.be\/([\w-]{11})(?:[/?#].*)?$/,
];

export function youtubeId(url: string): string | null {
  const u = url.trim();
  for (const p of PATTERNS) {
    const m = u.match(p);
    if (m) return m[1];
  }
  return null;
}

export const LINK_HINT = "Paste a youtube.com/watch, youtu.be or Shorts link.";
