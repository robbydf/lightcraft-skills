#!/usr/bin/env bash
# Export photos in small batches and move them safely into a watched folder (lightcraft-export).
#
# Usage (from Bash, as a background tool call, after lc-env.sh):
#   bash "$LC_SCRIPTS/export-stage.sh" RAWDIR DEST STAGING MANIFEST PICKS SIZE [APP_EXPORT_OPTS ...] -- ID ...
#     RAWDIR    scratch folder for LightCraft's raw output (under $SP; emptied per batch)
#     DEST      the trip folder inside the watched root, e.g. D:/Photos/GooglePhotos/2026-11 Japan
#     STAGING   same volume as DEST, outside the watched root (export_stage.py check)
#     MANIFEST  $RUN/export-<target>.jsonl
#     PICKS     the export_picks.py output (file names per id)
#     SIZE      mp=16 (megapixels) or edge=4000 (long edge, e.g. while GPU rendering is on)
#     APP_EXPORT_OPTS  the target's app.export options, e.g. format=jpeg quality=92 colorSpace=srgb
#   Env: BATCH (ids per app.export call, default 3), SIGS (history signatures file, default
#   MANIFEST with .hist.json). Ids already done in MANIFEST are skipped, so rerunning the same
#   command resumes; to export a done photo again, run `export_stage.py force` first.
#
# Per batch: history.list of each id (to notice later re-edits), app.export into RAWDIR, then
# export_stage.py stage (count and size check, names, pending -> copy -> link -> done). A crash leaves
# `pending` lines that the next run settles first. Prints one progress line per batch; stops at the
# first failing batch (exit 1) so a rerun with the same command resumes after the done ids.
# Never pipe app.export into `head`: closing the pipe early can break the export.
RAWDIR="${1:?usage: export-stage.sh RAWDIR DEST STAGING MANIFEST PICKS SIZE [OPTS] -- ID ...}"
DEST="${2:?dest}"; STAGING="${3:?staging}"; MANIFEST="${4:?manifest}"; PICKS="${5:?picks}"; SIZE="${6:?size}"
shift 6
OPTS=()
while [ $# -gt 0 ] && [ "$1" != "--" ]; do OPTS+=("$1"); shift; done
[ "${1:-}" = "--" ] || { echo "export-stage: missing -- before the ids" >&2; exit 1; }
shift
IDS=()
for a in "$@"; do for x in ${a//,/ }; do IDS+=("$x"); done; done
[ ${#IDS[@]} -gt 0 ] || { echo "export-stage: no ids" >&2; exit 1; }
source "$(dirname "${BASH_SOURCE[0]}")/lc-env.sh" >/dev/null 2>&1
CLI="${EXPORT_STAGE_CLI:-$CLI}"   # tests point this at a fake CLI
[ -n "${CLI:-}" ] || { echo "export-stage: LightCraft CLI not found" >&2; exit 1; }
PY="${LC_PY:-python}"
ST="$LC_SCRIPTS/export_stage.py"
case "$SIZE" in
  mp=*)   SZ=(megapixels="${SIZE#mp=}" dontEnlarge=true); CHK=(--max-mp "${SIZE#mp=}") ;;
  edge=*) SZ=(longEdge="${SIZE#edge=}" dontEnlarge=true); CHK=(--edge "${SIZE#edge=}") ;;
  *) echo "export-stage: SIZE must be mp=N or edge=N, not $SIZE" >&2; exit 1 ;;
esac
SIGS="${SIGS:-${MANIFEST%.jsonl}.hist.json}"
BATCH="${BATCH:-3}"
case "$BATCH" in ''|*[!0-9]*|0) echo "export-stage: BATCH must be a whole number of at least 1, not '$BATCH'" >&2; exit 1 ;; esac
all=$(IFS=,; echo "${IDS[*]}")
# Settle a crash's pending lines first, so a photo already in DEST counts as done and isn't exported again.
"$PY" -I "$ST" reconcile --dest "$DEST" --staging "$STAGING" --manifest "$MANIFEST" \
  || { echo "export-stage: reconcile failed" >&2; exit 1; }
todo=$("$PY" -I "$ST" todo --manifest "$MANIFEST" --ids "$all") \
  || { echo "export-stage: reading the manifest failed" >&2; exit 1; }
read -r -a IDS <<< "$todo"
[ ${#IDS[@]} -gt 0 ] || { echo "export-stage: nothing to do, all ${all//,/ } done"; exit 0; }
fwd() { cygpath -m "$1" 2>/dev/null || echo "$1"; }
total=${#IDS[@]}; nb=$(( (total + BATCH - 1) / BATCH )); k=0
for ((s = 0; s < total; s += BATCH)); do
  k=$((k + 1)); ids=("${IDS[@]:s:BATCH}"); csv=$(IFS=,; echo "${ids[*]}")
  t0=$(date +%s)
  B="$RAWDIR/b$k"; rm -rf "${B:?}"; mkdir -p "$B"
  hl=(); for i in "${ids[@]}"; do hl+=(history.list id="$i"); done
  "$CLI" run --connect "${hl[@]}" > "$B/hist.json" \
    && "$PY" -I "$ST" hist --merge --out "$SIGS" --ids "$csv" "$B/hist.json" >/dev/null \
    || { echo "batch $k/$nb [$csv]: history.list failed (see $B/hist.json)"; exit 1; }
  "$CLI" run --connect app.export "ids=[$csv]" dir="$(fwd "$B")" "${SZ[@]}" "${OPTS[@]}" \
      naming='{name}' conflict=unique > "$B/result.json"
  "$PY" -I "$ST" stage --result "$B/result.json" --dest "$DEST" --staging "$STAGING" \
      --manifest "$MANIFEST" --picks "$PICKS" --ids "$csv" "${CHK[@]}" --hist-sigs "$SIGS" \
      > "$B/stage.txt" 2>&1
  rc=$?
  if [ $rc -ne 0 ]; then echo "batch $k/$nb [$csv]: FAILED: $(tail -n 1 "$B/stage.txt")"; exit 1; fi
  echo "batch $k/$nb [$csv]: ok in $(( $(date +%s) - t0 )) s"
  rm -rf "${B:?}"
done
echo "export-stage: done, $total photos"
