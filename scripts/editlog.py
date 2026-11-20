"""Write and check $RUN/edits.jsonl, the edit skill's per-photo record.

Usage:
  python -I editlog.py RUN init                           # first edit of a library with no cull run:
                                                          # creates RUN (absolute path) and edits.jsonl
  python -I editlog.py RUN start ID CURSOR MASKS ROUND   # CURSOR: a number or null
  python -I editlog.py RUN done ID ROUND [key=value ...]  # extra fields, e.g. look=night denoise=50
  python -I editlog.py RUN check [--fix]                  # list invalid lines; --fix repairs None/True/False
  python -I editlog.py RUN done-ids ROUND [--ids 1,2,3 | 1 2 3 | 1-5]   # ids with a done line in ROUND (comma list);
                                                          # with --ids, also "todo:" the listed ids not done

Always valid JSON (null, true, false), one object per line, appended. `check --fix` keeps a backup
edits.before-fix.jsonl and only repairs lines that parse once Python literals are replaced.
"""
import json
import os
import re
import shutil
import sys


def num(v):
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def append(run, obj):
    path = os.path.join(run, "edits.jsonl")
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, separators=(",", ":")) + "\n")
    print(json.dumps(obj))


def check(run, fix):
    path = os.path.join(run, "edits.jsonl")
    lines = open(path, encoding="utf-8").read().splitlines()
    bad, out = [], []
    for n, line in enumerate(lines, 1):
        if not line.strip():
            out.append(line)
            continue
        try:
            json.loads(line)
            out.append(line)
        except json.JSONDecodeError:
            repaired = re.sub(r"\bNone\b", "null", line)
            repaired = re.sub(r"\bTrue\b", "true", repaired)
            repaired = re.sub(r"\bFalse\b", "false", repaired)
            try:
                json.loads(repaired)
                bad.append((n, "repairable"))
                out.append(repaired)
            except json.JSONDecodeError:
                bad.append((n, "NOT repairable"))
                out.append(line)
    for n, kind in bad:
        print(f"line {n}: invalid JSON ({kind})")
    print(f"{len(lines)} lines, {len(bad)} invalid")
    if fix and any(k == "repairable" for _, k in bad):
        bak = os.path.join(run, "edits.before-fix.jsonl")
        if os.path.exists(bak):
            sys.exit("refusing: backup exists " + bak)
        shutil.copy(path, bak)
        open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
        print("repaired, backup", bak)
    if fix:
        return 1 if any(k == "NOT repairable" for _, k in bad) else 0
    return 1 if bad else 0


def done_ids(run, rnd, rest):
    want = None
    if "--ids" in rest:  # check the ids first, so a bad list prints only the error
        want = []
        for t in (t for a in rest[rest.index("--ids") + 1:] for t in a.replace(",", " ").split()):
            a, dash, b = t.partition("-")
            if not (a.isdigit() and (not dash or b.isdigit())) or (dash and not 0 <= int(b) - int(a) < 100000):
                sys.exit(f"editlog: --ids: not an id or range: {t!r}")
            want += range(int(a), int(b) + 1) if dash else [int(t)]
        if not want:
            sys.exit("editlog: --ids needs a list of ids")
    done = set()
    path = os.path.join(run, "edits.jsonl")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                    if isinstance(o, dict) and o.get("done") and str(o.get("round")) == rnd and "id" in o:
                        done.add(int(o["id"]))
                except (ValueError, TypeError):
                    continue  # `check` reports these
    print("done:", ",".join(map(str, sorted(done))))
    if want is not None:
        print("todo:", ",".join(str(i) for i in want if i not in done))


def as_int(v, what):
    try:
        return int(v)
    except ValueError:
        sys.exit(f"editlog: {what} must be a whole number, got {v!r}\n{__doc__}")


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    run, cmd, rest = argv[0], argv[1], argv[2:]
    if cmd == "init":
        if not run.strip() or not os.path.isabs(run):
            sys.exit(f"editlog init: RUN must be an absolute path, got {run!r} (set RUN in this Bash call)")
        os.makedirs(run, exist_ok=True)
        path = os.path.join(run, "edits.jsonl")
        if not os.path.exists(path):
            open(path, "a", encoding="utf-8").close()
        print(f"run folder ready: {run}")
        return
    # An unset $RUN arrives as "" (or the command name shifts into its place): never write elsewhere.
    if not run.strip() or not os.path.isdir(run) or not (
            os.path.exists(os.path.join(run, "log.jsonl")) or os.path.exists(os.path.join(run, "edits.jsonl"))):
        sys.exit(f"editlog: RUN is not a run folder: {run!r} (set RUN in this Bash call; for a library with no cull run, run `editlog.py RUN init` once)")
    if cmd == "start" and len(rest) == 4:
        pid, cursor, masks, rnd = rest
        append(run, {"id": as_int(pid, "ID"), "cursor": None if cursor == "null" else as_int(cursor, "CURSOR"),
                     "masksBefore": as_int(masks, "MASKS"), "round": rnd})
    elif cmd == "done" and len(rest) >= 2:
        obj = {"id": as_int(rest[0], "ID"), "done": True, "round": rest[1]}
        for kv in rest[2:]:
            k, _, v = kv.partition("=")
            obj[k] = num(v)
        append(run, obj)
    elif cmd == "done-ids" and rest:
        done_ids(run, rest[0], rest[1:])
    elif cmd == "check":
        sys.exit(check(run, "--fix" in rest))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
