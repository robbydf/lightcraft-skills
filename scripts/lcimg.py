"""Image helpers shared by measure.py, lfit.py, rgb.py, sbs.py and tiltprev.py (Pillow + numpy).

Install once:  python -m pip install --user pillow numpy   (python3 on macOS / Linux)
"""
import glob
import os
import re
import sys

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:  # pragma: no cover - depends on the machine
    sys.exit(f"{os.path.basename(sys.argv[0])}: needs Pillow and numpy ({e.name} is missing). "
             "Install them with: python -m pip install --user pillow numpy")

__all__ = ["np", "Image", "ImageDraw", "ImageFont", "parse_region", "files", "load_rgb", "gray",
           "font", "box", "save"]


def parse_region(s, default=None, what=""):
    """'x0,x1,y0,y1' (fractions of the frame) -> [x0, x1, y0, y1]. Empty -> default (None = required)."""
    if s is None or not str(s).strip():
        if default is None:
            sys.exit(f"{what} needs -Region x0,x1,y0,y1".strip())
        return list(default)
    parts = [p for p in re.split(r"[,\s]+", str(s).strip()) if p]
    try:
        r = [float(p) for p in parts]
    except ValueError:
        sys.exit(f"Region must be four numbers x0,x1,y0,y1 (got: {s})")
    if len(r) != 4 or r[0] >= r[1] or r[2] >= r[3] or any(v < 0 or v > 1 for v in r):
        sys.exit(f"Region must be x0,x1,y0,y1 with 0<=x0<x1<=1 and 0<=y0<y1<=1 (got: {','.join(parts)})")
    return r


def files(args):
    """Expand wildcards (the shell may not have) and fail loudly on a missing file."""
    out = []
    for a in args:
        if any(c in a for c in "*?["):
            m = sorted(glob.glob(a))
        else:
            m = [a] if os.path.isfile(a) else []
        if not m:
            sys.exit(f"missing file: {a}")
        out += [os.path.abspath(p) for p in m]
    return out


def load_rgb(path):
    """The image as an H x W x 3 uint8 array."""
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"))


def gray(a):
    """Luma 0..255 (0.299 R + 0.587 G + 0.114 B) as float32."""
    a = a.astype(np.float32)
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


_FONTS = {
    False: ["arial.ttf", "Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
            "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf", "LiberationSans-Regular.ttf"],
    True: ["arialbd.ttf", "Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
           "/Library/Fonts/Arial Bold.ttf", "DejaVuSans-Bold.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
           "LiberationSans-Bold.ttf"],
}


def font(points, bold=False):
    """A sans-serif font at `points` (96 dpi, like the old System.Drawing labels)."""
    px = max(8, round(points * 96 / 72))
    for name in _FONTS[bold] + _FONTS[False]:
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default(px)


def box(r, w, h):
    """Region fractions -> pixel box (left, top, right, bottom), rounded like PowerShell's [int]."""
    x0, y0 = round(r[0] * w), round(r[2] * h)
    return x0, y0, x0 + round((r[1] - r[0]) * w), y0 + round((r[3] - r[2]) * h)


def save(im, out, fmt):
    """Save as PNG or JPEG (quality 90), creating the folder."""
    out = os.path.abspath(out)
    d = os.path.dirname(out)
    if d:
        os.makedirs(d, exist_ok=True)
    if fmt == "PNG":
        im.save(out, "PNG")
    else:
        im.convert("RGB").save(out, "JPEG", quality=90)
    return out
