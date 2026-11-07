"""Compose demo GIF frames: browser window + step caption, one accent colour."""
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FR = Path(sys.argv[1])
OUT = Path(sys.argv[2])
INK, PAPER, ACCENT, LINE, MUTED = (15, 17, 21), (247, 245, 240), (232, 89, 12), (222, 218, 208), (110, 112, 118)
SF = "/System/Library/Fonts/SFNS.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"


def font(path, size, weight=None):
    f = ImageFont.truetype(path, size)
    if weight:
        try:
            f.set_variation_by_axes([100, min(max(size,17),96), 400, weight])
        except Exception:
            pass
    return f


f_cap = font(SF, 22, 600)
f_step = font(SF, 15, 700)
f_url = font(MONO, 13)

frames = json.loads((FR / "frames.json").read_text())
VW, VH = 820, 560
M, TB, CB = 28, 40, 64
CW, CH = VW + 2 * M, M + TB + VH + CB + 10
STEPS = ["Scan", "Filter", "Fill", "Upload", "Dropdowns", "Essay", "Consent", "Stops"]

out, durs = [], []
for fr in frames:
    shot = Image.open(fr["file"]).convert("RGB").resize((VW, VH), Image.LANCZOS)
    c = Image.new("RGB", (CW, CH), PAPER)
    d = ImageDraw.Draw(c)
    x0, y0 = M, M
    # window shell
    d.rounded_rectangle([x0 - 1, y0 - 1, x0 + VW + 1, y0 + TB + VH + 1], 12, fill=LINE)
    d.rounded_rectangle([x0, y0, x0 + VW, y0 + TB + 12], 11, fill=(236, 233, 226))
    d.rectangle([x0, y0 + TB, x0 + VW, y0 + TB + VH], fill="white")
    for i, col in enumerate([(205, 200, 190)] * 3):
        d.ellipse([x0 + 16 + i * 18, y0 + 15, x0 + 26 + i * 18, y0 + 25], fill=col)
    d.rounded_rectangle([x0 + 90, y0 + 9, x0 + VW - 90, y0 + 31], 7, fill="white")
    url = fr["url"].replace("http://", "")
    d.text((x0 + 104, y0 + 13), url, font=f_url, fill=MUTED)
    c.paste(shot, (x0, y0 + TB))
    # caption
    cap = fr["caption"]
    head, _, rest = cap.partition(":")
    cy = y0 + TB + VH + 20
    if rest:
        tag = head.strip().upper()
        tw = d.textlength(tag, font=f_step)
        d.rounded_rectangle([x0, cy, x0 + tw + 20, cy + 28], 6, fill=ACCENT)
        d.text((x0 + 10, cy + 5), tag, font=f_step, fill="white")
        r = rest.strip(); d.text((x0 + tw + 34, cy + 1), r[:1].upper() + r[1:], font=f_cap, fill=INK)
    else:
        d.rounded_rectangle([x0, cy, x0 + 14, cy + 28], 4, fill=ACCENT)
        d.text((x0 + 26, cy + 1), cap, font=f_cap, fill=INK)
    out.append(c)
    durs.append(int(fr["hold"]) * 260)

# palette shared across frames for stable colours
pal_src = Image.new("RGB", (CW, CH * 3))
for i, k in enumerate([0, len(out) // 2, len(out) - 1]):
    pal_src.paste(out[k], (0, CH * i))
pal = pal_src.quantize(colors=128, method=Image.MEDIANCUT)
q = [im.quantize(palette=pal, dither=Image.NONE) for im in out]
q[0].save(OUT, save_all=True, append_images=q[1:], duration=durs, loop=0, optimize=True, disposal=1)
print(OUT, OUT.stat().st_size // 1024, "KB", len(q), "frames", sum(durs) / 1000, "s")
out[-1].save(OUT.with_name("demo-last.png"))
