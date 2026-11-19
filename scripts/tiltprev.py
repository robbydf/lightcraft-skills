"""Tilt previews: the frame rotated about its centre by each angle, for the user to pick one.

Positive = clockwise, like crop.straighten. Shows -Region (x0,x1,y0,y1 fractions of the frame) of
each rotated frame, with vertical guide lines, labelled with its angle.
Use it when measurements cannot settle a tilt (tapered towers, lit buildings at night): show the
sheet to the user on a card and let them pick, then refine with 1-degree steps around the pick.

Usage (Bash, after lc-env.sh):
  LCX tiltprev.py -In ID.jpg -Out ID-tilt.jpg [-Angles -6,-4,-2,0,2,4,6] [-Region "x0,x1,y0,y1"] [-W 900] [-Cols 2]
Needs Pillow and numpy. Prints "saved <file>".
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lcargs import fix_argv  # noqa: E402
from lcimg import Image, ImageDraw, files, font, parse_region, save  # noqa: E402

BG = (40, 40, 40)


def label(a):
    if a == 0:
        return "as is (0)"
    return f"+{a:g} deg (clockwise)" if a > 0 else f"{a:g} deg (counter-clockwise)"


def main(argv):
    ap = argparse.ArgumentParser(prog="tiltprev.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-In", required=True)
    ap.add_argument("-Out", required=True)
    ap.add_argument("-Angles", default="-6,-4,-2,0,2,4,6")
    ap.add_argument("-Region", default="0,1,0,1")
    ap.add_argument("-W", type=int, default=900)
    ap.add_argument("-Cols", type=int, default=1)
    a = ap.parse_args(fix_argv(argv, ["-In", "-Out", "-Angles", "-Region", "-W", "-Cols"]))
    try:
        angles = [float(s) for s in a.Angles.replace(" ", ",").split(",") if s]
    except ValueError:
        sys.exit(f"-Angles must be numbers separated by commas (got: {a.Angles})")
    if not angles:
        sys.exit("-Angles is empty")
    r = parse_region(a.Region, (0, 1, 0, 1))
    cols = max(1, a.Cols)
    with Image.open(files([a.In])[0]) as src0:
        src = src0.convert("RGB")
    sw, sh = src.size
    rx0, ry0 = r[0] * sw, r[2] * sh
    rw, rh = (r[1] - r[0]) * sw, (r[3] - r[2]) * sh
    cw = max(50, a.W)
    ch = max(1, round(rh * cw / rw))
    rows = math.ceil(len(angles) / cols)
    sheet = Image.new("RGB", (cw * cols + 8 * (cols - 1), (ch + 34) * rows), BG)
    d = ImageDraw.Draw(sheet)
    f = font(16, bold=True)
    for i, ang in enumerate(angles):
        # PIL rotates counter-clockwise for positive angles, so negate to match crop.straighten.
        rot = src.rotate(-ang, resample=Image.BICUBIC, center=(sw / 2, sh / 2), fillcolor=BG)
        tile = rot.crop((round(rx0), round(ry0), round(rx0 + rw), round(ry0 + rh))).resize((cw, ch), Image.LANCZOS)
        over = Image.new("RGBA", tile.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(over)
        for k in range(1, 12):
            x = int(cw * k / 12)
            od.line([(x, 0), (x, ch)], fill=(0, 255, 255, 150), width=1)
        tile = Image.alpha_composite(tile.convert("RGBA"), over).convert("RGB")
        x0, y0 = (i % cols) * (cw + 8), (i // cols) * (ch + 34)
        sheet.paste(tile, (x0, y0 + 34))
        d.text((x0 + 4, y0 + 4), label(ang), fill="yellow", font=f)
    out = save(sheet, a.Out, "PNG" if a.Out.lower().endswith(".png") else "JPEG")
    print(f"saved {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
