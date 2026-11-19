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
# Give at most 5-6 ids per call at 2000 px (the tool limit is 120 s) and 1-2 at 6000 px.
# Never pipe app.export into `head`: closing the pipe early can break the export.
DIR="${1:?usage: export-ids.sh DIR SUFFIX LONGEDGE ID [ID ...]}"; SUFFIX="${2:?suffix}"; EDGE="${3:?long edge}"; shift 3
[ $# -gt 0 ] || { echo "export-ids: no ids" >&2; exit 1; }
source "$(dirname "${BASH_SOURCE[0]}")/lc-env.sh" >/dev/null 2>&1
[ -n "${CLI:-}" ] || { echo "export-ids: LightCraft CLI not found" >&2; exit 1; }
TMP="$DIR/.export-$$"; mkdir -p "$TMP"
ids=$(IFS=,; echo "$*")
"$CLI" run --connect app.export "ids=[$ids]" dir="$TMP" longEdge="$EDGE" format=jpeg naming='{name}' conflict=overwrite > "$TMP/result.json"
python -I - "$TMP/result.json" "$DIR" "$SUFFIX" "$@" <<'EOF'
import json, os, shutil, sys
res, d, suffix, ids = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
r = json.load(open(res, encoding="utf-8-sig"))
if not r.get("ok"):
    sys.exit(f"export-ids: export failed: {r.get('error')}")
files = r["result"]["files"]
if len(files) != len(ids):
    sys.exit(f"export-ids: {len(ids)} ids but {len(files)} files; nothing renamed (see {res})")
for i, f in zip(ids, files):
    dest = os.path.join(d, f"{i}-{suffix}.jpg")
    shutil.move(f["path"], dest)
    print(i, os.path.basename(f["path"])[:-4], "->", dest)
EOF
rc=$?
[ $rc -eq 0 ] && { rm -f "$TMP/result.json"; rmdir "$TMP" 2>/dev/null; }
exit $rc
