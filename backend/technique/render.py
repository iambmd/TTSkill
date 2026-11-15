"""Vertical 1080x1920 coaching video built from the user's own clip.

Layout and pacing follow backend/style/swift_style.json: a persistent header (stroke + hook),
the footage in the middle with a glowing MediaPipe skeleton, and under it a two-word cue in
that step's colour with one line on what to look for and one on why. Each step plays at
real speed, slows into the key moment and freezes there with a ring on the bat hand; the
video ends with a recap of the three cues and a practice drill. TTSkill's own palette and
fonts (Barlow, OFL); nothing is copied from third-party videos."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import style
from .media import encode_frames
from .pose import CONNECTIONS, L_WRIST, NOSE, R_WRIST, PoseTrack, _interp_nan
from .schema import StrokeBreakdown
from .strokes import label as stroke_label

W, H, FPS = 1080, 1920, 30
VID_Y, VID_H = 400, 1080          # video area: y range [400, 1480)
CUE_Y = VID_Y + VID_H + 36        # cue block under the footage
BG = (26, 16, 11)                 # BGR near-black navy
ACCENT = style.accent()           # RGB ball orange (PIL)
PHASE = style.phase_colours()     # RGB, one per step
WHITE = (240, 242, 245)
GREY = (143, 151, 170)
INK = (12, 12, 14)

_FONT_DIRS = [Path(__file__).resolve().parent / "fonts", Path("/usr/share/fonts/truetype/dejavu"),
              Path("/System/Library/Fonts"), Path("C:/Windows/Fonts")]
_FONT_FILES = {"display": ["BarlowCondensed-ExtraBoldItalic.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
               "bold": ["BarlowCondensed-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
               "semibold": ["Barlow-SemiBold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
               "medium": ["Barlow-Medium.ttf", "DejaVuSans.ttf", "arial.ttf"]}


@lru_cache(None)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for d in _FONT_DIRS:
        for f in _FONT_FILES[kind]:
            p = d / f
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def phase(k: int) -> tuple[int, int, int]:
    return PHASE[k % len(PHASE)]


# ------------------------------------------------------------------ text layers (RGBA)

def _rich_line(d: ImageDraw.ImageDraw, xy, text: str, hl: list[str], f, base=WHITE, acc=ACCENT):
    """Draw text with highlighted phrases in the accent colour."""
    spans = [(text, False)]
    for phrase in sorted({h for h in hl if h}, key=len, reverse=True):
        nxt = []
        for s, is_hl in spans:
            if is_hl:
                nxt.append((s, True))
                continue
            low, pl = s.lower(), phrase.lower()
            i = low.find(pl)
            while i >= 0:
                nxt.append((s[:i], False))
                nxt.append((s[i:i + len(phrase)], True))
                s = s[i + len(phrase):]
                low = s.lower()
                i = low.find(pl)
            nxt.append((s, False))
        spans = [x for x in nxt if x[0]]
    x, y = xy
    for s, is_hl in spans:
        d.text((x, y), s, font=f, fill=acc if is_hl else base)
        x += d.textlength(s, font=f)


def _wrap(d, text, f, width) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit(d, text: str, kind: str, size: int, width: int, min_size: int = 30):
    f = font(kind, size)
    while d.textlength(text, font=f) > width and f.size > min_size:
        f = font(kind, f.size - 4)
    return f


def _brand(d):
    f = font("display", 40)
    tw = d.textlength("TTSKILL", font=f)
    x = W - 56 - tw
    d.ellipse((x - 26, 66, x - 10, 82), fill=ACCENT)
    d.text((x, 52), "TT", font=f, fill=WHITE)
    d.text((x + d.textlength("TT", font=f), 52), "SKILL", font=f, fill=ACCENT)


def _header(d, b: StrokeBreakdown):
    """Persistent two-line title: the stroke, then the hook in the accent colour."""
    _brand(d)
    d.text((56, 56), stroke_label(b.stroke_type or b.stroke).upper(), font=_fit(d, stroke_label(b.stroke_type or b.stroke).upper(), "bold", 48, W - 380), fill=WHITE)
    fh = font("display", 76)
    lines = _wrap(d, b.headline.upper(), fh, W - 112)
    while len(lines) > 2 and fh.size > 48:
        fh = font("display", fh.size - 6)
        lines = _wrap(d, b.headline.upper(), fh, W - 112)
    y = 118
    for ln in lines[:2]:
        d.text((56, y), ln, font=fh, fill=ACCENT)
        y += int(fh.size * 0.95)


def _chips(d, steps, active: int):
    """Numbered chips (01, 02, 03) just above the footage; the active one in its colour."""
    labels = [f"{i + 1:02d}  {s.title.upper()}" for i, s in enumerate(steps)]
    size = 30
    while size > 18:
        f = font("bold", size)
        total = sum(d.textlength(l, font=f) + 36 for l in labels) + 12 * (len(labels) - 1)
        if total <= W - 112:
            break
        size -= 1
    x, y = 56, VID_Y - 30 - size
    for i, lab in enumerate(labels):
        tw = d.textlength(lab, font=f)
        box = (x, y - 8, x + tw + 36, y + size + 12)
        if i == active:
            d.rounded_rectangle(box, 10, fill=phase(i))
            d.text((x + 18, y - 2), lab, font=f, fill=INK)
        else:
            d.rounded_rectangle(box, 10, outline=(60, 66, 80), width=2)
            d.text((x + 18, y - 2), lab, font=f, fill=GREY)
        x = box[2] + 12


def layer_step(b: StrokeBreakdown, k: int, paused: bool = False) -> np.ndarray:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _header(d, b)
    _chips(d, b.steps, k)
    s = b.steps[k]
    col = phase(k)
    cue = s.title.upper()
    fc = _fit(d, cue, "display", 132, W - 112, 72)
    d.text((56, CUE_Y), cue, font=fc, fill=col)
    y = CUE_Y + int(fc.size * 1.02) + 10
    if s.lines:
        _rich_line(d, (60, y), s.lines[0], s.highlight_words, font("semibold", 46), acc=col)
    if len(s.lines) > 1:
        _rich_line(d, (60, y + 64), s.lines[1], s.highlight_words, font("medium", 40), base=GREY, acc=col)
    if paused:
        f = font("bold", 26)
        t = "PAUSED"
        tw = d.textlength(t, font=f)
        x0, y0 = W - 56 - tw - 44, VID_Y + 24
        d.rounded_rectangle((x0, y0, x0 + tw + 44, y0 + 44), 10, fill=(10, 12, 18, 210))
        d.rectangle((x0 + 14, y0 + 13, x0 + 18, y0 + 31), fill=col)
        d.rectangle((x0 + 23, y0 + 13, x0 + 27, y0 + 31), fill=col)
        d.text((x0 + 36, y0 + 8), t, font=f, fill=WHITE)
    return np.array(img)


def layer_intro(b: StrokeBreakdown) -> np.ndarray:
    """Hook card: the header, then what the video will show."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _header(d, b)
    f = font("display", 120)
    x = 56
    for word, col in (("3", ACCENT), (" CUES TO COPY", WHITE)):
        d.text((x, CUE_Y), word, font=f, fill=col)
        x += d.textlength(word, font=f)
    sub = " · ".join(s.title.upper() for s in b.steps)
    y = CUE_Y + 140
    d.text((60, y), sub, font=_fit(d, sub, "bold", 40, W - 120, 24), fill=GREY)
    if b.player and b.player != "Player":
        d.text((60, y + 58), b.player, font=font("medium", 36), fill=GREY)
    return np.array(img)


