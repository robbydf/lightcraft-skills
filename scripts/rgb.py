"""Mean R/G/B of a region (x0,x1,y0,y1 as fractions), for colour checks (signs, food, skin).

Usage (Bash, after lc-env.sh):  LCX rgb.py <file> x0,x1,y0,y1      -> prints R/G/B, e.g. 182.4/150.1/121.9
Needs Pillow and numpy. Samples every second pixel in both directions, like the old rgb.ps1.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lcargs import fix_argv  # noqa: E402
from lcimg import files, load_rgb, np, parse_region  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser(prog="rgb.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("region")
    a = ap.parse_args(fix_argv(argv, []))
    r = parse_region(a.region, None, "rgb.py")
    img = load_rgb(files([a.file])[0])
    h, w = img.shape[:2]
    c = img[round(r[2] * h):round(r[3] * h):2, round(r[0] * w):round(r[1] * w):2].reshape(-1, 3)
    if len(c) == 0:
        sys.exit("rgb.py: region too small")
    m = c.mean(axis=0, dtype=np.float64)
    print(f"{m[0]:.1f}/{m[1]:.1f}/{m[2]:.1f}")


if __name__ == "__main__":
    main(sys.argv[1:])
