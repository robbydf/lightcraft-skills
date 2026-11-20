"""Choose the photos to export: picks (rating >= N) that show one of the user's own people.

Usage (from Bash, after lc-env.sh):
  python -I "$LC_SCRIPTS/export_picks.py" "$SP/marks-before.json" "$SP/faces/people-by-photo.json" \
      --people Sarah,Enzo,Robby [--min-rating 3] [--from 2026-11-01] [--to 2026-11-14] \
      [--manifest "$RUN/export-google-photos.jsonl"] [--hist-sigs "$SP/hist-sigs.json"] \
      [--decisions "$RUN/export-google-photos-decisions.json"] \
      [--out "$SP/export-picks.json"]

Inputs: a `catalog.query` output and the map `people.py` builds ({"1188": {"0": "Ana", "2": "suggested:Ben"}}).
A photo is one of the user's when any face is named one of --people (case-insensitive). A face named
someone else, a `suggested:` face or an `unnamed` face doesn't make it one: those go to `review`
(suggested ones first) unless the decisions file includes them. A virtual copy (`copyOf`) with no face
entry of its own uses its original's.

Skipped: rating below the minimum, deleted, rejected, videos (raw and image files are kept), outside the date range (compared on
the first 10 characters of `captured`, as the camera wrote it). Ids marked done in the manifest go to
`already_exported` (and to `changed` when their history signature differs from the one at export).
A photo marked `forced` by `export_stage.py force` is exported again.

Decisions file (JSON, written by the skill from the user's answers): {"include": [ids], "exclude": [ids]}.
Output (--out, else stdout): {"export", "review", "no_faces", "others_only", "not_edited",
"already_exported", "changed", "names", "days"}; a table per day goes to stderr.
"""
import argparse
import json
import os
import re
import sys


def load_json(path, what):
    if not os.path.isfile(path):
        sys.exit(f"export_picks: {what} not found: {path}")
    with open(path, encoding="utf-8-sig") as f:
        text = f.read().strip()
    if not text:
        sys.exit(f"export_picks: {what} is empty: {path}")
    try:
        return json.loads(text.splitlines()[-1] if what == "catalog" else text)
    except ValueError as e:
        sys.exit(f"export_picks: {what} is not JSON ({e}): {path}")


def load_catalog(path):
    d = load_json(path, "catalog")
    if isinstance(d, dict) and not d.get("ok", True):
        sys.exit(f"export_picks: catalog.query failed: {d.get('error')}")
    r = d.get("result", d) if isinstance(d, dict) else d
    photos = r.get("photos") if isinstance(r, dict) else r
    if not isinstance(photos, list):
        sys.exit(f"export_picks: no photo list in {path}")
    return photos


def load_people(path):
    m = load_json(path, "people map")
    if not isinstance(m, dict) or not m:
        sys.exit(f"export_picks: the people map has no photos: {path}. Is face recognition on, "
                 "and did faces.person run for each name?")
    return {str(k): v for k, v in m.items()}


def load_manifest(path):
    """Last line per id wins: {id: line}."""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8-sig") as f:
        lines = [x.strip() for x in f.read().splitlines() if x.strip()]
    for n, line in enumerate(lines, 1):
        try:
            e = json.loads(line)
            out[str(e["id"])] = e
        except (ValueError, KeyError, TypeError):
            if n == len(lines):  # a crash mid-append; export_stage.py ignores it the same way
                print(f"export_picks: ignoring the incomplete last line of {path}", file=sys.stderr)
                break
            sys.exit(f"export_picks: {path} line {n} is not a manifest line; fix or remove it")
    return out


def parse_ids(text):
    """'1,2,3' | '1 2 3' | '1-5' -> list of str ids."""
    ids = []
    for part in (text or "").replace(",", " ").split():
        if "-" in part:
            a, b = part.split("-", 1)
            ids += [str(i) for i in range(int(a), int(b) + 1)]
        else:
            ids.append(str(int(part)))
    return ids


def classify(entry, own):
    """-> 'own', ('review', why), 'others', or None (no faces)."""
    if not entry:
        return None
    vals = [str(v) for v in entry.values()]
    if any(v.lower() in own for v in vals):
        return "own"
    sug = [v.split(":", 1)[1] for v in vals if v.startswith("suggested:") and v.split(":", 1)[1].lower() in own]
    if sug:
        return ("review", "suggested:" + sug[0])
    if any(v == "unnamed" or v.startswith("suggested:") for v in vals):
        return ("review", "unnamed")
    return "others"


