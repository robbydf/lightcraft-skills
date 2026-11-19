"""Fit a straight edge (pole, roofline, horizon) near the line x0,y0 -> x1,y1 (fractions of the frame).

Prints its angle in degrees: more reliable than `M tilt` for one known edge.
Usage (Bash, after lc-env.sh):  LCX lfit.py <file> x0 y0 x1 y1 [-Band 12]
Needs Pillow and numpy.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lcargs import fix_argv  # noqa: E402
from lcimg import files, gray, load_rgb, np  # noqa: E402


def fit(path, fx0, fy0, fx1, fy1, band):
    g = gray(load_rgb(path))
    h, w = g.shape

    def L(x, y):
        return g[np.clip(y, 0, h - 1), np.clip(x, 0, w - 1)].astype(np.float64)

    X0, Y0, X1, Y1 = fx0 * w, fy0 * h, fx1 * w, fy1 * h
    horiz = abs(X1 - X0) >= abs(Y1 - Y0)
    n = int(abs(X1 - X0) if horiz else abs(Y1 - Y0))
    k = np.arange(0, n, 2)
    if len(k) == 0:
        return "too few points 0"
    t = k / n
    px, py = X0 + (X1 - X0) * t, Y0 + (Y1 - Y0) * t
    o = np.arange(-band, band + 1)
    if horiz:
        x = np.repeat(px.astype(int)[:, None], len(o), axis=1)
        y = py.astype(int)[:, None] + o[None, :]
        gr = np.abs((L(x - 1, y + 1) + 2 * L(x, y + 1) + L(x + 1, y + 1))
                    - (L(x - 1, y - 1) + 2 * L(x, y - 1) + L(x + 1, y - 1)))
    else:
        x = px.astype(int)[:, None] + o[None, :]
        y = np.repeat(py.astype(int)[:, None], len(o), axis=1)
        gr = np.abs((L(x + 1, y - 1) + 2 * L(x + 1, y) + L(x + 1, y + 1))
                    - (L(x - 1, y - 1) + 2 * L(x - 1, y) + L(x - 1, y + 1)))
    best = gr.max(axis=1)
    bo = o[gr.argmax(axis=1)]
    keep = best > 150
    if horiz:
        u, v = px[keep], (py + bo)[keep]
    else:
        u, v = py[keep], (px + bo)[keep]
    if len(u) < 20:
        return f"too few points {len(u)}"
    slope = ic = 0.0
    for it in range(4):
        sel = np.ones(len(u), bool) if it == 0 else np.abs(v - (slope * u + ic)) <= 2.5
        m = int(sel.sum())
        us, vs = u[sel], v[sel]
        den = m * (us * us).sum() - us.sum() ** 2
        if m < 2 or den == 0:
            return f"fit failed (inliers={m}/{len(u)})"
        slope = (m * (us * vs).sum() - us.sum() * vs.sum()) / den
        ic = (vs.sum() - slope * us.sum()) / m
    inl = int((np.abs(v - (slope * u + ic)) <= 2.5).sum())
    ang = math.degrees(math.atan(slope))
    kind = ("horizontal(y down+ = descends right)" if horiz
            else "vertical(+ = bottom moves right i.e. top leans left)")
    return f"{kind} slope_deg={ang:.2f} inliers={inl}/{len(u)}"


def main(argv):
    ap = argparse.ArgumentParser(prog="lfit.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    for c in ("x0", "y0", "x1", "y1"):
        ap.add_argument(c, type=float)
    ap.add_argument("-Band", type=int, default=12)
    a = ap.parse_args(fix_argv(argv, ["-Band"]))
    print(fit(files([a.file])[0], a.x0, a.y0, a.x1, a.y1, max(1, a.Band)))


if __name__ == "__main__":
    main(sys.argv[1:])
