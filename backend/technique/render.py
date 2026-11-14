"""Fallback renderer: vertical 1080x1920 coaching video built from the user's own clip.

Footage is dimmed and tinted, a glowing MediaPipe skeleton is drawn on the player, and the
breakdown is shown as a title card, three numbered steps (slow-mo + freeze at each key
moment, bat-hand marker with trail, callout labels) and a summary card. Original TTSkill
styling; nothing is copied from third-party videos."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .media import encode_frames
from .pose import CONNECTIONS, L_WRIST, NOSE, R_WRIST, PoseTrack, _interp_nan
from .schema import StrokeBreakdown

W, H, FPS = 1080, 1920, 30
VID_Y, VID_H = 560, 1080          # video area: y range [560, 1640)
BG = (20, 15, 11)                 # BGR near-black navy
ACCENT = (255, 212, 0)            # RGB yellow (PIL)
CYAN = (60, 230, 255)             # RGB
WHITE = (240, 240, 240)
GREY = (120, 128, 140)

_FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/dejavu",
              "/System/Library/Fonts", "C:/Windows/Fonts"]
_FONT_FILES = {"black": ["Inter-ExtraBold.otf", "InterDisplay-Bold.otf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
               "bold": ["Inter-Bold.otf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
               "medium": ["Inter-Medium.otf", "Inter-Regular.otf", "DejaVuSans.ttf", "arial.ttf"]}


@lru_cache(None)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for d in _FONT_DIRS:
        for f in _FONT_FILES[kind]:
            p = Path(d) / f
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


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


def _pills(d, steps, active: int, max_w: int = 790):
    labels = [f"{i + 1}  {s.title.upper()}" for i, s in enumerate(steps)]
    f = font("bold", 22)
    if sum(d.textlength(l, font=f) + 38 for l in labels) > max_w:
        stop = {"THE", "TO", "A", "AN", "FOR", "OF", "YOUR", "AND", "INTO", "ON"}
        labels = [f"{i + 1}  " + " ".join([w for w in s.title.upper().split() if w not in stop][:2])
                  for i, s in enumerate(steps)]
    size = 22
    while size > 14:
        f = font("bold", size)
        total = sum(d.textlength(l, font=f) + 28 for l in labels) + 10 * (len(labels) - 1)
        if total <= max_w:
            break
        size -= 1
    x = 48
    for i, label in enumerate(labels):
        tw = d.textlength(label, font=f)
        box = (x, 60, x + tw + 28, 60 + size + 18)
        if i == active:
            d.rounded_rectangle(box, 18, fill=ACCENT)
            d.text((x + 14, 68), label, font=f, fill=(15, 15, 15))
        else:
            d.rounded_rectangle(box, 18, outline=GREY, width=2)
            d.text((x + 14, 68), label, font=f, fill=GREY)
        x = box[2] + 10


def _brand(d):
    f = font("black", 40)
    d.text((W - 48 - d.textlength("TTSKILL", font=f), 54), "TTSKILL", font=f, fill=WHITE)
    f2 = font("bold", 18)
    t = "AI TECHNIQUE BREAKDOWN"
    d.text((W - 48 - d.textlength(t, font=f2), 100), t, font=f2, fill=GREY)


def _tag(d, text, y=470):
    f = font("bold", 22)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle((48, y, 48 + tw + 24, y + 38), 6, outline=WHITE, width=2)
    d.text((60, y + 7), text, font=f, fill=WHITE)


def layer_step(b: StrokeBreakdown, k: int, tag: str) -> np.ndarray:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _pills(d, b.steps, k)
    _brand(d)
    s = b.steps[k]
    d.rounded_rectangle((48, 178, 112, 252), 8, fill=ACCENT)
    fnum = font("black", 54)
    num = str(k + 1)
    d.text((80 - d.textlength(num, font=fnum) / 2, 184), num, font=fnum, fill=(15, 15, 15))
    ft = font("black", 62)
    title = s.title.upper()
    while d.textlength(title, font=ft) > W - 180 and ft.size > 36:
        ft = font("black", ft.size - 4)
    d.text((134, 182), title, font=ft, fill=WHITE)
    fl = font("medium", 42)
    for j, line in enumerate(s.lines[:2]):
        _rich_line(d, (52, 300 + j * 60), line, s.highlight_words, fl)
    _tag(d, tag)
    return np.array(img)


def layer_intro(b: StrokeBreakdown) -> np.ndarray:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _brand(d)
    f = font("bold", 34)
    t = f"QUICK BREAKDOWN · {b.stroke.upper()}"
    d.text(((W - d.textlength(t, font=f)) / 2, 190), t, font=f, fill=ACCENT)
    fh = font("black", 84)
    lines = _wrap(d, b.headline.upper(), fh, W - 120)
    while len(lines) > 3 and fh.size > 48:
        fh = font("black", fh.size - 6)
        lines = _wrap(d, b.headline.upper(), fh, W - 120)
    y = 260
    for ln in lines:
        d.text(((W - d.textlength(ln, font=fh)) / 2, y), ln, font=fh, fill=WHITE)
        y += fh.size + 12
    d.rectangle((W / 2 - 70, y + 16, W / 2 + 70, y + 22), fill=ACCENT)
    if b.player and b.player != "Player":
        fp = font("medium", 32)
        d.text(((W - d.textlength(b.player, font=fp)) / 2, y + 44), b.player, font=fp, fill=GREY)
    return np.array(img)


def layer_outro(b: StrokeBreakdown) -> np.ndarray:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _brand(d)
    f = font("black", 64)
    d.text((48, 170), "THE KEYS", font=f, fill=WHITE)
    d.rectangle((48, 252, 188, 258), fill=ACCENT)
    y = 300
    fl, fb = font("bold", 26), font("medium", 34)
    for label, txt in (("GRIP", b.grip), ("STANCE", b.stance), ("SWING", b.swing_path),
                       ("CONTACT", b.contact_point), ("FINISH", b.follow_through)):
        d.text((48, y), label, font=fl, fill=ACCENT)
        y += 34
        for ln in _wrap(d, txt, fb, W - 96)[:3]:
            d.text((48, y), ln, font=fb, fill=WHITE)
            y += 44
        y += 18
    # translucent panel behind the text so footage doesn't fight it
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rectangle((0, 150, W, y + 10), fill=(10, 12, 18, 200))
    return np.array(Image.alpha_composite(panel, img))


def layer_callouts(callouts: list[str], color=ACCENT) -> np.ndarray:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font("black", 30)
    y = VID_Y + VID_H + 30
    for c in callouts[:2]:
        t = c.upper()
        tw = d.textlength(t, font=f)
        d.rectangle((60, y, 60 + tw + 24, y + 46), fill=color)
        d.text((72, y + 7), t, font=f, fill=(15, 15, 15))
        y += 58
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

def compute_crop(track: PoseTrack, src_w: int, src_h: int) -> tuple[int, int, int]:
    """Constant square crop (x, y, size) around the player over the whole clip."""
    xy = track.lm[track.valid, :, :2] * np.array([src_w, src_h]) if track.valid.any() else None
    if xy is None or len(xy) == 0:
        s = min(src_w, src_h)
        return (src_w - s) // 2, (src_h - s) // 2, s
    lo = np.nanpercentile(xy.reshape(-1, 2), 2, axis=0)
    hi = np.nanpercentile(xy.reshape(-1, 2), 98, axis=0)
    cx, cy = (lo + hi) / 2
    size = max(hi - lo) * 1.5
    size = int(np.clip(size, min(src_w, src_h) * 0.45, min(src_w, src_h)))
    x = int(np.clip(cx - size / 2, 0, src_w - size))
    y = int(np.clip(cy - size / 2, 0, src_h - size))
    return x, y, size


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
        self.scale = VID_H / self.crop[2]
        n = len(track.times)
        self.pts = _interp_nan(track.lm[:, :, :2]) if n else np.zeros((0, 33, 2))
        self.pts = self.pts * np.array([sw, sh])
        self.vis = track.valid
        self.wrist = R_WRIST if side != "left" else L_WRIST

    def to_out(self, p: np.ndarray) -> np.ndarray:
        x, y, _ = self.crop
        return (p - np.array([x, y])) * self.scale + np.array([0, VID_Y])

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
        x, y, s = self.crop
        src = self.frames[min(fi, len(self.frames) - 1)][y:y + s, x:x + s]
        vid = cv2.resize(src, (W, VID_H), interpolation=cv2.INTER_AREA)
        vid = cv2.transform(vid, Scene._TINT)
        # vignette top/bottom so the video melts into the background
        ramp, r = Scene._RAMP, Scene._RAMP.shape[0]
        bgf = np.array(BG, np.float32)
        vid[:r] = (vid[:r] * ramp + bgf * (1 - ramp)).astype(np.uint8)
        vid[-r:] = (vid[-r:] * ramp[::-1] + bgf * (1 - ramp[::-1])).astype(np.uint8)
        if len(cache) > 8:
            cache.clear()
        cache[fi] = vid
        return vid

    def draw(self, fi: int, ring: Optional[tuple] = None, connector: bool = False,
             trail: bool = True) -> np.ndarray:
        if not hasattr(self, "_bg"):
            self._bg = np.full((H, W, 3), BG, np.uint8)
        canvas = self._bg.copy()
        canvas[VID_Y:VID_Y + VID_H] = self._video_band(fi)

        if len(self.pts):
            pi = self._pose_idx(fi)
            if self.vis[pi] or self.vis[max(0, pi - 3):pi + 3].any():
                self._skeleton(canvas, self.to_out(self.pts[pi]))
                if trail:
                    self._trail(canvas, pi)
                if ring:
                    self._ring(canvas, self.to_out(self.pts[pi, self.wrist]), *ring)
                    if connector:
                        self._connector(canvas, self.to_out(self.pts[pi, self.wrist]), ring[0])
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

    def _trail(self, canvas, pi, n=10):
        idx = [i for i in range(max(0, pi - n), pi + 1)]
        if len(idx) < 2:
            return
        pts = np.array([self.to_out(self.pts[i, self.wrist]) for i in idx]).astype(int)
        for k in range(1, len(pts)):
            a = k / len(pts)
            col = (int(255 * a), int(230 * a), int(60 * a))  # BGR cyan fading
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

    def fidx(t: float) -> int:
        return int(np.clip(round(t * fps_src), 0, n - 1))

    keys = []
    for i, s in enumerate(b.steps):
        t = s.key_time_s if s.key_time_s is not None else (i + 1) * (n / fps_src) / 4
        keys.append(fidx(t))
    keys = sorted(keys)

    def gen() -> Iterator[np.ndarray]:
        intro = layer_intro(b)
        for k in range(int(2.2 * FPS)):
            yield blend(scene.draw(0, trail=False), intro)
        cur = 0
        lead, tail = int(0.5 * fps_src), int(0.35 * fps_src)
        for si, kf in enumerate(keys):
            play = layer_step(b, si, "QUICK BREAKDOWN")
            paused = layer_step(b, si, "II  PAUSED")
            color = ACCENT if si != 0 else CYAN
            call = layer_callouts(b.steps[si].callouts, color)
            # normal speed up to the lead-in
            for fi in range(cur, max(cur, kf - lead)):
                yield blend(scene.draw(fi), play)
            # slow motion into the key moment (x0.33)
            for fi in range(max(cur, kf - lead), kf):
                fr = blend(scene.draw(fi), play)
                for _ in range(3):
                    yield fr
            # freeze with marker + callouts
            for k in range(int(1.6 * FPS)):
                fr = scene.draw(kf, ring=(color, k / FPS), connector=bool(b.steps[si].callouts))
                yield blend(blend(fr, paused), call)
            # slow out
            for fi in range(kf, min(n, kf + tail)):
                fr = blend(scene.draw(fi), play)
                for _ in range(2):
                    yield fr
            cur = min(n - 1, kf + tail)
        outro = layer_outro(b)
        end = min(n, cur + int(1.0 * fps_src))
        last = layer_step(b, len(keys) - 1, "QUICK BREAKDOWN")
        for fi in range(cur, end):
            yield blend(scene.draw(fi), last)
        for k in range(int(3.5 * FPS)):
            yield blend(scene.draw(end - 1, trail=False), outro)

    encode_frames(gen(), out_path, W, H, FPS)
    return out_path


def render_text_only(b: StrokeBreakdown, out_path: str) -> str:
    """Text input with no clip: animated cards on the dark background."""
    def gen():
        base = np.full((H, W, 3), BG, np.uint8)
        # simple table graphic in the video area
        cv2.rectangle(base, (140, VID_Y + 620), (940, VID_Y + 660), (120, 70, 30), -1)
        cv2.line(base, (540, VID_Y + 560), (540, VID_Y + 620), (200, 200, 200), 4)
        intro = blend(base, layer_intro(b))
        for _ in range(int(2.5 * FPS)):
            yield intro
        for si in range(len(b.steps)):
            fr = blend(blend(base, layer_step(b, si, "QUICK BREAKDOWN")),
                       layer_callouts(b.steps[si].callouts))
            for _ in range(int(3.0 * FPS)):
                yield fr
        out = blend(base, layer_outro(b))
        for _ in range(int(4 * FPS)):
            yield out
    encode_frames(gen(), out_path, W, H, FPS)
    return out_path
