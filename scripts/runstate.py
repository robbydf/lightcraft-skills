"""Durable state for a lightcraft-cull run: baseline snapshot, per-group log, verification, rollback.

RUN folder (outside the session scratchpad, survives sessions):
  $RUNS/<library-name>/   (RUNS from lc-env.sh)
    baseline.json   catalog.query output saved before the first mark (never overwritten)
    log.jsonl       one line per finished group

Commands (photos.json = fresh `catalog.query limit=100000` output):
  python -I runstate.py init     RUN photos.json        save baseline (refuses if one exists)
  python -I runstate.py protected RUN                   ids the user had marked before the run
  python -I runstate.py log      RUN '<json>'           append one group, validated:
        {"group": firstId, "ids": [...], "picks": [...], "rejects": [...], "unsure": [...],
         "reason": {"id": "why"}, "sharp": {"id": n}}
  python -I runstate.py amend    RUN '<json>'           change marks in groups already logged (the panel step):
        {"ids": [...], "picks": [...], "unpick": [...], "reason": {"id": "panel 3-0 keep"}}
        picks -> rating 3; unpick -> rating 0 (only this run's own picks). Applied in order after
        the group lines by check, summary, picks and rollback.
  python -I runstate.py check    RUN photos.json [--ids 1,2,3]
        compare the catalog with baseline + log; prints mismatches and changes the user made;
        exit 1 if anything is off
  python -I runstate.py marks    BEFORE.json NOW.json [--ids 1,2,3]
        compare ratings and flags of two catalog.query snapshots (no RUN needed): the edit skill's
        check that editing changed no mark; exit 1 if any differ
  python -I runstate.py summary  RUN                    counts per day, and the reject and unsure lists
  python -I runstate.py picks    RUN [--day D]          the logged picks (for lightcraft-edit)
  python -I runstate.py rollback RUN [--day D]          print the CLI commands that undo logged marks
"""
import json
import os
import sys
from collections import defaultdict


def load_catalog(path):
    with open(path, encoding="utf-8-sig") as f:
        line = next((l for l in f if l.strip()), None)
    if line is None:
        sys.exit(f"{path} is empty")
    d = json.loads(line)
    if d.get("ok") is False:
        sys.exit("catalog.query failed: " + str(d.get("error")))
    photos = d["result"]["photos"] if "result" in d else d["photos"]
    return {p["id"]: p for p in photos}


def state(p):
    return {"rating": p.get("rating") or 0, "flag": p.get("flag") or "none"}


def read_log(run):
    path = os.path.join(run, "log.jsonl")
    entries = []
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    return entries


def groups(entries):
    return [e for e in entries if not e.get("amend")]


def final_picks(entries):
    """The run's pick set after the group lines and amends, in log order."""
    picks = []
    for e in entries:
        for i in e.get("picks", []):
            if i not in picks:
                picks.append(i)
        for i in e.get("unpick", []):
            if i in picks:
                picks.remove(i)
    return picks


def baseline(run):
    path = os.path.join(run, "baseline.json")
    if not os.path.exists(path):
        sys.exit(f"no baseline in {run}: run `init` first")
    return load_catalog(path)


def protected_ids(base):
    return sorted(i for i, p in base.items() if state(p) != {"rating": 0, "flag": "none"})


def expected(run):
    """id -> expected {rating, flag} for every photo in a logged group."""
    base = baseline(run)
    exp = {}
    for e in read_log(run):
        if e.get("amend"):
            for i in e.get("picks", []):
                exp[i] = {"rating": 3, "flag": "none"}
            for i in e.get("unpick", []):
                exp[i] = {"rating": 0, "flag": "none"}
            continue
        for i in e["ids"]:
            exp[i] = state(base[i]) if i in base else {"rating": 0, "flag": "none"}
        for i in e["picks"]:
            exp[i] = {"rating": 3, "flag": "none"}
        for i in e["rejects"]:
            exp[i] = {"rating": 0, "flag": "reject"}
    return base, exp


def cmd_init(run, photos_path):
    os.makedirs(run, exist_ok=True)
    dst = os.path.join(run, "baseline.json")
    if os.path.exists(dst):
        sys.exit(f"baseline already exists: {dst} (never overwrite it; start a new RUN folder for a new run)")
    cat = load_catalog(photos_path)
    with open(photos_path, encoding="utf-8-sig") as f, open(dst, "w", encoding="utf-8") as o:
        o.write(next(l for l in f if l.strip()))
    prot = protected_ids(cat)
    print(f"baseline saved: {len(cat)} photos; {len(prot)} already marked by the user: {prot}")


