"""Cinematic product ad from a single still (fireplace).

Renders a 1080x1920 (9:16) clip: virtual camera moves, close-up reveals,
living flames (heat shimmer + flicker + bloom), light sweeps over the glass,
lighting ramps, vignette and grain. Product pixels are never repainted --
only re-lit and re-framed -- so design, colours, proportions and branding
stay as photographed.

Usage:
  python3 src/render.py base     -> out/kamin_basis_9x16.mp4   (no text)
  python3 src/render.py preview  -> out/kamin_vorschau_9x16.mp4 (with text)
"""
import math
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC = "assets/kamin_original.jpg"
W, H, FPS, DUR = 1080, 1920, 30, 15.0
FONT_DIR = "/usr/share/fonts/opentype/inter/"

img = cv2.imread(SRC).astype(np.float32) / 255.0
SH, SW = img.shape[:2]                      # 2576 x 1932
S = SW / 1500.0                             # reference coords were picked on a 1500px-wide view


def P(x, y):
    return (x * S, y * S)


# ---------------------------------------------------------------- masks (source space)
def soft_poly(pts, blur):
    m = np.zeros((SH, SW), np.float32)
    cv2.fillPoly(m, [np.array([P(*p) for p in pts], np.int32)], 1.0)
    return cv2.GaussianBlur(m, (0, 0), blur)


# stove body vs. surroundings (cabinet left, wall right get pushed into shadow)
stove = soft_poly([(110, 0), (1368, 0), (1368, 2000), (110, 2000)], 40)
# three-sided glass
glass = soft_poly([(170, 352), (690, 128), (1265, 385), (1242, 1610),
                   (640, 1890), (165, 1590)], 6)

# flames: bright + warm pixels, softened
b, g, r = img[..., 0], img[..., 1], img[..., 2]
lum = 0.114 * b + 0.587 * g + 0.299 * r
warm = np.clip((r - b) * 2.0, 0, 1)
flame = np.clip((lum - 0.35) * 2.2, 0, 1) * warm * glass
flame[: int(800 * S)] *= 0.25                 # keep the reflections on the top glass calm
flame = cv2.GaussianBlur(flame, (0, 0), 6)
flame_wide = cv2.GaussianBlur(flame, (0, 0), 60)
flame_wide /= flame_wide.max()

YY, XX = np.mgrid[0:SH, 0:SW].astype(np.float32)

# pre-graded base plate: surroundings darkened + desaturated, gentle S-curve
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[..., None]
surround = (0.55 * img + 0.45 * gray) * 0.20
base = img * stove[..., None] + surround * (1 - stove[..., None])
base = np.clip(base, 0, 1)
base = base + 0.10 * (base - 0.5) * (1 - np.abs(base - 0.5) * 2)  # mild contrast
base = np.clip(base, 0, 1)
# photo is cut at top and bottom: let it fall off into the dark backdrop
edge = np.clip(np.minimum(YY_ := np.arange(SH, dtype=np.float32), SH - 1 - YY_) / (260 * S), 0, 1) ** 1.5
base *= edge[:, None, None]


# ---------------------------------------------------------------- helpers
def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ease_io_cubic(t):
    t = min(max(t, 0.0), 1.0)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def noise1(t, seed=0.0):
    """Smooth pseudo-random signal in [-1, 1]."""
    return (0.5 * math.sin(7.1 * t + seed) + 0.3 * math.sin(13.7 * t + 2 * seed + 1.3)
            + 0.2 * math.sin(23.3 * t + 3 * seed + 0.7))


# ---------------------------------------------------------------- living fire
def fire_frame(t):
    """Source-resolution frame with flicker, shimmer and bloom applied."""
    y0, y1 = int(850 * S), int(1900 * S)
    x0, x1 = int(150 * S), int(1280 * S)
    roi = base[y0:y1, x0:x1]
    m = flame[y0:y1, x0:x1]
    X, Y = XX[y0:y1, x0:x1], YY[y0:y1, x0:x1]
    # heat shimmer: displacement travelling upward, only where flames are
    amp = 5.0 * m
    dx = amp * (np.sin(0.030 * Y + 9.0 * t + 0.004 * X) + 0.5 * np.sin(0.071 * Y + 15.0 * t))
    dy = amp * 0.6 * np.sin(0.022 * X - 6.0 * t + 0.011 * Y)
    out = base.copy()
    out[y0:y1, x0:x1] = cv2.remap(roi, X - x0 + dx, Y - y0 + dy, cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_REFLECT)
    # flicker on flames + warm spill on the whole stove
    f = noise1(t * 1.6, 1.0)
    gain = 1.0 + 0.16 * f * flame + 0.07 * noise1(t * 1.1, 4.0) * flame_wide
    out *= gain[..., None]
    return out


