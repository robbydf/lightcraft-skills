"""Labelled BEFORE | AFTER side-by-side of one region, at most -MaxW px wide (for viewing on a phone).

Usage (Bash, after lc-env.sh):
  LCX sbs.py -Before ID-before.jpg -After ID-after.jpg -Region x0,x1,y0,y1 -Out ID-sbs.jpg [-MaxW 1600]
Needs Pillow and numpy. Prints "saved WxH".
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lcargs import fix_argv  # noqa: E402
from lcimg import Image, ImageDraw, box, files, font, parse_region, save  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser(prog="sbs.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-Before", required=True)
    ap.add_argument("-After", required=True)
    ap.add_argument("-Region", default="0,1,0,1")
    ap.add_argument("-Out", required=True)
    ap.add_argument("-MaxW", type=int, default=1600)
    a = ap.parse_args(fix_argv(argv, ["-Before", "-After", "-Region", "-Out", "-MaxW"]))
    r = parse_region(a.Region, (0, 1, 0, 1))
    before, after = files([a.Before, a.After])
    with Image.open(before) as A, Image.open(after) as B:
        ca = A.convert("RGB").crop(box(r, A.width, A.height))
        cb = B.convert("RGB").crop(box(r, B.width, B.height))
    cw = round((max(a.MaxW, 100) - 8) / 2)
    sc = cw / ca.width
    if sc > 1:
        sc, cw = 1.0, ca.width
    ch = max(1, round(ca.height * sc))
    o = Image.new("RGB", (2 * cw + 8, ch), "white")
    o.paste(ca.resize((cw, ch), Image.LANCZOS), (0, 0))
    o.paste(cb.resize((cw, ch), Image.LANCZOS), (cw + 8, 0))
    d = ImageDraw.Draw(o)
    f = font(18)
    d.text((6, 6), "BEFORE", fill="yellow", font=f)
    d.text((cw + 14, 6), "AFTER", fill="yellow", font=f)
    fmt = "PNG" if a.Out.lower().endswith(".png") else "JPEG"
    save(o, a.Out, fmt)
    print(f"saved {o.width}x{o.height}")


if __name__ == "__main__":
    main(sys.argv[1:])
