"""Group LightCraft photos into bursts (>= 2 frames, each <= 1 s after the previous) and singles.

Usage:
  "$CLI" run --connect catalog.query limit=100000 > photos.json          # whole library
  python -I bursts.py photos.json [--gap 1] [--at 2025-06-14T14:05] [--day 2025-06-14]
                      [--bursts-only] [--json] [--log RUN/log.jsonl]
                      [--chunks --max-groups 25 --max-frames 120 [--out DIR]]

Input: the JSON line printed by `lightcraft-cli run --connect catalog.query ...`.
Text output: one line per group: kind, frame count, first capture time, id=filename pairs, and
rated=/flagged=/edited= ids. A group's key is its first photo id.
--log      drop groups whose key is already in the run log (resume).
--chunks   split the remaining groups into numbered chunks for subagents; chunks never cross a day,
           and a tail chunk of <= 6 frames is folded into the previous chunk of the same day.
           Prints JSON lines {"chunk": n, "day": d, "groups": count, "frames": count, "lines": [...]}.
--out DIR  with --chunks: also write DIR/chunkN.txt (one group line per line), deleting old ones.
"""
import argparse
import json
import sys
import re
from datetime import datetime


def parse_time(s):
    """ISO time as LightCraft writes it, on any Python 3.9+ (before 3.11 fromisoformat needs a 3- or
    6-digit fraction and no 'Z'). The wall-clock time is kept and any offset dropped."""
    s = s.strip()
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    m = re.match(r"^(.*?[T ]\d\d:\d\d:\d\d)\.(\d+)(.*)$", s)
    if m:
        s = f"{m.group(1)}.{(m.group(2) + '000000')[:6]}{m.group(3)}"
    t = datetime.fromisoformat(s)
    return t.replace(tzinfo=None)  # compare as written: a mix of 'Z' and plain times must not crash


def load_photos(path):
    with open(path, encoding="utf-8-sig") as f:
        line = next((l for l in f if l.strip()), None)
    if line is None:
        sys.exit(f"{path} is empty: did catalog.query fail? (run it again without redirecting)")
    data = json.loads(line)
    if data.get("ok") is False:
        sys.exit("catalog.query failed: " + str(data.get("error")))
    return data["result"]["photos"] if "result" in data else data["photos"]


def group_photos(photos, gap):
    # Virtual copies share capture time with their master and would form a false burst.
    photos = [p for p in photos if p.get("captured") and not p.get("deleted") and not p.get("copyOf")]
    for p in photos:
        p["_t"] = parse_time(p["captured"])
    # EXIF capture time is whole seconds; file name breaks ties within a second.
    photos.sort(key=lambda p: (p["_t"], p["fileName"]))
    groups, cur = [], []
    for p in photos:
        if cur and (p["_t"] - cur[-1]["_t"]).total_seconds() > gap:
            groups.append(cur)
            cur = []
        cur.append(p)
    if cur:
        groups.append(cur)
    return [
        {
            "key": g[0]["id"],
            "kind": "burst" if len(g) >= 2 else "single",
            "count": len(g),
            "captured": g[0]["captured"],
            "day": g[0]["captured"][:10],
            "ids": [p["id"] for p in g],
            "files": [p["fileName"] for p in g],
            "rated": [p["id"] for p in g if p.get("rating")],
            "flagged": [p["id"] for p in g if p.get("flag", "none") not in ("none", None)],
            "edited": [p["id"] for p in g if p.get("edited")],
        }
        for g in groups
    ]


def logged_keys(path):
    keys = set()
    try:
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    if "group" in d:  # runstate amend lines have none
                        keys.add(d["group"])
    except FileNotFoundError:
        pass
    return keys


def fmt(g):
    pairs = " ".join(f"{i}={n.rsplit('.', 1)[0]}" for i, n in zip(g["ids"], g["files"]))
    extra = "".join(f" {k}={','.join(map(str, g[k]))}" for k in ("rated", "flagged", "edited") if g[k])
    return f"{g['kind']:6} {g['count']:3}  {g['captured']}  {pairs}{extra}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--gap", type=float, default=1.0, help="max seconds between frames of a burst")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--at", help="only groups whose first capture time starts with this")
    ap.add_argument("--day", help="only groups starting on this day (YYYY-MM-DD)")
    ap.add_argument("--bursts-only", action="store_true", help="hide single photos")
    ap.add_argument("--log", help="run log (log.jsonl): skip groups already logged")
    ap.add_argument("--chunks", action="store_true", help="split remaining groups into chunks")
    ap.add_argument("--max-groups", type=int, default=25)
    ap.add_argument("--max-frames", type=int, default=120)
    ap.add_argument("--out", help="with --chunks: write DIR/chunkN.txt files")
    a = ap.parse_args()

    out = group_photos(load_photos(a.path), a.gap)
    total = len(out)
    if a.log:
        done = logged_keys(a.log)
        out = [g for g in out if g["key"] not in done]
    if a.at:
        out = [g for g in out if g["captured"].startswith(a.at)]
    if a.day:
        out = [g for g in out if g["day"] == a.day]
    if a.bursts_only:
        out = [g for g in out if g["kind"] == "burst"]

    if a.chunks:
        chunks, cur, frames = [], [], 0
        for g in out:
            if cur and (cur[-1]["day"] != g["day"] or len(cur) >= a.max_groups or frames + g["count"] > a.max_frames):
                chunks.append(cur)
                cur, frames = [], 0
            cur.append(g)
            frames += g["count"]
        if cur:
            chunks.append(cur)
        merged = []
        for c in chunks:
            if merged and merged[-1][0]["day"] == c[0]["day"] and sum(g["count"] for g in c) <= 6:
                merged[-1] += c
            else:
                merged.append(c)
        chunks = merged
        if a.out:
            import glob, os
            os.makedirs(a.out, exist_ok=True)
            for old in glob.glob(os.path.join(a.out, "chunk*.txt")):
                os.remove(old)
            for n, c in enumerate(chunks, 1):
                with open(os.path.join(a.out, f"chunk{n}.txt"), "w", encoding="utf-8") as f:
                    f.write("\n".join(fmt(g) for g in c) + "\n")
        for n, c in enumerate(chunks, 1):
            print(json.dumps({"chunk": n, "day": c[0]["day"], "groups": len(c),
                              "frames": sum(g["count"] for g in c), "lines": [fmt(g) for g in c]}))
        print(f"# {len(chunks)} chunks, {len(out)} groups remaining of {total}", file=sys.stderr)
        return
    if a.json:
        print(json.dumps(out))
        return
    b = [g for g in out if g["kind"] == "burst"]
    print(f"# shown: {len(b)} bursts ({sum(g['count'] for g in b)} frames), "
          f"{len(out) - len(b)} singles; {total} groups in the file")
    for g in out:
        print(fmt(g))


if __name__ == "__main__":
    main()