def layer_recap(b: StrokeBreakdown) -> np.ndarray:
    """All three cues on one line joined with '+', each in its colour, plus one summary line."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _header(d, b)
    words = [(s.title.upper(), phase(i)) for i, s in enumerate(b.steps)]
    size = 92
    while size > 44:
        f = font("display", size)
        lines, cur, cur_w = [], [], 0.0
        for i, (w, col) in enumerate(words):
            piece = [(w, col)] + ([(" + ", WHITE)] if i < len(words) - 1 else [])
            pw = sum(d.textlength(t, font=f) for t, _ in piece)
            if cur and cur_w + pw > W - 112:
                lines.append(cur)
                cur, cur_w = [], 0.0
            cur += piece
            cur_w += pw
        lines.append(cur)
        if len(lines) <= 2:
            break
        size -= 6
    y = CUE_Y - (int(size * 0.95) if len(lines) > 1 else 0)
    for ln in lines:
        x = 56
        for t, col in ln:
            d.text((x, y), t, font=f, fill=col)
            x += d.textlength(t, font=f)
        y += int(size * 0.95)
    summary = b.recap or ", ".join(s.title for s in b.steps) + "."
    d.text((60, y + 18), summary, font=_fit(d, summary, "semibold", 42, W - 120, 26), fill=WHITE)
    return np.array(img)


def layer_drill(b: StrokeBreakdown) -> np.ndarray:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _header(d, b)
    d.text((60, CUE_Y), "TRY THIS", font=font("bold", 40), fill=ACCENT)
    y = CUE_Y + 62
    for ln in _wrap(d, b.drill or "Shadow the stroke 20 times, checking each cue.", font("semibold", 52), W - 120)[:3]:
        d.text((60, y), ln, font=font("semibold", 52), fill=WHITE)
        y += 66
    return np.array(img)


def layer_callouts(callouts: list[str], color=ACCENT) -> np.ndarray:
    """Small labels in the step colour, inside the bottom-left of the footage."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font("bold", 32)
    y = VID_Y + VID_H - 70 - 56 * (min(2, len(callouts)) - 1)
    for c in callouts[:2]:
        t = c.upper()
        tw = d.textlength(t, font=f)
        d.rounded_rectangle((56, y, 56 + tw + 28, y + 46), 8, fill=color)
        d.text((70, y + 5), t, font=f, fill=INK)
        y += 56
    return np.array(img)


