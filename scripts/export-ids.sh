#!/usr/bin/env bash
# Export photos and name each file by its LightCraft id: DIR/ID-SUFFIX.jpg.
#
# Usage (from Bash, after lc-env.sh):
#   bash "$LC_SCRIPTS/export-ids.sh" "$SP" before 2000 501 502 503 504 505
#     -> $SP/501-before.jpg ... $SP/505-before.jpg  (2000 px long edge, JPEG)
#
# LightCraft names exports by the camera file name and has no id token, so this keeps the
# id -> file link: it exports into a temporary folder, reads the result's `files` list (in the order
# of the ids) and moves each file to ID-SUFFIX.jpg, overwriting an older one. Prints one line per id.
# Give at most 5-6 ids per call at 2000 px (the tool limit is 120 s) and 1-2 at 6000 px (at most 4000 px while GPU rendering is on with an entry-level GPU).
# Never pipe app.export into `head`: closing the pipe early can break the export.
DIR="${1:?usage: export-ids.sh DIR SUFFIX LONGEDGE ID [ID ...]}"; SUFFIX="${2:?suffix}"; EDGE="${3:?long edge}"; shift 3
[ $# -gt 0 ] || { echo "export-ids: no ids" >&2; exit 1; }
source "$(dirname "${BASH_SOURCE[0]}")/lc-env.sh" >/dev/null 2>&1
[ -n "${CLI:-}" ] || { echo "export-ids: LightCraft CLI not found" >&2; exit 1; }
EXP_TMP="$DIR/.export-$$"   # not TMP: Git Bash exports TMP as the system temp folder
PY="${LC_PY:-python}"
rename() {  # rename RESULT_JSON ID... : move each exported file to DIR/ID-SUFFIX.jpg
  "$PY" -I - "$1" "$DIR" "$SUFFIX" "${@:2}" <<'EOF'
import json, os, shutil, sys
res, d, suffix, ids = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
r = json.load(open(res, encoding="utf-8-sig"))
if not r.get("ok"):
    sys.exit(f"export-ids: export failed: {r.get('error')}")
files = r["result"]["files"]
if len(files) != len(ids):
    sys.exit(f"export-ids: {len(ids)} ids but {len(files)} files; nothing renamed (see {res})")
paths = [os.path.normcase(os.path.abspath(f["path"])) for f in files]
dups = [i for i, p in zip(ids, paths) if paths.count(p) > 1]
for i, f, p in zip(ids, files, paths):
    if paths.count(p) > 1:
        continue  # two photos share a file name: this file holds only one of them
    dest = os.path.join(d, f"{i}-{suffix}.jpg")
    shutil.move(f["path"], dest)
    print(i, os.path.basename(f["path"])[:-4], "->", dest)
if dups:
    with open(os.path.join(os.path.dirname(res), "dups.txt"), "w", encoding="utf-8") as o:
        o.write(" ".join(dups))
    sys.exit(3)  # the caller re-exports these ids one at a time
EOF
}
export1() {  # export1 FOLDER ID... : one app.export call into FOLDER, result in FOLDER/result.json
  mkdir -p "$1" || return 1
  local ids; ids=$(IFS=,; echo "${*:2}")
  "$CLI" run --connect app.export "ids=[$ids]" dir="$1" longEdge="$EDGE" format=jpeg naming='{name}' conflict=overwrite > "$1/result.json"
}
export1 "$EXP_TMP" "$@"
rename "$EXP_TMP/result.json" "$@"
rc=$?
if [ $rc -eq 3 ]; then
  # Same camera file name on two ids (virtual copies, two cameras): one folder per id for those.
  read -r -a dups < "$EXP_TMP/dups.txt"
  echo "export-ids: ${#dups[@]} ids share a file name (${dups[*]}), exporting them one at a time" >&2
  rc=0
  for id in "${dups[@]}"; do
    export1 "$EXP_TMP/$id" "$id" && rename "$EXP_TMP/$id/result.json" "$id" || { rc=1; break; }
  done
fi
[ $rc -eq 0 ] && rm -rf "${EXP_TMP:?}"
exit $rc
