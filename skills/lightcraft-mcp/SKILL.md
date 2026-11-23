---
name: lightcraft-mcp
description: Use when the user asks to start/launch or stop/shut down LightCraft (the ArtCraft photo editor GUI, not headless) together with the LightCraft CLI MCP bridge, to connect or disconnect Claude Code from the LightCraft MCP server, or runs /lightcraft-mcp start or /lightcraft-mcp stop. Also when lightcraft-cli --connect or mcp__lightcraft__* tools fail with "not reachable" because nothing is listening on 127.0.0.1:7980.
---

# lightcraft-mcp

Two subcommands, both handled by the plugin's script. The argument after the skill name picks one
(`/lightcraft-mcp start`, `/lightcraft-mcp stop`; installed as a plugin, `/lightcraft:lightcraft-mcp start`).
With no argument, ask which.

The script is in the plugin's `scripts` folder, two levels above this skill's base directory
(`<base>/../../scripts/lightcraft-mcp.py`). Use the real base directory you were given when this
skill loaded. From Bash or PowerShell (use `python3` on macOS and Linux if there is no `python`):

```bash
python "<base>/../../scripts/lightcraft-mcp.py" start
python "<base>/../../scripts/lightcraft-mcp.py" stop
```

- **Install folder:** found automatically by `find_lightcraft.py` in this order: `-LightCraftDir`,
  the `LIGHTCRAFT_DIR` environment variable, `LIGHTCRAFT_DIR=` in `~/.claude/lightcraft/config.env`,
  then per system: the registry and `Program Files\ArtCraft\LightCraft` (Windows),
  `/Applications/LightCraft.app/Contents/MacOS` (macOS), `/opt/lightcraft` and similar (Linux), and
  last `lightcraft-cli` on `PATH` (the full list is in the README).
  That folder holds the GUI (`lightcraft.exe`; `lightcraft` or `LightCraft` elsewhere) and the
  CLI and bridge (`lightcraft-cli.exe`; `lightcraft-cli` elsewhere).
- **Control address:** `127.0.0.1:7980`.
- **MCP server name in Claude Code:** `lightcraft`.

## start

1. Starts the GUI with `--control 7980`, or reuses an instance already serving the port.
2. Checks that the CLI can drive it (`lightcraft-cli run --connect … engine.commands`).
3. Checks that the bridge answers an MCP `initialize` (`lightcraft-cli mcp --connect 127.0.0.1:7980`).
4. Connects Claude Code if the server isn't registered yet, in **user scope** (every project):
   `claude mcp add -s user lightcraft -- "<cli>" mcp --connect 127.0.0.1:7980`. Claude Code spawns
   the bridge itself (stdio), so nothing is left running for it. A local-scope `lightcraft` entry in
   the current folder is removed first, even a matching one, because it would shadow the user one.

Options:
- `-Library "<folder>"`: only when it starts a new GUI; the default is the last library.
- `-Scope local`: register only for the current folder instead.
- `-Port`, `-TimeoutSec`, `-LightCraftDir`, and `-TokenFile` (see Token).

Success ends with `READY`.

**The registration is meant to stay, with LightCraft open or not.** Tested November 2026 with nothing
listening: the bridge starts in under a second and lists its tools. A tool call returns
`LightCraft app at 127.0.0.1:7980 is not reachable … (start it with \`lightcraft --control PORT\`)`,
and the bridge reconnects on every call. So:
- Once registered, every session has the `mcp__lightcraft__*` tools (deferred: they load only when a
  task needs them).
- **A "not reachable" error means LightCraft is closed:** run `start` in the same session. The tools
  work on the next call, with no new session needed.
- Only when the tools are missing from a session altogether (registered after the session began) does
  the user need a new session.
- One session can drive LightCraft and PhotoCraft together when PhotoCraft's MCP is registered the same
  way, so a hand-off needs no second session.

## stop

1. Closes the GUI gracefully (a window close, so the library saves) and waits up to `-TimeoutSec`.
2. Leaves the registration and the running bridges alone. Killing a bridge would cut that session's
   tools until it reconnects, and an idle bridge costs nothing.

Success ends with `STOPPED`. `-Force` kills LightCraft if it won't close; use it only when the user
says so.

`stop -Disconnect` also disconnects Claude Code, only when the user asks for that: `claude mcp remove
lightcraft` from the local and user scopes (a project's own `.mcp.json` is left alone), and it stops
the `lightcraft-cli … mcp` bridge processes.

## Exit codes

| Exit | Meaning | What to do |
|------|---------|------------|
| 2 | start: LightCraft is running **without** `--control` | Tell the user, and offer `stop` then `start`. Never kill it unasked. |
| 3 | start: the control port never opened | Check the log the script names: `%APPDATA%\LightCraft\logs\lightcraft.log` on Windows, `~/Library/Application Support/LightCraft/logs/` on macOS, `~/.local/share/LightCraft/logs/` on Linux (`control server failed to bind` means the port is busy). |
| 4 / 5 | start: the CLI or bridge handshake failed | Show the error line. |
| 6 | start: `claude mcp add` failed, `claude` isn't on PATH, or a project `.mcp.json` registers `lightcraft` at another address | Show the error line. A local or user registration pointing elsewhere (another port, a moved install) is replaced automatically; a `.mcp.json` entry is the user's to change. |
| 7 | stop: the GUI is still open (a dialog?) | Ask the user, and re-run `stop -Force` only on their yes. |
| 8 | stop -Disconnect: the registration is still present | Usually a project's own `.mcp.json` entry, which stop deliberately keeps. Run `claude mcp get lightcraft` to see the scope, and remove it by hand only if the user wants. |
| 9 | LightCraft not found | Ask for the install folder and save it as `LIGHTCRAFT_DIR=<folder>` in `~/.claude/lightcraft/config.env`. |

## Token

Tested on LightCraft 0.21.1, which has **no auth** on the control port (127.0.0.1 only), so no token
is needed.
- `-TokenFile <file>` or `LIGHTCRAFT_TOKEN_FILE` only sets `LIGHTCRAFT_TOKEN` inside the start
  script. That's a no-op on 0.21.1, kept for a future version that needs auth.
- Never print the token.
- If a newer LightCraft rejects connections for missing auth, look for a new token flag or
  environment variable in `lightcraft.exe --help` and in the `lightcraft-cli.exe` usage (run it with
  no arguments).

## Common mistakes

- `lightcraft-cli mcp` **without** `--connect` starts a separate headless session, not the GUI.
- `claude mcp get lightcraft` exiting 1 with `No MCP server named "lightcraft"` just means it isn't
  registered.
- Running `stop` closes the user's LightCraft window: only run it when they asked to stop.
- A **minimized** LightCraft draws no frames, so it ignores control requests ("the app drew no frame
  for 5 s") and window-close.
  - The script restores the window first.
  - If you call `lightcraft-cli` or `mcp__lightcraft__*` tools directly and see that error, restore
    the window, or re-run `start`.
- While a cull or edit run is going, the user should only view: clicking another photo can move a
  worker's mask or crop step onto it, and a filter change or a modal dialog can block requests. See
  "Using LightCraft while a run is going" in the plugin README.