_PREP: dict[int, tuple] = {}


def blend(dst: np.ndarray, rgba: np.ndarray) -> np.ndarray:
    """Alpha-composite an RGBA layer onto a BGR frame. Layers are static, so the
    premultiplied colour/alpha and the non-empty row range are cached per layer."""
    key = id(rgba)
    prep = _PREP.get(key)
    if prep is None or prep[0] is not rgba:
        rows = np.where(rgba[:, :, 3].any(1))[0]
        y0, y1 = (int(rows[0]), int(rows[-1]) + 1) if len(rows) else (0, 0)
        a = rgba[y0:y1, :, 3:4].astype(np.float32) / 255.0
        pre = rgba[y0:y1, :, 2::-1].astype(np.float32) * a
        prep = (rgba, y0, y1, pre, 1.0 - a)
        _PREP[key] = prep
    _, y0, y1, pre, inv = prep
    out = dst.copy()
    if y1 > y0:
        out[y0:y1] = (dst[y0:y1].astype(np.float32) * inv + pre).astype(np.uint8)
    return out


# ------------------------------------------------------------------ video area

def compute_crop(track: PoseTrack, src_w: int, src_h: int) -> tuple[int, int, int, int]:
    """Constant crop (x, y, w, h) around the player over the whole clip. The crop is as
    tall as the player needs (so heads/feet aren't cut off) and between 0.5:1 and 1:1 wide;
    portrait sources end up pillarboxed in the square video band."""
    xy = track.lm[track.valid, :, :2] * np.array([src_w, src_h]) if track.valid.any() else None
    if xy is None or len(xy) == 0:
        s_ = min(src_w, src_h)
        return (src_w - s_) // 2, (src_h - s_) // 2, s_, s_
    pts = xy.reshape(-1, 2)
    lo = np.nanpercentile(pts, 2, axis=0)
    hi = np.nanpercentile(pts, 98, axis=0)
    cx, cy = (lo + hi) / 2
    ch = int(np.clip((hi[1] - lo[1]) * 1.35, src_h * 0.45, src_h))
    cw = int(np.clip(max((hi[0] - lo[0]) * 1.4, ch * 0.5), 1, min(src_w, ch)))
    x = int(np.clip(cx - cw / 2, 0, src_w - cw))
    y = int(np.clip(cy - ch / 2, 0, src_h - ch))
    return x, y, cw, ch


