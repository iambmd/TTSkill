/** Mirrors STROKE_TYPES in backend/technique/strokes.py. Blank means auto-detect. */
export const STROKE_TYPES = [
  { value: "forehand_topspin", label: "Forehand topspin" },
  { value: "forehand_drive", label: "Forehand drive" },
  { value: "forehand_loop_backspin", label: "Forehand loop vs backspin" },
  { value: "backhand_topspin", label: "Backhand topspin" },
  { value: "backhand_flick", label: "Backhand flick" },
  { value: "backhand_push", label: "Backhand push" },
  { value: "chop", label: "Chop" },
  { value: "serve", label: "Serve" },
] as const;

export const STROKE_TYPE_VALUES: ReadonlySet<string> = new Set(STROKE_TYPES.map((s) => s.value));