def select(photos, people, own, min_rating=3, date_from=None, date_to=None, manifest=None,
           sigs=None, include=(), exclude=()):
    manifest, sigs = manifest or {}, sigs or {}
    include, exclude = set(map(str, include)), set(map(str, exclude))
    own = {n.strip().lower() for n in own if n.strip()}
    out = {k: [] for k in ("export", "review", "no_faces", "others_only", "not_edited",
                           "already_exported", "changed", "no_date")}
    names, days = {}, {}
    for p in photos:
        pid = str(p["id"])
        if p.get("deleted") or p.get("flag") == "reject" or (p.get("rating") or 0) < min_rating:
            continue
        if p.get("kind") == "video":  # raw, image (JPEG/HEIC/...) and merged photos export; videos don't
            continue
        day = (p.get("captured") or "")[:10]
        if (date_from or date_to) and not day:
            out["no_date"].append(pid)  # can't tell the trip: reported, not exported
            continue
        if (date_from and day < date_from) or (date_to and day > date_to):
            continue
        entry = people.get(pid) or (people.get(str(p["copyOf"])) if p.get("copyOf") else None)
        c = classify(entry, own)
        if pid in exclude:
            continue
        d = days.setdefault(day or "?", {"new": 0, "already": 0, "review": 0, "no_faces": 0, "not_edited": 0})
        if c != "own" and pid not in include:
            if c is None:
                out["no_faces"].append(pid); d["no_faces"] += 1
            elif c == "others":
                out["others_only"].append(pid)
            else:
                out["review"].append({"id": pid, "why": c[1], "day": day}); d["review"] += 1
            continue
        m = manifest.get(pid)
        if m and m.get("state") == "done":
            out["already_exported"].append(pid); d["already"] += 1
            if pid in sigs and m.get("hist") and sigs[pid] != m["hist"]:
                out["changed"].append(pid)
            continue
        out["export"].append(pid); d["new"] += 1
        names[pid] = p.get("fileName") or pid
        if not p.get("edited"):
            out["not_edited"].append(pid); d["not_edited"] += 1
    out["review"].sort(key=lambda r: (not r["why"].startswith("suggested:"), r["day"], int(r["id"])))
    out["names"], out["days"] = names, dict(sorted(days.items()))
    return out


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("catalog")
    a.add_argument("people_map")
    a.add_argument("--people", required=True, help="comma-separated names, e.g. Sarah,Enzo,Robby")
    a.add_argument("--min-rating", type=int, default=3)
    a.add_argument("--from", dest="date_from")
    a.add_argument("--to", dest="date_to")
    a.add_argument("--manifest")
    a.add_argument("--hist-sigs", help="JSON {id: signature} from export_stage.py hist")
    a.add_argument("--decisions", help='JSON {"include": [ids], "exclude": [ids]}')
    a.add_argument("--out")
    o = a.parse_args(argv)
    for d in (o.date_from, o.date_to):
        if d and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            sys.exit(f"export_picks: dates are YYYY-MM-DD, not {d}")
    dec = load_json(o.decisions, "decisions file") if o.decisions and os.path.isfile(o.decisions) else {}
    sigs = load_json(o.hist_sigs, "history signatures") if o.hist_sigs and os.path.isfile(o.hist_sigs) else {}
    r = select(load_catalog(o.catalog), load_people(o.people_map), o.people.split(","), o.min_rating,
               o.date_from, o.date_to, load_manifest(o.manifest), {str(k): v for k, v in sigs.items()},
               [str(i) for i in dec.get("include", [])], [str(i) for i in dec.get("exclude", [])])
    text = json.dumps(r, indent=1)
    if o.out:
        with open(o.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)
    print(f"{'day':10}  new  already  review  no_faces  not_edited", file=sys.stderr)
    for day, d in r["days"].items():
        print(f"{day:10}  {d['new']:3}  {d['already']:7}  {d['review']:6}  {d['no_faces']:8}  {d['not_edited']:10}",
              file=sys.stderr)
    print(f"export {len(r['export'])}, review {len(r['review'])}, "
          f"no faces {len(r['no_faces'])}, other people only {len(r['others_only'])}, "
          f"already exported {len(r['already_exported'])} (changed since {len(r['changed'])})"
          + (f", no capture date {len(r['no_date'])}" if r["no_date"] else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
