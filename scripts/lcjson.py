"""Read LightCraft CLI output (JSON on stdin) for the edit skill: history cursor, crop, masks.

Usage (pipe one CLI call into it; standard library only, run with python -I):
  "$CLI" run --connect history.list id=ID  | python -I "$LC_SCRIPTS/lcjson.py" cursor   # 12, or null
  "$CLI" run --connect develop.get id=ID   | python -I "$LC_SCRIPTS/lcjson.py" crop     # angle, crop %
  "$CLI" run --connect develop.get id=ID   | python -I "$LC_SCRIPTS/lcjson.py" masks    # mask count
  "$CLI" run --connect develop.get id=ID   | python -I "$LC_SCRIPTS/lcjson.py" geometry # upright etc.
  "$CLI" run --connect develop.get id=ID   | python -I "$LC_SCRIPTS/lcjson.py" seg NAME # "MASKID PARTS READY"
                                             (the mask called NAME; READY = parts with SAM `seg` data)

The CLI prints a blank line or several JSON lines (one per command, e.g. after library.select); this
reads the last line whose "command" matches, so `library.select 'ids=[ID]' history.list` works too.
`crop` prints e.g. `angle=-3.75 crop_per_edge=4.5% area_kept=82.0% constrain_crop=true upright=off`:
crop_per_edge is the largest of the four edges' cut, in % of the frame. Exit 1 with a message if the
command failed or the output has no such result.
"""
import json
import sys

WANT = {"cursor": "history.list", "crop": "develop.get", "masks": "develop.get", "geometry": "develop.get",
        "seg": "develop.get"}


def result(text, command):
    found = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("command") != command:
            continue
        if not o.get("ok", True):
            sys.exit(f"lcjson: {command} failed: {o.get('error')}")
        found = o.get("result") or {}
    if found is None:
        sys.exit(f"lcjson: no {command} result in the input")
    return found


def crop_line(r):
    c = r.get("crop") or {}
    g = c.get("geometry") or {}
    rect = g.get("rect") or {"x0": 0, "x1": 1, "y0": 0, "y1": 1}
    cuts = [rect["x0"], 1 - rect["x1"], rect["y0"], 1 - rect["y1"]]
    area = (rect["x1"] - rect["x0"]) * (rect["y1"] - rect["y0"])
    geo = r.get("geometry") or {}
    return (f"angle={g.get('angle', 0)} crop_per_edge={max(cuts) * 100:.1f}% area_kept={area * 100:.1f}% "
            f"constrain_crop={str(bool(geo.get('constrain_crop'))).lower()} upright={geo.get('upright', 'off')}")


def main(argv):
    if not argv or argv[0] not in WANT or len(argv) != (2 if argv[0] == "seg" else 1):
        sys.exit(__doc__)
    what = argv[0]
    r = result(sys.stdin.read(), WANT[what])
    if what == "cursor":
        print("null" if r.get("cursor") is None else r["cursor"])
    elif what == "crop":
        print(crop_line(r))
    elif what == "seg":
        m = [x for x in (r.get("masks") or []) if x.get("name") == argv[1]]
        if not m:
            print("none 0 0")
        else:
            parts = m[-1].get("components") or []
            print(m[-1].get("id"), len(parts), sum(1 for c in parts if (c.get("shape") or {}).get("seg")))
    elif what == "masks":
        print(len(r.get("masks") or []))
    else:
        g = r.get("geometry") or {}
        print(" ".join(f"{k}={json.dumps(g.get(k))}" for k in
                       ("upright", "constrain_crop", "rotate", "vertical", "horizontal", "scale")))


if __name__ == "__main__":
    main(sys.argv[1:])
