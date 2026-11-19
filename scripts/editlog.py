"""Write and check $RUN/edits.jsonl, the edit skill's per-photo record.

Usage:
  python -I editlog.py RUN start ID CURSOR MASKS ROUND   # CURSOR: a number or null
  python -I editlog.py RUN done ID ROUND [key=value ...]  # extra fields, e.g. look=night denoise=50
  python -I editlog.py RUN check [--fix]                  # list invalid lines; --fix repairs None/True/False

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
    return 1 if bad and not fix else 0


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    run, cmd, rest = argv[0], argv[1], argv[2:]
    if cmd == "start" and len(rest) == 4:
        pid, cursor, masks, rnd = rest
        append(run, {"id": int(pid), "cursor": None if cursor == "null" else int(cursor),
                     "masksBefore": int(masks), "round": rnd})
    elif cmd == "done" and len(rest) >= 2:
        obj = {"id": int(rest[0]), "done": True, "round": rest[1]}
        for kv in rest[2:]:
            k, _, v = kv.partition("=")
            obj[k] = num(v)
        append(run, obj)
    elif cmd == "check":
        sys.exit(check(run, "--fix" in rest))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
