#!/usr/bin/env bash
# Wait until LightCraft's denoise queue is empty, then write a marker file.
#
# Usage (from Bash, after lc-env.sh):
#   rm -f "${SP:?}/denoise.done"
#   bash "$LC_SCRIPTS/denoise-wait.sh" "$SP" &        # or run it as a background tool call
#   ... measure, write review lines ...
#   until [ -f "$SP/denoise.done" ]; do sleep 5; done; cat "$SP/denoise.done"; rm -f "${SP:?}/denoise.done"
#
# Polls `denoise.status` every INTERVAL seconds (default 20) until `queued` is 0 and `running` is
# null, then writes "$SP/denoise.done" with the elapsed time and the device that ran it (gpu / cpu)
# and exits. After MAX seconds (default 3600) it writes "TIMEOUT ..." to the marker instead.
# The app can stop answering ("drew no frame") during a CPU denoise: failed polls are retried.
SP="${1:?usage: denoise-wait.sh SP [INTERVAL] [MAX]}"
INTERVAL="${2:-20}"
MAX="${3:-3600}"
source "$(dirname "${BASH_SOURCE[0]}")/lc-env.sh" >/dev/null 2>&1   # lc-env.sh needs unset vars allowed
set -u
[ -n "${CLI:-}" ] || { echo "denoise-wait: LightCraft CLI not found" > "$SP/denoise.done"; exit 1; }
start=$(date +%s)
device="?"
while :; do
  s=$("$CLI" run --connect denoise.status 2>/dev/null)
  case "$s" in
    *'"device":{'*'"kind":"'*) d=$(printf '%s' "$s" | grep -o '"device":{[^}]*}' | grep -o '"kind":"[a-z]*"' | cut -d'"' -f4)
                               [ "$d" = gpu ] || [ "$d" = cpu ] && device="$d" ;;
  esac
  case "$s" in
    *'"ok":true'*'"queued":0'*'"running":null'* | *'"ok":true'*'"running":null'*'"queued":0'*)
      el=$(( $(date +%s) - start ))
      printf 'done after %ss on %s\n' "$el" "$device" > "$SP/denoise.done"
      exit 0 ;;
  esac
  if [ $(( $(date +%s) - start )) -ge "$MAX" ]; then
    printf 'TIMEOUT after %ss on %s: %s\n' "$MAX" "$device" "$(printf '%s' "$s" | head -c 300)" > "$SP/denoise.done"
    exit 2
  fi
  sleep "$INTERVAL"
done
