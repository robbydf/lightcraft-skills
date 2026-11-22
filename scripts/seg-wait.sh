#!/usr/bin/env bash
# Prepare SAM 3 for one photo and wait until it is ready (Path A of the edit skill).
#
# Usage (from Bash, after lc-env.sh; run it with the Bash tool's run_in_background, since a load can
# take longer than one tool call allows):
#   bash "$LC_SCRIPTS/seg-wait.sh" 501            # prints "ready after Ns" or "TIMEOUT ..."
#   bash "$LC_SCRIPTS/seg-wait.sh" 501 --max 300   # loads of up to 240 s were seen
#
# Runs `library.select ids=[ID] segment.prepare`, then polls `segment.model.status` every 3 s until
# loaded is true and busy and analyzing are false. The first load took 55-135 s in testing. Exit 0 when
# ready, 2 on timeout (default 240 s), 1 when SAM 3 isn't installed (use Path B).
ID="${1:?usage: seg-wait.sh ID [--max 240]}"; shift
MAX=240
[ "${1:-}" = "--max" ] && MAX="${2:?--max needs seconds}"
source "$(dirname "${BASH_SOURCE[0]}")/lc-env.sh" >/dev/null 2>&1
set -u
[ -n "${CLI:-}" ] || { echo "seg-wait: LightCraft CLI not found"; exit 1; }
s=$("$CLI" run --connect segment.model.status 2>/dev/null)
case "$s" in *'"installed":true'*) ;; *) echo "seg-wait: SAM 3 not installed (use Path B)"; exit 1 ;; esac
"$CLI" run --connect library.select "ids=[$ID]" segment.prepare > /dev/null 2>&1
start=$(date +%s)
while :; do
  s=$("$CLI" run --connect segment.model.status 2>/dev/null)
  case "$s" in
    *'"analyzing":false'*) case "$s" in *'"busy":false'*) case "$s" in *'"loaded":true'*)
      echo "ready after $(( $(date +%s) - start ))s"; exit 0 ;; esac ;; esac ;;
  esac
  if [ $(( $(date +%s) - start )) -ge "$MAX" ]; then
    echo "TIMEOUT after ${MAX}s: $(printf '%s' "$s" | grep -o '"analyzing":[a-z]*\|"busy":[a-z]*\|"loaded":[a-z]*' | tr '\n' ' ')"
    exit 2
  fi
  sleep 3
done
