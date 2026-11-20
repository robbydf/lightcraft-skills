"""Move exported files into a watched folder (Drive backup, a sync folder) safely, with a manifest.

Subcommands (from Bash, after lc-env.sh; run with python -I):
  export_stage.py check     --root ROOT --staging STG [--avoid DIR ...]
      ROOT exists and is writable; STG (made if missing) is on the same volume, outside ROOT;
      ROOT is not inside any --avoid folder (the library's photo folders, the originals).
  export_stage.py hist      --out SIGS.json --ids 1,2,3 [--merge] HIST.json [HIST2.json ...]
      HIST*.json: the JSON lines of `lightcraft-cli run history.list id=1 history.list id=2 ...` in id
      order (several files are read in order); writes {id: signature of that photo's edit history},
      a fresh file unless --merge keeps the signatures already in SIGS.json.
  export_stage.py reconcile --dest DEST --staging STG --manifest MAN
      settle `pending` lines left by a crash: done if DEST holds the same file (size and sha1),
      otherwise `abandoned` (the photo counts as not exported); empty STG. Never touches DEST.
  export_stage.py stage     --result R.json --dest DEST --staging STG --manifest MAN --picks PICKS.json
                            --ids 1,2,3 [--max-mp 16 | --edge 4000] [--hist-sigs SIGS.json]
      R.json is the `app.export` output for exactly these ids (in this order). Checks the count, that
      each file is a JPEG/PNG/... of the right size, names each file (camera name, or NAME-ID when
      the name is taken in the batch, in DEST or in the manifest, or the id was exported before), then
      per file: manifest `pending` -> copy into STG -> link/rename into DEST (never overwrite) -> `done`.
      Refuses ids whose last line is `done`.
  export_stage.py todo      --manifest MAN --ids 1,2,3     print the ids not done yet (reconcile first)
  export_stage.py done      --manifest MAN                 print the ids exported (last line `done`)
  export_stage.py force     --manifest MAN --ids 1,2       mark done ids `forced`: the next export
      writes them again as NAME-ID (the old file stays; the user removes the old copy on the platform)

Manifest: JSON lines {id, file, dest, size, sha1, hist?, state, at}; the last line per id wins. An
incomplete last line (a crash while writing it) is ignored with a warning.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

MAGIC = {b"\xff\xd8\xff": "jpeg", b"\x89PNG": "png", b"II*\x00": "tiff", b"MM\x00*": "tiff",
         b"RIFF": "webp"}


def die(msg, code=1):
    print(f"export_stage: {msg}", file=sys.stderr)
    sys.exit(code)


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_ids(text):
    ids = []
    for part in (text or "").replace(",", " ").split():
        if "-" in part:
            a, b = part.split("-", 1)
            ids += [str(i) for i in range(int(a), int(b) + 1)]
        else:
            ids.append(str(int(part)))
    return ids


def norm(p):
    return os.path.normcase(os.path.realpath(os.path.abspath(p)))


def inside(child, parent):
    c, p = norm(child), norm(parent)
    return c == p or c.startswith(p.rstrip(os.sep) + os.sep)


def read_manifest(path, ever_done=None):
    """Last line per id; with a set as ever_done, also collect the ids that were done at some point."""
    last = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8-sig") as f:
            lines = [x for x in f.read().splitlines() if x.strip()]
        for n, line in enumerate(lines, 1):
            try:
                e = json.loads(line)
                pid = str(e["id"])
            except (ValueError, KeyError, TypeError):
                if n == len(lines):  # a crash mid-append: the line was never complete
                    print(f"export_stage: ignoring the incomplete last line of {path}", file=sys.stderr)
                    break
                die(f"{path} line {n} is not a manifest line; fix or remove it")
            last[pid] = e
            if ever_done is not None and e.get("state") == "done":
                ever_done.add(pid)
    return last


def cmd_done(manifest):
    """Print the ids whose last manifest line is `done` (for history signatures)."""
    print(" ".join(i for i, e in read_manifest(manifest).items() if e.get("state") == "done"))


def cmd_todo(manifest, ids):
    """Print the ids whose last manifest line is not `done` (run reconcile first)."""
    last = read_manifest(manifest)
    print(" ".join(i for i in ids if last.get(i, {}).get("state") != "done"))


def cmd_force(manifest, ids):
    """Mark done ids for a re-export: they get a new file NAME-ID, the old file stays."""
    last = read_manifest(manifest)
    for i in ids:
        e = last.get(i)
        if not e or e.get("state") != "done":
            print(f"{i}: not exported yet, nothing to force")
            continue
        append(manifest, dict(e, state="forced", at=now()))
        print(f"{i}: will be exported again as a new file (the old {e.get('file', 'file')} stays)")


def append(path, entry):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if os.path.isfile(path) and os.path.getsize(path):
        with open(path, "rb+") as f:  # a crash mid-append left a partial last line: cut it off
            data = f.read()
            if not data.endswith(b"\n"):
                tail = data[data.rfind(b"\n") + 1:]
                try:
                    json.loads(tail)  # complete, only its newline is missing: keep it
                    f.write(b"\n")
                except ValueError:
                    f.truncate(data.rfind(b"\n") + 1)
                    print(f"export_stage: removed the incomplete last line of {path}", file=sys.stderr)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()
        os.fsync(f.fileno())


def cmd_check(root, staging, avoid):
    if not os.path.isdir(root):
        die(f"the export root does not exist: {root}")
    # No probe file: the watched folder must see only photos. On Windows os.access is nearly always
    # true for folders, so a read-only share shows up at the first move (a pending line reconcile settles).
    if not os.access(root, os.W_OK):
        die(f"cannot write to the export root {root}")
    if inside(staging, root):
        die(f"the staging folder {staging} is inside the export root {root}: the watched folder "
            "would see half-copied files. Set export.<target>.staging to a folder outside it")
    os.makedirs(staging, exist_ok=True)
    if os.stat(staging).st_dev != os.stat(root).st_dev:
        die(f"the staging folder {staging} is on another volume than {root}: a move would be a copy. "
            "Set export.<target>.staging to a folder on the same drive that is not backed up")
    for a in avoid:
        if a and inside(root, a):
            die(f"the export root {root} is inside {a} (a library or originals folder)")
    print(f"ok: root {root}, staging {staging}")


def cmd_hist(out, ids, hist_paths, merge=False):
    sigs = {}
    if merge and os.path.isfile(out):
        with open(out, encoding="utf-8-sig") as f:
            sigs = json.load(f)
    lines = []
    for hp in hist_paths:  # several files (one per CLI call) are read in order
        with open(hp, encoding="utf-8-sig") as f:
            lines += [json.loads(x) for x in f if x.strip()]
    hist_path = " ".join(hist_paths)
    if len(lines) != len(ids):
        die(f"{len(ids)} ids but {len(lines)} history.list results in {hist_path}")
    for i, d in zip(ids, lines):
        if not d.get("ok"):  # e.g. deleted since its export: no signature, so never "changed"
            print(f"export_stage: no history for {i} ({d.get('error')}); skipped", file=sys.stderr)
            continue
        r = d["result"]
        sigs[i] = hashlib.sha1(json.dumps([r.get("history"), r.get("cursor")], sort_keys=True)
                               .encode()).hexdigest()[:16]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sigs, f, indent=0)
    print(f"history signatures for {len(ids)} photos -> {out}")


def cmd_reconcile(dest, staging, manifest):
    settled = 0
    for pid, e in read_manifest(manifest).items():
        if e.get("state") != "pending":
            continue
        path = os.path.join(e["dest"], e["file"])
        ok = os.path.isfile(path) and os.path.getsize(path) == e["size"] and sha1(path) == e["sha1"]
        append(manifest, dict(e, state="done" if ok else "abandoned", at=now()))
        print(f"reconcile {pid} {e['file']}: {'done' if ok else 'abandoned (not in the folder)'}")
        settled += 1
    if os.path.isdir(staging):
        for name in os.listdir(staging):
            p = os.path.join(staging, name)
            if os.path.isfile(p):
                os.remove(p)
    return settled


def place(src, dst):
    """Move src to dst on the same volume without ever replacing an existing dst."""
    try:
        os.link(src, dst)  # fails with FileExistsError if dst exists
    except FileExistsError:
        raise
    except OSError:  # no hard links (FAT, some shares): check, then rename. On POSIX a file
        if os.path.exists(dst):  # appearing between the check and the rename would be replaced
            raise FileExistsError(dst)
        os.rename(src, dst)
        return
    try:
        os.remove(src)  # the file is in place; a staging leftover is removed by reconcile
    except OSError:
        pass


def cmd_stage(o):
    ids = parse_ids(o.ids)
    with open(o.result, encoding="utf-8-sig") as f:
        text = f.read().strip()
    if not text:
        die(f"{o.result} is empty: did app.export fail?")
    r = json.loads(text.splitlines()[-1])
    if not r.get("ok"):
        die(f"app.export failed: {r.get('error')}")
    files = r["result"].get("files") or [r["result"]]
    if len(files) != len(ids):
        die(f"{len(ids)} ids but {len(files)} files exported; nothing moved (see {o.result})", 2)
    with open(o.picks, encoding="utf-8-sig") as f:
        names = json.load(f).get("names", {})
    sigs = {}
    if o.hist_sigs and os.path.isfile(o.hist_sigs):
        with open(o.hist_sigs, encoding="utf-8-sig") as f:
            sigs = json.load(f)
    for i, fe in zip(ids, files):
        p = fe["path"]
        if not os.path.isfile(p) or os.path.getsize(p) == 0:
            die(f"photo {i}: exported file missing or empty: {p}", 2)
        with open(p, "rb") as f:
            head = f.read(4)
        if not any(head.startswith(m) for m in MAGIC):
            die(f"photo {i}: {p} is not an image file", 2)
        w, h = fe.get("width"), fe.get("height")
        if w and h:
            if o.max_mp and w * h > o.max_mp * 1e6 * 1.005:
                die(f"photo {i}: {w}x{h} is over {o.max_mp} MP", 2)
            if o.edge and max(w, h) > o.edge:
                die(f"photo {i}: {w}x{h} is over the {o.edge} px long edge", 2)
    os.makedirs(o.dest, exist_ok=True)
    os.makedirs(o.staging, exist_ok=True)
    if inside(o.staging, o.dest) or inside(o.dest, o.staging):
        die(f"the staging folder {o.staging} and the destination {o.dest} overlap")
    if os.stat(o.staging).st_dev != os.stat(o.dest).st_dev:
        die(f"the staging folder {o.staging} is on another volume than {o.dest}")
    cmd_reconcile(o.dest, o.staging, o.manifest)
    force = set()
    man = read_manifest(o.manifest, force)  # ids done before (forced re-exports) get NAME-ID
    again = [i for i in ids if man.get(i, {}).get("state") == "done"]
    if again:
        die(f"already exported: {','.join(again)} (use `export_stage.py force` to export them again)", 2)
    taken = {n.lower() for n in os.listdir(o.dest)}
    taken |= {e["file"].lower() for e in man.values()
              if e.get("state") in ("done", "pending") and norm(e["dest"]) == norm(o.dest)}
    ext_of = lambda p: os.path.splitext(p)[1].lower() or ".jpg"
    stems = [os.path.splitext(names.get(i) or os.path.basename(fe["path"]))[0] for i, fe in zip(ids, files)]
    dup = {s.lower() for s in stems if [x.lower() for x in stems].count(s.lower()) > 1}
    for i, fe, stem in zip(ids, files, stems):
        ext = ext_of(fe["path"])
        name = stem + ext
        if stem.lower() in dup or name.lower() in taken or i in force:
            name, n = f"{stem}-{i}{ext}", 2
            while name.lower() in taken:
                name, n = f"{stem}-{i}-{n}{ext}", n + 1
        taken.add(name.lower())
        src = fe["path"]
        entry = {"id": int(i), "file": name, "dest": os.path.abspath(o.dest), "size": os.path.getsize(src),
                 "sha1": sha1(src), "state": "pending", "at": now()}
        if i in sigs:
            entry["hist"] = sigs[i]
        append(o.manifest, entry)
        tmp = os.path.join(o.staging, name)
        shutil.copyfile(src, tmp)
        try:
            place(tmp, os.path.join(o.dest, name))
        except FileExistsError:
            os.remove(tmp)
            append(o.manifest, dict(entry, state="abandoned", at=now()))
            die(f"photo {i}: {name} appeared in {o.dest} meanwhile; not overwritten", 2)
        append(o.manifest, dict(entry, state="done", at=now()))
        os.remove(src)
        print(f"{i} -> {name}")


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = a.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--root", required=True)
    c.add_argument("--staging", required=True)
    c.add_argument("--avoid", action="append", default=[])
    h = sub.add_parser("hist")
    h.add_argument("--out", required=True)
    h.add_argument("--ids", required=True)
    h.add_argument("--merge", action="store_true", help="keep the signatures already in --out")
    h.add_argument("hist", nargs="+")
    r = sub.add_parser("reconcile")
    for k in ("--dest", "--staging", "--manifest"):
        r.add_argument(k, required=True)
    s = sub.add_parser("stage")
    for k in ("--result", "--dest", "--staging", "--manifest", "--picks", "--ids"):
        s.add_argument(k, required=True)
    s.add_argument("--max-mp", type=float)
    s.add_argument("--edge", type=int)
    s.add_argument("--hist-sigs")
    for name in ("todo", "force"):
        t = sub.add_parser(name)
        t.add_argument("--manifest", required=True)
        t.add_argument("--ids", required=True)
    sub.add_parser("done").add_argument("--manifest", required=True)
    o = a.parse_args(argv)
    try:
        if o.cmd == "check":
            cmd_check(o.root, o.staging, o.avoid)
        elif o.cmd == "hist":
            cmd_hist(o.out, parse_ids(o.ids), o.hist, o.merge)
        elif o.cmd == "reconcile":
            cmd_reconcile(o.dest, o.staging, o.manifest)
        elif o.cmd == "todo":
            cmd_todo(o.manifest, parse_ids(o.ids))
        elif o.cmd == "done":
            cmd_done(o.manifest)
        elif o.cmd == "force":
            cmd_force(o.manifest, parse_ids(o.ids))
        else:
            cmd_stage(o)
    except (OSError, ValueError, KeyError) as e:
        die(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
