"""Measure JPEG/PNG renders exported from LightCraft (needs Pillow and numpy).

Modes:
  sharp : Laplacian variance (higher = sharper). Noise inflates it: rank frames of ONE burst only,
          all in the same develop state, and confirm the winner with crops.
  tilt  : median lean of strong near-vertical edges (deg, + = top leans right) and median slope of
          near-horizontal edges. Trust it only when n >= ~2000; otherwise widen the region.
  mean  : mean luma 0..255 of the region (subject vs background brightness). Needs -Region.
  clip  : % of pixels in the region with any RGB channel at 255 (blown) and with all channels at 0 (crushed).
  crops : stacks the same region of up to 4 files into one PNG (-Out) for side-by-side viewing.
  sheet : contact sheet: up to 12 whole frames tiled -Cols across (default 3), each -Tile px wide
          (default 600) and labelled with its file name, into one PNG (-Out). 9 per sheet reads well.
  batch : one list file, one measurement per line: <image>|x0,x1,y0,y1[|label]. Prints mean, blown
          and crushed for every line (before/after on many photos in one start).
  grid  : one file; draws labelled coordinate lines over the region (every 0.01, labels every 0.05)
          and writes a PNG (-Out), for reading guide / brush / mask-point coordinates.

Usage (Bash, after lc-env.sh):  M tilt dir/*.jpg -Region 0.1,0.9,0.05,0.72
                                M mean a.jpg -Region 0,1,0,1
                                M grid a.jpg -Region 0.3,0.6,0.2,0.8 -Out a-grid.png
Region = x0,x1,y0,y1 as fractions of the frame (0 <= x0 < x1 <= 1, 0 <= y0 < y1 <= 1).
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lcargs import fix_argv  # noqa: E402
from lcimg import Image, ImageDraw, box, files, font, gray, load_rgb, np, parse_region, save, native_path  # noqa: E402

MODES = ("sharp", "tilt", "mean", "clip", "crops", "sheet", "batch", "grid")


class Cache:
    """Keeps the last few decoded images (batch mode measures several boxes per image)."""

    def __init__(self, n=3):
        self.n, self.d = n, {}

    def rgb(self, path):
        if path not in self.d:
            if len(self.d) >= self.n:
                self.d.pop(next(iter(self.d)))
            self.d[path] = load_rgb(path)
        return self.d[path]


CACHE = Cache()


def sharp(path, r):
    g = gray(CACHE.rgb(path))
    h, w = g.shape
    y0, y1 = max(1, int(r[2] * h)), min(h - 1, int(r[3] * h))
    x0, x1 = max(1, int(r[0] * w)), min(w - 1, int(r[1] * w))
    if y1 <= y0 or x1 <= x0:
        return "sharp=NA (region too small)"
    lap = (4 * g[y0:y1, x0:x1] - g[y0:y1, x0 - 1:x1 - 1] - g[y0:y1, x0 + 1:x1 + 1]
           - g[y0 - 1:y1 - 1, x0:x1] - g[y0 + 1:y1 + 1, x0:x1])
    return f"sharp={lap.var(dtype=np.float64):.0f}"


def mean(path, r):
    g = gray(CACHE.rgb(path))
    h, w = g.shape
    c = g[int(r[2] * h):min(h, int(r[3] * h)), int(r[0] * w):min(w, int(r[1] * w))]
    if c.size == 0:
        return "mean=NA (region too small)"
    return f"mean={c.mean(dtype=np.float64):.1f}"


def clip(path, r):
    a = CACHE.rgb(path)
    h, w = a.shape[:2]
    c = a[int(r[2] * h):min(h, int(r[3] * h)), int(r[0] * w):min(w, int(r[1] * w))]
    n = c.shape[0] * c.shape[1]
    if n == 0:
        return "clip=NA (region too small)"
    hi = int((c == 255).any(axis=-1).sum())
    lo = int((c == 0).all(axis=-1).sum())
    return f"blown={100.0 * hi / n:.2f}% crushed={100.0 * lo / n:.2f}%"


def tilt(path, r):
    g = gray(CACHE.rgb(path))
    h, w = g.shape
    y0, y1 = max(1, int(r[2] * h)), min(h - 1, int(r[3] * h))
    x0, x1 = max(1, int(r[0] * w)), min(w - 1, int(r[1] * w))
    if y1 <= y0 or x1 <= x0:
        return "vertical_tilt=NA (n=0) horizontal_slope=NA (n=0)"

    def L(dy, dx):
        return g[y0 + dy:y1 + dy, x0 + dx:x1 + dx]

    gx = (L(-1, 1) + 2 * L(0, 1) + L(1, 1)) - (L(-1, -1) + 2 * L(0, -1) + L(1, -1))
    gy = (L(1, -1) + 2 * L(1, 0) + L(1, 1)) - (L(-1, -1) + 2 * L(-1, 0) + L(-1, 1))
    strong = np.hypot(gx, gy) >= 120
    a = np.degrees(np.arctan2(gy[strong].astype(np.float64), gx[strong].astype(np.float64)))
    av = a.copy()
    av[av > 90] -= 180
    av[av < -90] += 180
    v = np.sort(-av[np.abs(av) < 12])
    ah = a - 90
    ah[ah > 90] -= 180
    ah[ah < -90] += 180
    hz = np.sort(ah[np.abs(ah) < 12])
    vt = f"{round(float(v[len(v) // 2]), 2) + 0.0:.2f}deg" if len(v) else "NA"   # + 0.0: no "-0.00"
    ht = f"{round(float(hz[len(hz) // 2]), 2) + 0.0:.2f}deg" if len(hz) else "NA"
    return f"vertical_tilt={vt} (n={len(v)}) horizontal_slope={ht} (n={len(hz)})"


def need_out(mode, out):
    if not out:
        sys.exit(f"{mode} needs -Out file.png")
    if not out.lower().endswith(".png"):
        sys.exit("-Out must end in .png")


def crops(fs, r, out):
    if len(fs) > 4:
        sys.exit(f"crops takes at most 4 files (got {len(fs)}); split them into sheets of 4")
    with Image.open(fs[0]) as first:
        W, H = first.size
    cw, ch = round((r[1] - r[0]) * W), round((r[3] - r[2]) * H)
    sheet = Image.new("RGB", (cw, ch * len(fs)), "black")
    d = ImageDraw.Draw(sheet)
    f = font(16)
    for i, p in enumerate(fs):
        with Image.open(p) as src:
            x, y = round(r[0] * src.width), round(r[2] * src.height)
            sheet.paste(src.convert("RGB").crop((x, y, x + cw, y + ch)), (0, i * ch))
        d.text((5, i * ch + 5), os.path.basename(p), fill="yellow", font=f)
    return f"saved {save(sheet, out, 'PNG')}"


def contact_sheet(fs, out, cols, tile):
    if len(fs) > 12:
        sys.exit(f"sheet takes at most 12 files (got {len(fs)}); 9 per sheet reads best")
    n = len(fs)
    c = min(cols, n)
    rows = math.ceil(n / c)
    th = round(tile * 2 / 3)  # 3:2 cells; portrait frames are fitted inside (narrower), not stretched
    sheet = Image.new("RGB", (c * tile, rows * th), "black")
    d = ImageDraw.Draw(sheet)
    f = font(14, bold=True)
    for i, p in enumerate(fs):
        with Image.open(p) as src:
            tw, tht = tile, round(tile * src.height / src.width)
            if tht > th:
                tht, tw = th, round(th * src.width / src.height)
            x = (i % c) * tile + round((tile - tw) / 2)
            y = (i // c) * th + round((th - tht) / 2)
            sheet.paste(src.convert("RGB").resize((tw, tht), Image.LANCZOS), (x, y))
        lab = os.path.splitext(os.path.basename(p))[0]
        l, t, rr, b = d.textbbox((x + 3, y + 3), lab, font=f)
        d.rectangle((x + 3, y + 3, rr + 2, b + 2), fill="black")
        d.text((x + 3, y + 3), lab, fill="yellow", font=f)
    return f"saved {save(sheet, out, 'PNG')} ({n} frames, {c} x {rows})"


def batch(listfile):
    base = os.path.dirname(listfile)
    lines = []
    with open(listfile, encoding="utf-8-sig") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = line.split("|")
            if len(p) < 2:
                lines.append(f"line {ln}: need <image>|x0,x1,y0,y1[|label]")
                continue
            img = native_path(p[0].strip())
            if not os.path.isabs(img):
                img = os.path.join(base, img)
            if not os.path.isfile(img):
                lines.append(f"line {ln}: missing file {img}")
                continue
            try:
                b = [float(v) for v in p[1].replace(" ", ",").split(",") if v]
            except ValueError:
                b = []
            if len(b) != 4 or b[0] >= b[1] or b[2] >= b[3]:
                lines.append(f"line {ln}: bad region {p[1]}")
                continue
            lab = p[2].strip() if len(p) > 2 else os.path.basename(img)
            lines.append(f"{lab}  {mean(img, b)} {clip(img, b)}  [{','.join(f'{v:g}' for v in b)}]")
    return lines


def grid(path, r, out):
    with Image.open(path) as src:
        W, H = src.size
        im = src.convert("RGB").crop(box(r, W, H)).convert("RGBA")
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    f = font(9)
    thin, bold = (0, 255, 255, 90), (0, 255, 255, 200)
    for v in range(math.ceil(r[0] * 100 - 1e-9), math.floor(r[1] * 100 + 1e-9) + 1):
        x = (v / 100 - r[0]) * W
        d.line([(x, 0), (x, im.height)], fill=bold if v % 5 == 0 else thin, width=1)
        if v % 5 == 0:
            d.text((x + 1, 2), f"{v / 100:.2f}", fill="yellow", font=f)
    for v in range(math.ceil(r[2] * 100 - 1e-9), math.floor(r[3] * 100 + 1e-9) + 1):
        y = (v / 100 - r[2]) * H
        d.line([(0, y), (im.width, y)], fill=bold if v % 5 == 0 else thin, width=1)
        if v % 5 == 0:
            d.text((2, y + 1), f"{v / 100:.2f}", fill="yellow", font=f)
    return f"saved {save(Image.alpha_composite(im, over), out, 'PNG')}"


def main(argv):
    ap = argparse.ArgumentParser(prog="measure.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=MODES)
    ap.add_argument("files", nargs="+")
    ap.add_argument("-Region", default=None)
    ap.add_argument("-Out", default="")
    ap.add_argument("-Cols", type=int, default=3)
    ap.add_argument("-Tile", type=int, default=600)
    a = ap.parse_args(fix_argv(argv, ["-Region", "-Out", "-Cols", "-Tile"]))
    fs = files(a.files)
    m = a.mode
    out = []
    if m == "sharp":
        r = parse_region(a.Region, (0.15, 0.85, 0.15, 0.70))
        out = [f"{os.path.basename(f)}  {sharp(f, r)}" for f in fs]
    elif m == "tilt":
        r = parse_region(a.Region, (0.1, 0.9, 0.05, 0.72))
        out = [f"{os.path.basename(f)}  {tilt(f, r)}" for f in fs]
    elif m == "mean":
        r = parse_region(a.Region, None, "mean")
        out = [f"{os.path.basename(f)}  {mean(f, r)}" for f in fs]
    elif m == "clip":
        r = parse_region(a.Region, (0, 1, 0, 1))
        out = [f"{os.path.basename(f)}  {clip(f, r)}" for f in fs]
    elif m == "crops":
        r = parse_region(a.Region, None, "crops")
        need_out(m, a.Out)
        out = [crops(fs, r, a.Out)]
    elif m == "sheet":
        need_out(m, a.Out)
        out = [contact_sheet(fs, a.Out, max(1, a.Cols), max(50, a.Tile))]
    elif m == "batch":
        if len(fs) != 1:
            sys.exit("batch takes one list file: <image>|x0,x1,y0,y1[|label] per line")
        out = batch(fs[0])
    elif m == "grid":
        if len(fs) != 1:
            sys.exit("grid takes exactly one file")
        need_out(m, a.Out)
        out = [grid(fs[0], parse_region(a.Region, (0, 1, 0, 1)), a.Out)]
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1:])