def cmd_log(run, raw):
    e = json.loads(raw)
    for k in ("group", "ids", "picks", "rejects"):
        if k not in e:
            sys.exit(f"log entry missing '{k}'")
    e.setdefault("unsure", [])
    if not e["ids"]:
        sys.exit("log entry has no ids")
    ids = set(e["ids"])
    for k in ("picks", "rejects", "unsure"):
        bad = set(e[k]) - ids
        if bad:
            sys.exit(f"{k} not in the group's ids: {sorted(bad)}")
    if set(e["picks"]) & set(e["rejects"]):
        sys.exit(f"an id is both pick and reject: {sorted(set(e['picks']) & set(e['rejects']))}")
    if e["group"] != e["ids"][0]:
        sys.exit("group must be the first id of the group")
    base = baseline(run)
    prot = set(protected_ids(base))
    touched = (set(e["picks"]) | set(e["rejects"])) & prot
    if touched:
        sys.exit(f"refusing: user-marked photos in picks/rejects: {sorted(touched)}")
    if e["group"] in {x["group"] for x in groups(read_log(run))}:
        sys.exit(f"group {e['group']} is already logged")
    with open(os.path.join(run, "log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(e, separators=(",", ":")) + "\n")
    print(f"logged group {e['group']}: {len(e['picks'])} picks, {len(e['rejects'])} rejects, {len(e['unsure'])} unsure")


def cmd_amend(run, raw):
    e = json.loads(raw)
    e.setdefault("picks", [])
    e.setdefault("unpick", [])
    if not e.get("ids"):
        sys.exit("amend entry needs 'ids'")
    ids = set(e["ids"])
    for k in ("picks", "unpick"):
        bad = set(e[k]) - ids
        if bad:
            sys.exit(f"{k} not in ids: {sorted(bad)}")
    if not (e["picks"] or e["unpick"]):
        sys.exit("amend entry changes nothing (no picks, no unpick)")
    if set(e["picks"]) & set(e["unpick"]):
        sys.exit(f"an id is both pick and unpick: {sorted(set(e['picks']) & set(e['unpick']))}")
    base = baseline(run)
    entries = read_log(run)
    logged = {i for x in groups(entries) for i in x["ids"]}
    missing = ids - logged
    if missing:
        sys.exit(f"not in a logged group (log the group first): {sorted(missing)}")
    touched = (set(e["picks"]) | set(e["unpick"])) & set(protected_ids(base))
    if touched:
        sys.exit(f"refusing: user-marked photos: {sorted(touched)}")
    own = set(final_picks(entries))
    already = set(e["picks"]) & own
    if already:
        sys.exit(f"already picks: {sorted(already)}")
    notown = set(e["unpick"]) - own
    if notown:
        sys.exit(f"unpick only takes back this run's own picks; not picks: {sorted(notown)}")
    _, exp = expected(run)
    rejected = {i for i in e["picks"] if exp.get(i, {}).get("flag") == "reject"}
    if rejected:
        sys.exit(f"refusing to pick rejected photos: {sorted(rejected)}")
    out = {"amend": True, "ids": e["ids"], "picks": e["picks"], "unpick": e["unpick"],
           "reason": e.get("reason", {})}
    with open(os.path.join(run, "log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(out, separators=(",", ":")) + "\n")
    print(f"amended: {len(e['picks'])} new picks, {len(e['unpick'])} unpicked")


def cmd_check(run, photos_path, only=None):
    base, exp = expected(run)
    cur = load_catalog(photos_path)
    bad, user = [], []
    for i, want in exp.items():
        if only and i not in only:
            continue
        if i not in cur:
            bad.append(f"{i}: missing from catalog")
        elif state(cur[i]) != want:
            bad.append(f"{i}: expected {want}, catalog has {state(cur[i])}")
    for i, p in cur.items():
        if only and i not in only:
            continue
        if i not in exp and i in base and state(p) != state(base[i]):
            user.append(f"{i}: changed outside the run {state(base[i])} -> {state(p)}")
    for line in bad:
        print("MISMATCH", line)
    for line in user:
        print("USER-CHANGE", line)
    print(f"checked {len(exp) if not only else len(only)} photos: {len(bad)} mismatches, {len(user)} changes outside the run")
    sys.exit(1 if bad else 0)


def cmd_marks(before_path, now_path, only=None):
    a, b = load_catalog(before_path), load_catalog(now_path)
    diff = []
    for i in sorted((set(a) | set(b) | set(only or ())) if only else set(a)):
        if only and i not in only:
            continue
        if i not in a:
            diff.append(f"{i}: missing from {before_path}")
        elif i not in b:
            diff.append(f"{i}: missing from {now_path}")
        elif i in a and state(a[i]) != state(b[i]):
            diff.append(f"{i}: {state(a[i])} -> {state(b[i])}")
    for line in diff:
        print("CHANGED", line)
    print(f"compared {len(only) if only else len(a)} photos: {len(diff)} marks changed")
    sys.exit(1 if diff else 0)


def cmd_summary(run):
    base = baseline(run)
    per = defaultdict(lambda: {"groups": 0, "frames": 0, "picks": 0, "rejects": 0, "unsure": 0})
    rejects, unsure, amends = [], [], []
    entries = read_log(run)
    final = set(final_picks(entries))
    for e in entries:
        if e.get("amend"):
            for i in e["picks"] + e["unpick"]:
                day = (base.get(i, {}).get("captured") or "?")[:10]
                kind = "PICK" if i in e["picks"] else "UNPICK"
                amends.append((day, i, base.get(i, {}).get("fileName"), kind + " " + e.get("reason", {}).get(str(i), "")))
            continue
        day = (base.get(e["group"], {}).get("captured") or "?")[:10]
        s = per[day]
        s["groups"] += 1; s["frames"] += len(e["ids"])
        s["picks"] += sum(1 for i in e["ids"] if i in final)
        s["rejects"] += len(e["rejects"]); s["unsure"] += sum(1 for i in e["unsure"] if i not in final)
        for i in e["rejects"]:
            rejects.append((day, i, base.get(i, {}).get("fileName"), e.get("reason", {}).get(str(i), "")))
        for i in e["unsure"]:
            if i in final:
                continue  # the panel made it a pick (see AMEND)
            unsure.append((day, i, base.get(i, {}).get("fileName"), e.get("reason", {}).get(str(i), "")))
    for day in sorted(per):
        print(day, json.dumps(per[day]))
    for kind, rows in (("REJECT", rejects), ("UNSURE", unsure), ("AMEND", amends)):
        for day, i, name, why in rows:
            print(kind, day, i, name, why)


def cmd_picks(run, day=None):
    base = baseline(run)
    n = 0
    for i in final_picks(read_log(run)):
        p = base.get(i, {})
        d = (p.get("captured") or "")[:10]
        if day and d != day:
            continue
        print(f"{d} {i} {p.get('fileName', '?')}")
        n += 1
    print(f"# {n} picks", file=sys.stderr)


def cmd_rollback(run, day=None):
    base = baseline(run)
    entries = read_log(run)
    picks = [i for i in final_picks(entries)
             if not day or (base.get(i, {}).get("captured") or "")[:10] == day]
    if picks:
        print(f"\"$CLI\" run --connect photo.rate rating=0 'ids={json.dumps(picks)}'")
    for e in groups(entries):
        d = (base.get(e["group"], {}).get("captured") or "")[:10]
        if day and d != day:
            continue
        if e["rejects"]:
            print(f"\"$CLI\" run --connect photo.flag flag=none 'ids={json.dumps(e['rejects'])}'")


def ids_arg(rest):
    if "--ids" not in rest:
        return None
    k = rest.index("--ids")
    if k + 1 >= len(rest) or not rest[k + 1].strip():
        sys.exit("--ids needs a comma-separated list of ids")
    try:
        return {int(x) for x in rest[k + 1].split(",") if x.strip()}
    except ValueError:
        sys.exit(f"--ids: not a list of ids: {rest[k + 1]!r}")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, run, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
    if cmd in ("init", "log", "amend", "check", "marks") and not rest:
        sys.exit(__doc__)
    if cmd == "init":
        cmd_init(run, rest[0])
    elif cmd == "protected":
        print(protected_ids(baseline(run)))
    elif cmd == "log":
        cmd_log(run, rest[0])
    elif cmd == "amend":
        cmd_amend(run, rest[0])
    elif cmd == "check":
        cmd_check(run, rest[0], ids_arg(rest))
    elif cmd == "marks":
        cmd_marks(run, rest[0], ids_arg(rest))
    elif cmd == "summary":
        cmd_summary(run)
    elif cmd == "picks":
        cmd_picks(run, rest[rest.index("--day") + 1] if "--day" in rest else None)
    elif cmd == "rollback":
        cmd_rollback(run, rest[rest.index("--day") + 1] if "--day" in rest else None)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
