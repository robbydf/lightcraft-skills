"""Build $RUN/people-by-photo.json: which of the user's named people are in each photo.

Usage (from Bash, after lc-env.sh):
  for n in Ana Ben; do "$CLI" run --connect faces.person name="$n" more=0 > "$RUN/faces-$n.json"; done
  "$CLI" run --connect faces.unnamed limit=5000 > "$RUN/faces-unnamed.json"
  python -I "$LC_SCRIPTS/people.py" "$RUN" "$RUN"/faces-*.json
  python -I "$LC_SCRIPTS/people.py" "$RUN" --ids 1165-1197      # print the entries for a chunk

Inputs are saved outputs of `faces.person` (confirmed faces of one person) and `faces.unnamed`
(unnamed faces, with a suggestion when recognition has a guess). Output, one entry per photo:
  {"1188": {"0": "Ana", "2": "suggested:Ben", "3": "unnamed"}}
Face keys are LightCraft's face index in that photo. "suggested:<name>" counts as the user's own
unless the clothing disagrees ("own or stranger?"); "unnamed" faces are judged by the day's people list.
`faces.suggest` lists only unnamed faces, so a photo whose faces are all named returns nothing there:
use this map instead of per-photo `faces.suggest` calls.
"""
import json
import os
import sys


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        d = json.load(f)
    if not d.get("ok", True):
        sys.exit(f"{path}: command failed: {d.get('error')}")
    return d.get("command", ""), d.get("result", d)


def build(run, files):
    people, unnamed, notes = {}, {}, []
    for path in files:
        cmd, r = load(path)
        if cmd == "faces.person" or "confirmed" in r:
            name = r.get("name") or os.path.basename(path)[6:-5]
            if r.get("more"):
                notes.append(f"{name}: {r['more']} more faces not listed; re-run with a higher limit")
            for fc in r.get("confirmed", []):
                people.setdefault(str(fc["photo"]), {})[str(fc["index"])] = name
            notes.append(f"{name}: {len(r.get('confirmed', []))} faces")
        elif cmd == "faces.unnamed" or "faces" in r:
            faces = r.get("faces", [])
            if r.get("total", len(faces)) > len(faces):
                notes.append(f"unnamed: {r['total'] - len(faces)} faces cut off by the limit; raise limit=")
            for fc in faces:
                s = (fc.get("suggestion") or {}).get("name")
                unnamed.setdefault(str(fc["photo"]), {})[str(fc["index"])] = f"suggested:{s}" if s else "unnamed"
            notes.append(f"unnamed: {len(faces)} faces, {sum(1 for f in faces if f.get('suggestion'))} with a suggestion")
        else:
            sys.exit(f"{path}: not a faces.person or faces.unnamed output")
    out = {}
    for pid in set(people) | set(unnamed):
        e = dict(unnamed.get(pid, {}))
        e.update(people.get(pid, {}))
        out[pid] = dict(sorted(e.items(), key=lambda kv: int(kv[0])))
    out = dict(sorted(out.items(), key=lambda kv: int(kv[0])))
    dest = os.path.join(run, "people-by-photo.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=0)
    own = sum(1 for e in out.values() if any(not v.startswith("unnamed") for v in e.values()))
    for n in notes:
        print(n)
    print(f"wrote {dest}: {len(out)} photos with faces, {own} with a named or suggested person")


def show(run, spec):
    with open(os.path.join(run, "people-by-photo.json"), encoding="utf-8") as f:
        d = json.load(f)
    ids = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        ids.update(range(int(a), int(b or a) + 1))
    for pid in sorted(ids):
        if str(pid) in d:
            print(pid, json.dumps(d[str(pid)]))


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    if argv[1] == "--ids" and len(argv) == 3:
        show(argv[0], argv[2])
    else:
        build(argv[0], argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:])
