#!/usr/bin/env bash
# Wait until LightCraft's denoise work is finished, then write a marker file.
#
# Usage (from Bash, after lc-env.sh):
#   rm -f "${SP:?}/denoise.done"
#   bash "$LC_SCRIPTS/denoise-wait.sh" "$SP" --ids 501,502,503     # as a background tool call
#   ... measure the frames that don't need denoise, write review lines ...
#   until [ -f "$SP/denoise.done" ]; do sleep 5; done; cat "$SP/denoise.done"; rm -f "${SP:?}/denoise.done"
#
# Done means: the queue is empty (`queued` 0, `running` null) AND, with --ids, every listed photo's
# own state (`denoise.status id=N` -> photo.state) is "ready" (or "idle" for a photo with denoise off).
# Without --ids an empty queue is enough, but then a render the app already finished, or one it has
# not queued yet, looks the same as "done": always pass --ids after changing develop settings.
# The marker says "done after Ns on gpu|cpu" (or "TIMEOUT ..."). Polls every --interval seconds
# (default 20); gives up after --max seconds (default 3600). Failed polls ("drew no frame" during a
# CPU denoise) are retried.
SP="${1:?usage: denoise-wait.sh SP [--ids 1,2,3 | --ids 1 2 3] [--interval 20] [--max 3600]}"; shift
IDS=""; INTERVAL=20; MAX=3600
while [ $# -gt 0 ]; do
  case "$1" in
    --ids) shift; IDS=""   # "1,2,3" or "1 2 3" (separate arguments), up to the next --flag
      while [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; do IDS="$IDS,${1//[[:space:]]/,}"; shift; done
      IDS=$(printf '%s' "$IDS" | tr -s ',' | sed 's/^,//;s/,$//')
      [ -n "$IDS" ] || { echo "denoise-wait: --ids needs ids" > "$SP/denoise.done"; exit 1; }
      case "$IDS" in *[!0-9,]*) echo "denoise-wait: --ids: not a list of ids: $IDS" > "$SP/denoise.done"; exit 1 ;; esac ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --max) MAX="$2"; shift 2 ;;
    *) echo "denoise-wait: unknown argument $1" > "$SP/denoise.done"; exit 1 ;;
  esac
done
source "$(dirname "${BASH_SOURCE[0]}")/lc-env.sh" >/dev/null 2>&1   # lc-env.sh needs unset vars allowed
set -u
[ -n "${CLI:-}" ] || { echo "denoise-wait: LightCraft CLI not found" > "$SP/denoise.done"; exit 1; }
start=$(date +%s)
device="?"
while :; do
  s=$("$CLI" run --connect denoise.status 2>/dev/null)
  d=$(printf '%s' "$s" | grep -o '"device":{[^}]*}' | grep -o '"kind":"[a-z]*"' | cut -d'"' -f4)
  case "$d" in gpu|cpu) device="$d" ;; esac
  idle=0
  case "$s" in
    *'"ok":true'*'"queued":0'*'"running":null'* | *'"ok":true'*'"running":null'*'"queued":0'*) idle=1 ;;
  esac
  if [ "$idle" = 1 ] && [ -n "$IDS" ]; then
    left=""
    for id in ${IDS//,/ }; do
      st=$("$CLI" run --connect denoise.status id="$id" 2>/dev/null | grep -o '"photo":{"state":"[a-z]*"' | cut -d'"' -f6)
      case "$st" in ready|idle) ;; *) left="$left $id:${st:-?}" ;; esac
    done
    [ -z "$left" ] || idle=0
  fi
  if [ "$idle" = 1 ]; then
    printf 'done after %ss on %s\n' "$(( $(date +%s) - start ))" "$device" > "$SP/denoise.done"
    exit 0
  fi
  if [ $(( $(date +%s) - start )) -ge "$MAX" ]; then
    printf 'TIMEOUT after %ss on %s; not ready:%s\n' "$MAX" "$device" "${left:- (queue busy)}" > "$SP/denoise.done"
    exit 2
  fi
  sleep "$INTERVAL"
done
