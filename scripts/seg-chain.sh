#!/usr/bin/env bash
# Make one SAM 3 prompt mask covering several people, waiting for each part (Path A of the edit skill).
#
# Usage (from Bash, after lc-env.sh; run it as a BACKGROUND tool call, then wait for the marker):
#   bash "$LC_SCRIPTS/seg-chain.sh" "$SP" 501 Subject "man with glasses" "boy in dark jacket"
#   timeout 170 bash -c 'until [ -f "$0/seg-501.done" ]; do sleep 5; done' "$SP"; cat "$SP/seg-501.done"
#   (repeat that short foreground poll until the marker exists: a foreground call past 180 s is moved away)
#
# Runs seg-wait.sh (loads SAM 3 for the photo), then `mask.add kind=prompt` with the first prompt, and
# `mask.addComponent op=add` for each further prompt, polling develop.get every 6 s until that part has
# its `seg` data (up to --max seconds per part, default 300: added parts took 18 s to about 4 min). A
# prompt that finds nothing stays "pending" for ever with no error (tested: "lamp post", "wall clock"),
# so a timeout usually means "not found": use a more specific prompt or clicked points. Never
# sets mask values: do the coverage check next. Writes "$SP/seg-ID.done": "MASK=N parts=K ready after
# Ns" or "FAILED ..." (exit 2 on a timeout, 1 on an error). Refuses when a mask called NAME exists.
SP="${1:?usage: seg-chain.sh SP ID NAME PROMPT [PROMPT ...] [--max 300]}"; ID="${2:?id}"; NAME="${3:?mask name}"; shift 3
MAX=300; PROMPTS=()
while [ $# -gt 0 ]; do
  case "$1" in --max) MAX="${2:?--max needs seconds}"; shift 2 ;; *) PROMPTS+=("$1"); shift ;; esac
done
DONE="$SP/seg-$ID.done"; rm -f "$DONE"
fail() { echo "FAILED $*" > "$DONE"; echo "FAILED $*" >&2; exit "${RC:-1}"; }
trap 'fail "stopped by a signal"' INT TERM
case "$ID" in ''|*[!0-9]*) fail "id must be a number, got '$ID'" ;; esac
[ ${#PROMPTS[@]} -gt 0 ] || fail "no prompt given"
HERE="$(dirname "${BASH_SOURCE[0]}")"
source "$HERE/lc-env.sh" >/dev/null 2>&1
[ -n "${CLI:-}" ] || fail "LightCraft CLI not found"
PY="${LC_PY:-python}"
seg() { "$CLI" run --connect develop.get id="$ID" 2>/dev/null | "$PY" -I "$HERE/lcjson.py" seg "$NAME" 2>&1; }
s=$(seg) || fail "develop.get: $s"
read -r mid _ _ <<< "$s"
[ "$mid" = "none" ] || fail "photo $ID already has a mask called $NAME (id $mid): delete it or use another name"
w=$(bash "$HERE/seg-wait.sh" "$ID") || fail "seg-wait: $w"
start=$(date +%s)
for k in "${!PROMPTS[@]}"; do
  p="${PROMPTS[$k]}"
  if [ "$k" -eq 0 ]; then
    out=$("$CLI" run --connect library.select "ids=[$ID]" mask.add kind=prompt "text=$p" "name=$NAME" 2>&1)
  else
    out=$("$CLI" run --connect library.select "ids=[$ID]" mask.addComponent "id=$mid" op=add kind=prompt "text=$p" 2>&1)
  fi
  rc=$?
  if [ $rc -ne 0 ] || printf '%s' "$out" | grep -Eq '"ok"[[:space:]]*:[[:space:]]*false'; then
    fail "prompt '$p' (CLI exit $rc): $(printf '%s' "$out" | grep -Eo '"error"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1)"
  fi
  t0=$(date +%s)
  while :; do
    # a failed poll (app busy) is retried; keep the last good mask id
    if s=$(seg); then read -r m parts ready <<< "$s"; [ "$m" != "none" ] && mid="$m"; else ready=0; fi
    [ "$m" != "none" ] && [ "${ready:-0}" -ge $((k + 1)) ] && break
    [ $(( $(date +%s) - t0 )) -ge "$MAX" ] && RC=2 fail "prompt '$p' (part $((k + 1))) has no seg data after ${MAX}s: SAM probably found nothing for it (mask ${mid}, parts ${parts:-0}, ready ${ready:-0})"
    sleep 6
  done
  echo "part $((k + 1)) '$p' ready after $(( $(date +%s) - t0 ))s"
done
echo "MASK=$mid parts=${#PROMPTS[@]} ready after $(( $(date +%s) - start ))s" | tee "$DONE"