def _add_glow(canvas: np.ndarray, glow: np.ndarray, sigma: float, gain: float):
    """Blur `glow` (video band only, half resolution) and add it onto canvas in place."""
    band = glow[VID_Y - 100:VID_Y + VID_H + 100]
    small = cv2.resize(band, (W // 2, band.shape[0] // 2), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigma / 2)
    big = cv2.resize(small, (W, band.shape[0]), interpolation=cv2.INTER_LINEAR)
    region = canvas[VID_Y - 100:VID_Y + VID_H + 100]
    cv2.addWeighted(region, 1.0, big, gain, 0, dst=region)




class Scene:
    def __init__(self, frames: list[np.ndarray], track: PoseTrack, side: str):
        self.frames = frames
        self.track = track
        sh, sw = frames[0].shape[:2]
        self.crop = compute_crop(track, sw, sh)
        self.scale = VID_H / self.crop[3]
        self.out_w = min(W, int(round(self.crop[2] * self.scale)))
        self.x_off = (W - self.out_w) // 2
        n = len(track.times)
        self.pts = _interp_nan(track.lm[:, :, :2]) if n else np.zeros((0, 33, 2))
        self.pts = self.pts * np.array([sw, sh])
        self.vis = track.valid
        self.wrist = R_WRIST if side != "left" else L_WRIST

    def to_out(self, p: np.ndarray) -> np.ndarray:
        x, y = self.crop[:2]
        return (p - np.array([x, y])) * self.scale + np.array([self.x_off, VID_Y])

    def _pose_idx(self, fi: int) -> int:
        return int(np.clip(fi, 0, len(self.pts) - 1))

    _TINT = None
    _RAMP = None

    def _video_band(self, fi: int) -> np.ndarray:
        """Dimmed, blue-tinted crop of the source frame (cached for repeated frames)."""
        cache = self.__dict__.setdefault("_band_cache", {})
        if fi in cache:
            return cache[fi]
        if Scene._TINT is None:
            gray = np.array([0.114, 0.587, 0.299], np.float32)
            gain = np.array([1.25, 1.0, 0.85], np.float32)
            Scene._TINT = (0.30 * np.outer(gain, gray) + 0.12 * np.diag(gain)).astype(np.float32)
            r = 140
            ramp = np.linspace(0, 1, r, dtype=np.float32)[:, None, None]
            Scene._RAMP = ramp
        x, y, cw, ch = self.crop
        src = self.frames[min(fi, len(self.frames) - 1)][y:y + ch, x:x + cw]
        interp = cv2.INTER_AREA if self.out_w <= cw else cv2.INTER_CUBIC
        clip = cv2.transform(cv2.resize(src, (self.out_w, VID_H), interpolation=interp),
                             Scene._TINT)
        bgf = np.array(BG, np.float32)
        if self.out_w < W:  # pillarbox: fade the left/right edges into the background
            e = min(90, self.out_w // 4)
            hr = np.linspace(0, 1, e, dtype=np.float32)[None, :, None]
            clip[:, :e] = (clip[:, :e] * hr + bgf * (1 - hr)).astype(np.uint8)
            clip[:, -e:] = (clip[:, -e:] * hr[:, ::-1] + bgf * (1 - hr[:, ::-1])).astype(np.uint8)
        vid = np.empty((VID_H, W, 3), np.uint8)
        vid[:] = BG
        vid[:, self.x_off:self.x_off + self.out_w] = clip
        # vignette top/bottom so the video melts into the background
        ramp, r = Scene._RAMP, Scene._RAMP.shape[0]
        vid[:r] = (vid[:r] * ramp + bgf * (1 - ramp)).astype(np.uint8)
        vid[-r:] = (vid[-r:] * ramp[::-1] + bgf * (1 - ramp[::-1])).astype(np.uint8)
        if len(cache) > 8:
            cache.clear()
        cache[fi] = vid
        return vid

    def draw(self, fi: int, ring: Optional[tuple] = None, connector: bool = False,
             trail: bool = True, trail_color: tuple = (56, 217, 245)) -> np.ndarray:
        if not hasattr(self, "_bg"):
            self._bg = np.full((H, W, 3), BG, np.uint8)
        canvas = self._bg.copy()
        canvas[VID_Y:VID_Y + VID_H] = self._video_band(fi)

        if len(self.pts):
            pi = self._pose_idx(fi)
            if self.vis[pi] or self.vis[max(0, pi - 3):pi + 3].any():
                self._skeleton(canvas, self.to_out(self.pts[pi]))
                if trail:
                    self._trail(canvas, pi, trail_color)
                if ring:
                    self._ring(canvas, self.to_out(self.pts[pi, self.wrist]), *ring)
                # keep the overlay inside the video band so it never runs under the text
                canvas[:VID_Y] = BG
                canvas[VID_Y + VID_H:] = BG
                if ring and connector:
                    c = self.to_out(self.pts[pi, self.wrist])
                    c[1] = np.clip(c[1], VID_Y, VID_Y + VID_H - 1)
                    self._connector(canvas, c, ring[0])
        return canvas

    def _skeleton(self, canvas, p):
        glow = np.zeros_like(canvas)
        pts = p.astype(int)
        for a, b in CONNECTIONS:
            cv2.line(glow, tuple(pts[a]), tuple(pts[b]), (255, 220, 120), 16, cv2.LINE_AA)
        _add_glow(canvas, glow, 9, 0.55)
        for a, b in CONNECTIONS:
            cv2.line(canvas, tuple(pts[a]), tuple(pts[b]), (245, 245, 245), 5, cv2.LINE_AA)
        for j in (11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28):
            cv2.circle(canvas, tuple(pts[j]), 8, (255, 255, 255), -1, cv2.LINE_AA)
        head_r = int(max(14, np.linalg.norm(p[11] - p[12]) * 0.35))
        cv2.circle(canvas, tuple(pts[NOSE]), head_r, (245, 245, 245), 4, cv2.LINE_AA)

    def _trail(self, canvas, pi, color_rgb=(56, 217, 245), n=10):
        idx = [i for i in range(max(0, pi - n), pi + 1)]
        if len(idx) < 2:
            return
        pts = np.array([self.to_out(self.pts[i, self.wrist]) for i in idx]).astype(int)
        for k in range(1, len(pts)):
            if np.linalg.norm(pts[k] - pts[k - 1]) > 0.18 * W:
                continue  # tracking jump: don't draw a streak across the frame
            a = k / len(pts)
            col = tuple(int(c * a) for c in color_rgb[::-1])  # BGR, fading toward the tail
            cv2.line(canvas, tuple(pts[k - 1]), tuple(pts[k]), col, int(2 + 6 * a), cv2.LINE_AA)

    def _ring(self, canvas, c, color_rgb, phase: float):
        bgr = tuple(int(v) for v in color_rgb[::-1])
        c = tuple(c.astype(int))
        glow = np.zeros_like(canvas)
        r = int(34 + 6 * np.sin(phase * 2 * np.pi))
        cv2.circle(glow, c, r, bgr, 14, cv2.LINE_AA)
        _add_glow(canvas, glow, 8, 1.0)
        cv2.circle(canvas, c, r, bgr, 5, cv2.LINE_AA)
        cv2.circle(canvas, c, 8, (255, 255, 255), -1, cv2.LINE_AA)

    def _connector(self, canvas, c, color_rgb):
        bgr = tuple(int(v) for v in color_rgb[::-1])
        c = c.astype(int)
        x0, y_lab = 72, VID_Y + VID_H + 30
        cv2.line(canvas, (int(c[0]), int(c[1])), (x0, int(c[1])), bgr, 3, cv2.LINE_AA)
        cv2.line(canvas, (x0, int(c[1])), (x0, y_lab), bgr, 3, cv2.LINE_AA)




# ------------------------------------------------------------------ timeline

def _read_frames(video: str) -> list[np.ndarray]:
    cap = cv2.VideoCapture(video)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    return frames


def render_breakdown(video: str, track: PoseTrack, b: StrokeBreakdown, out_path: str,
                     side: str = "right") -> str:
    frames = _read_frames(video)
    if not frames:
        raise RuntimeError("no frames in clip")
    scene = Scene(frames, track, side)
    fps_src = track.fps or 30.0
    n = len(frames)
    pace = style.pacing()

    def fidx(t: float) -> int:
        return int(np.clip(round(t * fps_src), 0, n - 1))

    keys = []
    for i, s in enumerate(b.steps):
        t = s.key_time_s if s.key_time_s is not None else (i + 1) * (n / fps_src) / 4
        keys.append(fidx(t))
    keys = sorted(keys)
    lead = max(1, int(pace["slowmo_lead_s"] * fps_src))
    repeat = max(1, round(1 / max(pace["slowmo_factor"], 0.1)))
    freeze_n = int(pace["freeze_s"] * FPS)
    tail = int(0.35 * fps_src)

    def gen() -> Iterator[np.ndarray]:
        intro = layer_intro(b)
        start = max(0, keys[0] - lead - int(1.0 * fps_src))
        for _ in range(int(pace["hook_s"] * FPS)):
            yield blend(scene.draw(start, trail=False), intro)
        cur = start
        for si, kf in enumerate(keys):
            col = phase(si)
            play, paused = layer_step(b, si), layer_step(b, si, paused=True)
            call = layer_callouts(b.steps[si].callouts, col)
            for fi in range(cur, max(cur, kf - lead)):          # real speed first
                yield blend(scene.draw(fi, trail_color=col), play)
            for fi in range(max(cur, kf - lead), kf):           # slow into the key moment
                fr = blend(scene.draw(fi, trail_color=col), play)
                for _ in range(repeat):
                    yield fr
            for k in range(freeze_n):                           # hold it, ring on the bat hand
                fr = scene.draw(kf, ring=(col, k / FPS), trail_color=col)
                yield blend(blend(fr, paused), call)
            for fi in range(kf, min(n, kf + tail)):             # ease out
                fr = blend(scene.draw(fi, trail_color=col), play)
                for _ in range(2):
                    yield fr
            cur = min(n - 1, kf + tail)
        last = layer_step(b, len(keys) - 1)
        end = min(n, cur + int(0.6 * fps_src))
        for fi in range(cur, end):
            yield blend(scene.draw(fi, trail_color=phase(len(keys) - 1)), last)
        hold = max(cur, end - 1)
        recap, drill = layer_recap(b), layer_drill(b)
        for _ in range(int(pace["recap_s"] * FPS)):
            yield blend(scene.draw(hold, trail=False), recap)
        for _ in range(int(pace["practice_s"] * FPS)):
            yield blend(scene.draw(hold, trail=False), drill)

    encode_frames(gen(), out_path, W, H, FPS)
    return out_path


def render_text_only(b: StrokeBreakdown, out_path: str) -> str:
    """Text input with no clip: the same cards over a simple table graphic."""
    pace = style.pacing()

    def gen():
        base = np.full((H, W, 3), BG, np.uint8)
        cv2.rectangle(base, (140, VID_Y + 700), (940, VID_Y + 740), (120, 70, 30), -1)
        cv2.line(base, (540, VID_Y + 640), (540, VID_Y + 700), (200, 200, 200), 4)
        cards = [(layer_intro(b), pace["hook_s"] + 0.5)]
        cards += [(layer_step(b, si), pace["seconds_per_step"]) for si in range(len(b.steps))]
        cards += [(layer_recap(b), pace["recap_s"]), (layer_drill(b), pace["practice_s"])]
        for si, (layer, secs) in enumerate(cards):
            fr = blend(base, layer)
            if 1 <= si <= len(b.steps):
                fr = blend(fr, layer_callouts(b.steps[si - 1].callouts, phase(si - 1)))
            for _ in range(int(secs * FPS)):
                yield fr
    encode_frames(gen(), out_path, W, H, FPS)
    return out_path