def bloom(frame, strength):
    small = cv2.resize(frame, (frame.shape[1] // 4, frame.shape[0] // 4), interpolation=cv2.INTER_AREA)
    hi = np.clip(small - 0.72, 0, 1) * 2.0
    glow = cv2.GaussianBlur(hi, (0, 0), 18) + 0.6 * cv2.GaussianBlur(hi, (0, 0), 50)
    glow = cv2.resize(glow, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
    glow *= np.array([0.55, 0.8, 1.0], np.float32)  # warm (BGR)
    return frame + strength * glow


def light_sweep(frame, t, t0, t1, mask, angle=-0.55, width=160, strength=0.22):
    """Soft diagonal highlight travelling across `mask` between t0 and t1 (source space)."""
    if not (t0 <= t <= t1):
        return frame
    u = ease_io_cubic((t - t0) / (t1 - t0))
    d = XX * math.cos(angle) + YY * math.sin(angle)
    lo, hi = d.min(), d.max()
    pos = lo + (hi - lo) * (-0.1 + 1.2 * u)
    band = np.exp(-((d - pos) / width) ** 2) + 0.35 * np.exp(-((d - pos + 2.6 * width) / (width * 0.4)) ** 2)
    env = math.sin(math.pi * u)
    return frame + (strength * env * band * mask)[..., None] * np.array([0.92, 0.97, 1.0], np.float32)


# ---------------------------------------------------------------- camera
def camera(frame, cx, cy, zoom, rot_deg):
    ch = SH / zoom
    cw = ch * W / H
    if zoom >= 1:
        cx = min(max(cx, cw / 2), SW - cw / 2)
        cy = min(max(cy, ch / 2), SH - ch / 2)
    s = H / ch
    M = cv2.getRotationMatrix2D((cx, cy), rot_deg, s)
    M[0, 2] += W / 2 - cx
    M[1, 2] += H / 2 - cy
    out = cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT,
                         borderValue=(0.012, 0.010, 0.010))
    if s > 1.2:  # restore crispness on close-ups
        out = cv2.addWeighted(out, 1.45, cv2.GaussianBlur(out, (0, 0), 1.6), -0.45, 0)
    return out


def lerp(a, b, u):
    return a + (b - a) * u


# scenes: (start, end, (cx,cy,zoom) from, (cx,cy,zoom) to) -- reference coords
SCENES = [
    dict(t0=0.0, t1=3.9, a=(740, 1000, 0.80), b=(740, 990, 0.93), name="hero"),
    dict(t0=3.1, t1=7.1, a=(700, 1300, 2.25), b=(600, 1270, 2.55), name="flames"),
    dict(t0=6.3, t1=10.1, a=(1100, 470, 2.75), b=(1040, 420, 3.05), name="glass"),
    dict(t0=9.3, t1=12.7, a=(640, 1640, 2.50), b=(660, 1590, 2.15), name="detail"),
    dict(t0=11.9, t1=15.0, a=(720, 1150, 1.40), b=(740, 1000, 0.84), name="finale"),
]
XF = 0.8  # cross-dissolve length


def render_scene(sc, t, src):
    u = ease_io_cubic((t - sc["t0"]) / (sc["t1"] - sc["t0"]))
    ax, ay, az = sc["a"]
    bx, by, bz = sc["b"]
    # subtle floating: slow drift + micro rotation
    fx = 6 * math.sin(t * 0.9 + sc["t0"])
    fy = 9 * math.sin(t * 0.7 + 1.3 + sc["t0"])
    rot = 0.35 * math.sin(t * 0.5 + sc["t0"])
    cx, cy = P(lerp(ax, bx, u) + fx, lerp(ay, by, u) + fy)
    return camera(src, cx, cy, lerp(az, bz, u), rot)


VIG = None


def vignette(strength):
    global VIG
    if VIG is None:
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((x - W / 2) / (W * 0.62)) ** 2 + ((y - H / 2) / (H * 0.60)) ** 2)
        VIG = np.clip(1 - r ** 2.4, 0, 1)
    return 1 - strength * (1 - VIG)


def exposure(t):
    e = 0.15 + 0.85 * ease(t / 1.8)                       # rise out of darkness
    e *= 1 - 0.18 * math.exp(-((t - 7.0) / 0.4) ** 2)     # breath between shots
    e *= 1 - ease((t - 14.2) / 0.8)                       # fade out
    return e


def frame_at(t):
    src = fire_frame(t)
    src = light_sweep(src, t, 2.2, 3.8, glass, strength=0.20)
    src = light_sweep(src, t, 7.2, 9.6, glass, angle=-0.35, width=120, strength=0.26)
    src = light_sweep(src, t, 10.0, 12.2, stove * (1 - glass) * 0.6 + glass * 0.4, angle=-0.9, width=140, strength=0.16)
    out = np.zeros((H, W, 3), np.float32)
    wsum = 0.0
    for sc in SCENES:
        if sc["t0"] - 1e-6 <= t <= sc["t1"] + 1e-6:
            w = min(1.0, (t - sc["t0"]) / XF if sc["t0"] > 0 else 1.0,
                    (sc["t1"] - t) / XF if sc["t1"] < DUR else 1.0)
            w = ease(w)
            if w > 0:
                out += w * render_scene(sc, t, src)
                wsum += w
    out /= max(wsum, 1e-6)
    out = bloom(out, 0.30 + 0.10 * noise1(t * 1.6, 1.0))
    # warm key light slowly travelling across frame
    kx = W * (0.2 + 0.6 * (t / DUR))
    xs = np.arange(W, dtype=np.float32)
    key = 0.94 + 0.10 * np.exp(-((xs - kx) / (W * 0.5)) ** 2)
    out *= key[None, :, None]
    out *= vignette(0.55)[..., None]
    out *= exposure(t)
    # filmic shoulder + subtle split tone
    out = (1 - np.exp(-out * 1.7)) / (1 - math.exp(-1.7))
    out[..., 0] += 0.012 * (1 - out[..., 0])  # cool shadows
    out[..., 2] += 0.010 * out[..., 2]        # warm highlights
    out += np.random.default_rng(int(t * FPS)).normal(0, 0.008, (H, W, 1)).astype(np.float32)
    return np.clip(out, 0, 1)


# ---------------------------------------------------------------- typography (preview only)
TEXTS = [
    # start, end, text, size, y, font, tracking
    (0.9, 3.4, "FEUER. NEU GEDACHT.", 64, 0.80, "Inter-ExtraLight.otf", 14),
    (3.9, 6.6, "Flammen, die den Raum verwandeln", 46, 0.84, "Inter-Light.otf", 2),
    (7.1, 9.6, "Rundum-Blick aufs Feuer", 50, 0.16, "Inter-Light.otf", 3),
    (10.0, 12.2, "MATT. SCHWARZ. ZEITLOS.", 54, 0.84, "Inter-ExtraLight.otf", 12),
    (12.9, 15.0, "Wärme mit Stil.", 78, 0.80, "InterDisplay-Light.otf", 3),
    (13.4, 15.0, "JETZT IM FACHHANDEL ENTDECKEN", 30, 0.865, "Inter-Regular.otf", 8),
]
CREAM = (243, 230, 211)
_font_cache = {}


def font(name, size):
    k = (name, size)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(FONT_DIR + name, size)
    return _font_cache[k]


def draw_tracked(draw, text, f, y, tracking, alpha):
    widths = [draw.textlength(c, font=f) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = (W - total) / 2
    for c, cw in zip(text, widths):
        draw.text((x, y), c, font=f, fill=CREAM + (int(255 * alpha),))
        x += cw + tracking


def text_layer(t):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for t0, t1, txt, size, yrel, fname, trk in TEXTS:
        if not (t0 <= t <= t1):
            continue
        a = ease((t - t0) / 0.7) * (1 - ease((t - (t1 - 0.6)) / 0.6) if t1 < DUR else 1)
        rise = 18 * (1 - ease((t - t0) / 1.0))
        spread = trk + 6 * (1 - ease((t - t0) / 1.4))
        draw_tracked(d, txt, font(fname, size), H * yrel + rise, spread, a * exposure(t) ** 0.5)
    # logo placeholder on the end card (no client logo is rebuilt)
    if t >= 12.9:
        a = ease((t - 12.9) / 0.8) * exposure(t) ** 0.5
        bx, by, bw, bh = W / 2 - 170, H * 0.09, 340, 90
        d.rounded_rectangle((bx, by, bx + bw, by + bh), 8, outline=CREAM + (int(170 * a),), width=2)
        draw_tracked(d, "PLATZHALTER", font("Inter-Light.otf", 30), by + 26, 6, a * 0.8)
        draw_tracked(d, "LOGO", font("Inter-Regular.otf", 16), by + bh + 14, 6, a * 0.6)
    return layer


def composite_text(frame_rgb_u8, t):
    im = Image.fromarray(frame_rgb_u8).convert("RGBA")
    lay = text_layer(t)
    # soft shadow for legibility
    sh = lay.split()[3].point(lambda v: int(v * 0.55))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow.putalpha(sh)
    from PIL import ImageFilter
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    im = Image.alpha_composite(im, shadow)
    im = Image.alpha_composite(im, lay)
    return np.asarray(im.convert("RGB"))


# ---------------------------------------------------------------- main
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "base"
    out = {"base": "out/kamin_basis_9x16_stumm.mp4", "preview": "out/kamin_vorschau_9x16_stumm.mp4"}[mode]
    n = int(DUR * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow",
                           "-crf", "15", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
                          stdin=subprocess.PIPE)
    for i in range(n):
        t = i / FPS
        fr = (frame_at(t)[..., ::-1] * 255 + 0.5).astype(np.uint8)
        if mode == "preview":
            fr = composite_text(np.ascontiguousarray(fr), t)
        ff.stdin.write(np.ascontiguousarray(fr).tobytes())
        if i % 30 == 0:
            print(f"{mode}: {i}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("wrote", out)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "still":
        t = float(sys.argv[2])
        fr = (frame_at(t)[..., ::-1] * 255 + 0.5).astype(np.uint8)
        fr = composite_text(np.ascontiguousarray(fr), t)
        Image.fromarray(fr).save(f"out/still_{t:05.2f}.jpg", quality=90)
    else:
        main()
