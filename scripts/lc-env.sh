# lc-env.sh: source this at the start of every Bash call (Git Bash on Windows):
#   source "<plugin>/scripts/lc-env.sh"      (use forward slashes in the path)
# It sets:
#   LC_SCRIPTS  this scripts folder
#   LC_HOME     your local LightCraft folder (default %USERPROFILE%/.claude/lightcraft; override with LIGHTCRAFT_HOME)
#   PREFS       $LC_HOME/preferences.md (your preferences; copy preferences.example.md there)
#   RUNS        the folder that holds one run folder per library (default $LC_HOME/runs)
#   CLI         lightcraft-cli.exe (empty if LightCraft can't be found)
#   M           function: measure.ps1 <mode> ...
#   PSX         function: PSX <script.ps1> <args>  (run another helper in this folder)
# Settings come from the environment or from $LC_HOME/config.env (KEY=value lines):
#   LIGHTCRAFT_DIR   folder holding lightcraft.exe and lightcraft-cli.exe (auto-detected if unset or stale)
#   LIGHTCRAFT_RUNS  run-state root (default $LC_HOME/runs)
LC_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -n "$LIGHTCRAFT_HOME" ]; then
  LC_HOME="$LIGHTCRAFT_HOME"
elif [ -n "$USERPROFILE" ]; then
  LC_HOME="$(cygpath -u "$USERPROFILE" 2>/dev/null || echo "$USERPROFILE")/.claude/lightcraft"
else
  LC_HOME="$HOME/.claude/lightcraft"
fi
export LIGHTCRAFT_HOME="$LC_HOME"   # find-lightcraft.ps1 reads the same config.env
LC_CFG="$LC_HOME/config.env"
if [ -f "$LC_CFG" ]; then
  # "|| [ -n "$k" ]" keeps a last line that has no trailing newline.
  while IFS='=' read -r k v || [ -n "$k" ]; do
    k="${k#$'\xef\xbb\xbf'}"; k="${k//[[:space:]]/}"
    v="${v%$'\r'}"; v="${v%"${v##*[![:space:]]}"}"; v="${v#"${v%%[![:space:]]*}"}"; v="${v%\"}"; v="${v#\"}"
    case "$k" in
      LIGHTCRAFT_DIR)  [ -z "$LIGHTCRAFT_DIR" ] && LIGHTCRAFT_DIR="$v" ;;
      LIGHTCRAFT_RUNS) [ -z "$LIGHTCRAFT_RUNS" ] && LIGHTCRAFT_RUNS="$v" ;;
    esac
  done < "$LC_CFG"
fi
lc_cli_of() { [ -n "$1" ] && printf '%s/lightcraft-cli.exe' "$(cygpath -u "$1" 2>/dev/null || echo "$1")"; }
CLI="$(lc_cli_of "$LIGHTCRAFT_DIR")"
if [ -z "$CLI" ] || [ ! -f "$CLI" ]; then
  [ -n "$LIGHTCRAFT_DIR" ] && echo "lc-env: no lightcraft-cli.exe in $LIGHTCRAFT_DIR; searching again" >&2
  LIGHTCRAFT_DIR="$(powershell -NoProfile -ExecutionPolicy Bypass -File "$LC_SCRIPTS/find-lightcraft.ps1" | tr -d '\r')"
  CLI="$(lc_cli_of "$LIGHTCRAFT_DIR")"
  if [ -n "$CLI" ] && [ -f "$CLI" ]; then
    mkdir -p "$LC_HOME"
    if [ -f "$LC_CFG" ]; then
      grep -v '^[[:space:]]*LIGHTCRAFT_DIR[[:space:]]*=' "$LC_CFG" > "$LC_CFG.tmp"; mv "$LC_CFG.tmp" "$LC_CFG"
      [ -s "$LC_CFG" ] && [ -n "$(tail -c1 "$LC_CFG")" ] && echo >> "$LC_CFG"
    fi
    printf 'LIGHTCRAFT_DIR=%s\n' "$LIGHTCRAFT_DIR" >> "$LC_CFG"
  else
    CLI=""
    echo "lc-env: LightCraft not found. Set LIGHTCRAFT_DIR=<install folder> in $LC_CFG" >&2
  fi
fi
RUNS="${LIGHTCRAFT_RUNS:-$LC_HOME/runs}"
PREFS="$LC_HOME/preferences.md"
M()   { powershell -NoProfile -ExecutionPolicy Bypass -File "$LC_SCRIPTS/measure.ps1" "$@"; }
PSX() { local s="$1"; shift; powershell -NoProfile -ExecutionPolicy Bypass -File "$LC_SCRIPTS/$s" "$@"; }
