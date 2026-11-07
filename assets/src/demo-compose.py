"""Compose the README demo from frames captured by demo-capture.py.

Adds an animated cursor with click ripples, a status pill, character-by-
character typing reveals between captured frames, and a closing card. The
applicant is fictional (see demo-persona.json), so nothing is blurred. Writes
numbered PNG frames for ffmpeg.

    python3 demo-compose.py <capture_dir> <out_frames_dir> [--fps 20] [--encode <assets_dir>]
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

CAP = Path(sys.argv[1])
OUT = Path(sys.argv[2])
FPS = int(sys.argv[sys.argv.index("--fps") + 1]) if "--fps" in sys.argv else 20
OUT.mkdir(parents=True, exist_ok=True)
for old in OUT.glob("*.png"):
    old.unlink()

INK, PAPER, ACCENT = (15, 17, 21), (247, 245, 240), (232, 89, 12)
SF = "/System/Library/Fonts/SFNS.ttf"


def font(size, weight):
    f = ImageFont.truetype(SF, size)
    try:
        f.set_variation_by_axes([weight, min(max(size, 17), 96)])
    except Exception:
        pass
    return f


F_PILL = font(14, 650)
F_STEP = font(13, 500)
F_END = font(30, 720)
F_END2 = font(17, 500)

meta = json.loads((CAP / "meta.json").read_text())
COMPANY, ROLE = meta["company"], meta["role"]
DPR = meta.get("dpr", 1.0)
man = json.loads((CAP / "manifest.json").read_text())
for e in man:  # capture rects are CSS px; frames are device px
    if e.get("t"):
        e["t"] = [v * DPR for v in e["t"]]
    e["sy"] = e.get("sy", 0) * DPR


cache = {}


def load(i):
    if i not in cache:
        e = man[i]
        img = Image.open(e["img"]).convert("RGB")
        cache[i] = img
    return cache[i]


frames = []  # (base PIL image, cursor xy, ripple t or None, status, end card alpha)


def emit(img, cur, status, ripple=None, end=0.0):
    frames.append((img, cur, ripple, status, end))


def center(r, left=False):
    x, y, w, h = r
    return (x + min(60, w * 0.3), y + h * 0.6) if left else (x + w / 2, y + h / 2)


def ease(t):
    return t * t * (3 - 2 * t)


def reveal(a, b, steps):
    """Yield images that reveal the pixels that differ from a to b in reading order."""
    A = np.asarray(a, dtype=np.int16)
    B = np.asarray(b, dtype=np.int16)
    diff = np.abs(A - B).max(axis=2) > 24
    ys, xs = np.nonzero(diff)
    if len(ys) == 0 or len(ys) > 400_000:
        yield b
        return
    band = (ys - ys.min()) // 20
    order = np.lexsort((xs, band))
    key = np.empty(len(ys), dtype=np.int64)
    key[order] = np.arange(len(ys))
    for k in range(1, steps + 1):
        lim = len(ys) * k / steps
        sel = key < lim
        out = A.copy()
        out[ys[sel], xs[sel]] = B[ys[sel], xs[sel]]
        yield Image.fromarray(out.astype(np.uint8))


FAST = ("Education", "Eligibility", "Final questions", "Links")
speed = [1.0]


def secs(s):
    return max(1, int(round(s * speed[0] * FPS)))


cur = (480.0, 700.0)
prev_img = None
prev_i = None
for i, e in enumerate(man):
    img = load(i)
    k, status = e["kind"], e["status"]
    tgt = e.get("t")
    speed[0] = 0.5 if status in FAST else 0.85
    if k == "hold":
        for _ in range(secs(0.8)):
            emit(img, cur, status)
    elif k == "read":
        for _ in range(secs(0.9)):
            emit(img, cur, status)
    elif k == "scroll":
        n = secs(0.24)
        delta = int(round(e["sy"] - man[prev_i]["sy"]))
        H = img.height
        for s in range(n):
            t = ease((s + 1) / n)
            if 0 < delta < H:
                sh = int(round(delta * t))
                fr = Image.new("RGB", img.size)
                fr.paste(prev_img.crop((0, sh, img.width, H)), (0, 0))
                fr.paste(img.crop((0, H - delta, img.width, H - delta + sh)), (0, H - sh))
            elif delta >= H:
                sh = int(round(H * t))
                fr = Image.new("RGB", img.size)
                fr.paste(prev_img.crop((0, sh, img.width, H)), (0, 0))
                fr.paste(img.crop((0, 0, img.width, sh)), (0, H - sh))
            else:
                fr = Image.blend(prev_img, img, t)
            emit(fr, (cur[0], cur[1]), status)
    elif k in ("move", "menu", "final"):
        dest = center(tgt, left=(k == "move" and tgt[2] > 300))
        n = secs(0.26 if k != "menu" else 0.2)
        start = cur
        for s in range(n):
            t = ease((s + 1) / n)
            p = (start[0] + (dest[0] - start[0]) * t, start[1] + (dest[1] - start[1]) * t - math.sin(t * math.pi) * 18)
            emit(img, p, status)
        cur = dest
        if k == "final":
            speed[0] = 1.0
            for _ in range(secs(0.6)):
                emit(img, cur, "Ready to submit")
            n = secs(0.3)
            for s in range(n):
                emit(img, cur, "Ready to submit", end=(s + 1) / n)
            for _ in range(secs(1.9)):
                emit(img, cur, "Ready to submit", end=1.0)
        else:
            nr = secs(0.14)
            for s in range(nr):
                emit(img, cur, status, ripple=(s + 1) / (nr + 1))
    elif k == "type":
        base = prev_img
        last = man[i - 1].get("typed", 0) if man[i - 1]["kind"] == "type" else 0
        chars = max(1, e.get("typed", last + 4) - last)
        steps = max(1, min(4, chars // 4))
        if "Writing" in status:
            steps = 3
        for im in reveal(base, img, steps):
            emit(im, cur, status)
    elif k in ("picked",):
        for _ in range(secs(0.14)):
            emit(img, cur, status)
    else:
        emit(img, cur, status)
    prev_img, prev_i = img, i


# ---------- overlay drawing ----------
def cursor_layer(draw, p):
    x, y = p
    pts = [(0, 0), (0, 22), (5.5, 17), (9.5, 26), (13, 24.5), (9, 16), (16, 16)]
    poly = [(x + a, y + b) for a, b in pts]
    draw.polygon([(px + 1.5, py + 2) for px, py in poly], fill=(0, 0, 0, 60))
    draw.polygon(poly, fill=(15, 17, 21, 255), outline=(255, 255, 255, 255), width=2)


def pill(draw, status):
    title = f"job-agent · filling {COMPANY} · {ROLE}"
    tw = draw.textlength(title, font=F_PILL)
    sw = draw.textlength(status, font=F_STEP)
    w = int(max(tw, sw + 22) + 44)
    x1 = 944
    x0 = x1 - w
    y0, y1 = 16, 70
    draw.rounded_rectangle((x0 + 2, y0 + 3, x1 + 2, y1 + 3), 14, fill=(0, 0, 0, 40))
    draw.rounded_rectangle((x0, y0, x1, y1), 14, fill=INK + (245,))
    draw.ellipse((x0 + 16, y0 + 15, x0 + 26, y0 + 25), fill=ACCENT + (255,))
    draw.text((x0 + 34, y0 + 11), title, font=F_PILL, fill=(255, 255, 255, 255))
    draw.text((x0 + 34, y0 + 32), status, font=F_STEP, fill=(214, 210, 200, 255))


def end_card(draw, a):
    if a <= 0:
        return
    W, H = 960, 800
    w, h = 580, 116
    x0, y0 = (W - w) // 2, 250
    al = int(250 * a)
    draw.rounded_rectangle((x0 + 3, y0 + 5, x0 + w + 3, y0 + h + 5), 18, fill=(0, 0, 0, int(50 * a)))
    draw.rounded_rectangle((x0, y0, x0 + w, y0 + h), 18, fill=PAPER + (al,), outline=INK + (al,), width=2)
    draw.rectangle((x0 + 28, y0 + 28, x0 + 34, y0 + h - 28), fill=ACCENT + (al,))
    draw.text((x0 + 52, y0 + 24), "Stopped at Submit.", font=F_END, fill=INK + (al,))
    draw.text((x0 + 52, y0 + 68), "You're in control. Auto-submit is off by default.", font=F_END2, fill=(70, 72, 78, al))


for n, (img, p, rip, status, end) in enumerate(frames):
    canvas = img.convert("RGBA")
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    if rip is not None:
        r = 6 + 22 * rip
        a = int(200 * (1 - rip))
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), outline=ACCENT + (a,), width=3)
        d.ellipse((p[0] - 7, p[1] - 7, p[0] + 7, p[1] + 7), fill=ACCENT + (int(110 * (1 - rip)),))
    pill(d, status)
    end_card(d, end)
    cursor_layer(d, p)
    Image.alpha_composite(canvas, ov).convert("RGB").save(OUT / f"{n:05d}.png")

print(f"{len(frames)} frames, {len(frames) / FPS:.1f}s at {FPS} fps")


# ---------- encode ----------
if "--encode" in sys.argv:
    import subprocess

    dest = Path(sys.argv[sys.argv.index("--encode") + 1])
    gif_w = int(sys.argv[sys.argv.index("--gif-width") + 1]) if "--gif-width" in sys.argv else 880
    gif_fps = int(sys.argv[sys.argv.index("--gif-fps") + 1]) if "--gif-fps" in sys.argv else 15
    src = ["-framerate", str(FPS), "-i", str(OUT / "%05d.png")]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *src, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "18", "-preset", "slow", "-movflags", "+faststart", str(dest / "demo.mp4")], check=True)
    vf = (f"fps={gif_fps},scale={gif_w}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *src, "-vf", vf, "-loop", "0", str(dest / "demo.gif")], check=True)
    for f in ("demo.mp4", "demo.gif"):
        print(f, f"{(dest / f).stat().st_size / 1e6:.2f} MB")
