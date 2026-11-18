# lc-env.sh: source this at the start of every Bash call (Git Bash on Windows):
#   source "<plugin>/scripts/lc-env.sh"
# It sets:
#   LC_SCRIPTS  this scripts folder
#   LC_HOME     your local LightCraft folder (default ~/.claude/lightcraft; override with LIGHTCRAFT_HOME)
#   PREFS       $LC_HOME/preferences.md (your preferences; copy preferences.example.md there)
#   RUNS        the folder that holds one run folder per library (default $LC_HOME/runs)
#   CLI         lightcraft-cli.exe
#   M           function: measure.ps1 <mode> ...
#   PSX         function: PSX <script.ps1> <args>  (run another helper in this folder)
# Settings come from the environment or from $LC_HOME/config.env (KEY=value lines):
#   LIGHTCRAFT_DIR   folder holding lightcraft.exe and lightcraft-cli.exe (auto-detected if unset)
#   LIGHTCRAFT_RUNS  run-state root (default $LC_HOME/runs)
LC_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LC_HOME="${LIGHTCRAFT_HOME:-$HOME/.claude/lightcraft}"
if [ -f "$LC_HOME/config.env" ]; then
  while IFS='=' read -r k v; do
    v="${v%$'\r'}"; v="${v%\"}"; v="${v#\"}"
    case "$k" in
      LIGHTCRAFT_DIR)  [ -z "$LIGHTCRAFT_DIR" ] && LIGHTCRAFT_DIR="$v" ;;
      LIGHTCRAFT_RUNS) [ -z "$LIGHTCRAFT_RUNS" ] && LIGHTCRAFT_RUNS="$v" ;;
    esac
  done < "$LC_HOME/config.env"
fi
if [ -z "$LIGHTCRAFT_DIR" ]; then
  LIGHTCRAFT_DIR="$(powershell -NoProfile -ExecutionPolicy Bypass -File "$LC_SCRIPTS/find-lightcraft.ps1" | tr -d '\r')"
  if [ -n "$LIGHTCRAFT_DIR" ]; then
    mkdir -p "$LC_HOME" && printf 'LIGHTCRAFT_DIR=%s\n' "$LIGHTCRAFT_DIR" >> "$LC_HOME/config.env"
  else
    echo "lc-env: LightCraft not found. Set LIGHTCRAFT_DIR in $LC_HOME/config.env" >&2
  fi
fi
CLI="$(cygpath -u "$LIGHTCRAFT_DIR" 2>/dev/null || echo "$LIGHTCRAFT_DIR")/lightcraft-cli.exe"
RUNS="${LIGHTCRAFT_RUNS:-$LC_HOME/runs}"
PREFS="$LC_HOME/preferences.md"
M()   { powershell -NoProfile -ExecutionPolicy Bypass -File "$LC_SCRIPTS/measure.ps1" "$@"; }
PSX() { local s="$1"; shift; powershell -NoProfile -ExecutionPolicy Bypass -File "$LC_SCRIPTS/$s" "$@"; }
